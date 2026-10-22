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
from flahax.mix_cli import WATER_IONS, main
from flahax.mix_store import Store

SPEC = ['20', '20', '20', '', '', '1']                          # tanks A, B, acid; ratio; temperature; fill
RO = ['1', '']                                                   # RO water; no limits
TOMATO = ['1', 'tomato (howard']                                 # a packaged formula, searched
TOMATO_KEYS = ['N_NO3', 'P', 'K', 'Mg', 'Ca', 'S', 'B', 'Fe', 'Zn', 'Cu', 'Mo', 'Mn']
CATALOGUE = ['1', '']                                            # whole catalogue; add nothing
NITRIC = ['1', 'HNO3', '60', '1.37', 'Nitric acid 60%', '']      # new acid from its certificate; done
END = ['', '1', '']                                              # pH 5.8; depth 1; session name


def water(name, values, *, units='1', alkalinity='1', ph='7.5', share='', limits=''):
    """A new analysis: ``values`` maps the lab's ion names to an entry or a (blank, choice[, limit]) tuple."""
    answers = ['2', name, units, alkalinity, ph]
    for ion in WATER_IONS:
        entry = values.get(ion, ('', '1'))
        answers += [entry] if isinstance(entry, str) else list(entry)
    return answers + [share, limits]


def changed_tomato(**values):
    return ['2', 'tomato (howard'] + [values.get(k, '') for k in TOMATO_KEYS] + ['']


BALANCED = {'Ca': '60.12', 'NO3': '62.0049', 'Alk': '100'}     # 3 meq/L each side (alkalinity as CaCO3)


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
        code = main(list(argv), ask=script, say=lambda *a: lines.append(' '.join(str(x) for x in a)))
        return code, lines, script

    def full(self, *, water_answers=RO, formula=TOMATO, out='out'):
        target = Path(self.tmp.name) / out
        code, lines, script = self.run_mix(SPEC + water_answers + formula + CATALOGUE + NITRIC + END,
                                           '--output', str(target))
        return code, lines, target

    def test_first_run_tomato_ro_fill_mode(self):
        code, lines, target = self.full()
        self.assertEqual(code, 0, '\n'.join(lines))
        sheet = (target / 'batch-sheet.html').read_text(encoding='utf-8')
        summary = json.loads((target / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual([t['name'] for t in summary['tanks']['tanks']], ['A', 'B'])
        self.assertNotIn('Tank C', sheet)
        self.assertNotIn('<td>C</td>', sheet)
        self.assertIn('2,000 L final solution', sheet)
        self.assertEqual(summary['volumes'], {'irrigation_litres': 2000.0, 'prepared_litres':
                                              {'A': 20.0, 'B': 20.0, 'acid': 20.0},
                                              'capacity_litres': {'A': 20.0, 'B': 20.0, 'acid': 20.0}})
        self.assertEqual(summary['tanks']['temperature_c'], 25)
        self.assertTrue(any(line.startswith('Tank A') for line in lines), lines)
        self.assertTrue(any('Nitric acid 60%' in line and 'mL' in line for line in lines), lines)
        store = Store(self.home)
        self.assertEqual(store.list('sessions'), ['tomato-howard-resh-ro'])
        session = store.load('sessions', 'tomato-howard-resh-ro')
        self.assertEqual(session['spec'], {'tank_litres': {'A': 20.0, 'B': 20.0, 'acid': 20.0}, 'ratio': 100.0,
                                           'temperature_c': 25.0, 'mode': 'fill', 'irrigation_litres': None})
        self.assertEqual((session['water'], session['formula'], session['store'], session['acids'], session['ph'],
                          session['depth']), ('ro', 'Tomato (Howard Resh)', 'catalogue', ['nitric-acid-60'], 5.8, 1))
        self.assertEqual(store.load('acids', 'nitric-acid-60'),
                         {'formula': 'HNO3', 'fraction': 0.6, 'density': 1.37, 'name': 'Nitric acid 60%'})

    def test_second_run_from_session_asks_nothing(self):
        code, _, first = self.full()
        self.assertEqual(code, 0)

        def refuse(prompt):
            raise AssertionError(f'asked {prompt!r}')
        lines = []
        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        try:
            code = main(['sessions/tomato-howard-resh-ro'], ask=refuse, say=lambda *a: lines.append(' '.join(a)))
        finally:
            os.chdir(cwd)
        self.assertEqual(code, 0, lines)
        again = json.loads((Path(self.tmp.name) / 'flahax-mix-tomato-howard-resh-ro/summary.json').read_text('utf-8'))
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
        self.assertAlmostEqual(to_elements({'Ca': 2, 'SO4': 2, 'Alk': 1}, 'meq', 'CaCO3')['Ca'], 40.078, places=3)
        self.assertAlmostEqual(to_elements({'SO4': 2}, 'meq', 'HCO3')['S'], 32.06, places=2)
        self.assertAlmostEqual(to_elements({'Alk': 1}, 'mmol', 'CaCO3')['HCO3'], 2 * 61.0168, places=4)
        self.assertAlmostEqual(to_elements({'NO3': 1}, 'mmol', 'HCO3')['N_NO3'], 14.0067, places=3)

    def test_wrong_unit_shows_imbalance(self):
        values = dict(BALANCED, NO3='12')      # NO3-N typed where the report asks for NO3
        code, lines, _ = self.run_mix(SPEC + water('well', values, alkalinity='2')[:-2])
        self.assertEqual(code, 1)
        warning = next(line for line in lines if line.startswith('Warning:'))
        apart = float(warning.split('are ')[1].split(' %')[0])
        self.assertGreater(apart, 5)
        self.assertIn('Ca', warning)

    def test_blank_is_never_guessed(self):
        values = dict(BALANCED, Fe=('', '1'), Mn=('', '2'), Zn=('', '3', '0.02'))
        code, lines, _ = self.full(water_answers=water('blanks', values, alkalinity='2'))
        self.assertIn(code, (0, 3), lines)
        saved = Store(self.home).load('waters', 'blanks')
        self.assertNotIn('Fe', saved['mg_per_litre'])
        self.assertEqual(saved['mg_per_litre']['Mn'], 0)
        self.assertNotIn('Zn', saved['mg_per_litre'])
        self.assertEqual(saved['below_detection'], {'Zn': 0.02})

    def test_interrupt_saves_nothing(self):
        code, lines, script = self.run_mix(SPEC + water('well', BALANCED, alkalinity='2'))
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
        shutil.rmtree(self.home)        # a fresh store, so the script below matches
        with mock.patch('flahax.mix_cli.run_batch', wraps=__import__('flahax.batch_cli').batch_cli.run_batch) as run:
            code, lines, target = self.full(water_answers=['1', 'Na=69'], out='limited')
        self.assertIn(code, (0, 3), lines)
        self.assertEqual(run.call_args.args[0].limit, [('Na', 69.0)])
        summary = json.loads((target / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual([(r['symbol'], r['maximumPpm']) for r in summary['limits']], [('Na', 69.0)])

    def test_batch_reads_saved_items(self):
        code, lines, _ = self.full(water_answers=water('well', BALANCED, alkalinity='2'),
                                   formula=changed_tomato(Ca='190'))
        self.assertIn(code, (0, 3), lines)
        store = Store(self.home)
        self.assertEqual(store.list('formulas'), ['tomato-howard-resh-changed'])
        self.assertEqual(store.load('formulas', 'tomato-howard-resh-changed')['Ca'], 190)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = batch(['--water', str(self.home / 'waters/well.json'), '--targets',
                          str(self.home / 'formulas/tomato-howard-resh-changed.json'), '--acid', 'HNO3:0.6:1.37',
                          '--output', str(Path(self.tmp.name) / 'batch')])
        self.assertIn(code, (0, 3), out.getvalue())

    def test_store_saves_atomically(self):
        store = Store(self.home)
        path = store.save('waters', 'Well 104', {'id': 'w'})
        self.assertEqual(path.name, 'well-104.json')
        with mock.patch('flahax.mix_store.os.replace', side_effect=OSError('disk')):
            with self.assertRaises(OSError):
                store.save('waters', 'well-104', {'id': 'changed'})
        self.assertEqual(store.load('waters', 'well-104'), {'id': 'w'})
        self.assertEqual(sorted(p.name for p in (self.home / 'waters').iterdir()), ['well-104.json'])


if __name__ == '__main__':
    unittest.main()
