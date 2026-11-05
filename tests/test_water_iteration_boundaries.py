# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Measured-water iteration failure witnesses for runtime coverage closure (#186)."""

import unittest
from unittest.mock import patch
from flahax import DeliveryError
from flahax import measured_water as water


class WaterIterationBoundaryTests(unittest.TestCase):
    def test_inferred_carbon_cannot_escape_the_domain(self):
        with (
            patch.object(water, 'solve', return_value=object()),
            patch.object(water, 'total_alkalinity', return_value=0),
        ):
            with self.assertRaises(DeliveryError) as caught:
                water._carbon_for_alkalinity({}, 7, 1, ())
        self.assertEqual(caught.exception.code, 'alkalinity_out_of_range')


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
