# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.pump_planning."""

import unittest
from datetime import datetime, timezone
from flahax import DeliveryError, VolumeLitres
from flahax.pump_planning import plan_pump_command

CALIBRATION_AS_OF = datetime(2026, 9, 27, tzinfo=timezone.utc)


def calibration():
    return {
        "schemaVersion": "0.1",
        "id": "pump-1",
        "source": "bench",
        "revision": "1",
        "recordedAt": "2026-09-25T12:00:00+03:00",
        "channelId": "A",
        "stockDensityKgPerL": 1.1,
        "testTemperatureC": 22,
        "flowLitresPerMinute": 0.12,
        "standardDeviationLitresPerMinute": 0.002,
        "validMinLitres": 0.02,
        "validMaxLitres": 2,
    }


class PumpPlanningTests(unittest.TestCase):
    def test_volume_runtime_and_uncertainty(self):
        p = plan_pump_command(
            calibration(), VolumeLitres(0.12), VolumeLitres(1), 0.01, as_of=CALIBRATION_AS_OF
        )
        self.assertAlmostEqual(p.runtime.value, 1)
        self.assertGreater(p.volume_uncertainty.value, 0)
        self.assertTrue(p.requires_operator_verification)

    def test_rejects_dry_tank_and_outside_calibration(self):
        with self.assertRaises(DeliveryError) as c:
            plan_pump_command(
                calibration(), VolumeLitres(0.01), VolumeLitres(1), as_of=CALIBRATION_AS_OF
            )
        self.assertEqual(c.exception.code, "out_of_calibration_range")
        with self.assertRaises(DeliveryError) as c:
            plan_pump_command(
                calibration(), VolumeLitres(0.12), VolumeLitres(0.1), as_of=CALIBRATION_AS_OF
            )
        self.assertEqual(c.exception.code, "dry_tank_risk")

    def test_rejects_stale_calibration(self):
        with self.assertRaises(DeliveryError) as c:
            plan_pump_command(
                calibration(),
                VolumeLitres(0.12),
                VolumeLitres(1),
                as_of=datetime(2026, 11, 1, tzinfo=timezone.utc),
            )
        self.assertEqual(c.exception.code, "stale_calibration")

    def test_rejects_zero_stock_density(self):
        item = calibration()
        item["stockDensityKgPerL"] = 0
        with self.assertRaises(DeliveryError) as c:
            plan_pump_command(item, VolumeLitres(0.12), VolumeLitres(1), as_of=CALIBRATION_AS_OF)
        self.assertEqual(c.exception.code, "out_of_range")


class PumpBoundaryTests(unittest.TestCase):
    def test_invalid_time_and_uncertainty(self):
        for changes in (
            {'as_of': datetime(2026, 9, 27)},
            {'as_of': 'today'},
            {'runtime_standard_deviation_minutes': True},
            {'runtime_standard_deviation_minutes': 'bad'},
            {'runtime_standard_deviation_minutes': -1},
            {'max_calibration_age_days': float('inf')},
        ):
            with self.subTest(changes=changes), self.assertRaises(DeliveryError):
                plan_pump_command(
                    calibration(),
                    VolumeLitres(0.1),
                    VolumeLitres(1),
                    **({'as_of': CALIBRATION_AS_OF} | changes),
                )
        for stamp in ('2026-10-01T00:00:00Z', '2026-09-25T00:00:00'):
            with self.subTest(stamp=stamp), self.assertRaises(DeliveryError):
                plan_pump_command(
                    calibration() | {'recordedAt': stamp},
                    VolumeLitres(0.1),
                    VolumeLitres(1),
                    as_of=CALIBRATION_AS_OF,
                )

    def test_hypotenuse_avoids_intermediate_square_overflow(self):
        p = plan_pump_command(
            calibration() | {'standardDeviationLitresPerMinute': 1e200},
            VolumeLitres(0.12),
            VolumeLitres(1),
            0,
            as_of=CALIBRATION_AS_OF,
        )
        self.assertEqual(p.volume_uncertainty.value, 1e200)

    def test_type_and_derived_overflow(self):
        with self.assertRaises(DeliveryError):
            plan_pump_command(calibration(), 0.1, VolumeLitres(1))
        for changes in (
            {'flowLitresPerMinute': 1e-320},
            {'standardDeviationLitresPerMinute': 1e308, 'flowLitresPerMinute': 0.01},
        ):
            with self.subTest(changes=changes), self.assertRaises(DeliveryError):
                plan_pump_command(
                    calibration() | changes,
                    VolumeLitres(0.12),
                    VolumeLitres(1),
                    as_of=CALIBRATION_AS_OF,
                )
