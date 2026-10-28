# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Numeric inventory includes inline decisions and data without inventing qualification."""

import json
from pathlib import Path
import tempfile
import unittest

from tools.inventory_numeric_decisions import inventory


class NumericInventoryTests(unittest.TestCase):
    def test_inline_defaults_named_comparisons_and_numeric_data_are_inventoried(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'src/flahax/data'
            data.mkdir(parents=True)
            (data.parent / 'model.py').write_text(
                'LIMIT = -1e-7\ndef check(x, threshold=LIMIT):\n    return x <= threshold\n',
                encoding='utf-8',
            )
            (data / 'values.json').write_text(
                json.dumps({'a/b': [2, False, None]}), encoding='utf-8'
            )
            rows = inventory(root)
            self.assertEqual(
                {r['syntax_kind'] for r in rows},
                {'numeric_literal', 'default', 'comparison', 'data_number'},
            )
            numbers = [r for r in rows if r['syntax_kind'] == 'data_number']
            self.assertEqual(len(numbers), 1)
            self.assertEqual(numbers[0]['json_pointer'], '/a~1b/0')
            self.assertTrue(all(r['classification'] == 'unreviewed' for r in rows))
            self.assertTrue(all(r['source_or_derivation'] is None for r in rows))
            before = {r['source_sha256'] for r in rows if r['path'].endswith('model.py')}
            (data.parent / 'model.py').write_text('LIMIT = 2\n', encoding='utf-8')
            after = {r['source_sha256'] for r in inventory(root) if r['path'].endswith('model.py')}
            self.assertNotEqual(before, after)

    def test_numeric_strings_are_not_confused_with_formulas_dates_or_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'src/flahax/data'
            data.mkdir(parents=True)
            (data / 'values.json').write_text(
                json.dumps(
                    dict(
                        coefficient='-1.2e-3',
                        schema='1',
                        formula='5Ca(NO3)2',
                        version='1.2.3',
                        date='2026-10-25',
                    )
                )
            )
            rows = inventory(root)
            self.assertEqual({r['json_pointer'] for r in rows}, {'/coefficient', '/schema'})
            self.assertTrue(all(r['syntax_kind'] == 'data_numeric_string' for r in rows))
            self.assertTrue(all(r['classification'] == 'unreviewed' for r in rows))


if __name__ == '__main__':
    unittest.main()
