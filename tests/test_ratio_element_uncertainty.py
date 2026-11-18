# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent label assays must not silently remain correlated or
bypass chemistry.
"""

import copy
import json
from pathlib import Path
import unittest

from flahax import plan_ratio_recipe, search_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from tests.test_ratio_analysis_uncertainty import request, bounds


def elemental_options(req, low=1.0):
    opts = bounds(req)
    opts['mode'] = 'water_product_elemental'
    opts.pop('product_assay_factors')
    opts['product_element_factors'] = {
        p['product']['name']: {k: [low, 1.0] for k in p['product']['elements']}
        for p in req['products']
    }
    return opts


class ElementAssayUncertaintyTests(unittest.TestCase):
    def test_fixed_element_assays_reproduce_nominal_rounded_chemistry(self):
        req = request()
        original = copy.deepcopy(req)
        result = plan_ratio_recipe(**dict(req, uncertainty=elemental_options(req)))
        c = result['uncertainty_verification']
        self.assertEqual(req, original)
        self.assertEqual(c['status'], 'passed')
        self.assertEqual(c['scenario_count'], 1)
        for phase, row in result['rounded_verification']['phase_maxima'].items():
            self.assertAlmostEqual(row['si'], c['phase_maxima'][phase]['si'])

    def test_nitrate_assay_moves_without_potassium_and_reconciles_chemistry(self):
        req = request()
        opts = elemental_options(req)
        name = req['products'][4]['product']['name']
        opts['product_element_factors'][name]['N_NO3'] = [0.8, 1.0]
        result = plan_ratio_recipe(**dict(req, uncertainty=opts))
        c = result['uncertainty_verification']
        self.assertEqual(c['status'], 'failed')
        self.assertIn('nutrient_ratios', c['failed_checks'])
        for low, high in c['ratio_percent_ranges'][:3]:
            self.assertAlmostEqual(low, high, places=9)
        self.assertGreater(c['ratio_percent_ranges'][3][1] - c['ratio_percent_ranges'][3][0], 0.1)
        self.assertGreater(c['maximum_abs_assay_chemistry_difference_mg_l']['K'], 0)

    def test_ph_reagent_elements_and_chloride_have_independent_dimensions(self):
        req = request()
        opts = elemental_options(req, 0.99)
        result = plan_ratio_recipe(**dict(req, uncertainty=opts))
        c = result['uncertainty_verification']
        base = req['products'][-1]['product']['name']
        nitrate = req['products'][4]['product']['name']
        self.assertIn('assay.' + base + '.K', c['dimensions'])
        self.assertIn('assay.' + base + '.Na', c['dimensions'])
        self.assertIn('assay.' + nitrate + '.Cl', c['dimensions'])
        self.assertFalse(c['continuous_chemistry_extrema_proved'])

    def test_missing_bounds_unknown_elements_and_derived_counterions_fail_closed(self):
        req = request()
        name = req['products'][0]['product']['name']
        for change in ('missing_product', 'missing_element', 'extra_element', 'invalid_factor'):
            opts = elemental_options(req)
            if change == 'missing_product':
                opts['product_element_factors'].pop(name)
            if change == 'missing_element':
                opts['product_element_factors'][name].pop('K')
            if change == 'extra_element':
                opts['product_element_factors'][name]['Na'] = [0.99, 1]
            if change == 'invalid_factor':
                opts['product_element_factors'][name]['K'] = [1, 0.99]
            with self.subTest(change=change), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**dict(req, uncertainty=opts))
        req['products'][4]['product']['elements'].pop('Cl')
        with self.assertRaises(DeliveryError) as caught:
            plan_ratio_recipe(**dict(req, uncertainty=elemental_options(req)))
        self.assertEqual(caught.exception.code, 'unsupported_elemental_counterion_bounds')

    def test_product_mass_correlation_is_preserved_in_analytical_bounds(self):
        from flahax.ratio_analysis_uncertainty import _ratio_extreme

        # Four feasible dose/assay vertices; the numerator and
        # denominator share dose.
        groups = [
            (
                'one',
                [1, 1, 0, 0, 0, 0, 0, 0],
                [2, 2, 0, 0, 0, 0, 0, 0],
                [1, 2, 0, 0, 0, 0, 0, 0],
                [2, 4, 0, 0, 0, 0, 0, 0],
            )
        ]
        low, _ = _ratio_extreme(groups, 0, 0, False)
        high, _ = _ratio_extreme(groups, 0, 0, True)
        self.assertAlmostEqual(low, 20.0)
        self.assertAlmostEqual(high, 100 / 3)

    def test_rounded_ten_litre_case_uses_prior_bounds_without_refitting(self):
        req = json.loads(Path('examples/steiner-commercial-uncertainty.json').read_text())
        nominal = plan_ratio_recipe(**dict(req, uncertainty=None))
        opts = elemental_options(req, 0.99)
        for key in (
            'weighing_error_g',
            'volume_error_litres',
            'water_relative_error',
            'water_ph_error',
            'max_scenarios',
        ):
            opts[key] = req['uncertainty'][key]
        req['uncertainty'] = opts
        result = plan_ratio_recipe(**req)
        self.assertEqual(
            result['rounded_verification']['ingredients'],
            nominal['rounded_verification']['ingredients'],
        )
        c = result['uncertainty_verification']
        self.assertLessEqual(c['elemental_mg_l_ranges']['Na'][1], 10.0)
        self.assertLessEqual(c['elemental_mg_l_ranges']['Cl'][1], 20.0)
        self.assertEqual(c['scenario_count'], 128)
        self.assertEqual(c['status'], 'passed')
        self.assertLessEqual(c['worst_ratio_relative_error'], 0.01)
        self.assertTrue(c['all_scenario_ph_in_range'])
        for phase in c['phase_maxima'].values():
            self.assertLess(phase['si'], -0.3)
        self.assertFalse(result['verified'])

    def test_failed_elemental_uncertainty_is_not_accepted_by_search(self):
        req = request()
        opts = elemental_options(req)
        opts['product_element_factors'][req['products'][-1]['product']['name']]['K'] = [0.1, 1]
        req.pop('counted_mmol_l')
        result = search_ratio_recipe(
            **req, strength_range=[1.2, 1.3], scan_points=3, uncertainty=opts
        )
        self.assertIsNone(result['recipe'])

    def test_independent_assay_and_mass_bounds_can_fail_sodium_ceiling(self):
        req = request()
        nominal = plan_ratio_recipe(**req)
        req['maximum_concentrations']['Na'] = nominal['elemental_mg_l']['Na'] * 1.00001
        opts = elemental_options(req, 0.99)
        opts['weighing_error_g'] = 0.001
        # Water and final volume are fixed here; only independently
        # bounded products change.
        result = plan_ratio_recipe(**dict(req, uncertainty=opts))
        check = result['uncertainty_verification']
        self.assertIn('sodium_chloride_limits', check['failed_checks'])
        water_na = 0.0003 * 0.1 * 22.989769 * 1000
        product_na = sum(
            (row['grams'] + 0.001) * row['product']['elements'].get('Na', 0) * 10
            for row in nominal['rounded_verification']['ingredients']
        )
        self.assertAlmostEqual(
            check['elemental_mg_l_ranges']['Na'][1], (water_na + product_na) / 10
        )
