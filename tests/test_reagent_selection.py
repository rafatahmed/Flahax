# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Available pH reagents at the batch and saved mix interfaces."""

import json
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from flahax.batch_cli import BatchOptions, acid_record, run_batch, main as batch
from flahax.mix_cli import main as mix
from flahax.mix_store import Store
from flahax.ph_adjustment import catalogue_ph_reagents
from tests.test_mix_cli import SPEC, RO, TOMATO, CATALOGUE, END, Script, GOOD_SESSION


class BatchAvailabilityTests(unittest.TestCase):
    def test_batch_cli_empty_availability_never_restores_catalogue_reagents(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'none.json'
            path.write_text('[]')
            with contextlib.redirect_stdout(io.StringIO()):
                code = batch(
                    [
                        '--water',
                        'ro',
                        '--formula',
                        'Tomato (Howard Resh)',
                        '--reagents',
                        str(path),
                        '--output',
                        str(root / 'out'),
                    ]
                )
            self.assertEqual(code, 3)
            result = json.loads((root / 'out' / 'summary.json').read_text())
            self.assertEqual(result['ph']['direction'], 'base')
            self.assertEqual(result['ph']['candidates'], [])
            self.assertIsNone(result['ph']['selected'])
            self.assertIn('none was offered: add a base', result['ph']['message'])

    def test_batch_rejects_reagent_json_that_is_not_an_array_of_records(self):
        for value in ({'id': 'not-an-array'}, ['not-a-record']):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                path = root / 'reagents.json'
                path.write_text(json.dumps(value))
                messages = io.StringIO()
                with contextlib.redirect_stderr(messages), contextlib.redirect_stdout(messages):
                    code = batch(
                        [
                            '--water',
                            'ro',
                            '--formula',
                            'DEFAULT',
                            '--reagents',
                            str(path),
                            '--output',
                            str(root / 'out'),
                        ]
                    )
                self.assertNotEqual(code, 0)
                self.assertIn(
                    'pH reagents must be a JSON array of product records', messages.getvalue()
                )
                self.assertFalse((root / 'out' / 'summary.json').exists())

    def test_batch_cli_uses_only_the_selected_catalogue_base(self):
        base = next(r for r in catalogue_ph_reagents() if r['chemicalFormula'] == 'KOH')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'base.json'
            path.write_text(json.dumps([base]))
            with contextlib.redirect_stdout(io.StringIO()):
                code = batch(
                    [
                        '--water',
                        'ro',
                        '--formula',
                        'Tomato (Howard Resh)',
                        '--reagents',
                        str(path),
                        '--output',
                        str(root / 'out'),
                    ]
                )
            self.assertEqual(code, 0)
            result = json.loads((root / 'out' / 'summary.json').read_text())
        self.assertEqual(result['ph']['selected']['product_id'], base['id'])
        self.assertEqual({r['product_id'] for r in result['ph']['candidates']}, {base['id']})
        self.assertAlmostEqual(result['chemistry']['final_ph'], 5.8, delta=1e-4)

    def test_empty_list_needs_no_reagent_when_mixed_ph_is_already_on_target(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'none.json'
            path.write_text('[]')
            result = run_batch(
                BatchOptions(
                    water='ro', formula='Tomato (Howard Resh)', reagents=str(path), ph=4.8927367
                )
            )
        self.assertEqual(result['ph']['direction'], 'none')
        self.assertNotEqual(result['ph']['status'], 'blocked')
        self.assertIsNone(result['ph']['selected'])
        self.assertEqual(result['ph']['candidates'], [])

    def test_empty_available_list_reports_missing_base_without_restoring_catalogue(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'none.json'
            path.write_text('[]')
            result = run_batch(
                BatchOptions(water='ro', formula='Tomato (Howard Resh)', reagents=str(path))
            )
        self.assertEqual(result['ph']['direction'], 'base')
        self.assertIsNone(result['ph']['selected'])
        self.assertEqual(result['ph']['candidates'], [])
        self.assertIn('none was offered: add a base', result['ph']['message'])

    def test_explicit_acid_only_list_does_not_add_catalogue_bases(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'reagents.json'
            path.write_text(json.dumps([acid_record('HNO3:0.65:1.39')]))
            result = run_batch(
                BatchOptions(
                    water='ro',
                    formula='Tomato (Howard Resh)',
                    reagents=str(path),
                )
            )
        self.assertIsNone(result['ph']['selected'])
        self.assertEqual(result['ph']['direction'], 'base')
        self.assertIn('none was offered: add a base', result['ph']['message'])


class MixAvailabilityTests(unittest.TestCase):
    def test_saved_acid_certificates_can_be_selected_without_inventing_solvent_content(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = Store(root / 'home')
            store.save(
                'acids',
                'declared',
                dict(
                    formula='HNO3',
                    fraction=0.65,
                    density=1.39,
                    name='Declared nitric',
                    solvent_fraction=0.35,
                ),
            )
            store.save(
                'acids',
                'unknown',
                dict(
                    formula='HNO3',
                    fraction=0.60,
                    density=1.37,
                    name='Unknown remainder',
                ),
            )
            store.save('sessions', 'old', dict(GOOD_SESSION))
            count = len(catalogue_ph_reagents())
            answers = Script(['2', f'{count + 1} {count + 2}', '1', 'certificates', 'reviewed'])
            mix(
                ['sessions/old', '--review-reagents', '--plain', '--output', str(root / 'out')],
                store=store,
                ask=answers,
                say=lambda *a: None,
            )
            records = store.load('reagents', 'certificates')
            self.assertEqual(
                [r['name'] for r in records], ['Declared nitric', 'Unknown remainder']
            )
            self.assertEqual([r['massFraction'] for r in records], [0.65, 0.60])
            self.assertEqual([r['solventMassFraction'] for r in records], [0.35, None])
            self.assertEqual(store.load('sessions', 'reviewed')['reagent_store'], 'certificates')
            self.assertEqual(answers.answers, [])
            result = json.loads((root / 'out' / 'summary.json').read_text())
            self.assertEqual(result['ph']['candidates'], [])
            self.assertIsNone(result['ph']['selected'])

    def test_saved_list_is_reused_and_duplicate_custom_name_keeps_original_composition(self):
        with tempfile.TemporaryDirectory() as folder:
            root, lines = Path(folder), []
            store = Store(root / 'home')
            record = acid_record('HNO3:0.65:1.39:My nitric:0.35')
            record['id'] = 'custom-my-nitric'
            store.save('reagents', 'available', [record])
            store.save('sessions', 'old', dict(GOOD_SESSION))
            original = store.path('reagents', 'available').read_bytes()
            answers = Script(
                [
                    '2',
                    '2',
                    'HNO3',
                    '60',
                    '1',
                    '1.37',
                    '40',
                    'My nitric',
                    '1',
                    'reviewed',
                ]
            )
            mix(
                ['sessions/old', '--review-reagents', '--plain', '--output', str(root / 'out')],
                store=store,
                ask=answers,
                say=lambda *a: lines.append(' '.join(map(str, a))),
            )
            self.assertIn(
                'A reagent with that name is already selected; use a distinct name.', lines
            )
            self.assertEqual(store.load('sessions', 'reviewed')['reagent_store'], 'available')
            self.assertEqual(store.path('reagents', 'available').read_bytes(), original)
            self.assertEqual(store.list('reagents'), ['available'])
            self.assertEqual(answers.answers, [])
            result = json.loads((root / 'out' / 'summary.json').read_text())
            self.assertEqual(result['ph']['candidates'], [])

    def test_review_option_requires_a_saved_session(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder)
            messages = io.StringIO()
            with contextlib.redirect_stderr(messages), self.assertRaises(SystemExit) as error:
                mix(['--review-reagents', '--plain'], store=store)
            self.assertEqual(error.exception.code, 2)
            self.assertIn('--review-reagents requires a saved session', messages.getvalue())
            self.assertEqual(store.list('sessions'), [])

    def test_review_cannot_replace_original_session_even_after_replace_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            root, lines = Path(folder), []
            store = Store(root / 'home')
            store.save('sessions', 'old', dict(GOOD_SESSION))
            original = store.path('sessions', 'old').read_bytes()
            answers = Script(['3', '1', 'none', 'old', '2'])
            code = mix(
                ['sessions/old', '--review-reagents', '--plain', '--output', str(root / 'out')],
                store=store,
                ask=answers,
                say=lines.append,
            )
            self.assertEqual(code, 1)
            self.assertIn(
                'Use a new session name to preserve the original answers', '\n'.join(lines)
            )
            self.assertEqual(store.path('sessions', 'old').read_bytes(), original)
            self.assertEqual(store.list('sessions'), ['old'])
            self.assertEqual(store.list('reagents'), [])
            self.assertFalse((root / 'out').exists())
            self.assertEqual(answers.answers, [])

    def test_empty_list_cannot_use_the_reserved_catalogue_name(self):
        with tempfile.TemporaryDirectory() as folder:
            root, lines = Path(folder), []
            store = Store(root / 'home')
            answers = Script(
                SPEC + RO + TOMATO + CATALOGUE + ['3', '1', 'catalogue', 'none'] + END
            )

            def say(*args):
                line = ' '.join(map(str, args))
                lines.append(line)
                if line.startswith('Saved the answers'):
                    self.assertEqual(store.list('reagents'), ['none'])

            mix(['--plain', '--output', str(root / 'out')], store=store, ask=answers, say=say)
            self.assertEqual(store.list('reagents'), ['none'], '\n'.join(lines))
            summary = json.loads((root / 'out' / 'summary.json').read_text())
            self.assertEqual(summary['ph']['candidates'], [])

    def test_reagent_review_does_not_accept_changed_fertilizer_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root, lines = Path(folder), []
            store = Store(root / 'home')
            store.save('stores', 'fertilizers', [])
            store.save('sessions', 'old', dict(GOOD_SESSION, store='fertilizers'))
            store.save('stores', 'fertilizers', [{'name': 'changed'}])
            answers = Script(['3', '1', 'none', 'reviewed'])
            code = mix(
                ['sessions/old', '--review-reagents', '--plain', '--output', str(root / 'out')],
                store=store,
                ask=answers,
                say=lines.append,
            )
            self.assertEqual(code, 1)
            self.assertIn('saved inputs or model changed', '\n'.join(lines))
            self.assertEqual(store.list('sessions'), ['old'])

    def test_custom_solid_accepts_exact_declared_water_remainder_without_density(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = Store(root / 'home')
            script = Script(
                SPEC
                + RO
                + TOMATO
                + CATALOGUE
                + [
                    '3',
                    '2',
                    'KOH',
                    '90',
                    '2',
                    '10',
                    'My solid',
                    '1',
                    'my reagents',
                    '4.5',
                    '1',
                    'solid-only',
                ]
            )
            lines = []
            mix(
                ['--plain', '--output', str(root / 'out')],
                store=store,
                ask=script,
                say=lambda *a: lines.append(' '.join(map(str, a))),
            )
            self.assertEqual(store.list('reagents'), ['my-reagents'], '\n'.join(lines))
            (record,) = store.load('reagents', 'my-reagents')
            self.assertEqual(record['physicalForm'], 'solid')
            self.assertIsNone(record['densityKgPerL'])
            self.assertEqual(record['solventMassFraction'], 0.1)

    def test_old_session_requires_review_and_can_save_explicit_availability_as_a_new_session(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = Store(root / 'home')
            original = dict(GOOD_SESSION)
            original.pop('reagent_store', None)
            store.save('sessions', 'old', original)
            original_bytes = store.path('sessions', 'old').read_bytes()
            lines = []
            code = mix(
                ['sessions/old', '--plain', '--output', str(root / 'blocked')],
                store=store,
                ask=lambda p: self.fail(p),
                say=lines.append,
            )
            self.assertEqual(code, 1)
            self.assertIn('--review-reagents', '\n'.join(lines))
            answers = Script(['3', '1', 'none', 'reviewed'])
            mix(
                [
                    'sessions/old',
                    '--review-reagents',
                    '--plain',
                    '--output',
                    str(root / 'reviewed'),
                ],
                store=store,
                ask=answers,
                say=lambda *a: None,
            )
            self.assertEqual(store.path('sessions', 'old').read_bytes(), original_bytes)
            self.assertEqual(store.load('sessions', 'reviewed')['reagent_store'], 'none')
            self.assertEqual(store.load('reagents', 'none'), [])

    def test_custom_base_can_be_saved_without_adding_unavailable_acids(self):
        with tempfile.TemporaryDirectory() as folder:
            root, lines = Path(folder), []
            store = Store(root / 'home')
            script = Script(
                SPEC
                + RO
                + TOMATO
                + CATALOGUE
                + [
                    '3',
                    '2',
                    'KOH',
                    '45',
                    '1',
                    '1.45',
                    '55',
                    'My base',
                    '1',
                    'my reagents',
                    '4.5',
                    '1',
                    'base-only',
                ]
            )
            mix(
                ['--plain', '--output', str(root / 'out')],
                store=store,
                ask=script,
                say=lambda *a: lines.append(' '.join(map(str, a))),
            )
            self.assertEqual(store.list('reagents'), ['my-reagents'], '\n'.join(lines))
            (record,) = store.load('reagents', 'my-reagents')
            self.assertEqual(record['chemicalFormula'], 'KOH')
            self.assertEqual(record['physicalForm'], 'liquid')
            self.assertEqual(record['solventMassFraction'], 0.55)
            summary = json.loads((root / 'out' / 'summary.json').read_text())
            self.assertIsNone(summary['ph']['selected'])
            self.assertEqual(summary['ph']['direction'], 'acid')

    def test_selected_acid_list_is_saved_and_replayed_without_catalogue_bases(self):
        catalogue = catalogue_ph_reagents()
        index = next(i for i, r in enumerate(catalogue, 1) if r['chemicalFormula'] == 'HNO3')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = Store(root / 'home')
            script = Script(
                SPEC + RO + TOMATO + CATALOGUE + ['2', str(index), '1', 'my reagents'] + END
            )
            lines = []

            def say(*args):
                text = ' '.join(map(str, args))
                self.assertNotIn('Acids for the pH plan', text)
                lines.append(text)

            mix(['--plain', '--output', str(root / 'first')], store=store, ask=script, say=say)
            self.assertEqual(store.list('reagents'), ['my-reagents'], '\n'.join(lines))
            session = store.load('sessions', 'tomato-howard-resh-ro')
            self.assertEqual(session['reagent_store'], 'my-reagents')
            self.assertEqual(
                [r['chemicalFormula'] for r in store.load('reagents', 'my-reagents')], ['HNO3']
            )
            mix(
                ['sessions/tomato-howard-resh-ro', '--plain', '--output', str(root / 'again')],
                store=store,
                ask=lambda p: self.fail('Replay asked: ' + p),
                say=lambda *a: None,
            )
            for name in ('first', 'again'):
                summary = json.loads((root / name / 'summary.json').read_text())
                self.assertIsNone(summary['ph']['selected'])
                self.assertIn('none was offered: add a base', summary['ph']['message'])
