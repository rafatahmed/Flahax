"""End-to-end, dependency-free release evidence for delivery planning."""

import copy
import unittest

from flahax import (
    DeliveryError,
    InjectionRatio,
    StockTank,
    TemperatureCelsius,
    VolumeLitres,
    final_solution_recipe,
    plan_ph,
    plan_pump_command,
    plan_stocks,
)
from tests.test_ph_planning import inputs
from tests.test_pump_planning import calibration
from tests.test_stock_planning import limits, recipe, rule


class DeliveryReleaseEvidence(unittest.TestCase):
    def test_high_alkalinity_measured_curve_is_a_bounded_golden_case(self):
        water, curve, reagent = inputs()
        water["alkalinityMgLAsCaCO3"] = 500
        curve["points"] = [
            {"demandMeqPerL": 0, "pH": 7.4},
            {"demandMeqPerL": 4.0, "pH": 6.0},
        ]
        plan = plan_ph(
            water, curve, reagent, 6.7, VolumeLitres(100), VolumeLitres(1),
            {"N_NO3": 100}, {"N_NO3": 177.28},
        )
        self.assertAlmostEqual(plan.source_alkalinity.value, 500 / 50.043)
        self.assertAlmostEqual(plan.demand.value, 2.0)
        self.assertAlmostEqual(plan.reagent_volume_litres, 0.02)
        self.assertTrue(plan.post_mix_measurement_required)

    def test_incompatible_calcium_phosphate_is_a_golden_rejection(self):
        with self.assertRaises(DeliveryError) as caught:
            plan_stocks(
                recipe(), InjectionRatio(100), [StockTank("A", VolumeLitres(2))],
                [rule()], limits(), TemperatureCelsius(20),
            )
        self.assertEqual(caught.exception.code, "no_stock_assignment")

    def test_bounded_sensitivity_is_visible_for_curve_assay_ratio_and_pump_flow(self):
        water, curve, reagent = inputs()
        baseline = plan_ph(
            water, curve, reagent, 6.7, VolumeLitres(100), VolumeLitres(1),
            {"N_NO3": 100}, {"N_NO3": 111.592},
        )
        higher_demand_curve = copy.deepcopy(curve)
        higher_demand_curve["points"][1]["demandMeqPerL"] = 2.4
        higher_demand = plan_ph(
            water, higher_demand_curve, reagent, 6.7, VolumeLitres(100), VolumeLitres(1),
            {"N_NO3": 100}, {"N_NO3": 123.184},
        )
        lower_assay = copy.deepcopy(reagent)
        lower_assay["elements"]["N_NO3"] = 10
        lower_assay_plan = plan_ph(
            water, curve, lower_assay, 6.7, VolumeLitres(100), VolumeLitres(1),
            {"N_NO3": 100}, {"N_NO3": 108.4},
        )
        self.assertGreater(higher_demand.reagent_volume_litres, baseline.reagent_volume_litres)
        self.assertLess(
            lower_assay_plan.nutrient_contribution["N_NO3"].value,
            baseline.nutrient_contribution["N_NO3"].value,
        )

        stock_recipe = final_solution_recipe(
            {"feasible": True, "salts": [{"id": "a", "name": "A", "gramsPerLitre": 0.1}]},
            VolumeLitres(100),
        )
        limit = [{
            "schemaVersion": "0.1", "id": "a-limit", "source": "fixture", "revision": "1",
            "recordedAt": "2026-09-25T12:00:00Z", "productId": "a",
            "maxGramsPerLitre": 50, "temperatureMinC": 10, "temperatureMaxC": 30,
        }]
        stock_100 = plan_stocks(stock_recipe, InjectionRatio(100), [StockTank("A", VolumeLitres(2))], [], limit, TemperatureCelsius(20))
        stock_50 = plan_stocks(stock_recipe, InjectionRatio(50), [StockTank("A", VolumeLitres(2))], [], limit, TemperatureCelsius(20))
        self.assertAlmostEqual(stock_100.tanks[0].salts[0].concentration.value, 10)
        self.assertAlmostEqual(stock_50.tanks[0].salts[0].concentration.value, 5)

        slow = calibration()
        slow["flowLitresPerMinute"] = 0.06
        baseline_command = plan_pump_command(calibration(), VolumeLitres(0.12), VolumeLitres(1))
        slow_command = plan_pump_command(slow, VolumeLitres(0.12), VolumeLitres(1))
        self.assertAlmostEqual(slow_command.runtime.value, 2 * baseline_command.runtime.value)

    def test_temperature_outside_a_sourced_solubility_range_fails_closed(self):
        with self.assertRaises(DeliveryError) as caught:
            plan_stocks(
                recipe(), InjectionRatio(100), [StockTank("A", VolumeLitres(2)), StockTank("B", VolumeLitres(2))],
                [rule()], limits(), TemperatureCelsius(40),
            )
        self.assertEqual(caught.exception.code, "missing_solubility_limit")

