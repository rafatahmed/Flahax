# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Approved fault injection tests rejection guards, not thermodynamic accuracy.

Internal faults are injected deliberately; assertions observe public recipe/search
results. Real-input numerical validation remains in the separate acceptance tests.
"""

import copy
import unittest
from unittest.mock import patch

from flahax import plan_ratio_recipe, search_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from flahax.ratio_ph_refinement import refine_ph
from tests.test_ratio_analysis_uncertainty import bounds, request
from tests.test_ratio_products import products
from tests.test_ratio_recipe import REQUEST
from tests.test_ratio_search import OPTIONS
from tests.test_ratio_stocks import UNCERTAINTY


class RecipeFaultInjectionTests(unittest.TestCase):
    def test_refinement_faults_cannot_pass_nominal_or_uncertain_chemistry(self):
        for mode in ('nominal', 'dry', 'commercial'):
            for fault, code in (
                ('budget', 'ph_refinement_incomplete'),
                ('missing_si', 'phase_unavailable'),
            ):
                args = dict(OPTIONS, counted_mmol_l=1)
                if mode == 'dry':
                    args['uncertainty'] = dict(
                        UNCERTAINTY,
                        volume_error_litres=0,
                        weighing_error_g=0,
                        purity_fraction=[1, 1],
                    )
                elif mode == 'commercial':
                    args = request()
                    args['uncertainty'] = bounds(args)
                calls = 0

                def injected(*values, **kwargs):
                    nonlocal calls
                    calls += 1
                    states, report = refine_ph(*values, **kwargs)
                    if calls == (1 if mode == 'nominal' else 2):
                        if fault == 'budget':
                            report['complete'] = False
                        else:
                            states = copy.deepcopy(states)
                            next(iter(states.values())).saturation_indices.clear()
                    return states, report

                with (
                    self.subTest(mode=mode, fault=fault),
                    patch('flahax.ratio_ph_refinement.refine_ph', side_effect=injected),
                ):
                    result = plan_ratio_recipe(**args)
                check = result[
                    'rounded_verification' if mode == 'nominal' else 'uncertainty_verification'
                ]
                self.assertEqual(check['status'], 'incomplete')
                self.assertEqual(check['error']['code'], code)

    def test_inaccurate_charge_root_is_rejected_by_independent_reconstruction(self):
        from flahax.root_finding import shrink_bracket

        def inaccurate(*args, **kwargs):
            lo, hi = shrink_bracket(*args, **kwargs)
            return lo + 0.001, hi + 0.001

        with patch('flahax.ratio_recipe.shrink_bracket', side_effect=inaccurate):
            with self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**REQUEST)
        self.assertEqual(caught.exception.code, 'ratio_verification_failed')

    def test_corrupt_product_reconstruction_cannot_pass(self):
        from flahax.ratio_products import reconstruct_products

        for fault, code in (
            ('solvent', 'ratio_product_fit_failed'),
            ('nutrients', 'ratio_verification_failed'),
        ):

            def corrupt(*args, **kwargs):
                result = reconstruct_products(*args, **kwargs)
                if fault == 'solvent':
                    result['solvent_inventory_passed'] = False
                else:
                    result['analytical_mmol_l']['K'] += 0.01
                return result

            with (
                self.subTest(fault=fault),
                patch('flahax.ratio_products.reconstruct_products', side_effect=corrupt),
                self.assertRaises(DeliveryError) as caught,
            ):
                plan_ratio_recipe(**dict(REQUEST, products=products()))
            self.assertEqual(caught.exception.code, code)

    def test_source_limit_recheck_refuses_inconsistent_water_inventory(self):
        with patch(
            'flahax.ratio_products.elemental_from_totals', side_effect=[{'Na': 0}, {'Na': 100}]
        ):
            with self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(
                    **dict(REQUEST, products=products(), maximum_concentrations={'Na': 1})
                )
        self.assertEqual(caught.exception.code, 'ratio_limit_exceeded')

    def test_product_inventory_disappearing_during_replay_is_rejected(self):
        from flahax.product_conversion import material_inventory

        calls = 0

        def disappearing(product):
            nonlocal calls
            calls += 1
            result = material_inventory(product)
            if calls > 6:
                result.update(
                    components_moles_per_gram=None,
                    limitation_code='injected_inventory_failure',
                    limitation='Injected loss of material inventory',
                )
            return result

        with patch('flahax.ratio_products.material_inventory', side_effect=disappearing):
            with self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**dict(REQUEST, products=products()))
        self.assertEqual(caught.exception.code, 'injected_inventory_failure')

    def test_exhausted_allocation_budget_cannot_return_a_recipe(self):
        def exhausted(*args):
            return range(0) if args == (60,) else range(*args)

        with patch('flahax.ratio_products.range', side_effect=exhausted, create=True):
            with self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**dict(REQUEST, products=products()))
        self.assertEqual(caught.exception.code, 'ratio_product_fit_failed')
        self.assertIn('iteration budget', str(caught.exception))

    def test_missing_blend_ingredient_chemistry_is_rejected(self):
        from tests.test_ratio_blend_uncertainty import blend_request

        with patch(
            'flahax.ratio_blend_uncertainty.material_inventory',
            return_value={'status': 'unsupported'},
        ):
            with self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**blend_request())
        self.assertEqual(caught.exception.code, 'unsupported_blend_bounds')

    def test_lost_uncertain_nutrient_inventory_cannot_pass(self):
        from flahax.ratio_element_uncertainty import product_vertices
        from tests.test_ratio_element_uncertainty import elemental_options

        def empty(*args):
            group, coordinates, masses = product_vertices(*args)
            return (group[0], *([0.0] * len(v) for v in group[1:])), coordinates, masses

        args = request()
        args['water'] = 'demineralized'
        args['uncertainty'] = elemental_options(args)
        with patch('flahax.ratio_element_uncertainty.product_vertices', side_effect=empty):
            result = plan_ratio_recipe(**args)
        self.assertEqual(result['uncertainty_verification']['status'], 'failed')
        self.assertEqual(result['uncertainty_verification']['failed_checks'], ['empty_ion_group'])

    def test_omitted_blend_dose_cannot_keep_nominal_nutrient_ratios(self):
        from flahax.ratio_blend_uncertainty import blend_vertices
        from tests.test_ratio_blend_uncertainty import blend_request

        def omitted(row, *args):
            row = dict(row, grams=0)
            return blend_vertices(row, *args)

        with patch('flahax.ratio_blend_uncertainty.blend_vertices', side_effect=omitted):
            result = plan_ratio_recipe(**blend_request())
        check = result['uncertainty_verification']
        self.assertNotEqual(check['status'], 'passed')
        self.assertIn('nutrient_ratios', check['failed_checks'])


class SearchFaultInjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nominal = plan_ratio_recipe(**dict(OPTIONS, counted_mmol_l=1))

    def test_disagreeing_final_replay_never_returns_a_selected_recipe(self):
        for fault in ('chemistry', 'stability'):
            calls = 0

            def candidate(**args):
                nonlocal calls
                calls += 1
                result = copy.deepcopy(self.nominal)
                result['stable'] = calls <= 3
                if fault == 'chemistry' and calls > 3:
                    result['rounded_verification']['status'] = 'failed'
                return result

            args = dict(OPTIONS, strength_range=[1, 1.1], scan_points=3)
            if fault == 'stability':
                args['batch_stability'] = {}
            with (
                self.subTest(fault=fault),
                patch('flahax.ratio_search.plan_ratio_recipe', side_effect=candidate),
            ):
                result = search_ratio_recipe(**args)
            self.assertEqual(result['status'], 'incomplete')
            self.assertIsNone(result['recipe'])

    def test_failed_record_checks_and_already_failed_candidates_remain_failed(self):
        candidate = copy.deepcopy(self.nominal)
        candidate.update(stable=False, stock_verification={'status': 'failed', 'failures': []})
        candidate['rounded_verification']['status'] = 'failed'
        with patch('flahax.ratio_search.plan_ratio_recipe', return_value=candidate):
            result = search_ratio_recipe(
                **dict(
                    OPTIONS,
                    strength_range=[1, 2],
                    scan_points=3,
                    batch_stability={},
                    stock_evidence={},
                )
            )
        self.assertEqual(result['status'], 'no_feasible_candidate_found')
        self.assertTrue(all(row['status'] == 'failed' for row in result['evaluations']))
        self.assertTrue(
            any(
                v['kind'] == 'record_check'
                for row in result['evaluations']
                for v in row['constraint_violations']
            )
        )

    def test_incomplete_midpoint_stops_strength_refinement(self):
        def candidate(**args):
            result = copy.deepcopy(self.nominal)
            strength = args['counted_mmol_l']
            result['rounded_verification']['status'] = (
                'passed' if strength == 1 else 'failed' if strength >= 2 else 'incomplete'
            )
            return result

        with patch('flahax.ratio_search.plan_ratio_recipe', side_effect=candidate):
            result = search_ratio_recipe(**dict(OPTIONS, strength_range=[1, 3], scan_points=3))
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['transition_brackets'][0]['width'], 1)

    def test_exhausted_refinement_loop_cannot_claim_a_resolved_transition(self):
        def candidate(**args):
            result = copy.deepcopy(self.nominal)
            result['rounded_verification']['status'] = (
                'passed' if args['counted_mmol_l'] < 2 else 'failed'
            )
            return result

        def exhausted(*args):
            return range(0) if args == (80,) else range(*args)

        with (
            patch('flahax.ratio_search.plan_ratio_recipe', side_effect=candidate),
            patch('flahax.ratio_search.range', side_effect=exhausted, create=True),
        ):
            result = search_ratio_recipe(**dict(OPTIONS, strength_range=[1, 3], scan_points=3))
        self.assertEqual(result['status'], 'incomplete')
        self.assertGreater(result['transition_brackets'][0]['width'], result['strength_tolerance'])
