# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Interactive ``flahax mix``: five steps, saved items and sessions (interactive mix Task 7)."""

import contextlib
import io
import json
import os
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from flahax.batch_cli import main as batch
from flahax.mix_cli import WATER_IONS, Prompts, main, number_answer
from flahax import __version__
from flahax.mix_store import Store
from tests.test_output_consistency import ANSWERS

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'mix'

SPEC = ['20', '20', '20', '', '', '1']  # tanks A, B, acid; ratio; temperature; fill
RO = ['1', '']  # RO water; no limits
TOMATO = ['1', 'tomato (howard']  # a packaged formula, searched
TOMATO_KEYS = ['N_NO3', 'P', 'K', 'Mg', 'Ca', 'S', 'B', 'Fe', 'Zn', 'Cu', 'Mo', 'Mn']
CATALOGUE = ['1', '']  # whole catalogue; add nothing
NITRIC = ['1', 'HNO3', '60', '1.37', 'Nitric acid 60%', '']  # new acid from its certificate; done
END = ['', '1', '']  # pH 5.8; depth 1; session name


def water(name, values, *, units='1', alkalinity='1', micro='1', ph='7.5', share='', limits=''):
    """A new analysis: ``values`` maps lab ion names to one answer or a list of answers (Enter =
    not measured)."""
    answers = ['2', name, units, alkalinity] + ([micro] if units != '1' else []) + [ph]
    for ion in WATER_IONS:
        entry = values.get(ion, '')
        answers += [entry] if isinstance(entry, str) else list(entry)
    return answers + [share, limits]


def changed_tomato(**values):
    return ['2', 'tomato (howard'] + [values.get(k, '') for k in TOMATO_KEYS] + ['']


BALANCED = {
    'Ca': '60.12',
    'NO3': '62.0049',
    'Alk': '100',
}  # 3 meq/L each side (alkalinity as CaCO3)


class Script:
    def __init__(self, answers):
        self.answers, self.prompts = list(answers), []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError
        return self.answers.pop(0)


class MixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / 'home'
        patcher = mock.patch.dict(os.environ, {'FLAHAX_HOME': str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_mix(self, answers, *argv):
        lines, script = [], Script(answers)
        code = main(
            list(argv), ask=script, say=lambda *a: lines.append(' '.join(str(x) for x in a))
        )
        return code, lines, script

    def full(self, *, water_answers=RO, formula=TOMATO, out='out'):
        target = Path(self.tmp.name) / out
        code, lines, _ = self.run_mix(
            SPEC + water_answers + formula + CATALOGUE + NITRIC + END, '--output', str(target)
        )
        return code, lines, target

    def test_first_run_tomato_ro_fill_mode(self):
        code, lines, target = self.full()
        self.assertEqual(code, 0, '\n'.join(lines))
        sheet = (target / 'batch-sheet.html').read_text(encoding='utf-8')
        summary = json.loads((target / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual([t['name'] for t in summary['tanks']['tanks']], ['A', 'B'])
        self.assertNotIn('Tank C', sheet)
        self.assertNotIn('<td>C</td>', sheet)
        self.assertIn('2,000 L of irrigation', sheet)
        self.assertEqual(
            summary['volumes'],
            {
                'irrigation_litres': 2000.0,
                'prepared_litres': {'A': 20.0, 'B': 20.0, 'acid': 20.0},
                'capacity_litres': {'A': 20.0, 'B': 20.0, 'acid': 20.0},
                'mode': 'fill',
            },
        )
        self.assertEqual(summary['tanks']['temperature_c'], 25)
        self.assertTrue(any(line.startswith('Tank A') for line in lines), lines)
        word = {'ready': 'ready', 'requires_review': 'review notes before mixing'}[
            summary['status']
        ]
        head = [line for line in lines if line.startswith('FlahaX') and ' - ' in line][-1]
        self.assertTrue(head.endswith(word), head)
        self.assertTrue(any(line.startswith('  [ ] ') for line in lines), lines)
        self.assertTrue(any('Nitric acid 60%' in line and 'mL' in line for line in lines), lines)
        store = Store(self.home)
        self.assertEqual(store.list('sessions'), ['tomato-howard-resh-ro'])
        session = store.load('sessions', 'tomato-howard-resh-ro')
        self.assertEqual(
            session['spec'],
            {
                'tank_litres': {'A': 20.0, 'B': 20.0, 'acid': 20.0},
                'ratio': 100.0,
                'temperature_c': 25.0,
                'mode': 'fill',
                'irrigation_litres': None,
            },
        )
        self.assertEqual(
            (
                session['water'],
                session['formula'],
                session['store'],
                session['acids'],
                session['ph'],
                session['depth'],
            ),
            ('ro', 'Tomato (Howard Resh)', 'catalogue', ['nitric-acid-60'], 5.8, 1),
        )
        self.assertEqual(
            store.load('acids', 'nitric-acid-60'),
            {'formula': 'HNO3', 'fraction': 0.6, 'density': 1.37, 'name': 'Nitric acid 60%'},
        )

    def test_second_run_from_session_asks_nothing(self):
        code, _, first = self.full()
        self.assertEqual(code, 0)

        def refuse(prompt):
            raise AssertionError(f'asked {prompt!r}')

        lines = []
        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        try:
            code = main(
                ['sessions/tomato-howard-resh-ro'],
                ask=refuse,
                say=lambda *a: lines.append(' '.join(a)),
            )
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 0, lines)
        again = json.loads(
            (Path(self.tmp.name) / 'flahax-mix-tomato-howard-resh-ro/summary.json').read_text(
                'utf-8'
            )
        )
        before = json.loads((first / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(again['tanks'], before['tanks'])
        self.assertEqual(again['ph'], before['ph'])

    def test_lab_report_in_mg_per_l_converts_to_elements(self):
        code, lines, _ = self.full(water_answers=water('well', BALANCED, alkalinity='2'))
        self.assertIn(code, (0, 3), lines)
        saved = Store(self.home).load('waters', 'well')
        self.assertAlmostEqual(saved['mg_per_litre']['N_NO3'], 14.0067, places=6)
        self.assertAlmostEqual(saved['mg_per_litre']['HCO3'], 121.93, places=2)
        self.assertEqual(saved['measured_ph'], 7.5)
        self.assertTrue(any('0.0 % apart' in line for line in lines), lines)

    def test_meq_and_mmol_convert_via_charge_and_molar_mass(self):
        from flahax.mix_cli import to_elements

        self.assertAlmostEqual(
            to_elements({'Ca': 2, 'SO4': 2, 'Alk': 1}, 'meq', 'CaCO3')['Ca'], 40.078, places=3
        )
        self.assertAlmostEqual(to_elements({'SO4': 2}, 'meq', 'HCO3')['S'], 32.06, places=2)
        self.assertAlmostEqual(
            to_elements({'Alk': 1}, 'mmol', 'CaCO3')['HCO3'], 2 * 61.0168, places=4
        )
        self.assertAlmostEqual(to_elements({'NO3': 1}, 'mmol', 'HCO3')['N_NO3'], 14.0067, places=3)

    def test_wrong_unit_shows_imbalance(self):
        values = dict(BALANCED, NO3='12')  # NO3-N typed where the report asks for NO3
        code, lines, _ = self.run_mix(SPEC + water('well', values, alkalinity='2')[:-2])
        self.assertEqual(code, 1)
        warning = next(line for line in lines if line.startswith('Warning:'))
        apart = float(warning.split('are ')[1].split(' %')[0])
        self.assertGreater(apart, 5)
        self.assertIn('Ca', warning)

    def test_formula_step_lists_every_formula_on_enter(self):
        # The owner's first session: fertilizer names typed at the formula step, then Enter, which
        # used to loop.
        from flahax import load_library

        names = [f['name'] for f in load_library()['formulas']]
        pick = str(names.index('Tomato (Howard Resh)') + 1)
        code, lines, target = self.full(formula=['1', 'MKP', '20-20-20', '', pick])
        self.assertEqual(code, 0, '\n'.join(lines))
        self.assertTrue(
            any(
                "Nothing matches 'mkp'; press Enter to see the whole list." in line
                for line in lines
            ),
            lines,
        )
        self.assertTrue(any(line == f'  {pick}  Tomato (Howard Resh)' for line in lines), lines)
        self.assertTrue(any('your fertilizers come in step 4' in line for line in lines), lines)
        self.assertFalse(any('This one is needed' in line for line in lines))
        summary = json.loads((target / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['title'], 'Tomato (Howard Resh)')

    def test_do_not_mix_always_says_why(self):
        # Field test 2026-10-23: blocked sheets listed sodium notes while the blocking reason was
        # empty.
        code, lines, _ = self.run_mix(
            SPEC + RO + TOMATO + CATALOGUE + ['2'] + END,
            '--output',
            str(Path(self.tmp.name) / 'no-acid'),
        )
        self.assertEqual(code, 3)
        self.assertTrue(any('do not mix' in line for line in lines))
        reason = next(line for line in lines if line.startswith('  ! ph_adjustment:'))
        self.assertIn('needs an acid to reach pH 5.80; none was offered: add an acid', reason)
        well = water('salty', {'Ca': '40', 'Na': '200', 'Cl': '308', 'Alk': '61'}, limits='Na=69')
        code, lines, _ = self.run_mix(
            SPEC + well + TOMATO + CATALOGUE + NITRIC + END,
            '--output',
            str(Path(self.tmp.name) / 'salty'),
        )
        self.assertEqual(code, 3)
        self.assertTrue(
            any('above the declared maximum 69 mg/L' in line for line in lines[-25:]), lines[-25:]
        )
        self.assertFalse(any('report.html' in line for line in lines))  # depth 1 writes no report

    def test_small_batches_show_their_volume(self):
        code, lines, _ = self.run_mix(
            ['20', '20', '20', '', '', '2', '1'] + RO + TOMATO + CATALOGUE + NITRIC + END,
            '--output',
            str(Path(self.tmp.name) / 'tiny'),
        )
        self.assertEqual(code, 0, '\n'.join(lines))
        self.assertIn('  1 L of irrigation; prepare 0.01 L in each container.', lines)

    def test_a_wrong_value_is_corrected_without_retyping_the_analysis(self):
        wrong = water(
            'typo',
            {'Ca': '60.12', 'Na': '23', 'NO3': '6.2', 'Cl': '35.45', 'Alk': '100'},
            alkalinity='2',
        )[:-2]
        fix = ['1', str(WATER_IONS.index('NO3') + 1), '62.0049']  # correct a value: NO3
        code, lines, _ = self.run_mix(
            SPEC + wrong + fix + ['', ''] + TOMATO + CATALOGUE + NITRIC + END,
            '--output',
            str(Path(self.tmp.name) / 'fixed'),
        )
        self.assertEqual(code, 0, '\n'.join(lines))
        self.assertTrue(
            any(line.startswith('Charge balance:') and '0.0 % apart' in line for line in lines),
            lines,
        )
        saved = Store(self.home).load('waters', 'typo')
        self.assertAlmostEqual(saved['mg_per_litre']['N_NO3'], 14.0067, places=3)

    def test_a_report_without_chloride_is_not_blocked(self):
        # #100, owner 2026-10-23: no chloride -> closed on the alkalinity, noted in the full report
        # only.
        clean = water('no-cl', {'Ca': '60.12', 'NO3': '62.0049', 'Alk': '100'}, alkalinity='2')
        target = Path(self.tmp.name) / 'no-cl'
        code, lines, _ = self.run_mix(
            SPEC + clean + TOMATO + CATALOGUE + NITRIC + ['', '3', ''], '--output', str(target)
        )
        self.assertEqual(code, 0, '\n'.join(lines))
        self.assertFalse(any('chloride' in line.lower() for line in lines), lines)
        report = (target / 'report.html').read_text(encoding='utf-8')
        self.assertIn('has no chloride, so it is closed on the alkalinity', report)
        self.assertNotIn(
            'chloride', (target / 'batch-sheet.html').read_text(encoding='utf-8').lower()
        )

    def test_owners_second_session_by_name_and_readable_grams(self):
        # Field test 2026-10-23: 100 L tanks with a 10 L acid container, saved as 'tomato stage 1'.
        spec = ['100', '100', '10', '', '', '1']
        stage1 = ['1', 'tomato stage.1']
        code, lines, _ = self.run_mix(
            spec + RO + stage1 + CATALOGUE + NITRIC + ['6', '1', 'tomato stage 1'],
            '--output',
            str(Path(self.tmp.name) / 'first'),
        )
        self.assertEqual(code, 0, '\n'.join(lines))
        self.assertIn(
            '  1,000 L of irrigation; prepare 10 L in each container (your 10 L acid container '
            'sets the batch).',
            lines,
        )
        self.assertTrue(
            any(
                line.startswith(
                    'Tank A: prepare 10 L in your 100 L tank (your 10 L acid container'
                )
                for line in lines
            )
        )
        weights = [line for line in lines if line.startswith('  [ ] ')]
        self.assertFalse([line for line in weights if line.endswith(': 0 g')], weights)
        for typed in (
            ['Tomato', 'Stage.1'],
            ['tomato', 'stage', '1'],
            ['sessions/Tomato', 'Stage', '1'],
        ):
            with self.subTest(typed=typed):
                code, again, _ = self.run_mix(
                    [], *typed, '--output', str(Path(self.tmp.name) / '-'.join(typed))
                )
                self.assertEqual(code, 0, '\n'.join(again))
        code, listed, _ = self.run_mix([], 'sessions')
        self.assertEqual((code, listed), (0, ['Saved sessions: tomato-stage-1']))
        code, missing, _ = self.run_mix([], 'sessions/x')
        self.assertEqual(code, 1)
        self.assertIn("Saved: tomato-stage-1", missing[-1])

    def test_sweep_findings_acid_title_repeats(self):
        # Pre-release sweep 2026-10-23: #112 unknown acid, #114 changed-formula title, #113
        # repeated notes.
        bad = ['1', '1', 'hno3', '60', '1.37', '', '']  # '1' refused, 'hno3' accepted as HNO3
        changed = (
            ['2', 'lettuce general', '180'] + [''] * 12 + ['']
        )  # default name 'Lettuce General ... changed'
        code, lines, _ = self.run_mix(
            SPEC + RO + changed + CATALOGUE + bad + END,
            '--output',
            str(Path(self.tmp.name) / 'sweep'),
        )
        self.assertEqual(code, 0, chr(10).join(lines))
        self.assertIn('  FlahaX plans with these acids only: HNO3, H3PO4, H2SO4, C6H8O7.', lines)
        self.assertTrue(
            any(
                line.startswith('FlahaX ') and 'Lettuce General (Howard Resh) changed - ' in line
                for line in lines
            )
        )
        self.assertTrue(any('HNO3 60%' in line and 'mL' in line for line in lines), lines)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(err):
            code = batch(
                [
                    '--formula',
                    'Tomato (Howard Resh)',
                    '--water',
                    'ro',
                    '--acid',
                    '1:0.6:1.37',
                    '--output',
                    str(Path(self.tmp.name) / 'bad-acid'),
                ]
            )
        self.assertEqual(code, 1)
        self.assertIn('the acid must be one of HNO3, H3PO4, H2SO4, C6H8O7', err.getvalue())

    def test_blank_is_never_guessed(self):
        values = dict(BALANCED, Fe='', Mn='0', Zn='<0.02')
        code, lines, _ = self.full(water_answers=water('blanks', values, alkalinity='2'))
        self.assertIn(code, (0, 3), lines)
        saved = Store(self.home).load('waters', 'blanks')
        self.assertNotIn('Fe', saved['mg_per_litre'])
        self.assertEqual(saved['mg_per_litre']['Mn'], 0)
        self.assertNotIn('Zn', saved['mg_per_litre'])
        self.assertEqual(saved['below_detection'], {'Zn': 0.02})

    def test_interrupt_saves_nothing(self):
        code, lines, _ = self.run_mix(SPEC + water('well', BALANCED, alkalinity='2'))
        self.assertEqual(code, 1)
        self.assertEqual(lines[-1], 'Stopped; nothing saved.')
        self.assertIn('3/5', '\n'.join(lines))
        self.assertFalse(self.home.exists() and any(p.is_file() for p in self.home.rglob('*')))

    def test_formula_imbalance_warned_at_entry(self):
        code, lines, _ = self.run_mix(SPEC + RO + changed_tomato(K='600'))
        self.assertEqual(code, 1)
        warning = next(i for i, line in enumerate(lines) if 'targetIonBalance' in line)
        step4 = next(i for i, line in enumerate(lines) if line.startswith('4/5'))
        self.assertLess(warning, step4)

    def test_limits_are_never_assumed(self):
        code, _, _ = self.full()
        self.assertEqual(Store(self.home).load('sessions', 'tomato-howard-resh-ro')['limits'], {})
        shutil.rmtree(self.home)  # a fresh store, so the script below matches
        with mock.patch(
            'flahax.mix_cli.run_batch', wraps=__import__('flahax.batch_cli').batch_cli.run_batch
        ) as run:
            code, lines, target = self.full(water_answers=['1', 'Na=69'], out='limited')
        self.assertIn(code, (0, 3), lines)
        self.assertEqual(run.call_args.args[0].limit, [('Na', 69.0)])
        summary = json.loads((target / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(
            [(r['symbol'], r['maximumPpm']) for r in summary['limits']], [('Na', 69.0)]
        )

    def test_batch_reads_saved_items(self):
        code, lines, _ = self.full(
            water_answers=water('well', BALANCED, alkalinity='2'), formula=changed_tomato(Ca='190')
        )
        self.assertIn(code, (0, 3), lines)
        store = Store(self.home)
        self.assertEqual(store.list('formulas'), ['tomato-howard-resh-changed'])
        self.assertEqual(store.load('formulas', 'tomato-howard-resh-changed')['Ca'], 190)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = batch(
                [
                    '--water',
                    str(self.home / 'waters/well.json'),
                    '--targets',
                    str(self.home / 'formulas/tomato-howard-resh-changed.json'),
                    '--acid',
                    'HNO3:0.6:1.37',
                    '--output',
                    str(Path(self.tmp.name) / 'batch'),
                ]
            )
        self.assertIn(code, (0, 3), out.getvalue())

    def test_blocked_result_says_do_not_mix_with_the_reason(self):
        code, lines, _ = self.full(water_answers=['1', 'Na=1e-9'])
        self.assertEqual(code, 3, lines)
        head = next(
            i for i, line in enumerate(lines) if line.startswith('FlahaX') and ' - ' in line
        )
        self.assertTrue(lines[head].endswith('do not mix'), lines[head])
        self.assertIn('exceeds', '\n'.join(lines[head + 1 : head + 5]))
        self.assertFalse(any('[ ]' in line for line in lines), lines)
        self.assertFalse(
            any(
                'measure pH after mixing' in line or line.startswith('Acid container')
                for line in lines
            ),
            lines,
        )

    def test_missing_alkalinity_is_asked_at_entry_never_defaulted(self):
        values = {
            'Ca': '40.078',
            'NO3': '124.0098',
            'Alk': ['', '', '2'],
        }  # Enter asks again; 2 = measured zero
        code, lines, _ = self.full(water_answers=water('zero-alk', values))
        self.assertIn(code, (0, 3), lines)
        self.assertTrue(any('pH plan will be blocked' in line for line in lines), lines)
        self.assertEqual(Store(self.home).load('waters', 'zero-alk')['mg_per_litre']['HCO3'], 0)
        shutil.rmtree(self.home)
        values = dict(BALANCED, Alk=['', '1', '122'])
        self.full(water_answers=water('typed-alk', values), out='typed')
        self.assertEqual(Store(self.home).load('waters', 'typed-alk')['mg_per_litre']['HCO3'], 122)

    def test_micronutrients_in_umol_are_converted(self):
        from flahax.mix_cli import to_elements

        self.assertAlmostEqual(
            to_elements({'Fe': 1}, 'mmol', 'HCO3', 'umol')['Fe'], 0.055845, places=6
        )
        self.assertAlmostEqual(
            to_elements({'B': 10}, 'meq', 'HCO3', 'umol')['B'], 0.1081, places=6
        )
        # mmol/L report, micronutrients in umol/L: nine major ions not measured, alkalinity 1, then
        # Fe.
        code, lines, script = self.run_mix(
            SPEC + ['2', 'w', '3', '1', '2', '7.5'] + [''] * 9 + ['1']
        )
        self.assertEqual(code, 1)
        self.assertIn('Micronutrients on your report in', lines)
        self.assertTrue(script.prompts[-1].startswith('Fe, µmol/L'), script.prompts[-1])
        code, lines, script = self.run_mix(
            SPEC + ['2', 'w', '3', '1', '1', '7.5'] + [''] * 9 + ['1']
        )
        self.assertTrue(script.prompts[-1].startswith('Fe, mg/L'), script.prompts[-1])

    def test_phosphate_meq_assumption_is_shown(self):
        code, _, script = self.run_mix(SPEC + ['2', 'w', '2', '1', '1', '7.5'] + [''] * 8)
        self.assertEqual(code, 1)
        self.assertTrue(script.prompts[-1].startswith('PO4, meq/L as H2PO4-'), script.prompts[-1])

    def test_one_prompt_per_ion_reads_lab_notation(self):
        from flahax.mix_water import lab_entry

        self.assertEqual(
            [lab_entry(a) for a in ('', '0', '0.4', '<0.02', '< 0.5')],
            [(None, None), (0.0, None), (0.4, None), (None, 0.02), (None, 0.5)],
        )
        for bad in ('abc', '<0', '-1', '<'):
            with self.assertRaises(ValueError):
                lab_entry(bad)
        _, lines, script = self.run_mix(SPEC + ['2', 'w', '1', '1', '7.5', 'x', '<0.1'])
        self.assertIn("  'x': type a number, 0, <limit, or Enter.", lines)
        self.assertEqual(script.prompts[-3], script.prompts[-2])  # Ca asked again after 'x'
        self.assertTrue(script.prompts[-1].startswith('Mg, mg/L'), script.prompts[-1])

    def test_added_products_keep_notes_and_run_through_batch(self):
        single = [
            '2',
            'iron ii sulfate',
            'Ferrous sulfate 97 %',
            'Example Supplier',
            '2026-01-15',
            'TDS-1',
            '',
            '',
            'use within a week',
        ]
        compound = [
            '3',
            'WS NPK 20-20-20 + TE',
            'Van Iperen International',
            '2025-03-28',
            'WS NPK sheet',
            '5',
            '3',
            '12',
            '20',
            '20',
            '',
            '',
            '',
            '0.056',
            '0.028',
            '0.008',
            '0.006',
            '0.01',
            '0.004',
            '',
            '',
            '1',
            'tank pH above 4; keep dry',
        ]
        target = Path(self.tmp.name) / 'out'
        code, lines, _ = self.run_mix(
            SPEC + RO + TOMATO + ['1'] + single + compound + ['1', ''] + NITRIC + END,
            '--output',
            str(target),
        )
        self.assertIn(code, (0, 3), lines)
        self.assertIn('Added Ferrous sulfate 97 % as Iron II Sulfate (Hepahydrate).', lines)
        store = Store(self.home).load('stores', 'my-fertilizers')
        graded = {p['name']: p for p in store if 'grade' in p}
        self.assertEqual(
            graded['Iron II Sulfate (Hepahydrate)']['grade']['compatibility_notes'],
            ['use within a week'],
        )
        self.assertEqual(
            graded['WS NPK 20-20-20 + TE']['grade']['compatibility_notes'],
            ['tank pH above 4', 'keep dry'],
        )
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = batch(
                [
                    '--crop',
                    'tomato (howard',
                    '--water',
                    'ro',
                    '--acid',
                    'HNO3:0.6:1.37',
                    '--products',
                    str(self.home / 'stores/my-fertilizers.json'),
                    '--output',
                    str(Path(self.tmp.name) / 'b'),
                ]
            )
        self.assertIn(code, (0, 3), err.getvalue())
        summary = json.loads((Path(self.tmp.name) / 'b/summary.json').read_text(encoding='utf-8'))
        self.assertNotEqual(
            summary['stages']['chemistry']['status'], 'blocked', summary['stages']['chemistry']
        )

    def test_store_saves_atomically(self):
        store = Store(self.home)
        path = store.save('waters', 'Well 104', {'id': 'w'})
        self.assertEqual(path.name, 'well-104.json')
        with mock.patch('flahax.mix_store.os.replace', side_effect=OSError('disk')):
            with self.assertRaises(OSError):
                store.save('waters', 'well-104', {'id': 'changed'})
        self.assertEqual(store.load('waters', 'well-104'), {'id': 'w'})
        self.assertEqual(
            sorted(p.name for p in (self.home / 'waters').iterdir()), ['well-104.json']
        )


def owner_transcript():
    """Every prompt and line of the owner's session (line mode), temp folder and version hidden."""
    with tempfile.TemporaryDirectory() as tmp:
        answers, lines = list(ANSWERS), []

        def ask(prompt):
            lines.append('? ' + prompt)
            return answers.pop(0)

        with mock.patch.dict(os.environ, {'FLAHAX_HOME': str(Path(tmp) / 'home')}):
            main(
                ['--output', str(Path(tmp) / 'out')],
                ask=ask,
                say=lambda *a: lines.append(' '.join(map(str, a))),
            )
    return '\n'.join(lines).replace(tmp, '<TMP>').replace(__version__, '<VERSION>') + '\n'


class LineModeTranscriptTests(unittest.TestCase):
    def test_plain_transcript_unchanged(self):
        expected = (FIXTURES / 'owner-session-plain.txt').read_text(encoding='utf-8')
        self.assertEqual(owner_transcript().splitlines(), expected.splitlines())


class PromptInterfaceTests(unittest.TestCase):
    def prompts(self, answers):
        lines = []
        return Prompts(Script(answers), lines.append), lines

    def test_number_answer(self):
        self.assertEqual(number_answer('', 5), (5, None))
        self.assertEqual(number_answer('x', None), (None, "  'x' is not a number."))
        self.assertEqual(
            number_answer('0', None, positive=True), (None, '  Enter a number above 0.')
        )
        self.assertEqual(
            number_answer('70', 25, high=60), (None, '  Enter a number from 0 up to 60.')
        )
        self.assertIsNone(number_answer('nan', None)[0])
        self.assertEqual(number_answer('', None, blank=True), (None, None))
        self.assertEqual(number_answer('7.5', None), (7.5, None))

    def test_pick_many_plain(self):
        p, lines = self.prompts(['3 1 3'])
        self.assertEqual(p.pick_many('Fertilizers', ['a', 'b', 'c']), [2, 0])
        self.assertIn('   1  a', lines)
        p, lines = self.prompts(['0', '2'])
        self.assertEqual(p.pick_many('Fertilizers', ['a', 'b', 'c']), [1])
        self.assertIn('  Use numbers 1 to 3.', lines)

    def test_step_and_answered_plain(self):
        p, lines = self.prompts([])
        p.step(5)
        p.answered('Tanks', 'A 20 L')
        self.assertEqual(lines, [])
        p.step(5, '5/5 pH requirement')
        self.assertEqual(lines, ['5/5 pH requirement'])


if __name__ == '__main__':
    unittest.main()
