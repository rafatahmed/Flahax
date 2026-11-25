# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The stock and equipment words the reports use are defined once in the glossary (D7)."""

import re
import unittest
from pathlib import Path

GLOSSARY = (Path(__file__).resolve().parents[1] / 'GLOSSARY.md').read_text(encoding='utf-8')
TERMS = (
    'Stock assignment',
    'Required tanks',
    'Available tanks',
    'Equipment fit',
    'Single-product solubility',
)


def entry(term):
    match = re.search(rf'^\*\*{re.escape(term)}\*\*:\n(.+?)(?:\n\n|\Z)', GLOSSARY, re.S | re.M)
    return match.group(1) if match else None


class StockGlossaryTests(unittest.TestCase):
    def test_each_term_is_defined_once(self):
        for term in TERMS:
            with self.subTest(term=term):
                self.assertEqual(
                    len(re.findall(rf'^\*\*{re.escape(term)}\*\*:', GLOSSARY, re.M)), 1
                )
                self.assertTrue(entry(term))

    def test_the_stock_assignment_names_the_words_to_avoid(self):
        text = entry('Stock assignment')
        for avoided in ('Tank grouping', 'Tank assignment', 'Separation assignment'):
            self.assertIn(avoided, text)

    def test_equipment_terms_name_the_summary_fields(self):
        self.assertIn('tanks.equipment.fit', entry('Equipment fit'))
        self.assertIn('available_tanks_declared', entry('Available tanks'))
        self.assertIn('tanks.required_tanks', entry('Required tanks'))

    def test_single_product_solubility_says_it_is_not_mixture_approval(self):
        text = entry('Single-product solubility')
        self.assertIn('mixture', text)
        self.assertIn('unverified', text)


if __name__ == '__main__':
    unittest.main()
