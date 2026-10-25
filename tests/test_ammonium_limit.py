# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""An ammonium allowance is an explicit caller policy, never an invented default."""

import unittest

from flahax import load_library, recommend

LIBRARY = load_library()
SALTS = LIBRARY["salts"]


def formula(name):
    return next(f for f in LIBRARY["formulas"] if f["name"] == name)


def final(result, symbol):
    return next((row["final"] for row in result["rows"] if row["symbol"] == symbol), 0.0)


def total_n(targets):
    return sum(targets.get(key, 0.0) for key in ("N_NO3", "N_NH4", "N_UREA"))


class AmmoniumLimitTests(unittest.TestCase):
    def test_fraction_is_explicit_and_default_adds_no_limit(self):
        targets = formula("Tomato (Howard Resh)")["targets"]  # total N 140 -> 14 mg/L
        self.assertIsNone(recommend(SALTS, targets, {})['ammoniumLimit'])
        result = recommend(SALTS, targets, {}, max_ammonium_fraction=0.10)
        self.assertEqual(result["ammoniumLimit"]["fractionOfTotalN"], 0.10)
        self.assertAlmostEqual(result["ammoniumLimit"]["mgPerL"], 0.10 * total_n(targets))
        self.assertIn("explicit caller", result["ammoniumLimit"]["basis"])

    def test_fraction_has_no_undeclared_absolute_cap(self):
        targets = formula("Chilli (maximumyield)")["targets"]  # total N 320 -> 32 > 21.01
        result = recommend(SALTS, targets, {}, max_ammonium_fraction=0.10)
        self.assertEqual(result["ammoniumLimit"]["mgPerL"], 32)
        self.assertIsNone(result["ammoniumLimit"]["absoluteCapMgPerL"])
        self.assertLessEqual(final(result, "N_NH4"), 32)

    def test_target_exact_recipes_now_pass_within_the_limit(self):
        for name in ("Chilli (maximumyield)", "Tomato (Howard Resh)"):
            with self.subTest(formula=name):
                targets = formula(name)["targets"]
                result = recommend(SALTS, targets, {}, max_ammonium_fraction=0.10)
                self.assertTrue(result["feasible"], result["rows"])
                self.assertLessEqual(final(result, "N_NH4"), 0.10 * total_n(targets) + 1e-12)
                self.assertEqual(result["limitViolations"], [])

    def test_formula_with_an_ammonium_target_is_unaffected(self):
        targets = formula("Pepper (Howard Resh)")["targets"]
        self.assertGreater(targets["N_NH4"], 0)
        default = recommend(SALTS, targets, {})
        without = recommend(SALTS, targets, {}, max_ammonium_fraction=None)
        self.assertIsNone(default["ammoniumLimit"])
        self.assertEqual(default["salts"], without["salts"])

    def test_explicit_zero_ammonium_target_keeps_its_penalty(self):
        targets = dict(formula("Chilli (maximumyield)")["targets"], N_NH4=0)
        result = recommend(SALTS, targets, {})
        self.assertIsNone(result["ammoniumLimit"])
        self.assertEqual(
            result["salts"], recommend(SALTS, targets, {}, max_ammonium_fraction=None)["salts"]
        )

    def test_explicit_maximum_overrides_the_fraction(self):
        targets = formula("Chilli (maximumyield)")["targets"]
        result = recommend(SALTS, targets, {}, maximum_concentrations={"N_NH4": 12})
        self.assertIsNone(result["ammoniumLimit"])
        self.assertLessEqual(final(result, "N_NH4"), 12 + 1e-12)

    def test_none_restores_the_penalty_only_fit(self):
        targets = formula("Chilli (maximumyield)")["targets"]
        result = recommend(SALTS, targets, {}, max_ammonium_fraction=None)
        self.assertIsNone(result["ammoniumLimit"])
        self.assertFalse(result["feasible"])  # the documented #54 miss without a limit

    def test_invalid_fraction_is_rejected(self):
        targets = formula("Chilli (maximumyield)")["targets"]
        for bad in (-0.1, 1.5, float("nan")):
            with self.subTest(bad=bad), self.assertRaises(Exception):
                recommend(SALTS, targets, {}, max_ammonium_fraction=bad)

    def test_zero_fraction_is_recorded_without_becoming_an_unspecified_limit(self):
        result = recommend(SALTS, {'K': 100, 'N_NO3': 100}, max_ammonium_fraction=0)
        self.assertEqual(result['ammoniumLimit']['mgPerL'], 0)


if __name__ == "__main__":
    unittest.main()
