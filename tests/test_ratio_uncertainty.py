"""Preparation uncertainty must participate in recipe and search acceptance."""

import unittest
from unittest.mock import patch

from flahax import plan_ratio_recipe, search_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from tests.test_ratio_search import OPTIONS

UNCERTAINTY = dict(
    weighing_error_g=0.001,
    purity_fraction=[0.99, 1.0],
    volume_error_litres=0.05,
    ratio_relative_tolerance=0.01,
    concentration_relative_tolerance=0.02,
    impurity_model="inert",
)


class RatioUncertaintyTests(unittest.TestCase):
    def recipe(self, uncertainty, **overrides):
        return plan_ratio_recipe(
            **dict(OPTIONS, counted_mmol_l=1.7, uncertainty=uncertainty, **overrides)
        )

    def test_zero_uncertainty_reproduces_rounded_recipe(self):
        result = self.recipe(
            dict(UNCERTAINTY, weighing_error_g=0, purity_fraction=[1, 1], volume_error_litres=0)
        )
        check = result["uncertainty_verification"]
        self.assertEqual(check["status"], "passed")
        self.assertEqual(check["scenario_count"], 1)
        for phase, row in check["phase_maxima"].items():
            self.assertAlmostEqual(
                row["si"], result["rounded_verification"]["phase_maxima"][phase]["si"]
            )

    def test_volume_bounds_change_concentration_but_not_ratios(self):
        result = self.recipe(dict(UNCERTAINTY, weighing_error_g=0, purity_fraction=[1, 1]))
        check = result["uncertainty_verification"]
        rounded = result["rounded_verification"]
        self.assertEqual(check["scenario_count"], 2)
        self.assertAlmostEqual(
            check["counted_mmol_l_range"][0], rounded["counted_mmol_l"] * 10 / 10.05
        )
        self.assertAlmostEqual(
            check["counted_mmol_l_range"][1], rounded["counted_mmol_l"] * 10 / 9.95
        )
        for low, high in check["ratio_percent_ranges"]:
            self.assertEqual(low, high)

    def test_invalid_bounds_and_reactive_impurities_rejected(self):
        for change in (
            {"weighing_error_g": -1},
            {"purity_fraction": [0.9, 1.1]},
            {"purity_fraction": [True, 1]},
            {"volume_error_litres": 10},
            {"ratio_relative_tolerance": float("nan")},
            {"impurity_model": "carbonate"},
        ):
            with self.subTest(change=change), self.assertRaises(DeliveryError):
                self.recipe(dict(UNCERTAINTY, **change))

    def test_failed_or_incomplete_uncertainty_cannot_pass_search(self):
        for status in ("failed", "incomplete"):
            with patch(
                "flahax.ratio_search.plan_ratio_recipe",
                return_value={
                    "rounded_verification": {"status": "passed"},
                    "uncertainty_verification": {
                        "status": status,
                        "failed_checks": ["equilibrium_ph"],
                    },
                },
            ):
                result = search_ratio_recipe(
                    **dict(OPTIONS, strength_range=[1, 3], scan_points=3, uncertainty=UNCERTAINTY)
                )
            self.assertIsNone(result["recipe"])
            self.assertEqual(
                result["status"],
                "incomplete" if status == "incomplete" else "no_feasible_candidate_found",
            )

    def test_missing_phase_cannot_pass(self):
        with patch(
            "flahax.ratio_uncertainty.solve",
            side_effect=DeliveryError("phase_unavailable", "missing"),
        ):
            result = self.recipe(UNCERTAINTY)
        self.assertEqual(result["uncertainty_verification"]["status"], "incomplete")

    def test_purity_and_weighing_bounds_include_koh_potassium(self):
        # Use endpoints for this fast corner accounting test; the real example
        # verifies every interior grid point too.
        from flahax.ratio_uncertainty import verify_uncertainty

        result = plan_ratio_recipe(**dict(OPTIONS, counted_mmol_l=1.7))
        result["rounded_verification"]["evaluated_ph"] = [6.28, 6.32]
        check = verify_uncertainty(result, UNCERTAINTY)
        self.assertEqual(check["scenario_count"], 128)
        self.assertFalse(check["all_scenario_ph_in_range"])
        self.assertIn("equilibrium_ph", check["failed_checks"])
        self.assertGreater(check["worst_ratio_relative_error"], 0.01)
        self.assertEqual(len(check["ratio_percent_ranges"]), 6)

    def test_search_uses_uncertainty_verification_on_delivery(self):
        result = search_ratio_recipe(
            **dict(
                OPTIONS,
                strength_range=[1, 1.5],
                scan_points=3,
                uncertainty=dict(
                    UNCERTAINTY, weighing_error_g=0, purity_fraction=[1, 1], volume_error_litres=0
                ),
            )
        )
        self.assertEqual(result["status"], "found")
        self.assertEqual(result["recipe"]["uncertainty_verification"]["status"], "passed")
