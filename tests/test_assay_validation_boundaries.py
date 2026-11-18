# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Public recipe validation rejects incomplete assay and physical
uncertainty bounds.
"""

import unittest

from flahax import plan_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from tests.test_ratio_analysis_uncertainty import bounds, request
from tests.test_ratio_blend_uncertainty import blend_request
from tests.test_ratio_documented_assays import documented_request
from tests.test_ratio_physical_uncertainty import physical_request


class AssayValidationBoundaryTests(unittest.TestCase):
    def test_analysis_contract_requires_complete_and_physical_inputs(self):
        for change in ('missing', 'volume', 'budget', 'water_ph', 'water_error', 'no_products'):
            req = request()
            req['uncertainty'] = bounds(req)
            if change == 'missing':
                req['uncertainty'].pop('max_scenarios')
            elif change == 'volume':
                req['volume_litres'] = False
            elif change == 'budget':
                req['uncertainty']['max_scenarios'] = 0
            elif change == 'water_ph':
                req['uncertainty']['water_ph_error'] = 8
            elif change == 'water_error':
                req['uncertainty']['water_relative_error'] = 1.1
            else:
                req['products'] = None
            with self.subTest(change=change), self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**req)
            self.assertEqual(caught.exception.code, 'invalid_analysis_uncertainty')

    def test_demineralized_water_has_no_analysis_uncertainty_contribution(self):
        req = request()
        req['water'] = 'demineralized'
        options = bounds(req)
        options['max_scenarios'] = 1
        result = plan_ratio_recipe(**dict(req, uncertainty=options))
        check = result['uncertainty_verification']
        self.assertEqual(check['status'], 'passed')
        self.assertFalse(any(name.startswith('water.') for name in check['dimensions']))

    def test_analysis_weighing_interval_cannot_include_negative_doses(self):
        req = request()
        options = bounds(req)
        options['weighing_error_g'] = 10
        result = plan_ratio_recipe(**dict(req, uncertainty=options))
        self.assertEqual(
            result['uncertainty_verification']['failed_checks'],
            ['weighing_interval_includes_negative_mass'],
        )

    def test_rounding_to_empty_ion_groups_cannot_pass_analysis(self):
        req = request()
        req['water'] = 'demineralized'
        req['mass_decimals'] = 0
        result = plan_ratio_recipe(**dict(req, uncertainty=bounds(req)))
        self.assertEqual(result['uncertainty_verification']['failed_checks'], ['nominal_recipe'])

    def test_volume_bound_cannot_leave_less_water_than_supplied_solvent(self):
        req = request()
        options = bounds(req)
        options['volume_error_litres'] = 9.8999
        result = plan_ratio_recipe(**dict(req, uncertainty=options))
        self.assertNotEqual(result['uncertainty_verification']['status'], 'passed')
        self.assertIn('solvent_inventory', result['uncertainty_verification']['failed_checks'])

    def test_assay_document_selectors_require_a_matching_document(self):
        for change, code in (
            ('not_mapping', 'invalid_analysis_uncertainty'),
            ('unknown_source', 'invalid_assay_document_source'),
            ('missing_grade', 'missing_assay_document'),
            ('blend_grade', 'unsupported_elemental_grade'),
        ):
            req, name = documented_request()
            if change == 'not_mapping':
                req['uncertainty']['product_element_factors'] = []
            elif change == 'unknown_source':
                req['uncertainty']['product_element_factors'][name] = {'source': 'unspecified'}
            elif change == 'missing_grade':
                req['products'][0]['product'].pop('grade')
            else:
                req = blend_request()
                req['uncertainty']['product_element_factors']['Potassium Nitrate'] = {
                    'source': 'grade'
                }
            with self.subTest(change=change), self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**req)
            self.assertEqual(caught.exception.code, code)

    def test_physical_intervals_require_nominal_containment(self):
        for change, code in (
            ('water', 'unsupported_physical_uncertainty'),
            ('missing', 'invalid_physical_uncertainty'),
            ('unordered', 'invalid_physical_uncertainty'),
            ('fraction', 'invalid_physical_uncertainty'),
            ('source_mass', 'invalid_physical_uncertainty'),
            ('product_solvent', 'invalid_physical_uncertainty'),
        ):
            req = physical_request()
            physical = req['uncertainty']['physical_preparation']
            if change == 'water':
                req['water'] = 'demineralized'
            elif change == 'missing':
                physical.pop('solution_density_kg_l')
            elif change == 'unordered':
                physical['solution_density_kg_l'] = [1.1, 1]
            elif change == 'fraction':
                physical['source_water_solvent_fraction'] = [0.9, 1.1]
            elif change == 'source_mass':
                physical['source_water_mass_kg'] = [0.2, 0.3]
            else:
                physical['product_solvent_fractions'][req['products'][0]['product']['name']] = [
                    0.1,
                    0.2,
                ]
            with self.subTest(change=change), self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**req)
            self.assertEqual(caught.exception.code, code)

    def test_blend_intervals_require_supported_ingredients_and_complete_bounds(self):
        for change, code in (
            ('impurities', 'unsupported_blend_bounds'),
            ('extra', 'invalid_blend_bounds'),
            ('missing', 'invalid_blend_bounds'),
            ('unordered', 'invalid_blend_bounds'),
        ):
            req = blend_request()
            entry = req['uncertainty']['product_element_factors']['Potassium Nitrate']
            if change == 'impurities':
                req['products'][4]['product']['grade']['impurity_limits'] = {'Na': 0.1}
            elif change == 'extra':
                entry['unexpected'] = 1
            elif change == 'missing':
                entry['mass_fraction_bounds'] = {}
            else:
                entry['mass_fraction_bounds']['idn-potassium-nitrate'] = [0.5, 0.49]
            with self.subTest(change=change), self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**req)
            self.assertEqual(caught.exception.code, code)
