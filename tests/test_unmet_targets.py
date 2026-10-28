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
        result = recommend(SALTS, {"N_NO3": 60, "Ca": 160}, {})
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
        reasons = {
            "no_source",
            "limited_by_ceiling",
            "fit_degradation",
            "conflicting_targets",
            "water_exceeds_target",
            "target_above_maximum",
            "prohibited_by_zero_requirement",
        }
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
                        self.assertIn(item["status"], {"proven_infeasible", "search_incomplete"})

    def test_structural_proofs_and_search_observations_are_distinct(self):
        product = dict(id='a', name='a', elements={'K': 10, 'Ca': 10})
        cases = [
            ({'Si': 1}, {}, {}, 'no_source'),
            ({'K': 1}, {'K': 2}, {}, 'water_exceeds_target'),
            ({'K': 0}, {'K': 2}, {}, 'water_exceeds_target'),
            ({'K': 100, 'Ca': 0}, {}, {}, 'prohibited_by_zero_requirement'),
            ({'K': 100}, {}, {'K': 50}, 'target_above_maximum'),
        ]
        for targets, water, maxima, reason in cases:
            result = recommend([product], targets, water, maximum_concentrations=maxima)
            self.assertFalse(result['feasible'])
            item = result['unmetTargets'][0]
            self.assertEqual(item['reason'], reason)
            self.assertEqual(item['status'], 'proven_infeasible')
            self.assertTrue(item['proofScope'])
        conflict = recommend([product], {'K': 100, 'Ca': 50})
        for item in conflict['unmetTargets']:
            self.assertEqual(item['status'], 'search_incomplete')
            self.assertIsNone(item['proofScope'])
            self.assertIn('relaxed', item['searchScope'])

    def test_zero_requirement_miss_is_not_hidden_by_null_relative_error(self):
        result = recommend([dict(id='k', name='k', elements={'K': 10})], {'K': 0}, {'K': 1})
        self.assertEqual(result['unmetTargets'][0]['symbol'], 'K')
        self.assertIsNone(result['unmetTargets'][0]['deltaPct'])

    def test_relaxed_search_cannot_certify_a_fully_permitted_inventory(self):
        result = recommend(
            [dict(id='a', name='a', elements={'K': 10, 'Ca': 10})],
            {'K': 100, 'Ca': 50},
            allow_ions={'Cl'},
        )
        for item in result['unmetTargets']:
            self.assertEqual(item['status'], 'search_incomplete')
            self.assertEqual(item['reason'], 'conflicting_targets')
            self.assertNotIn('reachableWithChloride', item)


if __name__ == "__main__":
    unittest.main()
