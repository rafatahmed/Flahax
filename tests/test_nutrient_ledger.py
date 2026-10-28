# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Optional aggregate elemental N ledger: forms stay independent; no invented splits."""

from fractions import Fraction
import unittest

from flahax import recommend
from flahax.composition import InputError, validate_profile
from flahax.engine import (
    AMMONIUM_CAP_MG_PER_L,
    AMMONIUM_FRACTION,
    CEILING_MARGIN,
    CEILING_TOLERANCE,
    forward,
    gap_for,
    score,
)
from flahax.nutrient_ledger import (
    N_FORMS,
    assess_nitrogen_constraints,
    elemental_nitrogen,
    merge_nutrient_totals,
)


class ValidateAggregateNitrogen(unittest.TestCase):
    def test_accepts_aggregate_n_in_targets(self):
        clean = validate_profile({"N": 140, "K": 280}, "targets")
        self.assertEqual(clean["N"], 140.0)
        self.assertEqual(clean["K"], 280.0)

    def test_accepts_aggregate_n_in_maxima(self):
        clean = validate_profile({"N": 200, "Cl": 70}, "maximum_concentrations")
        self.assertEqual(clean["N"], 200.0)

    def test_rejects_inconsistent_form_sum_versus_aggregate(self):
        with self.assertRaises(InputError) as caught:
            validate_profile({"N": 140, "N_NO3": 100, "N_NH4": 10}, "targets")
        self.assertIn("inconsistent", str(caught.exception).lower())

    def test_accepts_consistent_forms_with_aggregate(self):
        clean = validate_profile({"N": 140, "N_NO3": 100, "N_NH4": 40}, "targets")
        self.assertEqual(clean["N"], 140.0)
        self.assertEqual(clean["N_NO3"], 100.0)
        self.assertEqual(clean["N_NH4"], 40.0)

    def test_forms_only_profile_unchanged(self):
        clean = validate_profile({"N_NO3": 140, "Ca": 200}, "targets")
        self.assertNotIn("N", clean)
        self.assertEqual(clean["N_NO3"], 140.0)

    def test_bare_water_ion_n_is_rejected(self):
        with self.assertRaises(InputError) as caught:
            validate_profile({"N": 5, "Ca": 20}, "water")
        message = str(caught.exception).lower()
        self.assertTrue("n_no3" in message or "water" in message or "unsupported" in message)

    def test_water_analysis_ions_reject_bare_n(self):
        with self.assertRaises(InputError):
            validate_profile({"N": 5}, "waterAnalysis.ions")


class ElementalNitrogenAccounting(unittest.TestCase):
    def test_elemental_nitrogen_sums_forms(self):
        totals = {"N_NO3": 100.0, "N_NH4": 11.0, "N_UREA": 5.0, "K": 200.0}
        self.assertAlmostEqual(elemental_nitrogen(totals), 116.0)
        self.assertEqual(N_FORMS, ("N_NO3", "N_NH4", "N_UREA"))

    def test_elemental_nitrogen_ignores_aggregate_key(self):
        # Reading N from totals would double-count when forms are also present.
        totals = {"N": 999.0, "N_NO3": 100.0, "N_NH4": 10.0}
        self.assertAlmostEqual(elemental_nitrogen(totals), 110.0)

    def test_water_salt_reagent_counts_acid_n_once(self):
        water = {"N_NO3": 10.0, "Ca": 40.0}
        from_salts = {"N_NO3": 100.0, "N_NH4": 11.0, "Ca": 150.0}
        from_reagent = {"N_NO3": 5.0}  # nitric acid contribution, once
        totals = merge_nutrient_totals(water, from_salts, from_reagent)
        self.assertAlmostEqual(totals["N_NO3"], 115.0)
        self.assertAlmostEqual(totals["N_NH4"], 11.0)
        self.assertAlmostEqual(elemental_nitrogen(totals), 126.0)
        # No aggregate N key invented in the merged form map.
        self.assertNotIn("N", totals)


class AssessNitrogenConstraints(unittest.TestCase):
    def test_aggregate_target_met_by_form_sum(self):
        totals = {"N_NO3": 130.0, "N_NH4": 10.0}
        assessment = assess_nitrogen_constraints(totals, targets={"N": 140})
        self.assertAlmostEqual(assessment["elementalNitrogen"], 140.0)
        self.assertEqual(assessment["violations"], [])
        self.assertTrue(assessment["withinTolerance"])

    def test_aggregate_target_miss_is_a_violation(self):
        totals = {"N_NO3": 100.0, "N_NH4": 10.0}
        assessment = assess_nitrogen_constraints(totals, targets={"N": 140})
        self.assertFalse(assessment["withinTolerance"])
        symbols = {row["symbol"] for row in assessment["violations"]}
        self.assertIn("N", symbols)

    def test_form_targets_remain_independent(self):
        totals = {"N_NO3": 140.0, "N_NH4": 0.0}
        assessment = assess_nitrogen_constraints(
            totals, targets={"N_NO3": 140, "N_NH4": 0}, maxima={"N_NH4": 0}
        )
        self.assertTrue(assessment["withinTolerance"])
        self.assertEqual(assessment["forms"]["N_NO3"], 140.0)


class EngineNitrogenAccounting(unittest.TestCase):
    def test_score_uses_elemental_nitrogen_for_aggregate_target(self):
        achieved = {"N_NO3": 100.0, "N_NH4": 40.0, "K": 280.0}
        loss, rows = score(achieved, {"N": 140, "K": 280})
        n_row = next(row for row in rows if row["symbol"] == "N")
        self.assertAlmostEqual(n_row["final"], 140.0)
        self.assertAlmostEqual(n_row["deltaPct"], 0.0)
        self.assertAlmostEqual(loss, 0.0)

    def test_gap_for_subtracts_water_forms_from_aggregate_n(self):
        gap = gap_for({"N": 140, "K": 200}, {"N_NO3": 10, "N_NH4": 5, "K": 20})
        self.assertAlmostEqual(gap["N"], 125.0)
        self.assertAlmostEqual(gap["K"], 180.0)

    def test_forward_forms_feed_elemental_nitrogen(self):
        salts = [{"name": "demo", "elements": {"N_NO3": 10.0, "N_NH4": 1.0, "Ca": 19.0}}]
        achieved = forward(salts, [1.0], {"N_NO3": 5.0})
        self.assertAlmostEqual(achieved["N_NO3"], 5.0 + 100.0)
        self.assertAlmostEqual(achieved["N_NH4"], 10.0)
        self.assertAlmostEqual(elemental_nitrogen(achieved), 115.0)


class AggregateNitrogenCeiling(unittest.TestCase):
    def test_aggregate_n_maximum_binds_without_n_target(self):
        # Forms-only K target: 10 g/L KNO3 meets K and delivers ~138.5 mg/L N.
        # maxima N=50 must constrain the NNLS ceiling search, not only post-hoc flag.
        salts = [
            {
                "id": "kno3-ledger",
                "name": "Potassium Nitrate",
                "formula": "KNO3",
                "elements": {"K": 38.67, "N_NO3": 13.856},
            }
        ]
        limit = 50.0
        result = recommend(salts, {"K": 386.7}, {}, maximum_concentrations={"N": limit})
        finals = {row["symbol"]: row["final"] for row in result["rows"]}
        total_n = elemental_nitrogen(finals)
        self.assertLessEqual(total_n, limit + 1e-9)
        self.assertAlmostEqual(
            total_n,
            limit * (1 - CEILING_MARGIN),
            delta=2 * CEILING_TOLERANCE * limit + 1e-6,
        )


class FeasibilityContractTests(unittest.TestCase):
    """F01/F02/F04-class recommend contract + Dutch NH4 disclosure (#160 / spine Task 3)."""

    def test_f01_explicit_zero_nh4_rejects_calcium_nitrate_inventory(self):
        ca_nitrate = {
            "id": "ca-nit-ag",
            "name": "Calcium Nitrate (ag grade)",
            "elements": {"N_NO3": 14.4, "N_NH4": 1.1, "Ca": 19.0},
        }
        result = recommend(
            [ca_nitrate],
            {"N_NO3": 144.0, "Ca": 190.0, "N_NH4": 0.0},
            {},
            ridge=0,
        )
        nh4 = next(row["final"] for row in result["rows"] if row["symbol"] == "N_NH4")
        self.assertEqual(nh4, 0.0)
        self.assertEqual(result["salts"], [])
        self.assertFalse(result["feasible"])
        self.assertIsNone(result["ammoniumLimit"])
        reasons = {miss["reason"] for miss in result["unmetTargets"]}
        self.assertIn("prohibited_by_zero_requirement", reasons)

    def test_f02_targeted_max_below_stoichiometric_binds_in_search(self):
        # Meeting K=100 from K2SO4-like assay would deliver S≈41; max S=20 must bind.
        salt = {"id": "ks", "name": "ks", "elements": {"K": 44.87, "S": 18.4}}
        result = recommend(
            [salt],
            {"K": 100.0},
            {},
            maximum_concentrations={"S": 20.0},
            ridge=0,
        )
        finals = {row["symbol"]: row["final"] for row in result["rows"]}
        self.assertLessEqual(finals["S"], 20.0 + 1e-9)
        self.assertLess(finals["K"], 99.0)
        self.assertEqual(result["limitViolations"], [])
        self.assertFalse(result["feasible"])

    def test_f04_tiny_mo_dose_matches_emitted_salts(self):
        product = {"id": "mo", "name": "mo", "elements": {"Mo": 10.0}}
        target = 1e-5
        result = recommend([product], {"Mo": target}, {}, ridge=0)
        self.assertEqual(len(result["salts"]), 1)
        emitted = Fraction(str(result["salts"][0]["gramsPerLitre"])) * 100
        mo_final = next(row["final"] for row in result["rows"] if row["symbol"] == "Mo")
        self.assertGreater(emitted, 0)
        self.assertAlmostEqual(mo_final, float(emitted), places=14)
        self.assertAlmostEqual(mo_final / target, 1.0, places=12)
        self.assertTrue(result["feasible"])

    def test_dutch_cap_disclosed_when_nh4_omitted(self):
        self.assertEqual(AMMONIUM_FRACTION, 0.10)
        self.assertAlmostEqual(AMMONIUM_CAP_MG_PER_L, 1.5 * 14.0067)
        # total N 140 → 10% = 14 < 21.01 absolute cap
        result = recommend(
            [
                {
                    "id": "ca-nit-ag",
                    "name": "Calcium Nitrate (ag grade)",
                    "elements": {"N_NO3": 14.4, "N_NH4": 1.1, "Ca": 19.0},
                },
                {"id": "kno3", "name": "Potassium Nitrate", "elements": {"K": 38.67, "N_NO3": 13.856}},
            ],
            {"N_NO3": 140.0, "Ca": 190.0, "K": 280.0},
            {},
        )
        limit = result["ammoniumLimit"]
        self.assertIsNotNone(limit)
        self.assertEqual(limit["fractionOfTotalN"], 0.10)
        self.assertAlmostEqual(limit["absoluteCapMgPerL"], AMMONIUM_CAP_MG_PER_L)
        self.assertAlmostEqual(limit["mgPerL"], 14.0)
        self.assertIn("achievedMgPerL", limit)
        nh4 = next(row["final"] for row in result["rows"] if row["symbol"] == "N_NH4")
        self.assertAlmostEqual(limit["achievedMgPerL"], nh4)
        self.assertLessEqual(nh4, limit["mgPerL"] + 1e-12)
        self.assertIn("Dutch", limit["basis"])


if __name__ == "__main__":
    unittest.main()

