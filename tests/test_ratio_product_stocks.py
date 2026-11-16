# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Volumetric product delivery through the public recipe workflow."""

from copy import deepcopy
import unittest

from flahax import plan_ratio_recipe, search_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from tests.ratio_allocation_cases import base_request


def stock_request():
    req = base_request(1.2)
    names = [p['product']['name'] for p in req['products']]
    req['stock_dosing'] = dict(
        basis='product_mass',
        concentrations_g_l=dict.fromkeys(names, 100),
        concentration_relative_error=0,
        dose_error_ml=0,
        dose_decimals=4,
        density_kg_l={name: [0.999, 1.001] for name in names},
        carrier='demineralized_water',
    )
    return req


class ProductStockTests(unittest.TestCase):
    def test_unused_product_has_no_dispensing_or_weighing_event(self):
        req = stock_request()
        name = 'Unused sodium chloride'
        req['products'].append(
            dict(
                product=dict(name=name, formula='NaCl', elements={'Na': 0.1, 'Cl': 0.1542117533}),
                role='fertilizer',
                solvent_fraction=0.98,
            )
        )
        opts = req['uncertainty']
        opts['max_scenarios'] = 1
        opts['product_element_factors'][name] = {'Na': [0.99, 1], 'Cl': [0.99, 1]}
        opts['physical_preparation']['product_solvent_fractions'][name] = [0.9799, 0.98]
        req['stock_dosing']['concentrations_g_l'][name] = 100
        req['stock_dosing']['density_kg_l'][name] = [0.999, 1.001]
        result = plan_ratio_recipe(**req)
        stock = result['stock_delivery']['stocks'][-1]
        self.assertEqual(stock['dose_ml'], 0)
        self.assertEqual(stock['effective_grams'], 0)
        self.assertEqual(stock['minimum_carrier_mass_kg'], 0)
        self.assertNotIn('mass.' + name, result['uncertainty_verification']['dimensions'])

    def test_product_mass_cannot_exceed_stock_mass(self):
        req = stock_request()
        name = req['products'][0]['product']['name']
        req['stock_dosing']['concentrations_g_l'][name] = 1001
        with self.assertRaisesRegex(DeliveryError, 'Product mass exceeds'):
            plan_ratio_recipe(**req)

    def test_search_reports_infeasible_carrier_without_accepting_a_recipe(self):
        req = stock_request()
        del req['counted_mmol_l']
        stocks = req['stock_dosing']
        stocks['concentrations_g_l'] = dict.fromkeys(stocks['concentrations_g_l'], 1000)
        stocks['density_kg_l'] = {name: [1, 1] for name in stocks['density_kg_l']}
        result = search_ratio_recipe(**req, strength_range=[1.1, 1.2], scan_points=3)
        self.assertIsNone(result['recipe'])
        self.assertEqual(len(result['evaluations']), 3)
        for row in result['evaluations']:
            self.assertEqual(row['status'], 'failed')
            self.assertEqual(row['error_code'], 'ratio_stock_carrier_infeasible')

    def test_product_names_do_not_change_stock_parameter_validation(self):
        req = stock_request()
        old = req['products'][0]['product']['name']
        name = 'dose_error_ml'
        req['products'][0]['product']['name'] = name
        mappings = [
            req['stock_dosing']['concentrations_g_l'],
            req['stock_dosing']['density_kg_l'],
            req['uncertainty']['product_element_factors'],
            req['uncertainty']['physical_preparation']['product_solvent_fractions'],
        ]
        for mapping in mappings:
            mapping[name] = mapping.pop(old)
        req['uncertainty']['max_scenarios'] = 1
        result = plan_ratio_recipe(**req)
        self.assertEqual(result['rounded_verification']['status'], 'passed')
        req['stock_dosing']['concentrations_g_l'] = {}
        with self.assertRaisesRegex(DeliveryError, 'every declared stock'):
            plan_ratio_recipe(**req)

    def test_uncertain_delivery_preserves_reserve_and_checks_every_phase(self):
        req = stock_request()
        req['stock_dosing'].update(concentration_relative_error=0.0001, dose_error_ml=0.001)
        result = plan_ratio_recipe(**req)
        check = result['uncertainty_verification']
        self.assertEqual(check['status'], 'passed', check['failed_checks'])
        self.assertEqual(check['scenario_count'], 128)
        self.assertFalse(check['continuous_chemistry_extrema_proved'])
        self.assertLessEqual(check['worst_ratio_relative_error'], 0.01)
        self.assertLessEqual(check['worst_concentration_relative_error'], 0.02)
        self.assertTrue(check['all_scenario_ph_in_range'])
        self.assertEqual(set(check['phase_maxima']), {'CaHPO4:2H2O', 'CaHPO4', 'Hydroxylapatite'})
        for phase in check['phase_maxima'].values():
            self.assertLess(phase['si'], -0.3000001)
        for key, ceiling in req['maximum_concentrations'].items():
            self.assertLessEqual(check['elemental_mg_l_ranges'][key][1], ceiling * 0.95)
        for row in result['stock_delivery']['stocks']:
            lo, hi = check['dimensions']['mass.' + row['name']]
            self.assertLess(lo, row['effective_grams'] - 0.001)
            self.assertGreater(hi, row['effective_grams'] + 0.001)
        self.assertFalse(result['verified'])
        self.assertFalse(result['stable'])

    def test_incomplete_or_ambiguous_stock_contracts_are_rejected(self):
        original = stock_request()
        for change in (
            {'basis': 'active_compound'},
            {'carrier': 'source_water'},
            {'density_kg_l': {}},
            {'density_kg_l': None},
            {'concentration_relative_error': 1},
            {'concentrations_g_l': {}},
            {'dose_decimals': True},
            {'dose_error_ml': -1},
        ):
            req = deepcopy(original)
            req['stock_dosing'].update(change)
            with self.subTest(change=change), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**req)
        for pair in ([0, 1], [1.1, 1], [True, 1], [float('nan'), 1], [1], 'one'):
            req = deepcopy(original)
            name = req['products'][0]['product']['name']
            req['stock_dosing']['density_kg_l'][name] = pair
            with self.subTest(pair=pair), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**req)
        for missing in ('basis', 'density_kg_l', 'carrier'):
            req = deepcopy(original)
            del req['stock_dosing'][missing]
            with self.subTest(missing=missing), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**req)
        for field in ('stock_evidence', 'batch_stability'):
            req = deepcopy(original)
            req[field] = {}
            with self.subTest(field=field), self.assertRaises(DeliveryError) as caught:
                plan_ratio_recipe(**req)
            self.assertEqual(caught.exception.code, 'unsupported_product_stock_evidence')

    def test_stock_density_and_source_water_can_exhaust_makeup_mass(self):
        req = stock_request()
        req['stock_dosing']['density_kg_l'] = {
            name: [100, 100] for name in req['stock_dosing']['density_kg_l']
        }
        result = plan_ratio_recipe(**req)
        check = result['uncertainty_verification']
        self.assertEqual(check['status'], 'failed')
        self.assertIn('physical_mass_balance', check['failed_checks'])

    def test_coarse_stock_doses_cannot_pass_nominal_replay(self):
        req = stock_request()
        req['stock_dosing']['dose_decimals'] = 0
        result = plan_ratio_recipe(**req)
        self.assertEqual(result['rounded_verification']['status'], 'failed')
        self.assertEqual(result['uncertainty_verification']['failed_checks'], ['nominal_recipe'])

    def test_insufficient_chemistry_budget_stays_incomplete(self):
        req = stock_request()
        req['uncertainty']['max_scenarios'] = 1
        check = plan_ratio_recipe(**req)['uncertainty_verification']
        self.assertEqual(check['status'], 'incomplete')
        self.assertIn('insufficient_sampling_budget', check['failed_checks'])

    def test_stock_mass_must_cover_product_and_weighing_allowance(self):
        req = stock_request()
        stocks = req['stock_dosing']
        stocks['concentrations_g_l'] = dict.fromkeys(stocks['concentrations_g_l'], 1000)
        stocks['density_kg_l'] = {name: [1, 1] for name in stocks['density_kg_l']}
        with self.assertRaises(DeliveryError) as caught:
            plan_ratio_recipe(**req)
        self.assertEqual(caught.exception.code, 'ratio_stock_carrier_infeasible')

    def test_volumetric_and_equivalent_gram_recipes_agree(self):
        req = stock_request()
        stock = plan_ratio_recipe(**req)
        del req['stock_dosing']
        grams = plan_ratio_recipe(**req)
        sc, gc = stock['rounded_verification'], grams['rounded_verification']
        self.assertEqual(sc['status'], 'passed')
        self.assertEqual(sc['delivery_basis'], 'rounded_stock_doses')
        for field in ('analytical_mmol_l', 'aqueous_totals_mol_kg', 'elemental_mg_l'):
            for key, value in gc[field].items():
                self.assertAlmostEqual(sc[field][key], value, places=12)
        for key in ('counted_mmol_l_range', 'final_water_mass_kg_range'):
            for a, b in zip(
                stock['uncertainty_verification'][key], grams['uncertainty_verification'][key]
            ):
                self.assertAlmostEqual(a, b, places=12)
        self.assertEqual(stock['uncertainty_verification']['status'], 'passed')
        self.assertAlmostEqual(stock['maximum_concentrations']['N_NO3'], 5.7)
        self.assertEqual(len(sc['phase_maxima']), 3)
        self.assertFalse(stock['verified'])
        self.assertFalse(stock['stable'])


if __name__ == '__main__':
    unittest.main()
