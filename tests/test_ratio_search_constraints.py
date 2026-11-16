# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Observed strength boundaries are distinct from the highest-SI mineral."""

import unittest
from flahax import search_ratio_recipe
from tests.test_ratio_search import OPTIONS


class SearchConstraintTests(unittest.TestCase):
    def test_pure_salt_volume_uncertainty_retains_nutrient_limit_evidence(self):
        result = search_ratio_recipe(
            **dict(OPTIONS, saturation_margin=0.3),
            strength_range=[1.19, 1.2],
            scan_points=3,
            strength_tolerance=0.01,
            maximum_concentrations={'N_NO3': 5.419305966627288 / 0.95},
            nutrient_ceiling_reserve=0.05,
            uncertainty=dict(
                weighing_error_g=0,
                purity_fraction=[1, 1],
                volume_error_litres=0.05,
                ratio_relative_tolerance=0.01,
                concentration_relative_tolerance=0.02,
                impurity_model='inert',
            ),
        )
        self.assertEqual(result['status'], 'found')
        evidence = result['observed_strength_limit']
        self.assertEqual(evidence['status'], 'identified')
        rows = [v for v in evidence['violations'] if v['kind'] == 'nutrient_ceiling']
        self.assertEqual([v['name'] for v in rows], ['N_NO3'])
        self.assertGreater(rows[0]['value'], rows[0]['limit'])
        self.assertAlmostEqual(rows[0]['limit'], 5.419305966627288, places=12)
        self.assertEqual(rows[0]['basis'], 'analytical_interval_upper')

    def test_nominal_saturation_failure_retains_mineral_evidence(self):
        from tests.ratio_allocation_cases import base_request

        request = base_request()
        request.pop('counted_mmol_l')
        request['saturation_margin'] = 2.0
        result = search_ratio_recipe(**request, strength_range=[1.15, 1.2], scan_points=3)
        self.assertEqual(result['status'], 'no_feasible_candidate_found')
        for row in result['evaluations']:
            self.assertTrue(
                any(x['kind'] == 'mineral_saturation' for x in row['constraint_violations'])
            )

    def test_unreported_allocation_limit_remains_unknown(self):
        result = search_ratio_recipe(
            **dict(OPTIONS, saturation_margin=0.3),
            strength_range=[1.1, 1.5],
            scan_points=3,
            strength_tolerance=0.001,
            maximum_concentrations={'N_NO3': 6},
            nutrient_ceiling_reserve=0.05,
        )
        self.assertEqual(result['status'], 'found')
        evidence = result['observed_strength_limit']
        self.assertEqual(evidence['status'], 'unknown')
        self.assertFalse(evidence['violations'])
        self.assertIsNotNone(evidence['reason'])

    def test_nitrate_reserve_not_highest_si_mineral_controls_observed_boundary(self):
        from tests.ratio_allocation_cases import base_request

        request = base_request()
        request.pop('counted_mmol_l')
        result = search_ratio_recipe(
            **request,
            strength_range=[1.2680127620697021, 1.268019676208496],
            scan_points=3,
            strength_tolerance=1e-5,
        )
        self.assertEqual(result['status'], 'found')
        evidence = result['observed_strength_limit']
        self.assertEqual(evidence['status'], 'identified')
        rows = [r for r in evidence['violations'] if r['kind'] == 'nutrient_ceiling']
        self.assertEqual([r['name'] for r in rows], ['N_NO3'])
        self.assertAlmostEqual(rows[0]['limit'], 5.7, places=12)
        self.assertGreater(rows[0]['value'], 5.7)
        self.assertEqual(result['highest_si_phase'], 'Hydroxylapatite')
        self.assertFalse(any(r['kind'] == 'mineral_saturation' for r in evidence['violations']))

    def test_mineral_control_preserves_all_anchor_nutrient_and_uncertainty_limits(self):
        from tests.ratio_allocation_cases import base_request

        request = base_request()
        request.pop('counted_mmol_l')
        # Deliberately stricter mineral reserve; nutrient/uncertainty limits unchanged.
        request['saturation_margin'] = 1.4
        result = search_ratio_recipe(
            **request, strength_range=[1.2, 1.24], scan_points=3, strength_tolerance=0.005
        )
        self.assertEqual(result['status'], 'found')
        evidence = result['observed_strength_limit']
        self.assertEqual(evidence['status'], 'identified')
        self.assertEqual(
            [r['name'] for r in evidence['violations'] if r['kind'] == 'mineral_saturation'],
            ['Hydroxylapatite'],
        )
        self.assertFalse(any(r['kind'] == 'nutrient_ceiling' for r in evidence['violations']))
        self.assertEqual(result['recipe']['nutrient_ceiling_reserve']['fraction'], 0.05)

    def test_unknown_local_fit_cause_is_not_invented(self):
        from tests.ratio_allocation_cases import base_request, remove_products

        request = base_request()
        request.pop('counted_mmol_l')
        remove_products(request, {1})
        request['water']['totals_mol_kg']['Ca+2'] = 0
        result = search_ratio_recipe(**request, strength_range=[1, 1.2], scan_points=3)
        self.assertEqual(result['observed_strength_limit']['status'], 'unknown')
        self.assertTrue(
            all(r['error_code'] == 'ratio_product_fit_failed' for r in result['evaluations'])
        )
        self.assertTrue(all(not r['constraint_violations'] for r in result['evaluations']))
        self.assertIsNone(result['highest_si_phase'])

    def test_search_does_not_erase_incomplete_uncertainty(self):
        from tests.ratio_allocation_cases import base_request

        request = base_request()
        request.pop('counted_mmol_l')
        request['uncertainty']['max_scenarios'] = 1
        result = search_ratio_recipe(**request, strength_range=[1, 1.2], scan_points=3)
        self.assertEqual(result['status'], 'incomplete')
        self.assertTrue(all(r['status'] == 'incomplete' for r in result['evaluations']))
        self.assertIsNone(result['recipe'])

    def test_cap_is_not_reported_as_a_discovered_constraint(self):
        result = search_ratio_recipe(**OPTIONS, strength_range=[1, 1.1], scan_points=3)
        self.assertEqual(result['observed_strength_limit']['status'], 'search_cap')


class RefinementRobustnessTests(unittest.TestCase):
    def test_observed_interior_peak_is_resolved(self):
        import math
        from types import SimpleNamespace
        from flahax.ratio_ph_refinement import refine_ph

        phase = 'Hydroxylapatite'

        def curve(ph):
            return SimpleNamespace(
                saturation_indices={
                    phase: -0.35 + 0.1 * math.exp(-(((ph - 6.30037) / 0.002) ** 2))
                }
            )

        states, report = refine_ph(
            curve, [6.28 + i * 0.001 for i in range(41)], [phase], -0.3000001
        )
        peak = max(states, key=lambda p: states[p].saturation_indices[phase])
        self.assertTrue(report['complete'])
        self.assertAlmostEqual(states[peak].saturation_indices[phase], -0.25, delta=1e-6)
        self.assertLess(abs(peak - 6.30037), 1e-5)
        self.assertTrue(report['crossing_brackets'][phase])

    def test_unobserved_narrow_peak_keeps_continuous_limit_explicit(self):
        import math
        from types import SimpleNamespace
        from flahax.ratio_ph_refinement import refine_ph

        phase = 'Hydroxylapatite'

        def curve(ph):
            return SimpleNamespace(
                saturation_indices={phase: -1 + 2 * math.exp(-(((ph - 6.3005) / 0.00001) ** 2))}
            )

        states, report = refine_ph(
            curve, [6.28 + i * 0.001 for i in range(41)], [phase], -0.3000001
        )
        self.assertTrue(all(s.saturation_indices[phase] < -0.3000001 for s in states.values()))
        self.assertGreater(curve(6.3005).saturation_indices[phase], -0.3000001)
        self.assertFalse(report['continuous_extrema_proved'])
        self.assertIn('unsampled', report['qualification'])
