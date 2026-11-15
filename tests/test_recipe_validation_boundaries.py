# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Public recipe requests reject unsupported or inconsistent preparation inputs."""

import math
import unittest

from flahax import plan_ratio_recipe, search_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from tests.test_ratio_products import products
from tests.test_ratio_recipe import REQUEST
from tests.test_ratio_search import OPTIONS
from tests.test_ratio_stocks import STOCKS, UNCERTAINTY
from tests.test_ratio_water import water


class RecipeValidationBoundaryTests(unittest.TestCase):
    def test_adjacent_float_search_bounds_reuse_identical_candidates(self):
        result = search_ratio_recipe(
            **dict(OPTIONS, strength_range=[1, math.nextafter(1, math.inf)], scan_points=3)
        )
        self.assertEqual(result['status'], 'found')
        self.assertEqual(result['evaluation_count'], 2)
        self.assertTrue(result['search_cap_reached'])

    def test_unrepresentable_strength_tolerance_reports_incomplete(self):
        result = search_ratio_recipe(
            **dict(OPTIONS, strength_range=[1, 3], scan_points=3, strength_tolerance=1e-30)
        )
        self.assertEqual(result['status'], 'incomplete')
        self.assertTrue(
            any(
                row['width'] > result['strength_tolerance']
                for row in result['transition_brackets']
            )
        )

    def test_command_requires_all_recipe_fields(self):
        from flahax.planning_cli import execute

        with self.assertRaises(DeliveryError) as caught:
            execute('ratio', {})
        self.assertEqual(caught.exception.code, 'missing_field')

    def test_preparation_modes_require_compatible_inputs(self):
        dry = dict(UNCERTAINTY, weighing_error_g=0.001, purity_fraction=[0.99, 1])
        cases = (
            (
                {'ph_reagents': ['HNO3'], 'uncertainty': dry},
                'unsupported_ratio_reagent_uncertainty',
            ),
            ({'batch_stability': {}}, 'missing_stock_dosing'),
            ({'stock_evidence': {}}, 'missing_stock_dosing'),
            (
                {'stock_dosing': STOCKS, 'uncertainty': {'mode': 'water_product'}},
                'unsupported_ratio_product_uncertainty',
            ),
            ({'uncertainty': dry}, 'missing_ph_range'),
            ({'stock_dosing': {}}, 'invalid_stock_dosing'),
            ({'ph_range': [6.3]}, 'invalid_ph_range'),
        )
        for changes, code in cases:
            with self.subTest(changes=changes), self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**dict(REQUEST, **changes))
            self.assertEqual(caught.exception.code, code)

    def test_water_records_reject_unknown_fields_and_blank_identifiers(self):
        for source in (dict(water(), unknown=1), dict(water(), analysis_id=' ')):
            with self.subTest(source=source), self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**dict(REQUEST, water=source))
            self.assertEqual(caught.exception.code, 'invalid_ratio_water')

    def test_product_records_require_names_and_possible_mass_fractions(self):
        cases = [[], 'products']
        for change in (
            {'product': {'name': ' '}},
            {'solvent_fraction': -0.1},
            {'solvent_fraction': 1},
        ):
            supplied = products()
            supplied[0].update(change)
            cases.append(supplied)
        for supplied in cases:
            with self.subTest(supplied=supplied), self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**dict(REQUEST, products=supplied))
            self.assertEqual(caught.exception.code, 'invalid_ratio_products')

    def test_limits_reject_unknown_units_and_source_water_exceedance(self):
        for limits in ([], {'NO3': 6}):
            with self.subTest(limits=limits), self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**dict(REQUEST, maximum_concentrations=limits))
            self.assertEqual(caught.exception.code, 'invalid_ratio_limits')
        with self.assertRaises(DeliveryError) as caught:
            plan_ratio_recipe(
                **dict(
                    REQUEST, products=products(), water=water(), maximum_concentrations={'Na': 5}
                )
            )
        self.assertEqual(caught.exception.code, 'ratio_limit_exceeded')

    def test_no_product_can_supply_a_positive_target_with_zero_headroom(self):
        with self.assertRaises(DeliveryError) as caught:
            plan_ratio_recipe(
                **dict(
                    REQUEST, products=products(), maximum_concentrations={'K': 0, 'Ca': 0, 'Mg': 0}
                )
            )
        self.assertEqual(caught.exception.code, 'ratio_product_fit_failed')

    def test_extreme_ph_without_enough_nutrients_has_no_charge_solution(self):
        with self.assertRaises(DeliveryError) as caught:
            plan_ratio_recipe(**dict(REQUEST, ph=2, counted_mmol_l=0.001))
        self.assertEqual(caught.exception.code, 'ratio_infeasible')

    def test_search_rejects_malformed_and_conflicting_requests(self):
        for changes, code in (
            ({'strength_range': [1]}, 'invalid_strength_range'),
            ({'counted_mmol_l': 1}, 'duplicate_strength'),
            ({'water': 'unknown'}, 'invalid_ratio_water'),
        ):
            args = dict(OPTIONS, strength_range=[1, 2])
            args.update(changes)
            with self.subTest(changes=changes), self.assertRaises(DeliveryError) as caught:
                search_ratio_recipe(**args)
            self.assertEqual(caught.exception.code, code)

    def test_weighing_interval_cannot_include_negative_doses(self):
        result = plan_ratio_recipe(
            **dict(
                OPTIONS,
                counted_mmol_l=1,
                uncertainty=dict(UNCERTAINTY, weighing_error_g=1, purity_fraction=[0.99, 1]),
            )
        )
        self.assertEqual(result['uncertainty_verification']['status'], 'failed')
        self.assertEqual(
            result['uncertainty_verification']['failed_checks'],
            ['weighing_interval_includes_negative_mass'],
        )

    def test_search_reports_rounding_and_ph_failures(self):
        result = search_ratio_recipe(
            **dict(OPTIONS, strength_range=[1, 1.1], scan_points=3, mass_decimals=0)
        )
        self.assertEqual(result['status'], 'incomplete')
        kinds = {
            row['kind']
            for evaluation in result['evaluations']
            for row in evaluation['constraint_violations']
        }
        self.assertIn('rounding', kinds)
        self.assertIn('ph_interval', kinds)

    def test_empty_rounded_ion_groups_cannot_pass_preparation_uncertainty(self):
        result = plan_ratio_recipe(
            **dict(
                OPTIONS,
                counted_mmol_l=1,
                mass_decimals=0,
                uncertainty=dict(UNCERTAINTY, weighing_error_g=0, purity_fraction=[1, 1]),
            )
        )
        self.assertEqual(result['uncertainty_verification']['failed_checks'], ['nominal_recipe'])

    def test_dosing_bounds_that_allow_all_zero_ingredients_cannot_pass(self):
        nominal = plan_ratio_recipe(**dict(OPTIONS, counted_mmol_l=1))
        stocks = dict(
            STOCKS,
            dose_error_ml=1,
            concentration_relative_error=0,
            concentrations_g_l={
                row['formula']: row['grams'] * 1000 for row in nominal['ingredients']
            },
        )
        result = plan_ratio_recipe(
            **dict(OPTIONS, counted_mmol_l=1, stock_dosing=stocks, uncertainty=UNCERTAINTY)
        )
        self.assertEqual(result['uncertainty_verification']['failed_checks'], ['empty_ion_group'])
