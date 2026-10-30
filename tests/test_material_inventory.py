# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent mass/stoichiometric checks of pre-fit material accounting (#164)."""

from copy import deepcopy
import unittest

from flahax import component_nutrient_masses, load_library, material_inventory
from flahax.engine import forward, recommend
from flahax.measured_water import nutrient_mg_per_litre
from flahax.ph_adjustment import REAGENTS
from flahax.product_conversion import catalogue_dose_totals
from tests.catalogue_history import historical_catalogue


class MaterialInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(historical_catalogue())
        cls.products = {p['name']: p for p in load_library()['salts']}

    def test_counterion_changes_selection_before_fit(self):
        pool = [self.products[n] for n in ('Iron EDTA', 'Iron II Sulfate (Hepahydrate)')]
        for ordered in (pool, pool[::-1]):
            result = recommend(ordered, {'Fe': 1}, maximum_concentrations={'Na': 0.01}, ridge=0)
            self.assertTrue(result['feasible'])
            self.assertEqual(
                [s['name'] for s in result['salts']], ['Iron II Sulfate (Hepahydrate)']
            )
            self.assertFalse(result['limitViolations'])
            self.assertEqual(result['materialInventory'][0]['status'], 'supported_components')

    def test_iron_edta_independent_element_and_ligand_sums(self):
        product = self.products['Iron EDTA']
        original = deepcopy(product)
        inventory = material_inventory(product)
        # Label Fe=13%; Na:Fe:EDTA is 1:1:1. No chemistry/solver function supplies the oracle.
        moles = 0.13 / 55.845
        self.assertAlmostEqual(inventory['nutrient_percent']['Na'], moles * 22.989769 * 100)
        self.assertAlmostEqual(inventory['components_moles_per_gram']['Edta-4'], moles)
        self.assertAlmostEqual(inventory['components_moles_per_gram']['Na+'], moles)
        self.assertFalse({'N_NO3', 'N_NH4', 'N_UREA'} & inventory['nutrient_percent'].keys())
        result = forward([product], [0.125], {'Na': 2.0})
        self.assertAlmostEqual(result['Na'], 2 + 0.125 * moles * 22.989769 * 1000)
        self.assertAlmostEqual(result['Fe'], 0.125 * 0.13 * 1000)
        self.assertEqual(product, original)

    def test_assayed_sodium_is_not_counted_twice(self):
        product = self.products['Sodium Molybdate (Dihydrate)']
        inventory = material_inventory(product)
        self.assertEqual(inventory['nutrient_percent']['Na'], product['elements']['Na'])
        self.assertAlmostEqual(forward([product], [0.2])['Na'], product['elements']['Na'] * 2)

    def test_catalogue_components_and_fitting_agree(self):
        for product in self.products.values():
            with self.subTest(product=product['name']):
                inv = material_inventory(product)
                self.assertEqual(inv['status'], 'supported_components')
                chemical = component_nutrient_masses(inv['components_moles_per_gram'])
                fitted = forward([product], [1])
                for ion, grams in chemical.items():
                    self.assertAlmostEqual(fitted[ion], grams * 1000, delta=1e-10)

    def test_water_products_and_reagents_add_on_same_basis(self):
        # 2 L final solution, 1.5 kg water; 0.4 g FeEDTA and 0.003 mol HNO3.
        water = {'Na+': 0.001, 'NO3-': 0.002}
        water_ppm = nutrient_mg_per_litre(water, 1.5, 2)
        reagent_ppm = nutrient_mg_per_litre({'NO3-': 0.003 / 1.5}, 1.5, 2)
        supply = {k: water_ppm.get(k, 0) + reagent_ppm.get(k, 0) for k in water_ppm}
        fitted = forward([self.products['Iron EDTA']], [0.4 / 2], supply)
        self.assertAlmostEqual(
            fitted['Na'], (0.001 * 1.5 + 0.4 * 0.13 / 55.845) * 22.989769 * 1000 / 2
        )
        self.assertAlmostEqual(fitted['N_NO3'], (0.002 * 1.5 + 0.003) * 14.0067 * 1000 / 2)
        self.assertAlmostEqual(fitted['Fe'], 0.4 * 0.13 * 1000 / 2)

    def test_reagent_nutrients_follow_stoichiometry(self):
        expected = {
            'HNO3': {'N_NO3': 14.0067},
            'H3PO4': {'P': 30.973762},
            'H2SO4': {'S': 32.06},
            'C6H8O7': {},
            'KOH': {'K': 39.0983},
            'KHCO3': {'K': 39.0983},
            'K2CO3': {'K': 78.1966},
        }
        for formula, (_, components, _, _) in REAGENTS.items():
            self.assertEqual(component_nutrient_masses(components), expected[formula])
        self.assertEqual(REAGENTS['C6H8O7'][1], {'Citrate-3': 1})
        self.assertEqual(REAGENTS['K2CO3'][1], {'K+': 2, 'CO3-2': 1})

    def test_both_iron_states_and_urea_atom_count(self):
        masses = component_nutrient_masses(
            {'Fe+2': 0.1, 'Fe+3': 0.2, 'Ure': 0.3, 'Edta-4': 1, 'Citrate-3': 2, 'CO3-2': 3}
        )
        self.assertAlmostEqual(masses['Fe'], 0.3 * 55.845)
        self.assertAlmostEqual(masses['N_UREA'], 0.6 * 14.0067)
        self.assertEqual(set(masses), {'Fe', 'N_UREA'})

    def test_product_and_assay_order_do_not_change_inventory(self):
        self.enterContext(historical_catalogue())
        doses = {'Iron EDTA': 0.04, 'Potassium Nitrate': 0.8, 'CH - micro': 0.02}
        products = [deepcopy(self.products[n]) for n in doses]
        baseline = catalogue_dose_totals(doses, products=products)
        for p in products:
            p['elements'] = dict(reversed(list(p['elements'].items())))
        reordered = catalogue_dose_totals(
            dict(reversed(list(doses.items()))), products=products[::-1]
        )
        self.assertEqual(set(baseline), set(reordered))
        for basis, value in baseline.items():
            self.assertAlmostEqual(value, reordered[basis], delta=1e-15)

    def test_unknown_chemistry_is_explicitly_assay_only(self):
        product = {'name': 'Unspecified material', 'elements': {'K': 5.0}}
        inv = material_inventory(product)
        self.assertEqual(inv['status'], 'assay_only')
        self.assertIsNone(inv['components_moles_per_gram'])
        self.assertTrue(inv['limitation_code'])
        self.assertEqual(forward([product], [2]), {'K': 100.0})
        self.assertEqual(forward([{'elements': {'K': 5.0}}], [2]), {'K': 100.0})

    def test_invalid_water_component_cannot_cancel_another_valence(self):
        from flahax.delivery_contracts import DeliveryError

        with self.assertRaises(DeliveryError):
            nutrient_mg_per_litre({'Fe+2': -1, 'Fe+3': 2})
        self.assertEqual(nutrient_mg_per_litre({'Na+': None}), {})

    def test_disclosed_blend_reports_both_observations(self):
        self.enterContext(historical_catalogue())
        from tests.test_materials import grade
        from flahax.materials import resolve_material

        material = resolve_material(
            'CH - micro',
            grade=grade(
                grade_id='grd-inventory',
                identity_id=None,
                composition='disclosed',
                components=[{'identity_id': 'idn-sodium-iron-edta', 'mass_fraction': 0.6}],
                analysis={'Fe': {'typical': 7.0}},
            ),
        )
        inv = material_inventory(material.record, material=material)
        self.assertEqual(inv['nutrient_percent']['Fe'], 7.0)
        self.assertAlmostEqual(inv['component_nutrient_percent']['Fe'], 7.8)
        self.assertAlmostEqual(inv['assay_component_difference_percent']['Fe'], -0.8)
        self.assertAlmostEqual(inv['nutrient_percent']['Na'], 7.8 / 55.845 * 22.989769)

    def test_formula_order_is_not_an_accounting_input(self):
        products = [
            {'name': 'custom', 'formula': formula, 'elements': {'K': 39.0}}
            for formula in ('KNO3', 'NO3K')
        ]
        self.assertEqual(material_inventory(products[0]), material_inventory(products[1]))

    def test_grade_record_assay_mismatch_is_explicit(self):
        from tests.test_materials import DeclaredCompoundTests

        product, _ = DeclaredCompoundTests().product()
        valid = material_inventory(product)
        self.assertEqual(valid['status'], 'supported_components')
        product = deepcopy(product)
        product['elements']['K'] += 1
        invalid = material_inventory(product)
        self.assertEqual(invalid['status'], 'assay_only')
        self.assertEqual(invalid['limitation_code'], 'material_mismatch')

    def test_chemistry_rejects_unknown_or_incomplete_material(self):
        from flahax.delivery_contracts import DeliveryError

        with self.assertRaises(DeliveryError) as caught:
            catalogue_dose_totals({'unknown': 1})
        self.assertEqual(caught.exception.code, 'unknown_product')
        with self.assertRaises(DeliveryError) as caught:
            catalogue_dose_totals(
                {'unknown': 1},
                products=[
                    {'name': 'unknown', 'elements': {'K': 5}},
                ],
            )
        self.assertEqual(caught.exception.code, 'material_undefined')
