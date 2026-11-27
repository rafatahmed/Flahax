# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Results have the same digits on every supported Python (#346).

The recorded values were produced on Windows with Python 3.11, 3.12, 3.13 and 3.14, which all
agree to the last digit. Doses, totals, ionic strength and acid amount are compared exactly on
every CI leg (Linux included); the tiny species are compared to 1e-9 relative, because their last
digits depend on the platform's math library, not on the Python version. A new Python-dependent
sum, or a change that is not bit-identical, fails on the leg where it differs. Regenerate only for
an intended numerical change: ``python -m tests.test_cross_version_digits --write``.
"""

import ast
import json
from pathlib import Path
import sys
import unittest

from flahax import load_library, recommend
from flahax.aqueous_model import nitric_target, solve

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'cross_version_digits.json'
WATER = {'Ca': 20.0, 'Mg': 5.0, 'N_NO3': 2.0}
BASE = {'Ca': 100.0, 'K': 150.0, 'Mg': 40.0, 'P': 40.0, 'S': 60.0}
TOTALS = {
    'CO3-2': 0.001,
    'Na+': 0.002,
    'Cl-': 0.001,
    'H3BO3': 1e-4,
    'Dtp-5': 1e-5,
    'Fe+3': 1e-5,
}


def current():
    salts = load_library()['salts']
    plain = recommend(salts, {**BASE, 'N': 150.0}, WATER)['grams']
    forms = recommend(salts, {**BASE, 'N_NO3': 130.0, 'N_NH4': 15.0}, WATER)['grams']
    capped = recommend(salts, {**BASE, 'N': 150.0}, WATER, max_ammonium_fraction=0.1)['grams']
    initial = solve(TOTALS, 7.4)
    acid = nitric_target(TOTALS, 7.4, 6.0)
    return {
        'recommend_plain': plain,
        'recommend_forms': forms,
        'recommend_ammonium_cap': capped,
        'aqueous_initial_species': dict(sorted(initial.species.items())),
        'nitric_acid_molal': acid.nitric_acid_molal,
        'nitric_target_ionic_strength': acid.target.ionic_strength,
        'nitric_target_charge_balance': acid.target.charge_balance,
        'nitric_target_species': dict(sorted(acid.target.species.items())),
    }


SPECIES = {'aqueous_initial_species', 'nitric_target_species'}


class CrossVersionDigitTests(unittest.TestCase):
    def test_results_match_the_recorded_digits_exactly(self):
        expected = json.loads(FIXTURE.read_text(encoding='utf-8'))
        actual = json.loads(json.dumps(current()))
        self.assertEqual(sorted(actual), sorted(expected))
        for name in expected:
            with self.subTest(result=name):
                if name in SPECIES:
                    self.assert_species_close(actual[name], expected[name])
                else:
                    self.assertEqual(actual[name], expected[name])

    def assert_species_close(self, actual, expected):
        # Species far below the solver tolerance (1e-14 mol/kg) differ by about 1e-13 relative
        # between Linux and Windows math libraries, on the same Python. They are compared to 1e-9
        # relative; every total, dose, ionic strength and acid amount stays exact.
        self.assertEqual(sorted(actual), sorted(expected))
        for species, value in expected.items():
            if value == 0:
                self.assertEqual(actual[species], 0, msg=species)
            else:
                self.assertAlmostEqual(actual[species] / value, 1.0, delta=1e-9, msg=species)

    def test_the_builtin_sum_is_not_reached_through_another_name(self):
        found = []
        for path in sorted((ROOT / 'src' / 'flahax').glob('*.py')):
            if path.name == 'float_sum.py':
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Attribute) and node.attr in {'sum', 'sumprod'}:
                    found.append(f'{path.name}:{node.lineno}')
                if isinstance(node, ast.ImportFrom) and node.module in {'builtins', 'math'}:
                    if any(alias.name in {'sum', 'sumprod'} for alias in node.names):
                        found.append(f'{path.name}:{node.lineno}')
        self.assertEqual(found, [], 'use float_sum so Python 3.11 and 3.12+ agree (#334, #346)')


if __name__ == '__main__':
    if '--write' in sys.argv:
        text = json.dumps(current(), indent=1, sort_keys=True) + '\n'
        FIXTURE.write_text(text, encoding='utf-8', newline='\n')
    else:
        unittest.main()
