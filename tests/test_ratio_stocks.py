"""Stock delivery preserves units, potassium accounting and uncertainty gates."""

import copy
import unittest

from flahax import plan_ratio_recipe
from flahax.composition import ATOMIC, parse_formula
from flahax.delivery_contracts import DeliveryError
from flahax.ratio_stocks import prepare_stock_delivery
from tests.test_ratio_search import OPTIONS

STOCKS = dict(
    concentrations_g_l={
        "KH2PO4": 10,
        "Ca(NO3)2.4H2O": 10,
        "MgSO4.7H2O": 10,
        "Mg(NO3)2.6H2O": 10,
        "KNO3": 10,
        "KOH": 1,
    },
    concentration_relative_error=0.001,
    dose_error_ml=0.02,
    dose_decimals=2,
)
UNCERTAINTY = dict(
    volume_error_litres=0.05,
    ratio_relative_tolerance=0.01,
    concentration_relative_tolerance=0.02,
    impurity_model="inert",
)


class RatioStockTests(unittest.TestCase):
    def recipe(self, **changes):
        # Tight zero-width error bounds provide a fast nominal delivery test.
        stocks = dict(STOCKS, concentration_relative_error=0, dose_error_ml=0)
        args = dict(
            OPTIONS,
            counted_mmol_l=1.7,
            stock_dosing=stocks,
            uncertainty=dict(UNCERTAINTY, volume_error_litres=0),
        )
        args.update(changes)
        return plan_ratio_recipe(**args)

    def test_doses_are_reconstructed_without_second_mass_rounding(self):
        result = self.recipe()
        check = result["rounded_verification"]
        self.assertEqual(check["status"], "passed")
        self.assertEqual(check["delivery_basis"], "rounded_stock_doses")
        potassium = 0
        for stock, ingredient in zip(result["stock_delivery"]["stocks"], check["ingredients"]):
            self.assertAlmostEqual(
                ingredient["grams"], stock["dose_ml"] * stock["concentration_g_l"] / 1000
            )
            atoms = parse_formula(stock["formula"])["atoms"]
            mw = sum(ATOMIC[e] * n for e, n in atoms.items())
            potassium += ingredient["grams"] / mw * atoms.get("K", 0) * 1000 / 10
        self.assertAlmostEqual(check["analytical_mmol_l"]["K"], potassium)
        self.assertEqual(result["uncertainty_verification"]["status"], "passed")
        self.assertFalse(result["verified"])
        self.assertEqual(result["stock_verification"]["evidence_status"], "missing")

    def test_effective_bounds_use_concentration_times_delivered_volume(self):
        recipe = {"ingredients": [{"formula": "KOH", "grams": 0.025}], "volume_litres": 10}
        delivery = prepare_stock_delivery(recipe, STOCKS, 0.05)
        row = delivery["stocks"][0]
        self.assertEqual(row["dose_ml"], 25)
        self.assertAlmostEqual(row["effective_grams_bounds"][0], 24.98 * 0.999 / 1000)
        self.assertAlmostEqual(row["effective_grams_bounds"][1], 25.02 * 1.001 / 1000)

    def test_invalid_stocks_and_ambiguous_raw_assay_are_rejected(self):
        for change in (
            {"dose_error_ml": -1},
            {"dose_decimals": True},
            {"concentration_relative_error": 1},
            {"concentrations_g_l": {}},
            {"dose_error_ml": float("nan")},
        ):
            with self.subTest(change=change), self.assertRaises(DeliveryError):
                self.recipe(stock_dosing=dict(STOCKS, **change))
        with self.assertRaises(DeliveryError):
            self.recipe(uncertainty=None)
        with self.assertRaises(DeliveryError):
            self.recipe(uncertainty=dict(UNCERTAINTY, purity_fraction=[0.99, 1]))

    def test_coarse_delivery_does_not_pass_nominal_rounding(self):
        result = self.recipe(stock_dosing=dict(STOCKS, dose_decimals=0))
        self.assertEqual(result["rounded_verification"]["status"], "failed")
        self.assertEqual(result["uncertainty_verification"]["status"], "failed")

    def test_overfilled_stock_doses_are_rejected(self):
        stocks = copy.deepcopy(STOCKS)
        stocks["concentrations_g_l"] = {k: 0.0001 for k in stocks["concentrations_g_l"]}
        with self.assertRaises(DeliveryError) as caught:
            self.recipe(stock_dosing=stocks)
        self.assertEqual(caught.exception.code, "ratio_stock_volume_infeasible")

    def test_small_or_negative_possible_dose_is_rejected(self):
        with self.assertRaises(DeliveryError) as caught:
            self.recipe(stock_dosing=dict(STOCKS, dose_error_ml=50))
        self.assertEqual(caught.exception.code, "ratio_stock_dose_infeasible")

    def test_stock_uncertainty_corners_pass_and_large_errors_fail(self):
        from flahax.ratio_uncertainty import verify_uncertainty

        result = self.recipe(saturation_margin=0.3)
        result["rounded_verification"]["evaluated_ph"] = [6.28, 6.32]
        for dose_error, expected in ((0.02, "passed"), (0.5, "failed")):
            delivery = prepare_stock_delivery(result, dict(STOCKS, dose_error_ml=dose_error), 0.05)
            result["stock_delivery"] = delivery
            check = verify_uncertainty(
                result, UNCERTAINTY, effective_bounds=delivery["effective_grams_bounds"]
            )
            self.assertEqual(check["scenario_count"], 128)
            self.assertEqual(check["status"], expected)
            if expected == "passed":
                for row in check["phase_maxima"].values():
                    self.assertLess(row["si"], -0.3000001)
            if expected == "failed":
                self.assertIn("nutrient_ratios", check["failed_checks"])
