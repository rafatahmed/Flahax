# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Measured-water iteration failure witnesses for runtime coverage closure (#186)."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch
from flahax import DeliveryError
from flahax import measured_water as water


class WaterIterationBoundaryTests(unittest.TestCase):
    def carbonate(self, first, subsequent):
        state = SimpleNamespace(charge_balance=first)
        with patch.object(
            water,
            'solve',
            side_effect=lambda *a, **k: SimpleNamespace(charge_balance=next(subsequent)),
        ):
            return water._close_on_carbonate(
                {'CO3-2': 0.001}, state, 7, (), 1, 'inorganic_carbon', {}
            )

    def test_flat_nonzero_residual_is_not_charge_closure(self):
        with self.assertRaises(DeliveryError) as caught:
            self.carbonate(1e-4, iter([1e-4]))
        self.assertEqual(caught.exception.code, 'nonconvergent')

    def test_negative_carbon_and_iteration_exhaustion_fail_closed(self):
        with self.assertRaises(DeliveryError) as caught:
            self.carbonate(1, iter([1.001]))
        self.assertEqual(caught.exception.code, 'alkalinity_exhausted')
        # Oscillation of decreasing secant slopes never reaches the existing residual bound.
        from itertools import cycle

        with self.assertRaises(DeliveryError) as caught:
            self.carbonate(1, cycle([-0.5, 1]))
        self.assertEqual(caught.exception.code, 'nonconvergent')

    def test_inferred_carbon_cannot_escape_the_domain(self):
        with (
            patch.object(water, 'solve', return_value=object()),
            patch.object(water, 'total_alkalinity', return_value=0),
        ):
            with self.assertRaises(DeliveryError) as caught:
                water._carbon_for_alkalinity({}, 7, 1, ())
        self.assertEqual(caught.exception.code, 'alkalinity_out_of_range')

    def test_balance_ion_exhaustion_and_nonconvergence_are_explicit(self):
        from tests.test_measured_water import STATION_104
        from dataclasses import replace

        state = water.solve(STATION_104, 7.8)
        for residual, code in [(-1, 'balance_ion_exhausted'), (1e-4, 'nonconvergent')]:
            stalled = replace(state, charge_balance=residual)
            with (
                patch.object(water, 'solve', return_value=stalled),
                patch.object(water, '_imbalance_percent', return_value=1),
            ):
                with self.assertRaises(DeliveryError) as caught:
                    water.balance_water_analysis(STATION_104, measured_ph=7.8)
            self.assertEqual(caught.exception.code, code)


class WaterInputPreservationTests(unittest.TestCase):
    def test_carbon_measurement_cannot_be_reinferred(self):
        with self.assertRaises(DeliveryError) as caught:
            water._carbon_for_alkalinity({'CO3-2': 0}, 7, 1, ())
        self.assertEqual(caught.exception.code, 'ambiguous_carbon')

    def test_interview_restart_and_below_detection_alkalinity(self):
        from unittest.mock import Mock
        from flahax.mix_water import ask_analysis, WATER_IONS

        prompts = Mock()
        prompts.new_name.return_value = 'Synthetic water'
        prompts.number.return_value = 7
        prompts.choose.side_effect = [0, 0, 2, 0, 0]
        first = [(1 if ion == 'Na' else 0, None) for ion in WATER_IONS]
        second = [(None, 1) if ion == 'Alk' else (None, None) for ion in WATER_IONS]
        with patch('flahax.mix_water.ask_ion', side_effect=first + second):
            name, data = ask_analysis(prompts, None)
        self.assertEqual(prompts.new_name.call_count, 2)
        self.assertEqual(name, 'Synthetic water')
        self.assertNotIn('Na', data['mg_per_litre'])
        self.assertNotIn('HCO3', data['mg_per_litre'])
        self.assertGreater(data['alkalinity_below_detection_meq_per_litre'], 0)
        self.assertNotIn('HCO3', data['below_detection'])
