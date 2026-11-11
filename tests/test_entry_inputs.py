# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Bad input at every entry point gets a plain message and an exit code, never a traceback
(#117)."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from flahax.__main__ import main as flahax
from flahax.batch_cli import main as batch

TOMATO = ['--formula', 'Tomato (Howard Resh)']


def run(command, argv, stdin=''):
    out, err = io.StringIO(), io.StringIO()
    with (
        mock.patch('sys.argv', ['flahax', *argv]),
        mock.patch('sys.stdin', io.StringIO(stdin)),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        try:
            code = command(argv) if command is batch else command()
        except SystemExit as exc:
            code = exc.code
    return code, err.getvalue() + out.getvalue()


class EntryInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        (self.dir / 'bad.json').write_text('{"bad json', encoding='utf-8')
        (self.dir / 'lots.json').write_text(
            json.dumps({'measured_ph': 7, 'mg_per_litre': {'Ca': 'lots'}}), encoding='utf-8'
        )

    def batch(self, *extra):
        return run(batch, [*TOMATO, '--water', 'ro', '--output', str(self.dir / 'out'), *extra])

    def test_numbers_are_checked_at_the_command_line(self):
        for option, value, said in (
            ('--ratio', '0', '--ratio must be above 0, not 0'),
            ('--volume', '-5', '--volume must be above 0'),
            ('--ph', '20', '--ph must be at least 0 and at most 14'),
            ('--ratio', 'abc', "--ratio 'abc' is not a number"),
            ('--max-reagent-litres', '0', '--max-reagent-litres must be above 0'),
        ):
            with self.subTest(option=option, value=value):
                code, text = self.batch(option, value)
                self.assertEqual(code, 2)
                self.assertIn(said, text)
                self.assertNotIn('Traceback', text)

    def test_files_are_named_with_the_line(self):
        code, text = run(
            batch,
            [*TOMATO, '--water', str(self.dir / 'bad.json'), '--output', str(self.dir / 'o')],
        )
        self.assertEqual(code, 1)
        self.assertIn('water file', text)
        self.assertRegex(text, r'bad\.json is not valid JSON: \w.* at line 1, column \d+')
        self.assertNotIn('at at', text)
        code, text = run(
            batch,
            [*TOMATO, '--water', str(self.dir / 'none.json'), '--output', str(self.dir / 'o')],
        )
        self.assertIn('none.json was not found', text)
        code, text = run(
            batch,
            [
                '--targets',
                str(self.dir / 'bad.json'),
                '--water',
                'ro',
                '--output',
                str(self.dir / 'o'),
            ],
        )
        self.assertIn('targets file', text)

    def test_water_values_and_acid_numbers_are_named(self):
        _, text = run(
            batch,
            [*TOMATO, '--water', str(self.dir / 'lots.json'), '--output', str(self.dir / 'o')],
        )
        self.assertIn("water value Ca = 'lots' is not a number of mg/L", text)
        _, text = self.batch('--acid', 'HNO3:abc:1.4')
        self.assertIn("the assay (mass fraction) 'abc' is not a number", text)

    def test_stdin_json_errors_give_the_position(self):
        code, text = run(flahax, ['workflow'], '{"bad json')
        self.assertEqual(code, 1)
        self.assertRegex(text, r'stdin is not valid JSON: \w.* at line 1, column \d+')
        code, text = run(flahax, [], '{bad')
        self.assertIn('Expected a JSON object on stdin: Expecting property name', text)

    def test_custom_product_missing_id_is_an_input_error(self):
        path = self.dir / 'products.json'
        path.write_text('[{}]', encoding='utf-8')
        code, text = self.batch('--products', str(path))
        self.assertEqual(code, 1)
        self.assertIn('products entry 1', text)
        self.assertIn('id', text)
        self.assertNotIn('Traceback', text)
        self.assertFalse((self.dir / 'out').exists())

    def test_malformed_custom_records_name_the_entry(self):
        for option, label, records, message in (
            ('--products', 'products', {}, 'JSON array'),
            ('--products', 'products', [None], 'product record'),
            ('--products', 'products', [{'id': 'custom'}], 'name'),
            ('--reagents', 'pH reagents', [{}], 'id'),
            ('--reagents', 'pH reagents', [None], 'product record'),
        ):
            with self.subTest(option=option, records=records):
                path = self.dir / 'records.json'
                path.write_text(json.dumps(records), encoding='utf-8')
                code, text = self.batch(option, str(path))
                self.assertEqual(code, 1)
                self.assertIn(label + (' entry 1' if isinstance(records, list) else ''), text)
                self.assertIn(message, text)
                self.assertNotIn('Traceback', text)
                self.assertFalse((self.dir / 'out').exists())

    def test_distinct_product_ids_cannot_share_a_name(self):
        from flahax import load_library

        products = [
            dict(p, id=f'custom-{p["formula"]}', name='Custom fertilizer')
            for p in load_library()['salts']
            if p['formula'] in ('KNO3', 'KH2PO4')
        ]
        path = self.dir / 'products.json'
        reagents = self.dir / 'reagents.json'
        reagents.write_text('[]', encoding='utf-8')
        targets = self.dir / 'targets.json'
        targets.write_text(json.dumps({'K': 150, 'N_NO3': 40, 'P': 25}), encoding='utf-8')
        for ordered in (products, list(reversed(products))):
            with self.subTest(order=[p['id'] for p in ordered]):
                path.write_text(json.dumps(ordered), encoding='utf-8')
                code, text = run(
                    batch,
                    [
                        '--targets',
                        str(targets),
                        '--products',
                        str(path),
                        '--reagents',
                        str(reagents),
                        '--water',
                        'ro',
                        '--ph',
                        '5.8',
                        '--volume',
                        '1000',
                        '--output',
                        str(self.dir / 'out'),
                    ],
                )
                self.assertEqual(code, 1)
                self.assertIn('distinct names', text)
                self.assertIn('Custom fertilizer', text)
                self.assertFalse((self.dir / 'out').exists())

    def test_distinct_custom_names_preserve_accounting_and_reports(self):
        from fractions import Fraction
        from flahax import load_library

        products = [
            dict(p, id=f'custom-{p["formula"]}', name=f'Custom {p["formula"]}')
            for p in load_library()['salts']
            if p['formula'] in ('KNO3', 'KH2PO4')
        ]
        path = self.dir / 'products.json'
        targets = self.dir / 'targets.json'
        targets.write_text(json.dumps({'K': 150, 'N_NO3': 40, 'P': 25}), encoding='utf-8')
        reagents = self.dir / 'reagents.json'
        reagents.write_text('[]', encoding='utf-8')
        prefixed = [dict(p, name='test_' + p['formula']) for p in products]
        for index, ordered in enumerate(
            (products, list(reversed(products)), prefixed, list(reversed(prefixed)))
        ):
            with self.subTest(order=[p['id'] for p in ordered]):
                path.write_text(json.dumps(ordered), encoding='utf-8')
                output = self.dir / f'distinct-{index}'
                code, text = run(
                    batch,
                    [
                        '--targets',
                        str(targets),
                        '--products',
                        str(path),
                        '--reagents',
                        str(reagents),
                        '--water',
                        'ro',
                        '--ph',
                        '5.8',
                        '--volume',
                        '1000',
                        '--output',
                        str(output),
                    ],
                )
                self.assertEqual(code, 3, text)  # No base was offered; chemistry still reports.
                result = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
                self.assertEqual(result['stages']['chemistry']['status'], 'calculated')
                self.assertEqual(result['ph']['direction'], 'base')
                self.assertAlmostEqual(result['ph']['unadjusted_ph'], 5.135056763887405, places=8)
                by_id = {p['id']: p for p in ordered}
                salts = result['formulation']['salts']
                self.assertEqual({s['id'] for s in salts}, set(by_id))
                for row in result['formulation']['rows']:
                    expected = sum(
                        Fraction(str(s['gramsPerBatch']))
                        * Fraction(str(by_id[s['id']]['elements'].get(row['symbol'], 0)))
                        / 100
                        for s in salts
                    )  # grams per 1,000 L have the same numerical value as mg/L.
                    self.assertAlmostEqual(row['final'], float(expected), places=10)
                for filename in ('report.html', 'batch-sheet.html'):
                    report = (output / filename).read_text(encoding='utf-8')
                    for product in ordered:
                        self.assertIn(product['name'], report)

    def test_added_acid_cannot_duplicate_an_offered_reagent_name(self):
        from flahax import catalogue_ph_reagents

        acid = next(p for p in catalogue_ph_reagents() if p['chemicalFormula'] == 'HNO3')
        path = self.dir / 'reagents.json'
        path.write_text(json.dumps([dict(acid, name='Same reagent')]), encoding='utf-8')
        code, text = self.batch('--reagents', str(path), '--acid', 'HNO3:0.6:1.37:Same reagent')
        self.assertEqual(code, 1)
        self.assertIn('pH reagents need distinct names', text)
        self.assertFalse((self.dir / 'out').exists())

    def test_reagent_density_type_is_checked_before_configuring_joint_fit(self):
        from flahax import catalogue_ph_reagents

        reagent = next(p for p in catalogue_ph_reagents() if p['chemicalFormula'] == 'KOH')
        path = self.dir / 'reagents.json'
        for density in ('1.45', True, float('nan'), float('inf'), 0, -1):
            with self.subTest(density=density):
                path.write_text(
                    json.dumps([dict(reagent, densityKgPerL=density)]), encoding='utf-8'
                )
                code, text = self.batch('--reagents', str(path))
                self.assertEqual(code, 1)
                self.assertIn('densityKgPerL', text)
                self.assertNotIn('Traceback', text)
                self.assertFalse((self.dir / 'out').exists())

    def test_valid_input_returns_the_current_result(self):
        code, text = self.batch('--acid', 'HNO3:0.60:1.37:Nitric acid 60%')
        self.assertEqual(code, 0, text)
        self.assertIn(' - requires review', text)
        self.assertNotIn('mL Nitric acid 60%', text)
        summary = json.loads((self.dir / 'out/summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['status'], 'requires_review')
        self.assertEqual(summary['ph']['selected']['direction'], 'base')


if __name__ == '__main__':
    unittest.main()
