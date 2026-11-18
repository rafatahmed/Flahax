# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Documented bounds enter the public recipe workflow without inventing
assays.
"""

import copy
import unittest

from flahax import plan_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from flahax.materials import make_grade, resolve_material
from tests.test_ratio_analysis_uncertainty import request
from tests.test_ratio_element_uncertainty import elemental_options
from tests.test_ratio_grade_uncertainty import with_grade


def documented_request():
    req = with_grade(request())
    grade = req['products'][0]['product']['grade']
    for band in grade['analysis'].values():
        band.update(minimum=band['typical'] * 0.995, maximum=band['typical'] * 1.005)
    req['uncertainty'] = elemental_options(req)
    name = req['products'][0]['product']['name']
    req['uncertainty']['product_element_factors'][name] = {'source': 'grade'}
    return req, name


class DocumentedAssayTests(unittest.TestCase):
    def test_document_impurity_limits_are_not_silently_treated_as_zero(self):
        req, _ = documented_request()
        req['products'][0]['product']['grade']['impurity_limits'] = {'Na': 0.1}
        with self.assertRaises(DeliveryError) as caught:
            plan_ratio_recipe(**req)
        self.assertEqual(caught.exception.code, 'unsupported_assay_impurity_bounds')

    def test_complete_grade_bounds_reach_recipe_and_keep_provenance(self):
        req, name = documented_request()
        original = copy.deepcopy(req)
        result = plan_ratio_recipe(**req)
        check = result['uncertainty_verification']
        self.assertEqual(req, original)
        self.assertEqual(check['status'], 'passed')
        self.assertAlmostEqual(
            check['assumptions']['product_element_factors'][name]['P'][0], 0.995
        )
        self.assertAlmostEqual(
            check['assumptions']['product_element_factors'][name]['P'][1], 1.005
        )
        evidence = check['assay_bound_sources'][name]
        self.assertEqual(evidence['grade'], req['products'][0]['product']['grade'])
        self.assertEqual(evidence['units'], 'elemental_mass_percent')
        self.assertFalse(result['verified'])

    def test_linked_lot_uncertainty_reaches_factors_without_changing_nominal_recipe(self):
        req, name = documented_request()
        product = req['products'][0]['product']
        lot = dict(
            lot_id='illustrative-lot',
            grade_id=product['grade']['grade_id'],
            document=copy.deepcopy(product['grade']['document']),
            measured={k: v * 1.002 for k, v in product['elements'].items()},
            uncertainty={k: v * 0.003 for k, v in product['elements'].items()},
        )
        req['uncertainty']['product_element_factors'][name] = {'source': 'lot', 'lot': lot}
        original = copy.deepcopy(req)
        result = plan_ratio_recipe(**req)
        c = result['uncertainty_verification']
        self.assertEqual(req, original)
        self.assertEqual(c['status'], 'passed')
        self.assertAlmostEqual(c['assumptions']['product_element_factors'][name]['P'][0], 0.999)
        self.assertAlmostEqual(c['assumptions']['product_element_factors'][name]['P'][1], 1.005)
        self.assertEqual(c['assay_bound_sources'][name]['lot'], lot)
        self.assertEqual(result['ingredients'][0]['product']['elements'], product['elements'])

    def test_lot_cannot_silently_add_an_unmodeled_element(self):
        req, name = documented_request()
        product = req['products'][0]['product']
        lot = dict(
            lot_id='extra-element',
            grade_id=product['grade']['grade_id'],
            document=copy.deepcopy(product['grade']['document']),
            measured=dict(product['elements'], N_NO3=0.1),
            uncertainty={k: 0 for k in (*product['elements'], 'N_NO3')},
        )
        req['uncertainty']['product_element_factors'][name] = {'source': 'lot', 'lot': lot}
        with self.assertRaises(DeliveryError) as caught:
            plan_ratio_recipe(**req)
        self.assertEqual(caught.exception.code, 'assay_document_element_mismatch')

    def test_oxide_bounds_preserve_units_and_source_conversion(self):
        req, name = documented_request()
        product = req['products'][0]['product']
        grade = product['grade']
        grade['analysis'].pop('P')
        grade['analysis']['P2O5'] = dict(minimum=25, typical=25.25, maximum=25.5)
        product['elements'] = resolve_material(name, grade=make_grade(grade)).record['elements']
        check = plan_ratio_recipe(**req)['uncertainty_verification']
        factors = check['assumptions']['product_element_factors'][name]['P']
        self.assertAlmostEqual(factors[0], 100 / 101)
        self.assertAlmostEqual(factors[1], 102 / 101)
        evidence = check['assay_bound_sources'][name]
        self.assertEqual(evidence['oxide_conversions']['P2O5']['element'], 'P')
        self.assertEqual(evidence['grade']['analysis']['P2O5']['minimum'], 25)

    def test_incomplete_grade_bounds_are_not_filled_from_theory(self):
        for missing in ('minimum', 'maximum', 'both'):
            req, _ = documented_request()
            band = req['products'][0]['product']['grade']['analysis']['P']
            for key in ('minimum', 'maximum') if missing == 'both' else (missing,):
                band.pop(key)
            with self.subTest(missing=missing), self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**req)
            self.assertEqual(caught.exception.code, 'incomplete_assay_bounds')

    def test_lot_requires_complete_uncertainty_and_correct_linkage(self):
        for problem in ('uncertainty', 'linkage'):
            req, name = documented_request()
            product = req['products'][0]['product']
            lot = dict(
                lot_id='lot',
                grade_id=product['grade']['grade_id'],
                document=copy.deepcopy(product['grade']['document']),
                measured=copy.deepcopy(product['elements']),
                uncertainty={k: 0 for k in product['elements']},
            )
            if problem == 'uncertainty':
                lot['uncertainty'].pop('P')
            else:
                lot['grade_id'] = 'different-grade'
            req['uncertainty']['product_element_factors'][name] = {'source': 'lot', 'lot': lot}
            with self.subTest(problem=problem), self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**req)
            self.assertEqual(
                caught.exception.code,
                'incomplete_assay_bounds' if problem == 'uncertainty' else 'material_mismatch',
            )
