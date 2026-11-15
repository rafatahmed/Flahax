"""An explicit operating reserve survives rounding and preparation uncertainty."""

import unittest

from flahax import plan_ratio_recipe
from tests.test_ratio_search import OPTIONS


class NutrientReserveTests(unittest.TestCase):
    def test_recipe_preserves_declared_and_effective_ceilings(self):
        ceilings = {"N_NO3": 6, "K": 16, "Na": 10}
        result = plan_ratio_recipe(
            **OPTIONS,
            counted_mmol_l=1.2,
            maximum_concentrations=ceilings,
            nutrient_ceiling_reserve=0.05,
        )
        reserve = result["nutrient_ceiling_reserve"]
        self.assertEqual(reserve["declared_maximum_concentrations"], ceilings)
        for key, value in {"N_NO3": 5.7, "K": 15.2, "Na": 9.5}.items():
            self.assertAlmostEqual(reserve["effective_maximum_concentrations"][key], value)
        self.assertEqual(
            result["maximum_concentrations"], reserve["effective_maximum_concentrations"]
        )
        self.assertEqual(ceilings, {"N_NO3": 6, "K": 16, "Na": 10})
        self.assertEqual(result["rounded_verification"]["status"], "passed")

    def test_cli_search_applies_reserve_after_volume_uncertainty(self):
        from flahax.planning_cli import execute
        from tests.test_ratio_uncertainty import UNCERTAINTY

        request = dict(
            OPTIONS,
            strength_range=[1.2, 1.4],
            scan_points=3,
            strength_tolerance=0.001,
            maximum_concentrations={"N_NO3": 6},
            nutrient_ceiling_reserve=0.05,
            uncertainty=dict(UNCERTAINTY, weighing_error_g=0, purity_fraction=[1, 1]),
        )
        result = execute("ratio", request)
        self.assertEqual(result["status"], "found")
        self.assertLess(result["requested_strength_mmol_l"], 1.3)
        check = result["recipe"]["uncertainty_verification"]
        self.assertEqual(check["status"], "passed")
        self.assertLessEqual(
            result["recipe"]["rounded_verification"]["elemental_mg_l"]["N_NO3"] * 10 / 9.95,
            5.7,
        )
        failing = dict(
            request, counted_mmol_l=result["transition_brackets"][0]["failing_strength"]
        )
        for key in ("strength_range", "scan_points", "strength_tolerance"):
            failing.pop(key)
        next_recipe = execute("ratio", failing)
        self.assertTrue(next_recipe["rounded_verification"]["limit_assessment"]["passed"])
        self.assertIn("nutrient_limits", next_recipe["uncertainty_verification"]["failed_checks"])

    def test_invalid_or_unscoped_reserve_is_rejected(self):
        from flahax.delivery_contracts import DeliveryError

        for reserve, limits in (
            (-0.1, {"K": 16}),
            (1, {"K": 16}),
            (True, {"K": 16}),
            (float("nan"), {"K": 16}),
            (float("inf"), {"K": 16}),
            (0.05, {}),
        ):
            with self.subTest(reserve=reserve), self.assertRaises(DeliveryError):
                plan_ratio_recipe(
                    **OPTIONS,
                    counted_mmol_l=1.2,
                    maximum_concentrations=limits,
                    nutrient_ceiling_reserve=reserve,
                )

    def test_product_uncertainty_cannot_consume_the_reserve(self):
        from tests.test_ratio_analysis_uncertainty import request, bounds

        req = request()
        req['maximum_concentrations'] = {'N_NO3': 6.15}
        req['uncertainty'] = bounds(req)
        req['uncertainty']['volume_error_litres'] = 0.05
        without = plan_ratio_recipe(**req)
        self.assertEqual(without['uncertainty_verification']['status'], 'passed')
        with_reserve = plan_ratio_recipe(**req, nutrient_ceiling_reserve=0.05)
        self.assertTrue(with_reserve['rounded_verification']['limit_assessment']['passed'])
        self.assertIn('nutrient_limits', with_reserve['uncertainty_verification']['failed_checks'])
