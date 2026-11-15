# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Physical preparation bounds preserve source-water correlation and solvent mass."""

import unittest

from flahax import plan_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from tests.test_ratio_analysis_uncertainty import request
from tests.test_ratio_element_uncertainty import elemental_options


def physical_request():
    req = request()
    opts = elemental_options(req)
    opts['water_mass_model'] = 'closed_batch_mass_balance'
    opts['physical_preparation'] = dict(
        solution_density_kg_l=[1.001, 1.001],
        source_water_mass_kg=[0.1, 0.1],
        source_water_solvent_fraction=[0.9999, 0.9999],
        product_solvent_fractions={p['product']['name']: [0.5, 0.5] for p in req['products']},
    )
    req['uncertainty'] = opts
    return req


class PhysicalUncertaintyTests(unittest.TestCase):
    def test_product_name_cannot_change_physical_parameter_validation(self):
        req = physical_request()
        old = req['products'][0]['product']['name']
        new = 'solution_density_kg_l'
        req['products'][0]['product']['name'] = new
        u = req['uncertainty']
        u['product_element_factors'][new] = u['product_element_factors'].pop(old)
        fractions = u['physical_preparation']['product_solvent_fractions']
        fractions[new] = fractions.pop(old)
        result = plan_ratio_recipe(**req)
        self.assertEqual(result['uncertainty_verification']['status'], 'passed')

    def test_solvent_interval_changes_water_mass_without_changing_ratio_bounds(self):
        req = physical_request()
        baseline = plan_ratio_recipe(**req)
        row = baseline['rounded_verification']['ingredients'][-1]
        req['uncertainty']['physical_preparation']['product_solvent_fractions'][row['name']] = [
            0.5,
            0.51,
        ]
        c = plan_ratio_recipe(**req)['uncertainty_verification']
        self.assertEqual(
            c['ratio_percent_ranges'], baseline['uncertainty_verification']['ratio_percent_ranges']
        )
        self.assertAlmostEqual(
            c['final_water_mass_kg_range'][1] - c['final_water_mass_kg_range'][0],
            row['grams'] * 0.01 / 1000,
        )

    def test_invalid_physical_bounds_and_product_mass_are_rejected(self):
        for problem in ('density', 'missing_solvent', 'mass_excess'):
            req = physical_request()
            p = req['uncertainty']['physical_preparation']
            if problem == 'density':
                p['solution_density_kg_l'] = [0, 1]
            elif problem == 'missing_solvent':
                p['product_solvent_fractions'].pop(next(iter(p['product_solvent_fractions'])))
            else:
                p['product_solvent_fractions'][req['products'][0]['product']['name']] = [0.5, 1]
            with self.subTest(problem=problem), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**req)

    def test_density_changes_chemistry_water_mass_not_analytical_nutrients(self):
        req = physical_request()
        a = plan_ratio_recipe(**req)
        req['uncertainty']['physical_preparation']['solution_density_kg_l'] = [1.002, 1.002]
        b = plan_ratio_recipe(**req)
        ac, bc = a['uncertainty_verification'], b['uncertainty_verification']
        self.assertEqual(ac['counted_mmol_l_range'], bc['counted_mmol_l_range'])
        self.assertEqual(ac['ratio_percent_ranges'], bc['ratio_percent_ranges'])
        self.assertAlmostEqual(
            bc['final_water_mass_kg_range'][0] - ac['final_water_mass_kg_range'][0], 0.01
        )
        self.assertNotEqual(ac['phase_maxima']['CaHPO4']['si'], bc['phase_maxima']['CaHPO4']['si'])

    def test_source_quantity_counts_all_water_nutrients_and_sodium_together(self):
        req = physical_request()
        req['uncertainty']['physical_preparation']['source_water_mass_kg'] = [0.1, 0.2]
        req['maximum_concentrations']['Na'] = 0.14
        c = plan_ratio_recipe(**req)['uncertainty_verification']
        self.assertAlmostEqual(c['counted_mmol_l_range'][1] - c['counted_mmol_l_range'][0], 0.0097)
        self.assertAlmostEqual(
            c['elemental_mg_l_ranges']['Na'][1] - c['elemental_mg_l_ranges']['Na'][0], 0.068969307
        )
        self.assertIn('sodium_chloride_limits', c['failed_checks'])
        self.assertIn('source_water.mass', c['dimensions'])

    def test_excess_input_mass_cannot_pass_with_positive_solvent_mass(self):
        req = physical_request()
        req['uncertainty']['physical_preparation']['source_water_mass_kg'] = [0.1, 10.1]
        c = plan_ratio_recipe(**req)['uncertainty_verification']
        self.assertEqual(c['status'], 'failed')
        self.assertIn('physical_mass_balance', c['failed_checks'])

    def test_source_solvent_fraction_cannot_ignore_known_element_mass(self):
        req = physical_request()
        req['uncertainty']['physical_preparation']['source_water_solvent_fraction'] = [1, 1]
        with self.assertRaises(DeliveryError) as caught:
            plan_ratio_recipe(**req)
        self.assertEqual(caught.exception.code, 'invalid_source_solvent_bounds')
