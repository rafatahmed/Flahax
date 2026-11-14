"""Strength searches return only verified rounded recipes."""

import unittest
from unittest.mock import patch

from flahax import search_ratio_recipe
from flahax.delivery_contracts import DeliveryError

OPTIONS = dict(
    cation_shares=[50, 30, 20],
    anion_shares=[5, 3, 1],
    ph=6.3,
    volume_litres=10,
    water="demineralized",
    water_mass_kg=10,
    ph_range=[6.28, 6.32],
    mass_decimals=5,
    selected_phases=["Brushite", "Monetite", "Hydroxyapatite"],
)


class RatioSearchTests(unittest.TestCase):
    def test_strongest_steiner_candidate(self):
        result = search_ratio_recipe(strength_range=[1, 3], **OPTIONS)
        self.assertEqual(result["status"], "found")
        self.assertGreater(result["requested_strength_mmol_l"], 1.8)
        self.assertLess(result["requested_strength_mmol_l"], 1.95)
        check = result["recipe"]["rounded_verification"]
        self.assertEqual(check["status"], "passed")
        for row in check["phase_maxima"].values():
            self.assertLess(row["si"], check["si_required_below"])
        self.assertEqual(result["limiting_phase"], "Hydroxylapatite")
        self.assertEqual(result["controlling_ph"], 6.32)
        from flahax import plan_ratio_recipe

        bracket = result["transition_brackets"][-1]
        self.assertLessEqual(bracket["width"], result["strength_tolerance"])
        next_recipe = plan_ratio_recipe(counted_mmol_l=bracket["failing_strength"], **OPTIONS)
        self.assertEqual(next_recipe["rounded_verification"]["status"], "failed")

    def test_cap_and_no_feasible_recipe(self):
        cap = search_ratio_recipe(strength_range=[1, 1.5], scan_points=3, **OPTIONS)
        self.assertTrue(cap["search_cap_reached"])
        self.assertEqual(cap["requested_strength_mmol_l"], 1.5)
        none = search_ratio_recipe(strength_range=[3, 4], scan_points=3, **OPTIONS)
        self.assertEqual(none["status"], "no_feasible_candidate_found")
        self.assertIsNone(none["recipe"])

    def test_invalid_search_parameters(self):
        for changes in (
            {"strength_range": [3, 1]},
            {"strength_range": [0, 3]},
            {"strength_tolerance": 0},
            {"scan_points": True},
            {"scan_points": 2},
            {"ph_range": None},
        ):
            args = dict(OPTIONS, strength_range=[1, 3])
            args.update(changes)
            with self.subTest(changes=changes), self.assertRaises(DeliveryError):
                search_ratio_recipe(**args)

    def test_incomplete_evaluation_cannot_claim_complete_search(self):
        from flahax.ratio_recipe import plan_ratio_recipe

        def evaluate(**options):
            result = plan_ratio_recipe(**options)
            if options["counted_mmol_l"] > 1.4:
                result["rounded_verification"]["status"] = "incomplete"
            return result

        with patch("flahax.ratio_search.plan_ratio_recipe", side_effect=evaluate):
            result = search_ratio_recipe(strength_range=[1, 2], scan_points=3, **OPTIONS)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["recipe"]["rounded_verification"]["status"], "passed")

    def test_cli_adapter_selects_search_and_rejects_two_strength_modes(self):
        from flahax.planning_cli import execute

        payload = dict(OPTIONS, strength_range=[1, 1.5], scan_points=3)
        self.assertTrue(execute("ratio", payload)["search_cap_reached"])
        with self.assertRaises(DeliveryError):
            execute("ratio", dict(payload, counted_mmol_l=1))

    def test_refines_multiple_observed_feasible_regions(self):
        def evaluate(**options):
            strength = options["counted_mmol_l"]
            passed = strength < 1.3 or 2 <= strength < 2.7
            return {
                "rounded_verification": {
                    "status": "passed" if passed else "failed",
                    "phase_maxima": {"Hydroxylapatite": {"si": -0.1, "ph": 6.32}},
                }
            }

        with patch("flahax.ratio_search.plan_ratio_recipe", side_effect=evaluate):
            result = search_ratio_recipe(strength_range=[1, 3], scan_points=5, **OPTIONS)
        self.assertEqual(result["status"], "found")
        self.assertEqual(len(result["transition_brackets"]), 2)
        self.assertAlmostEqual(result["requested_strength_mmol_l"], 2.7, delta=1e-5)
        for bracket in result["transition_brackets"]:
            self.assertLessEqual(bracket["width"], 1e-5)

    def test_activity_model_limit_is_incomplete(self):
        with patch(
            "flahax.ratio_search.plan_ratio_recipe",
            side_effect=DeliveryError("activity_model_out_of_range", "Davies limit"),
        ):
            result = search_ratio_recipe(strength_range=[1, 3], scan_points=3, **OPTIONS)
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["recipe"])
