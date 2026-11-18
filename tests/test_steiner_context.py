# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Historical source claims must not become model validation or
acceptance bounds.
"""

import copy
import json
import unittest

from flahax import plan_ratio_recipe, search_ratio_recipe
from tests.test_ratio_recipe import REQUEST
from tests.test_ratio_search import OPTIONS


class SteinerContextTests(unittest.TestCase):
    def test_recipe_reports_structured_source_evidence(self):
        result = plan_ratio_recipe(**REQUEST)
        self.assertIn('historical_context', result)
        evidence = result['historical_context']['article']
        design = evidence['experimental_design']
        self.assertEqual(design['anion_ratios'] * design['cation_ratios'], 320)
        self.assertEqual(design['nominal_conditions'], 1600)
        self.assertEqual(design['later_printed_combinations'], 360)
        self.assertEqual(design['additional_intermediate_combinations'], 80)
        self.assertIsNone(design['resolved_curve_development_sample_count'])
        self.assertTrue(design['precipitating_mixtures_excluded_from_reformulation'])
        self.assertEqual(evidence['worked_example']['expected_ph'], 6.37)
        self.assertEqual(evidence['worked_example']['evidence_kind'], 'stated_expectation')
        self.assertEqual(evidence['solution_1a']['measured_ph'], [5.33, 6.45, 6.58])
        self.assertEqual(evidence['solution_1a']['evidence_kind'], 'reported_measurements')
        self.assertFalse(result['historical_context']['establishes_experimental_validation'])

    def test_source_definitions_units_and_missing_evidence_preserved(self):
        from flahax.steiner_context import article_evidence

        a = article_evidence()
        self.assertEqual(a['concentration_basis']['modern_unit'], 'mmol/L')
        self.assertEqual(a['concentration_basis']['ideal_osmotic_estimate']['temperature_c'], 15)
        self.assertEqual(a['figure_6']['curve_a_printed_k_ca'], [80, 20])
        self.assertEqual(a['figure_6']['solution_1a_k_ca_before_normalization'], [80, 10])
        self.assertFalse(a['figure_6']['mapping_resolved'])
        self.assertFalse(a['figure_6']['raw_fit_points_available'])
        self.assertIn('never', a['water_conductivity']['verbatim_transcription'])
        self.assertFalse(a['water_conductivity']['inequality_resolved'])
        self.assertEqual([x['threshold'] for x in a['empirical_screens']], [60, 2.2])
        self.assertTrue(
            all(
                x['interpreted_unit'] == '(mmol/L)^2' and not x['thermodynamic_ksp']
                for x in a['empirical_screens']
            )
        )
        self.assertEqual(
            [b['reported_plus_minus_ph'] for b in a['historical_domain']['ph_precision']],
            [0.2, 0.15, 0.1, 0.2],
        )
        self.assertEqual(a['historical_domain']['additional_ions']['NH4'], 'not_investigated')

    def test_strength_and_ph_interval_warnings_do_not_certify_source_coverage(self):
        from flahax.steiner_context import historical_context

        def codes(strength, interval):
            result = historical_context(
                strength_range=[strength, strength],
                ph_range=interval,
                cation_shares=[50, 30, 20],
                anion_shares=[5, 3, 1],
            )
            self.assertFalse(result['establishes_experimental_validation'])
            return {w['code'] for w in result['warnings']}

        self.assertIn('below_historical_tested_strength', codes(1.71, [6.28, 6.32]))
        self.assertIn('limited_20_mmol_l_evidence', codes(20, [6.3, 6.3]))
        self.assertIn('untested_strength_interpolation', codes(25, [6.3, 6.3]))
        self.assertNotIn('below_historical_tested_strength', codes(30, [6.3, 6.3]))
        self.assertIn('above_main_historical_strength', codes(42, [6.3, 6.3]))
        self.assertIn('ph_below_investigated_curves', codes(30, [4.9, 6.3]))
        self.assertIn('reduced_precision_above_ph_7', codes(30, [6.3, 7.1]))
        self.assertIn('curve_specific_coverage_unverified', codes(30, [6.3, 6.3]))

    def test_zero_calcium_or_phosphate_exclusions_and_no_invented_extreme_cutoff(self):
        from flahax.steiner_context import historical_context

        c = historical_context(
            strength_range=[30, 30],
            ph_range=[6.3, 6.3],
            cation_shares=[1, 0, 0],
            anion_shares=[1, 0, 0],
        )
        codes = {w['code'] for w in c['warnings']}
        self.assertIn('historical_calcium_phosphate_exclusion', codes)
        self.assertIsNone(c['article']['historical_domain']['extreme_ratio_numeric_cutoff'])

    def test_context_is_independent_and_cannot_mutate_future_reports(self):
        from flahax.steiner_context import article_evidence

        a = article_evidence()
        a['experimental_design']['nominal_conditions'] = 0
        self.assertEqual(article_evidence()['experimental_design']['nominal_conditions'], 1600)

    def test_search_and_cli_preserve_context_even_without_a_deliverable(self):
        from flahax.planning_cli import execute

        request = dict(OPTIONS, strength_range=[20, 21], scan_points=3)
        result = execute('ratio', request)
        self.assertIsNone(result['recipe'])
        self.assertIn('historical_context', result)
        json.dumps(result, allow_nan=False)
        found = search_ratio_recipe(strength_range=[1, 1.5], scan_points=3, **OPTIONS)
        self.assertIn('historical_context', found['recipe'])
        self.assertIn(
            'below_historical_tested_strength',
            {w['code'] for w in found['historical_context']['warnings']},
        )

    def test_rounded_and_uncertainty_strengths_are_in_report_scope(self):
        from flahax.steiner_context import recipe_historical_context

        result = dict(
            counted_mmol_l=30,
            target_ph=6.3,
            cation_percent=[50, 30, 20],
            anion_percent=[55, 34, 11],
            rounded_verification={'counted_mmol_l': 29.999, 'ph_range': [6.28, 6.32]},
            uncertainty_verification={'counted_mmol_l_range': [19.9, 30.1]},
        )
        original = copy.deepcopy(result)
        c = recipe_historical_context(result)
        self.assertEqual(result, original)
        self.assertEqual(c['assessed_strength_range_mmol_l'], [19.9, 30.1])
        self.assertEqual(c['assessed_ph_range'], [6.28, 6.32])
        self.assertIn('below_historical_tested_strength', {w['code'] for w in c['warnings']})
