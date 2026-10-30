# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The ammonium allowance (G23): incidental NH4-N up to min(10% of total N, 1.5 mmol/L)."""

import unittest

from flahax import load_library, recommend
from tests.catalogue_history import historical_catalogue

# Formulas and products of the pre-owner catalogue: Chilli (maximumyield) is not in the owner
# catalogue.
with historical_catalogue():
    LIBRARY = load_library()
SALTS = LIBRARY["salts"]
PACKAGED = load_library()  # the packaged catalogue (Flaha Agri Tech Analysis Ver 0.0)
BASIS = "Dutch soilless practice (De Kreij, Voogt et al.)"
CAP = 1.5 * 14.0067  # 1.5 mmol/L NH4 as N, 21.01 mg/L


def formula(name, library=LIBRARY):
    return next(f for f in library["formulas"] if f["name"] == name)


def final(result, symbol):
    return next((row["final"] for row in result["rows"] if row["symbol"] == symbol), 0.0)


def total_n(targets):
    return sum(targets.get(key, 0.0) for key in ("N_NO3", "N_NH4", "N_UREA"))


class AmmoniumLimitTests(unittest.TestCase):
    def test_default_is_the_ammonium_allowance_with_its_basis(self):
        # Packaged Tomato (Howard Resh): N_NO3 140, N_NH4 0 -> min(14, 21.01) = 14 mg/L (G23, G24).
        targets = formula("Tomato (Howard Resh)", PACKAGED)["targets"]
        self.assertEqual((targets["N_NO3"], targets["N_NH4"]), (140, 0))
        result = recommend(PACKAGED["salts"], targets, {})
        self.assertEqual(result["ammoniumLimit"]["fractionOfTotalN"], 0.10)
        self.assertEqual(result["ammoniumLimit"]["mgPerL"], 14.0)
        self.assertEqual(result["ammoniumLimit"]["absoluteCapMgPerL"], CAP)
        self.assertEqual(result["ammoniumLimit"]["basis"], BASIS)
        explicit = recommend(PACKAGED["salts"], targets, {}, max_ammonium_fraction=0.10)
        self.assertEqual(explicit["ammoniumLimit"], result["ammoniumLimit"])
        self.assertEqual(explicit["salts"], result["salts"])

    def test_fraction_is_capped_at_one_and_a_half_millimolar(self):
        targets = formula("Chilli (maximumyield)")["targets"]  # total N 320 -> 32 > 21.01
        result = recommend(SALTS, targets, {}, max_ammonium_fraction=0.10)
        self.assertEqual(result["ammoniumLimit"]["mgPerL"], CAP)
        self.assertEqual(result["ammoniumLimit"]["absoluteCapMgPerL"], CAP)
        self.assertLessEqual(final(result, "N_NH4"), CAP)

    # Runs on the frozen pre-2026-10-29 catalogue: the packaged one has no Chilli
    # (maximumyield), and its Tomato (Howard Resh) cannot be met exactly (N_NO3 +1.86 %).
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

    def test_explicit_zero_ammonium_target_is_no_requirement(self):
        # G24: N_NH4 = 0 sets no row and no ban; the allowance applies as when it is absent.
        absent = formula("Chilli (maximumyield)")["targets"]
        self.assertNotIn("N_NH4", absent)
        targets = dict(absent, N_NH4=0)
        result = recommend(SALTS, targets, {})
        self.assertEqual(result["ammoniumLimit"]["mgPerL"], CAP)
        self.assertGreater(final(result, "N_NH4"), 0)
        self.assertLessEqual(final(result, "N_NH4"), CAP)
        self.assertEqual(
            [row["target"] for row in result["rows"] if row["symbol"] == "N_NH4"], [None]
        )
        self.assertEqual(result["salts"], recommend(SALTS, absent, {})["salts"])

    def test_explicit_maximum_overrides_the_fraction(self):
        targets = formula("Chilli (maximumyield)")["targets"]
        result = recommend(SALTS, targets, {}, maximum_concentrations={"N_NH4": 12})
        self.assertIsNone(result["ammoniumLimit"])
        self.assertLessEqual(final(result, "N_NH4"), 12 + 1e-12)

    def test_none_keeps_accuracy_first_fit_without_an_implicit_limit(self):
        targets = formula("Chilli (maximumyield)")["targets"]
        result = recommend(SALTS, targets, {}, max_ammonium_fraction=None)
        self.assertIsNone(result["ammoniumLimit"])
        self.assertTrue(result["feasible"])
        self.assertEqual(result["limitViolations"], [])

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
