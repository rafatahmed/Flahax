# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Every error code a user can meet is explained in the shipped user guide (hardening 2/4)."""

from importlib.resources import files
from pathlib import Path
import re
import unittest

from flahax.delivery_contracts import DeliveryError
from flahax.material_chemistry import material_chemistry

ROOT = Path(__file__).resolve().parents[1]
RAISED = re.compile(r"DeliveryError\(\s*['\"]([a-z_]+)['\"]")


def raised_codes():
    codes = {}
    for path in sorted((ROOT / 'src' / 'flahax').glob('*.py')):
        for code in RAISED.findall(path.read_text(encoding='utf-8')):
            codes.setdefault(code, path.name)
    return codes


class ErrorCatalogueTests(unittest.TestCase):
    def test_every_raised_code_is_in_the_user_guide(self):
        guide = files('flahax').joinpath('data/USER_GUIDE.md').read_text(encoding='utf-8')
        documented = set(re.findall(r'`([a-z][a-z_]+)`', guide))
        missing = {
            code: module for code, module in raised_codes().items() if code not in documented
        }
        self.assertEqual(missing, {}, 'explain these codes in USER_GUIDE.md, section 8')

    def test_a_mistyped_formula_says_what_is_wrong(self):
        cases = (
            ('Ca(NO3', 'cannot be read: check the brackets'),
            ('KXx3', 'cannot be read'),
            ('C6H12O6', 'does not split into the fertilizer ions FlahaX knows'),
        )
        for formula, said in cases:
            with self.subTest(formula=formula), self.assertRaises(DeliveryError) as caught:
                material_chemistry({'name': 'My salt', 'formula': formula, 'elements': {}})
            self.assertEqual(caught.exception.code, 'material_undefined')
            self.assertIn(said, str(caught.exception))
            self.assertNotIn('give its formula, its ions', str(caught.exception))
        with self.assertRaises(DeliveryError) as caught:
            material_chemistry({'name': 'My salt', 'elements': {}})
        self.assertIn('give its formula, its ions, or its analysis', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
