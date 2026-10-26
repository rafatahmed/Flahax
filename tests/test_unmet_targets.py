# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Every missed target is explained (#39): no source, a binding limit, or named conflicts."""

import unittest

from flahax import load_library, recommend

LIBRARY = load_library()
SALTS = LIBRARY["salts"]


def formula(name):
    return next(f for f in LIBRARY["formulas"] if f["name"] == name)


def unmet(result):
    return {item["symbol"]: item for item in result["unmetTargets"]}


class UnmetTargetTests(unittest.TestCase):
    def test_feasible_recipe_has_no_unmet_targets(self):
        result = recommend(SALTS, formula("Hoagland solution")["targets"], {})
        self.assertTrue(result["feasible"])
        self.assertEqual(result["unmetTargets"], [])

    def test_element_without_any_source_is_reported(self):
        result = recommend(SALTS, formula("Rice (Douglas Peckenpaugh)")["targets"], {})
        si = unmet(result)["Si"]
        self.assertEqual(si["reason"], "no_source")
        self.assertAlmostEqual(si["deltaPct"], -100.0)

    def test_calcium_nitrate_conflict_names_partner_and_chloride_route(self):
        result = recommend(
            SALTS, formula("Tomatoes - till First Cluster (U of Florida)")["targets"], {}
        )
        ca = unmet(result)["Ca"]
        self.assertEqual(ca["reason"], "conflicting_targets")
        self.assertIn("N_NO3", ca["conflictsWith"])
        self.assertTrue(ca["reachableWithChloride"])

    def test_binding_ceiling_is_named(self):
        result = recommend(
            SALTS,
            formula("Generic Grow (maximumyield)")["targets"],
            {},
            max_ammonium_fraction=0.10,
        )
        items = result["unmetTargets"]
        self.assertTrue(items)
        for item in items:
            self.assertEqual(item["reason"], "limited_by_ceiling", item)
            self.assertIn("N_NH4", item["bindingLimits"])

    def test_every_benchmark_miss_is_explained(self):
        reasons = {"no_source", "limited_by_ceiling", "fit_degradation", "conflicting_targets"}
        for f in LIBRARY["formulas"]:
            for water in ({}, {"Ca": 20}):
                with self.subTest(formula=f["name"], water=water):
                    result = recommend(SALTS, f["targets"], water)
                    missed = {
                        row["symbol"]
                        for row in result["rows"]
                        if row["deltaPct"] is not None and abs(row["deltaPct"]) > 1.0
                    }
                    self.assertEqual(missed, set(unmet(result)))
                    for item in result["unmetTargets"]:
                        self.assertIn(item["reason"], reasons)


if __name__ == "__main__":
    unittest.main()
