# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Adaptive pH evidence is observable through the recipe workflow."""

import unittest

from flahax import plan_ratio_recipe
from tests.test_ratio_search import OPTIONS


class AdaptivePhTests(unittest.TestCase):
    def test_real_hydroxyapatite_crossing_is_refined_and_remains_failed(self):
        c = plan_ratio_recipe(**dict(OPTIONS, counted_mmol_l=1.95))['rounded_verification']
        self.assertEqual(c['status'], 'failed')
        self.assertIn('Hydroxylapatite', c['failed_phases'])
        brackets = c['ph_refinement']['crossing_brackets']['Hydroxylapatite']
        self.assertTrue(brackets)
        for row in brackets:
            a, b = row['ph_interval']
            self.assertLessEqual(b - a, 1.000001e-5)
        self.assertTrue(c['ph_refinement']['complete'])

    def test_single_ph_request_has_no_artificial_refinement(self):
        c = plan_ratio_recipe(**dict(OPTIONS, counted_mmol_l=1.3, ph_range=[6.3, 6.3]))[
            'rounded_verification'
        ]
        self.assertEqual(c['evaluated_ph'], [6.3])
        self.assertEqual(c['ph_refinement']['added_points'], 0)
        self.assertTrue(c['ph_refinement']['complete'])

    def test_legacy_preparation_scenarios_are_refined_too(self):
        from tests.test_ratio_uncertainty import UNCERTAINTY

        opts = dict(UNCERTAINTY, weighing_error_g=0, purity_fraction=[1, 1], volume_error_litres=0)
        c = plan_ratio_recipe(**dict(OPTIONS, counted_mmol_l=1.3, uncertainty=opts))[
            'uncertainty_verification'
        ]
        self.assertEqual(len(c['ph_refinement']['scenarios']), 1)
        self.assertTrue(c['ph_refinement']['scenarios'][0]['complete'])

    def test_each_physical_uncertainty_scenario_gets_its_own_refinement(self):
        from tests.test_ratio_physical_uncertainty import physical_request

        req = physical_request()
        req['uncertainty']['physical_preparation']['solution_density_kg_l'] = [1.001, 1.002]
        c = plan_ratio_recipe(**req)['uncertainty_verification']
        checks = c['ph_refinement']['scenarios']
        self.assertEqual(len(checks), c['scenario_count'])
        self.assertGreater(len(checks), 1)
        self.assertTrue(all(x['complete'] for x in checks))
        self.assertTrue(all(x['added_points'] > 0 for x in checks))
        self.assertFalse(c['continuous_chemistry_extrema_proved'])

    def test_rounded_recipe_refines_observed_mineral_maxima(self):
        c = plan_ratio_recipe(**dict(OPTIONS, counted_mmol_l=1.3))['rounded_verification']
        a = c['ph_refinement']
        self.assertTrue(a['complete'])
        self.assertGreater(a['added_points'], 0)
        self.assertFalse(a['continuous_extrema_proved'])
        self.assertGreater(len(c['evaluated_ph']), len(c['base_evaluated_ph']))
        for intervals in a['maximum_neighbour_intervals'].values():
            for low, high in intervals:
                self.assertLessEqual(high - low, 1.000001e-5)
        self.assertEqual(c['evaluated_ph'][0], 6.28)
        self.assertEqual(c['evaluated_ph'][-1], 6.32)
