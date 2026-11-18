# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Commercial assay, reagent and incidental-ion conservation at fixed
ratios.
"""

import copy
import unittest

from flahax import plan_ratio_recipe
from flahax.composition import theoretical_assay
from flahax.delivery_contracts import DeliveryError
from tests.test_ratio_recipe import REQUEST
from tests.test_ratio_water import water

FORMULAS = ['KH2PO4', 'Ca(NO3)2.4H2O', 'MgSO4.7H2O', 'Mg(NO3)2.6H2O', 'KNO3', 'KOH']


def products(fraction=0.5):
    return [
        dict(
            product=dict(
                name='Synthetic ' + f,
                formula=f,
                elements={k: v * fraction for k, v in theoretical_assay(f).items()},
            ),
            role='ph_reagent' if f == 'KOH' else 'fertilizer',
            solvent_fraction=1 - fraction,
        )
        for f in FORMULAS
    ]


def contaminated_products():
    records = products()
    # Independently specified mass fractions: KNO3 plus NaCl
    # contamination.
    records[4]['product'] = dict(
        name='Synthetic contaminated nitrate',
        ions={'K+': 1, 'NO3-': 1, 'Na+': 0.02, 'Cl-': 0.02},
        elements={
            'K': 39.0983 / 102.27079538 * 50,
            'N_NO3': 14.0067 / 102.27079538 * 50,
            'Na': 0.45979538 / 102.27079538 * 50,
            'Cl': 0.709 / 102.27079538 * 50,
        },
    )
    # KOH + sodium hydroxide; Na must be counted even when delivered as
    # reagent.
    records[5]['product'] = dict(
        name='Synthetic sodium-bearing base',
        ions={'K+': 1, 'Na+': 0.01, 'OH-': 1.01},
        elements={'K': 39.0983 / 56.50510609 * 50, 'Na': 0.22989769 / 56.50510609 * 50},
    )
    return records


class RatioProductTests(unittest.TestCase):
    def test_half_assay_products_double_mass_without_changing_final_targets(self):
        pure = plan_ratio_recipe(**REQUEST)
        supplied = products()
        original = copy.deepcopy(supplied)
        actual = plan_ratio_recipe(**dict(REQUEST, products=supplied))
        self.assertEqual(supplied, original)
        for p, a in zip(pure['ingredients'], actual['ingredients']):
            self.assertAlmostEqual(a['grams'], p['grams'] * 2, delta=2e-6)
        for key in pure['analytical_mmol_l']:
            self.assertAlmostEqual(
                actual['analytical_mmol_l'][key], pure['analytical_mmol_l'][key], delta=1e-7
            )
        self.assertLess(abs(actual['charge_closure_error_mol_kg']), 1e-10)

    def test_water_fertilizer_and_reagent_contributions_include_sodium_chloride(self):
        result = plan_ratio_recipe(
            **dict(
                REQUEST,
                water=water(),
                products=contaminated_products(),
                maximum_concentrations={'Na': 10, 'Cl': 20},
                ph_range=[6.28, 6.32],
            )
        )
        audit = result['elemental_accounting_mg_l']
        self.assertAlmostEqual(audit['water']['Na'], 5.51754456)
        self.assertAlmostEqual(audit['water']['Cl'], 11.344)
        self.assertGreater(audit['fertilizers']['Na'], 0)
        self.assertGreater(audit['ph_reagents']['Na'], 0)
        self.assertGreater(audit['fertilizers']['Cl'], 0)
        for nutrient, total in result['elemental_mg_l'].items():
            self.assertAlmostEqual(total, sum(audit[k].get(nutrient, 0) for k in audit))
        for nutrient, total in result['analytical_mmol_l'].items():
            self.assertAlmostEqual(
                total, sum(v[nutrient] for v in result['nutrient_accounting'].values())
            )
        self.assertAlmostEqual(result['counted_mmol_l'], 30, delta=1e-7)
        for actual, target in zip(
            result['cation_percent'] + result['anion_percent'],
            [50, 30, 20, 500 / 9, 100 / 3, 100 / 9],
        ):
            self.assertAlmostEqual(actual, target, delta=1e-7)
        self.assertTrue(result['limit_assessment']['passed'])
        self.assertTrue(result['rounded_verification']['limit_assessment']['passed'])
        self.assertTrue(result['rounded_verification']['rounded_ph_in_range'])
        self.assertFalse(result['verified'])

    def test_water_above_ceiling_and_negative_limits_are_refused(self):
        for limits in (
            {'Na': 5},
            {'Cl': 11},
            {'Na': -1},
            {'Na': True},
            {'Na': float('nan')},
            {'K': 5},
        ):
            with self.subTest(limits=limits), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**dict(REQUEST, water=water(), maximum_concentrations=limits))

    def test_sodium_limit_selects_clean_alternative(self):
        supplied = contaminated_products()
        supplied.append(products()[4])
        supplied.append(products()[5])
        result = plan_ratio_recipe(
            **dict(REQUEST, products=supplied, maximum_concentrations={'Na': 0, 'Cl': 0})
        )
        self.assertEqual(result['elemental_mg_l'].get('Na', 0), 0)
        self.assertEqual(result['elemental_mg_l'].get('Cl', 0), 0)
        self.assertAlmostEqual(result['counted_mmol_l'], 30, delta=1e-7)

    def test_unknown_chemistry_and_ambiguous_product_inputs_are_refused(self):
        cases = []
        for mutation in (
            'unknown',
            'missing_solvent',
            'duplicate',
            'invalid_assay',
            'unsupported_role',
        ):
            supplied = products()
            if mutation == 'unknown':
                supplied[0]['product'].pop('formula')
            if mutation == 'missing_solvent':
                supplied[0].pop('solvent_fraction')
            if mutation == 'duplicate':
                supplied.append(supplied[0])
            if mutation == 'invalid_assay':
                supplied[0]['product']['elements']['P'] = -1
            if mutation == 'unsupported_role':
                supplied[0]['role'] = 'other'
            cases.append(supplied)
        for supplied in cases:
            with self.subTest(products=supplied), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**dict(REQUEST, products=supplied))
        with self.assertRaises(DeliveryError):
            plan_ratio_recipe(**dict(REQUEST, products=products(), ph_reagents=['KOH']))
        w = water()
        w['source_water_mass_kg'] = 10
        with self.assertRaises(DeliveryError):
            plan_ratio_recipe(**dict(REQUEST, products=products(), water=w))

    def test_commercial_acid_nitrate_and_solvent_are_counted(self):
        supplied = products()
        supplied[-1] = dict(
            product=dict(
                name='Synthetic 50 percent nitric acid',
                formula='HNO3',
                elements={k: v * 0.5 for k, v in theoretical_assay('HNO3').items()},
            ),
            role='ph_reagent',
            solvent_fraction=0.5,
        )
        result = plan_ratio_recipe(**dict(REQUEST, products=supplied, water=water(0.006)))
        self.assertGreater(result['nutrient_accounting']['ph_reagents_mmol_l']['NO3'], 0)
        self.assertAlmostEqual(result['counted_mmol_l'], 30, delta=1e-7)
        self.assertGreater(result['declared_product_solvent_kg'], 0)
        self.assertTrue(result['solvent_inventory_passed'])

    def test_cli_search_rechecks_limits_on_rounded_products(self):
        from flahax.planning_cli import execute

        request = dict(
            REQUEST,
            products=products(),
            ph_range=[6.28, 6.32],
            maximum_concentrations={'Na': 0, 'Cl': 0},
        )
        request.pop('counted_mmol_l')
        result = execute('ratio', dict(request, strength_range=[1, 1.5], scan_points=3))
        self.assertIsNotNone(result['recipe'])
        self.assertTrue(result['recipe']['rounded_verification']['limit_assessment']['passed'])

    def test_rounding_rechecks_product_sodium_not_just_nutrient_ratios(self):
        opts = dict(REQUEST, products=contaminated_products(), ph_range=[6.28, 6.32])
        precise = plan_ratio_recipe(**opts)
        # Force a delivered mass increase while retaining the exact
        # analytical limit.
        from flahax.ratio_verification import verify_rounded_recipe, DEFAULT_PHASES

        precise['maximum_concentrations'] = {'Na': precise['elemental_mg_l']['Na']}
        masses = [r['grams'] * 1.000001 for r in precise['ingredients']]
        check = verify_rounded_recipe(
            precise, [6.28, 6.32], DEFAULT_PHASES, 5, delivered_grams=masses
        )
        self.assertFalse(check['limit_assessment']['passed'])
        self.assertNotEqual(check['status'], 'passed')

    def test_positive_limit_is_enforced_during_product_selection(self):
        supplied = contaminated_products() + [products()[4], products()[5]]
        result = plan_ratio_recipe(
            **dict(REQUEST, products=supplied, maximum_concentrations={'Na': 0.01, 'Cl': 0.01})
        )
        self.assertLessEqual(result['elemental_mg_l'].get('Na', 0), 0.01)
        self.assertLessEqual(result['elemental_mg_l'].get('Cl', 0), 0.01)
        self.assertAlmostEqual(result['counted_mmol_l'], 30, delta=1e-7)

    def test_assay_and_model_difference_remains_visible(self):
        supplied = products()
        # The existing reconciliation keeps excess assay K out of
        # chemistry.
        supplied[4]['product']['elements']['K'] *= 1.01
        result = plan_ratio_recipe(**dict(REQUEST, products=supplied))
        self.assertGreater(result['analytical_minus_chemistry_mg_l']['K'], 0)
        self.assertAlmostEqual(result['counted_mmol_l'], 30, delta=1e-7)
        self.assertLess(abs(result['charge_closure_error_mol_kg']), 1e-10)

    def test_pure_recipe_limits_and_product_uncertainty_fail_closed(self):
        from tests.test_ratio_stocks import UNCERTAINTY

        result = plan_ratio_recipe(
            **dict(REQUEST, maximum_concentrations={'Na': 0, 'Cl': 0}, ph_range=[6.28, 6.32])
        )
        self.assertTrue(result['rounded_verification']['limit_assessment']['passed'])
        with self.assertRaises(DeliveryError):
            plan_ratio_recipe(
                **dict(
                    REQUEST, products=products(), uncertainty=UNCERTAINTY, ph_range=[6.28, 6.32]
                )
            )
        with self.assertRaises(DeliveryError):
            plan_ratio_recipe(**dict(REQUEST, maximum_concentrations={'Na': True}))

    def test_unstated_counterions_are_not_lost_or_double_counted(self):
        for missing in ('Na', 'Cl'):
            supplied = contaminated_products()
            supplied[4]['product']['elements'].pop(missing)
            result = plan_ratio_recipe(**dict(REQUEST, products=supplied))
            row = result['ingredients'][4]
            moles = row['grams'] * 0.5 / 102.27079538 * 0.02
            expected = moles * (22.989769 if missing == 'Na' else 35.45) * 1000 / 10
            self.assertAlmostEqual(
                result['elemental_accounting_mg_l']['fertilizers'][missing], expected
            )
            self.assertGreater(expected, 0)

    def test_catalogue_calcium_nitrate_ammonium_stays_outside_six_ion_count(self):
        from flahax import load_library

        library = {p['name']: p for p in load_library()['salts']}
        names = [
            'Potassium Monobasic Phosphate',
            'Calcium Nitrate (ag grade)',
            'Magnesium Sulfate (Heptahydrate)',
            'Potassium Nitrate',
            'Potassium Hydroxide (45% solution)',
        ]
        supplied = [
            dict(
                product=library[n],
                role='ph_reagent' if 'Hydroxide' in n else 'fertilizer',
                solvent_fraction=0.55 if 'Hydroxide' in n else 0,
            )
            for n in names
        ]
        supplied.insert(3, products(1)[3])
        result = plan_ratio_recipe(**dict(REQUEST, products=supplied, ph_range=[6.28, 6.32]))
        calcium = result['ingredients'][1]
        expected = calcium['grams'] / 10 * 11
        self.assertGreater(expected, 0)
        self.assertAlmostEqual(result['elemental_mg_l']['N_NH4'], expected)
        self.assertGreater(result['aqueous_totals_mol_kg']['NH4+'], 0)
        self.assertAlmostEqual(result['counted_mmol_l'], 30, delta=1e-7)
        self.assertTrue(result['rounded_verification']['rounded_ph_in_range'])

    def test_product_ceiling_can_control_strength_search(self):
        from flahax import search_ratio_recipe

        request = dict(
            REQUEST,
            products=contaminated_products(),
            ph_range=[6.28, 6.32],
            maximum_concentrations={'Na': 0.055},
        )
        request.pop('counted_mmol_l')
        result = search_ratio_recipe(
            **request, strength_range=[1, 1.5], scan_points=3, strength_tolerance=0.001
        )
        self.assertIsNotNone(result['recipe'])
        self.assertLess(result['requested_strength_mmol_l'], 1.5)
        self.assertGreater(result['requested_strength_mmol_l'], 1)
        self.assertLessEqual(
            result['recipe']['rounded_verification']['elemental_mg_l']['Na'], 0.055
        )
        self.assertFalse(result['search_cap_reached'])

    def test_no_supported_allocation_does_not_return_a_passing_recipe(self):
        for changes in ({'maximum_concentrations': {'Na': 0.01}}, {'products': products()[:2]}):
            options = dict(REQUEST, products=contaminated_products())
            options.update(changes)
            with self.subTest(changes=changes), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**options)
