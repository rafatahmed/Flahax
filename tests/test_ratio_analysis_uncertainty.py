# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Water and product uncertainty must act on fixed rounded doses, not refitted recipes."""

import copy
import unittest

from flahax import plan_ratio_recipe, search_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from tests.test_ratio_products import contaminated_products
from tests.test_ratio_recipe import REQUEST
from tests.test_ratio_water import water


def request():
    w = water()
    w['source_water_mass_kg'] = 0.1
    return dict(
        REQUEST,
        water=w,
        products=contaminated_products(),
        counted_mmol_l=1.3,
        ph_range=[6.28, 6.32],
        maximum_concentrations={'Na': 1, 'Cl': 1},
        saturation_margin=0.3,
    )


def bounds(req, **changes):
    return dict(
        mode='water_product',
        weighing_error_g=0,
        volume_error_litres=0,
        ratio_relative_tolerance=0.01,
        concentration_relative_tolerance=0.02,
        water_relative_error=0,
        water_ph_error=0,
        product_assay_factors={p['product']['name']: [1, 1] for p in req['products']},
        impurity_model='inert',
        water_mass_model='scale_with_final_volume',
        max_scenarios=64,
        **changes,
    )


class AnalysisUncertaintyTests(unittest.TestCase):
    def test_zero_bounds_reproduce_full_rounded_inventory(self):
        req = request()
        before = copy.deepcopy(req)
        result = plan_ratio_recipe(**dict(req, uncertainty=bounds(req)))
        check = result['uncertainty_verification']
        rounded = result['rounded_verification']
        self.assertEqual(req, before)
        self.assertEqual(check['status'], 'passed')
        self.assertEqual(check['scenario_count'], 1)
        self.assertAlmostEqual(check['counted_mmol_l_range'][0], rounded['counted_mmol_l'])
        for phase in rounded['phase_maxima']:
            self.assertAlmostEqual(
                check['phase_maxima'][phase]['si'], rounded['phase_maxima'][phase]['si']
            )
        self.assertFalse(result['verified'])

    def test_water_and_product_upper_bounds_can_fail_na_cl(self):
        req = request()
        nominal = plan_ratio_recipe(**req)
        req['maximum_concentrations'] = {
            'Na': nominal['elemental_mg_l']['Na'] * 1.001,
            'Cl': nominal['elemental_mg_l']['Cl'] * 1.001,
        }
        opts = bounds(req)
        opts['water_relative_error'] = 0.1
        check = plan_ratio_recipe(**dict(req, uncertainty=opts))['uncertainty_verification']
        self.assertEqual(check['status'], 'failed')
        self.assertIn('sodium_chloride_limits', check['failed_checks'])
        self.assertGreater(
            check['elemental_mg_l_ranges']['Na'][1], req['maximum_concentrations']['Na']
        )
        opts = bounds(req)
        opts['weighing_error_g'] = 0.01
        check = plan_ratio_recipe(**dict(req, uncertainty=opts))['uncertainty_verification']
        self.assertNotEqual(check['status'], 'passed')

    def test_volume_changes_count_and_limits_without_changing_ratio_bounds(self):
        req = request()
        opts = bounds(req)
        opts['volume_error_litres'] = 0.05
        result = plan_ratio_recipe(**dict(req, uncertainty=opts))
        check = result['uncertainty_verification']
        rounded = result['rounded_verification']
        self.assertAlmostEqual(
            check['counted_mmol_l_range'][0], rounded['counted_mmol_l'] * 10 / 10.05
        )
        self.assertAlmostEqual(
            check['counted_mmol_l_range'][1], rounded['counted_mmol_l'] * 10 / 9.95
        )
        for low, high in check['ratio_percent_ranges']:
            self.assertAlmostEqual(low, high, places=9)

    def test_reagent_assay_changes_nutrient_ratio_and_ph(self):
        req = request()
        opts = bounds(req)
        opts['product_assay_factors'][req['products'][-1]['product']['name']] = [0.1, 1]
        check = plan_ratio_recipe(**dict(req, uncertainty=opts))['uncertainty_verification']
        self.assertEqual(check['status'], 'failed')
        self.assertIn('nutrient_ratios', check['failed_checks'])
        self.assertIn('equilibrium_ph', check['failed_checks'])

    def test_source_ph_and_carbon_recompute_each_scenario_reference(self):
        req = request()
        req['water'] = water(0.003)
        req['water']['source_water_mass_kg'] = 0.1
        opts = bounds(req)
        opts.update(water_relative_error=0.01, water_ph_error=0.02)
        check = plan_ratio_recipe(**dict(req, uncertainty=opts))['uncertainty_verification']
        self.assertGreater(
            check['reference_charge_mol_kg_range'][1], check['reference_charge_mol_kg_range'][0]
        )
        self.assertGreater(
            check['inorganic_carbon_mol_kg_range'][1], check['inorganic_carbon_mol_kg_range'][0]
        )
        self.assertFalse(check['continuous_chemistry_extrema_proved'])
        self.assertLessEqual(check['scenario_count'], opts['max_scenarios'])

    def test_missing_product_bounds_bad_ranges_and_undersized_coverage_fail_closed(self):
        req = request()
        for key, value in [
            ('product_assay_factors', {}),
            ('water_relative_error', -1),
            ('water_ph_error', True),
            ('max_scenarios', 0),
            ('water_mass_model', 'unknown'),
            ('impurity_model', 'carbonate'),
        ]:
            opts = bounds(req)
            opts[key] = value
            with self.subTest(key=key), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**dict(req, uncertainty=opts))
        for ph in (None, True, float('nan'), '6.3'):
            invalid = copy.deepcopy(req)
            invalid['water']['measured_ph'] = ph
            with self.subTest(ph=ph), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**dict(invalid, uncertainty=bounds(req)))
        opts = bounds(req)
        opts.update(water_relative_error=0.01, max_scenarios=1)
        check = plan_ratio_recipe(**dict(req, uncertainty=opts))['uncertainty_verification']
        self.assertEqual(check['status'], 'incomplete')

    def test_search_does_not_accept_failing_uncertainty(self):
        req = request()
        opts = bounds(req)
        opts['product_assay_factors'][req['products'][-1]['product']['name']] = [0.1, 1]
        req.pop('counted_mmol_l')
        result = search_ratio_recipe(
            **req, strength_range=[1.2, 1.3], scan_points=3, uncertainty=opts
        )
        self.assertIsNone(result['recipe'])

    def test_ratio_bounds_include_divalent_equivalents(self):
        from flahax.ratio_analysis_uncertainty import _ratio_extreme

        groups = [
            ('K', [10, 0, 0, 0, 0, 0, 0, 0], [20, 0, 0, 0, 0, 0, 0, 0]),
            ('Ca', [0, 5, 0, 0, 0, 0, 0, 0], [0, 10, 0, 0, 0, 0, 0, 0]),
        ]
        low, _ = _ratio_extreme(groups, 0, 0, False)
        high, _ = _ratio_extreme(groups, 0, 0, True)
        self.assertAlmostEqual(low, 100 / 3)
        self.assertAlmostEqual(high, 200 / 3)

    def test_alkalinity_inference_and_missing_phase_are_not_silently_skipped(self):
        from flahax.ratio_analysis_uncertainty import verify_analysis_uncertainty

        req = request()
        req['water']['totals_mol_kg'].pop('CO3-2')
        req['water']['measured_ph'] = 7.5
        req['water']['alkalinity_eq_per_kg'] = 0.002
        opts = bounds(req)
        opts.update(water_relative_error=0.01, water_ph_error=0.02, max_scenarios=48)
        result = plan_ratio_recipe(**dict(req, uncertainty=opts))
        check = result['uncertainty_verification']
        self.assertGreater(check['inorganic_carbon_mol_kg_range'][0], 0)
        result['rounded_verification']['selected_phases'] = ['Missing phase']
        incomplete = verify_analysis_uncertainty(result, opts)
        self.assertEqual(incomplete['status'], 'incomplete')
        self.assertEqual(incomplete['error']['code'], 'phase_unavailable')

    def test_user_bounds_pass_dilute_product_case_without_refitting(self):
        req = request()
        for product in req['products']:
            product['product']['elements'] = {
                k: v * 0.04 for k, v in product['product']['elements'].items()
            }
            product['solvent_fraction'] = 0.98
        opts = bounds(req)
        opts.update(
            weighing_error_g=0.001,
            volume_error_litres=0.05,
            water_relative_error=0.01,
            water_ph_error=0.02,
            max_scenarios=64,
        )
        opts['product_assay_factors'] = {p['product']['name']: [0.99, 1] for p in req['products']}
        nominal = plan_ratio_recipe(**req)
        result = plan_ratio_recipe(**dict(req, uncertainty=opts))
        self.assertEqual(
            result['rounded_verification']['ingredients'],
            nominal['rounded_verification']['ingredients'],
        )
        check = result['uncertainty_verification']
        self.assertEqual(check['status'], 'passed')
        self.assertLessEqual(check['worst_ratio_relative_error'], 0.01)
        self.assertLessEqual(check['worst_concentration_relative_error'], 0.02)
        self.assertTrue(check['all_scenario_ph_in_range'])
        for phase in check['phase_maxima'].values():
            self.assertLess(phase['si'], -0.3)
        self.assertFalse(check['continuous_chemistry_extrema_proved'])
        self.assertFalse(result['verified'])

    def test_original_concentrated_products_fail_user_ratio_tolerance(self):
        req = request()
        opts = bounds(req)
        opts.update(
            weighing_error_g=0.001,
            volume_error_litres=0.05,
            water_relative_error=0.01,
            water_ph_error=0.02,
            max_scenarios=64,
        )
        opts['product_assay_factors'] = {p['product']['name']: [0.99, 1] for p in req['products']}
        check = plan_ratio_recipe(**dict(req, uncertainty=opts))['uncertainty_verification']
        self.assertEqual(check['status'], 'failed')
        self.assertIn('nutrient_ratios', check['failed_checks'])
        self.assertGreater(check['worst_ratio_relative_error'], 0.015)
