# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Incidental ammonium is allowed up to a share of the formula's total N (#54)."""

import unittest

from flahax import load_library, recommend
from flahax.engine import AMMONIUM_CAP_MG_PER_L, AMMONIUM_FRACTION

LIBRARY = load_library()
SALTS = LIBRARY["salts"]


def formula(name):
    return next(f for f in LIBRARY["formulas"] if f["name"] == name)


def final(result, symbol):
    return next((row["final"] for row in result["rows"] if row["symbol"] == symbol), 0.0)


def total_n(targets):
    return sum(targets.get(key, 0.0) for key in ("N_NO3", "N_NH4", "N_UREA"))


class AmmoniumLimitTests(unittest.TestCase):
    def test_default_is_ten_percent_of_total_n(self):
        self.assertEqual(AMMONIUM_FRACTION, 0.10)
        targets = formula("Tomato (Howard Resh)")["targets"]  # total N 140 -> 14 mg/L
        result = recommend(SALTS, targets, {})
        self.assertEqual(result["ammoniumLimit"]["fractionOfTotalN"], 0.10)
        self.assertAlmostEqual(result["ammoniumLimit"]["mgPerL"], 0.10 * total_n(targets))
        self.assertIn("Voogt", result["ammoniumLimit"]["basis"])

    def test_absolute_cap_is_one_and_a_half_mmol(self):
        self.assertAlmostEqual(AMMONIUM_CAP_MG_PER_L, 1.5 * 14.0067)
        targets = formula("Chilli (maximumyield)")["targets"]  # total N 320 -> 32 > 21.01
        result = recommend(SALTS, targets, {})
        self.assertAlmostEqual(result["ammoniumLimit"]["mgPerL"], AMMONIUM_CAP_MG_PER_L)
        self.assertLessEqual(final(result, "N_NH4"), AMMONIUM_CAP_MG_PER_L + 1e-12)

    def test_target_exact_recipes_now_pass_within_the_limit(self):
        for name in ("Chilli (maximumyield)", "Tomato (Howard Resh)"):
            with self.subTest(formula=name):
                targets = formula(name)["targets"]
                result = recommend(SALTS, targets, {})
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


if __name__ == "__main__":
    unittest.main()
