import copy
import unittest

from flahax import (
    DeliveryError,
    MilligramsPerLitre,
    VolumeLitres,
    alkalinity_meq_per_litre,
    plan_ph,
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


def inputs():
    water = record(
        "water-wc1", ions={"Ca": 20}, temperatureC=22, pH=7.4, alkalinityMgLAsCaCO3=120
    )
    curve = record(
        "wc1-nitric", waterAnalysisId="water-wc1", reagentId="nitric-acid",
        points=[{"demandMeqPerL": 0, "pH": 7.4}, {"demandMeqPerL": 1.2, "pH": 6.0}],
    )
    reagent = record(
        "nitric-acid", name="Nitric acid", kind="acid", elements={"N_NO3": 13.8},
        densityKgPerL=1.4, normalityMeqPerL=10000,
    )
    return water, curve, reagent


class PhPlanning(unittest.TestCase):
    def test_interpolates_measured_curve_and_rescores_nutrient_addition(self):
        water, curve, reagent = inputs()
        plan = plan_ph(
            water, curve, reagent, 6.7, VolumeLitres(100), VolumeLitres(1), {"N_NO3": 100}, {"N_NO3": 111.592}
        )
        self.assertEqual(plan.direction, "acid")
        self.assertAlmostEqual(plan.demand.value, 0.6)
        self.assertAlmostEqual(plan.source_alkalinity.value, 120 / 50.043)
        self.assertAlmostEqual(plan.reagent_volume_litres, 0.006)
        self.assertAlmostEqual(plan.reagent_mass.value, 8.4)
        self.assertAlmostEqual(plan.nutrient_contribution["N_NO3"].value, 11.592)
        self.assertAlmostEqual(plan.rows[0]["deltaPct"], 0)
        self.assertTrue(plan.post_mix_measurement_required)

    def test_alkalinity_converts_from_calcium_carbonate_basis(self):
        self.assertAlmostEqual(alkalinity_meq_per_litre(MilligramsPerLitre(50.043)).value, 1.0)

    def test_missing_measurements_or_mismatched_records_fail_closed(self):
        water, curve, reagent = inputs()
        del water["alkalinityMgLAsCaCO3"]
        with self.assertRaises(DeliveryError) as caught:
            plan_ph(water, curve, reagent, 6.7, VolumeLitres(100), VolumeLitres(1), {}, {})
        self.assertEqual(caught.exception.code, "missing_measurement")

        water, curve, reagent = inputs()
        curve["waterAnalysisId"] = "other"
        with self.assertRaises(DeliveryError) as caught:
            plan_ph(water, curve, reagent, 6.7, VolumeLitres(100), VolumeLitres(1), {}, {})
        self.assertEqual(caught.exception.code, "mismatched_record")

    def test_outside_curve_and_wrong_reagent_direction_are_rejected(self):
        water, curve, reagent = inputs()
        with self.assertRaises(DeliveryError) as caught:
            plan_ph(water, curve, reagent, 5.8, VolumeLitres(100), VolumeLitres(1), {}, {})
        self.assertEqual(caught.exception.code, "outside_titration_range")

        water, curve, reagent = inputs()
        reagent["kind"] = "base"
        with self.assertRaises(DeliveryError) as caught:
            plan_ph(water, curve, reagent, 6.7, VolumeLitres(100), VolumeLitres(1), {}, {})
        self.assertEqual(caught.exception.code, "mismatched_record")

    def test_titration_curve_rejects_non_monotonic_ph(self):
        water, curve, reagent = inputs()
        curve = copy.deepcopy(curve)
        curve["points"].append({"demandMeqPerL": 2, "pH": 6.2})
        with self.assertRaises(DeliveryError) as caught:
            plan_ph(water, curve, reagent, 6.7, VolumeLitres(100), VolumeLitres(1), {}, {})
        self.assertEqual(caught.exception.code, "invalid_value")

    def test_reagent_dose_cannot_exceed_explicit_safety_limit(self):
        water, curve, reagent = inputs()
        with self.assertRaises(DeliveryError) as caught:
            plan_ph(water, curve, reagent, 6.7, VolumeLitres(100), VolumeLitres(0.001), {}, {})
        self.assertEqual(caught.exception.code, "dose_limit_exceeded")


if __name__ == "__main__":
    unittest.main()
