import unittest

from flahax import (
    DeliveryError,
    InjectionRatio,
    StockTank,
    TemperatureCelsius,
    VolumeLitres,
    final_solution_recipe,
    plan_stocks,
)


def record(record_id, **fields):
    return {
        "schemaVersion": "0.1",
        "id": record_id,
        "source": "bench-validation",
        "revision": "1",
        "recordedAt": "2026-09-25T12:00:00+03:00",
        **fields,
    }


def recipe(feasible=True):
    return final_solution_recipe(
        {
            "feasible": feasible,
            "salts": [
                {"id": "calcium-nitrate", "name": "Calcium nitrate", "gramsPerLitre": 0.5},
                {"id": "phosphate", "name": "Phosphate", "gramsPerLitre": 0.25},
            ],
        },
        VolumeLitres(100),
    )


def rule():
    return record(
        "calcium-phosphate-separate",
        productIds=["calcium-nitrate", "phosphate"],
        constraint="separate",
        reason="Bench compatibility rule.",
        temperatureMinC=5,
        temperatureMaxC=35,
    )


def limits(calcium_limit=100, phosphate_limit=100):
    return [
        record(
            "calcium-limit",
            productId="calcium-nitrate",
            maxGramsPerLitre=calcium_limit,
            temperatureMinC=10,
            temperatureMaxC=30,
        ),
        record(
            "phosphate-limit",
            productId="phosphate",
            maxGramsPerLitre=phosphate_limit,
            temperatureMinC=10,
            temperatureMaxC=30,
        ),
    ]


class StockPlanning(unittest.TestCase):
    def test_compatible_recipe_is_split_deterministically(self):
        plan = plan_stocks(
            recipe(),
            InjectionRatio(100),
            [StockTank("B", VolumeLitres(2)), StockTank("A", VolumeLitres(2))],
            [rule()],
            limits(),
            TemperatureCelsius(20),
        )
        self.assertEqual([tank.tank.tank_id for tank in plan.tanks], ["A", "B"])
        self.assertEqual(plan.tanks[0].stock_volume.value, 1)
        self.assertEqual(plan.tanks[0].salts[0].concentration.value, 50)
        self.assertEqual(plan.tanks[1].salts[0].concentration.value, 25)
        self.assertEqual(plan.compatibility_rule_ids, ("calcium-phosphate-separate",))

    def test_infeasible_recipe_and_missing_temperature_limit_are_rejected(self):
        with self.assertRaises(DeliveryError) as caught:
            plan_stocks(recipe(False), InjectionRatio(100), [StockTank("A", VolumeLitres(2))], [], limits(), TemperatureCelsius(20))
        self.assertEqual(caught.exception.code, "infeasible_recipe")

        with self.assertRaises(DeliveryError) as caught:
            plan_stocks(recipe(), InjectionRatio(100), [StockTank("A", VolumeLitres(2))], [], limits(), TemperatureCelsius(40))
        self.assertEqual(caught.exception.code, "missing_solubility_limit")

    def test_limit_capacity_and_assignment_fail_closed(self):
        with self.assertRaises(DeliveryError) as caught:
            plan_stocks(recipe(), InjectionRatio(100), [StockTank("A", VolumeLitres(2))], [], limits(calcium_limit=49), TemperatureCelsius(20))
        self.assertEqual(caught.exception.code, "solubility_exceeded")

        with self.assertRaises(DeliveryError) as caught:
            plan_stocks(recipe(), InjectionRatio(100), [StockTank("A", VolumeLitres(0.5))], [], limits(), TemperatureCelsius(20))
        self.assertEqual(caught.exception.code, "capacity_exceeded")

        with self.assertRaises(DeliveryError) as caught:
            plan_stocks(recipe(), InjectionRatio(100), [StockTank("A", VolumeLitres(2))], [rule()], limits(), TemperatureCelsius(20))
        self.assertEqual(caught.exception.code, "no_stock_assignment")


if __name__ == "__main__":
    unittest.main()
