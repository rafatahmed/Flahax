# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent rational hydraulic bookkeeping, not hardware qualification."""

from fractions import Fraction
import unittest

from flahax import DeliveryError, VolumeLitres
from flahax.injector_sizing import size_injection_requirements
from flahax.pump_planning import plan_pump_command
from tests.test_pump_planning import calibration, CALIBRATION_AS_OF


class InjectorSizingTests(unittest.TestCase):
    def args(self):
        return dict(
            duration_hours=2,
            final_volume_litres=120,
            equipment_type='dosing_pump',
            channels={
                name: dict(final_litres_per_stock_litre=ratio, available_stock_litres=10)
                for name, ratio in [('A', 100), ('B', 200), ('acid', 400)]
            },
        )

    def test_rational_volume_flow_and_calibrated_runtime_identity(self):
        args = self.args()
        result = size_injection_requirements(**args)
        total = Fraction(0)
        for name, ratio in [('A', 100), ('B', 200), ('acid', 400)]:
            dose = Fraction(120, ratio)
            total += dose
            self.assertEqual(result['channels'][name]['required_stock_litres'], float(dose))
            self.assertEqual(
                result['channels'][name]['required_flow_litres_per_hour'], float(dose / 2)
            )
            command = plan_pump_command(
                calibration() | {'channelId': name},
                VolumeLitres(float(dose)),
                VolumeLitres(10),
                as_of=CALIBRATION_AS_OF,
            )
            self.assertAlmostEqual(command.runtime.value, float(dose / Fraction(12, 100)))
        self.assertEqual(result['carrier_water_litres'], float(120 - total))
        self.assertEqual(result['final_flow_litres_per_hour'], 60)
        self.assertIsNone(result['selected_model'])
        self.assertEqual(result['model_selection_status'], 'needs_manufacturer_operating_point')
        area = self.args()
        del area['final_volume_litres']
        area.update(active_area_m2=40, gross_depth_mm=3)
        self.assertEqual(size_injection_requirements(**area), result)

    def test_equipment_and_insufficient_inventory(self):
        for equipment in ('venturi', 'dosatron'):
            args = self.args()
            args['equipment_type'] = equipment
            args['channels']['A']['available_stock_litres'] = 1
            result = size_injection_requirements(**args)
            self.assertEqual(result['status'], 'insufficient_stock')
            self.assertFalse(result['channels']['A']['inventory_sufficient'])

    def test_boundaries(self):
        for change in (
            {'equipment_type': 'unknown'},
            {'duration_hours': 0},
            {'final_volume_litres': None},
            {'active_area_m2': 40},
            {'channels': {}},
            {'channels': []},
            {'channels': {'': {}}},
            {'channels': {'A': None}},
            {'channels': {'A': {}}},
            {'channels': {'A': dict(final_litres_per_stock_litre=1, available_stock_litres=120)}},
            {'duration_hours': 1e-320},
            {'final_volume_litres': float('inf')},
            {'final_volume_litres': 5e-324},
            {'final_volume_litres': None, 'active_area_m2': 1e308, 'gross_depth_mm': 10},
        ):
            with self.subTest(change=change), self.assertRaises(DeliveryError):
                size_injection_requirements(**(self.args() | change))
