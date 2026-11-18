# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Explicit nutrient ceilings apply to rounded and uncertain final
inventories.
"""

import unittest

from flahax import plan_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from tests.test_ratio_analysis_uncertainty import request
from tests.test_ratio_element_uncertainty import elemental_options


class NutrientLimitTests(unittest.TestCase):
    def test_ammonium_limit_requires_explicit_source_water_ammonium(self):
        req = request()
        req['maximum_concentrations']['N_NH4'] = 0.1
        with self.assertRaises(DeliveryError) as caught:
            plan_ratio_recipe(**req)
        self.assertEqual(caught.exception.code, 'missing_water_ammonium')
        req['water']['totals_mol_kg'] = None
        with self.assertRaises(DeliveryError):
            plan_ratio_recipe(**req)

    def test_physical_source_quantity_bounds_ammonium(self):
        from tests.test_ratio_physical_uncertainty import physical_request

        req = physical_request()
        req['water']['totals_mol_kg']['NH4+'] = 0.00001
        req['uncertainty']['physical_preparation']['source_water_mass_kg'] = [0.1, 0.2]
        req['maximum_concentrations']['N_NH4'] = 0.002
        c = plan_ratio_recipe(**req)['uncertainty_verification']
        self.assertAlmostEqual(c['elemental_mg_l_ranges']['N_NH4'][1], 0.00280134)
        self.assertIn('nutrient_limits', c['failed_checks'])

    def test_fertilizer_ammonium_uncertainty_counts_as_nitrogen(self):
        from flahax.engine import load_library

        req = request()
        req['water']['totals_mol_kg']['NH4+'] = 0
        product = next(
            p for p in load_library()['salts'] if p['name'] == 'Calcium Nitrate (ag grade)'
        )
        req['products'][1] = dict(
            product=dict(product, name='Illustrative calcium nitrate'),
            role='fertilizer',
            solvent_fraction=0,
        )
        nominal = plan_ratio_recipe(**req)
        req['maximum_concentrations']['N_NH4'] = nominal['elemental_mg_l']['N_NH4'] * 1.001
        opts = elemental_options(req)
        opts['product_element_factors']['Illustrative calcium nitrate']['N_NH4'] = [1, 1.01]
        result = plan_ratio_recipe(**dict(req, uncertainty=opts))
        c = result['uncertainty_verification']
        self.assertIn('nutrient_limits', c['failed_checks'])
        self.assertAlmostEqual(
            c['elemental_mg_l_ranges']['N_NH4'][1],
            result['rounded_verification']['elemental_mg_l']['N_NH4'] * 1.01,
        )

    def test_pure_recipe_cannot_ignore_nominal_nutrient_ceiling(self):
        from tests.test_ratio_recipe import REQUEST

        with self.assertRaises(DeliveryError) as caught:
            plan_ratio_recipe(**dict(REQUEST, maximum_concentrations={'K': 0}))
        self.assertEqual(caught.exception.code, 'ratio_limit_exceeded')

    def test_legacy_pure_uncertainty_checks_expanded_limits(self):
        from tests.test_ratio_search import OPTIONS
        from tests.test_ratio_uncertainty import UNCERTAINTY

        req = dict(OPTIONS, counted_mmol_l=1.3)
        baseline = plan_ratio_recipe(**req)
        req['maximum_concentrations'] = {'P': baseline['elemental_mg_l']['P'] * 1.001}
        req['uncertainty'] = dict(UNCERTAINTY, weighing_error_g=0, purity_fraction=[1, 1])
        c = plan_ratio_recipe(**req)['uncertainty_verification']
        self.assertIn('nutrient_limits', c['failed_checks'])

    def test_source_ammonium_is_bounded_as_nitrogen_outside_six_count(self):
        req = request()
        req['water']['totals_mol_kg']['NH4+'] = 0.00001
        req['maximum_concentrations']['N_NH4'] = 0.00145
        opts = elemental_options(req)
        opts['water_relative_error'] = 0.1
        result = plan_ratio_recipe(**dict(req, uncertainty=opts))
        self.assertAlmostEqual(result['elemental_mg_l']['N_NH4'], 0.00140067)
        self.assertAlmostEqual(sum(result['analytical_mmol_l'].values()), 1.3)
        c = result['uncertainty_verification']
        self.assertAlmostEqual(c['elemental_mg_l_ranges']['N_NH4'][1], 0.001540737)
        self.assertIn('nutrient_limits', c['failed_checks'])

    def test_phosphate_limit_can_fail_only_after_assay_uncertainty(self):
        req = request()
        base = plan_ratio_recipe(**req)
        req['maximum_concentrations']['P'] = base['elemental_mg_l']['P'] * 1.001
        opts = elemental_options(req)
        opts['product_element_factors'][req['products'][0]['product']['name']]['P'] = [1, 1.01]
        result = plan_ratio_recipe(**dict(req, uncertainty=opts))
        self.assertTrue(result['rounded_verification']['limit_assessment']['passed'])
        c = result['uncertainty_verification']
        self.assertIn('nutrient_limits', c['failed_checks'])
        self.assertGreater(c['elemental_mg_l_ranges']['P'][1], req['maximum_concentrations']['P'])
