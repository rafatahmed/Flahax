# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.ph_planning."""

import copy
import unittest
from types import SimpleNamespace

from flahax import (
    DeliveryError,
    MilligramsPerLitre,
    VolumeLitres,
    alkalinity_meq_per_litre,
    plan_ph,
)
from flahax.nutrient_ledger import elemental_nitrogen, merge_nutrient_totals
from flahax.saturation_policy import REVIEW, assess_saturation


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
    water = record("water-wc1", ions={"Ca": 20}, temperatureC=22, pH=7.4, alkalinityMgLAsCaCO3=120)
    curve = record(
        "wc1-nitric",
        waterAnalysisId="water-wc1",
        reagentId="nitric-acid",
        points=[{"demandMeqPerL": 0, "pH": 7.4}, {"demandMeqPerL": 1.2, "pH": 6.0}],
    )
    reagent = record(
        "nitric-acid",
        name="Nitric acid",
        kind="acid",
        elements={"N_NO3": 13.8},
        densityKgPerL=1.4,
        normalityMeqPerL=10000,
    )
    return water, curve, reagent


class PhPlanning(unittest.TestCase):
    def test_interpolates_measured_curve_and_rescores_nutrient_addition(self):
        water, curve, reagent = inputs()
        plan = plan_ph(
            water,
            curve,
            reagent,
            6.7,
            VolumeLitres(100),
            VolumeLitres(1),
            {"N_NO3": 100},
            {"N_NO3": 111.592},
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


class TargetStatePhaseAndLedgerWitness(unittest.TestCase):
    """Core-contract-spine Task 6: REVIEW at target pH; reagent N counted once."""

    def test_review_class_si_at_target_does_not_hard_block(self):
        state = SimpleNamespace(
            saturation_indices={'Hydroxylapatite': 4.0, 'MnHPO4': 3.0, 'CaHPO4': -0.5},
            precipitated={},
            totals={},
        )
        assessed = assess_saturation(state)
        self.assertFalse(assessed['blocks'])
        self.assertEqual(
            {p for p, *_ in assessed['review']}, {'Hydroxylapatite', 'MnHPO4'}
        )
        self.assertTrue({'Hydroxylapatite', 'MnHPO4'} <= set(REVIEW))

    def test_hard_blocker_at_target_still_blocks(self):
        state = SimpleNamespace(
            saturation_indices={'CaHPO4': 0.2, 'Hydroxylapatite': 1.0},
            precipitated={},
            totals={},
        )
        assessed = assess_saturation(state)
        self.assertTrue(assessed['blocks'])
        self.assertIn('CaHPO4', [p for p, _ in assessed['blocking']])

    def test_reagent_n_merged_once_on_ledger(self):
        water = {'N_NO3': 100.0, 'Ca': 50.0}
        reagent = {'N_NO3': 12.0, 'N': 999.0}  # aggregate N must not double-count
        merged = merge_nutrient_totals(water, reagent)
        self.assertAlmostEqual(merged['N_NO3'], 112.0)
        self.assertNotIn('N', merged)
        self.assertAlmostEqual(elemental_nitrogen(merged), 112.0)


if __name__ == "__main__":
    unittest.main()
