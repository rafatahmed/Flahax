# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Composition guards: assays match their formulas and total N is refused."""

import math
import unittest

from flahax import InputError, gap_for, load_library, recommend
from flahax.composition import assay_conflict, assay_drift, theoretical_assay
from flahax.engine import _lstsq, nnls
from flahax.requirement_fit import met
from tests.catalogue_history import historical_catalogue

TARGETS = {"N_NO3": 128, "P": 58, "K": 211, "Ca": 104, "Mg": 40, "S": 54}


class CompositionGuards(unittest.TestCase):
    def test_parseable_assays_match_their_formulas(self):
        conflicts = []
        for salt in load_library()["salts"]:
            if theoretical_assay(salt["formula"]) is None:
                continue
            reason = assay_conflict(salt)
            if reason and "placeholder" not in reason:
                conflicts.append(reason)
        self.assertEqual(conflicts, [])

    def test_total_nitrogen_is_rejected(self):
        with self.assertRaises(InputError):
            gap_for(TARGETS, {"N": 5, "Ca": 20})

    def test_negative_and_unknown_ppm_are_rejected(self):
        with self.assertRaises(InputError):
            recommend(load_library()["salts"], {"K": -1})
        with self.assertRaises(InputError):
            recommend(load_library()["salts"], {"K": 10}, {"Foo": 1})
        with self.assertRaises(InputError):
            recommend(load_library()["salts"], {"K": math.nan})

    def test_default_recipe_omits_restricted_and_carbonate_salts(self):
        result = recommend(load_library()["salts"], TARGETS, {"Ca": 20})
        names = {salt["name"] for salt in result["salts"]}
        self.assertNotIn("Sodium Nitrate", names)
        self.assertNotIn("Potassium Chloride", names)
        self.assertNotIn("Ammonium Chloride", names)
        self.assertNotIn("Calcium Carbonate", names)
        self.assertNotIn("Sodium Borate (Decahydrate) (borax)", names)
        self.assertTrue(result["feasible"])
        # Every target met within the numerical tolerance (G25), on the unrounded values.
        for row in result["rows"]:
            if row["target"] is not None:
                self.assertTrue(met(row["target"], row["final"]), row["symbol"])

    def test_an_overshoot_does_not_admit_chloride_or_borax(self):
        formula = next(
            item for item in load_library()["formulas"] if item["name"] == "Pepper (Howard Resh)"
        )
        result = recommend(load_library()["salts"], formula["targets"], {"Ca": 20})
        names = {salt["name"] for salt in result["salts"]}
        self.assertNotIn("Potassium Chloride", names)
        self.assertNotIn("Ammonium Chloride", names)
        self.assertNotIn("Sodium Borate (Decahydrate) (borax)", names)
        self.assertIn("Sodium Molybdate (Dihydrate)", names)
        self.assertFalse(result["feasible"])
        # Residual magnitude changes with the declared objective; exclusion
        # policy and the known sulfur deficit are the contract here.
        self.assertFalse(any("Potassium Chloride" in note for note in result["warnings"]))
        sulfur = next(row for row in result["rows"] if row["symbol"] == "S")
        self.assertLess(sulfur["deltaPct"], -30)

    def test_a_restricted_ion_is_admitted_only_as_the_sole_source(self):
        salts = [
            salt
            for salt in load_library()["salts"]
            if "Mo" not in salt["elements"] or "Na" in salt["elements"]
        ]
        result = recommend(salts, {**TARGETS, "Mo": 0.03}, {"Ca": 20})
        names = {salt["name"] for salt in result["salts"]}
        self.assertIn("Sodium Molybdate (Dihydrate)", names)
        self.assertTrue(any("only source of Mo" in note for note in result["warnings"]))
        self.assertIn("Na", {item["symbol"] for item in result["undesiredIons"]})

    def test_hydrate_formula_drift_is_reported_from_the_stored_assay(self):
        # 2026-10-18 catalogue correction (Mg Nitrate D1 / phosphoric 75 %): the shipped Mg Nitrate
        # is now Mg(NO3)2.6H2O theory and no longer drifts; the retired row keeps the hydrate case.
        retired = {
            "name": "Mg Nitrate",
            "formula": "Mg(NO3)2",
            "elements": {"N_NO3": 11, "Mg": 9.65},
        }
        self.assertTrue(assay_drift(retired).startswith("Mg Nitrate"))
        notes = {salt["name"]: assay_drift(salt) for salt in load_library()["salts"]}
        self.assertIsNone(notes["Mg Nitrate"])
        # The 75 % acid is dosed from its stored solution assay, below the H3PO4 formula value.
        self.assertIn("P assay 23.706% vs formula 31.61%", notes["Phosphoric Acid (75%)"])

    def test_chloride_salts_are_used_only_with_consent(self):
        self.enterContext(historical_catalogue())
        library = load_library()
        chloride = sorted(
            salt["name"] for salt in library["salts"] if float(salt["elements"].get("Cl") or 0) > 0
        )
        self.assertEqual(chloride, ["Calcium Chloride (Dihydrate)", "Potassium Chloride"])
        for formula in library["formulas"]:
            for water in ({}, {"Ca": 20}):
                with self.subTest(formula=formula["name"], water=water):
                    result = recommend(library["salts"], formula["targets"], water)
                    self.assertFalse(set(chloride) & {s["name"] for s in result["salts"]})


class LeastSquares(unittest.TestCase):
    def test_householder_solves_a_known_system(self):
        # Columns [1, 1, 0] and [0, 1, 1], observation [1, 2, 1] -> [1, 1].
        solution = _lstsq([[1.0, 1.0, 0.0], [0.0, 1.0, 1.0]], [1.0, 2.0, 1.0])
        self.assertAlmostEqual(solution[0], 1.0, places=8)
        self.assertAlmostEqual(solution[1], 1.0, places=8)

    @staticmethod
    def objective(matrix, rhs, x):
        return sum((sum(a * w for a, w in zip(row, x)) - b) ** 2 for row, b in zip(matrix, rhs))

    def test_nnls_does_not_stop_early_on_near_dependent_columns(self):
        # Benchmark v1 near_dependent case (#36): the unique optimum is [1, 1] with
        # objective ~0. A fixed 1e-10 stopping threshold stopped at objective 1.5e-12.
        matrix = [[1.0, 1.0], [1.0, 1.000001], [0.0, 0.000001]]
        rhs = [2.0, 2.000001, 0.000001]
        x = nnls(matrix, rhs)
        self.assertLess(self.objective(matrix, rhs, x), 1e-20)
        self.assertAlmostEqual(x[0], 1.0, places=6)
        self.assertAlmostEqual(x[1], 1.0, places=6)

    def test_nnls_raises_instead_of_returning_at_its_iteration_cap(self):
        from flahax import engine

        original = engine.NNLS_ADDITION_FACTOR
        engine.NNLS_ADDITION_FACTOR = 0
        try:
            with self.assertRaisesRegex(InputError, "did not reach optimality"):
                nnls([[1.0, 0.0], [0.0, 1.0]], [1.0, 2.0])
        finally:
            engine.NNLS_ADDITION_FACTOR = original
        self.assertEqual(nnls([[1.0, 0.0], [0.0, 1.0]], [1.0, 2.0]), [1.0, 2.0])

    def test_nnls_result_does_not_depend_on_problem_scale(self):
        matrix = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
        rhs = [2.0, 3.0, 5.0]
        for scale in (1e-8, 1.0, 1e8):
            with self.subTest(scale=scale):
                x = nnls([[a * scale for a in row] for row in matrix], [b * scale for b in rhs])
                self.assertAlmostEqual(x[0], 2.0, places=8)
                self.assertAlmostEqual(x[1], 3.0, places=8)


if __name__ == "__main__":
    unittest.main()
