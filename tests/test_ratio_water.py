"""Final ratios include measured source water, pure salts and pH reagents."""

import copy
import unittest

from flahax import plan_ratio_recipe, search_ratio_recipe
from flahax.aqueous_model import solve
from flahax.delivery_contracts import DeliveryError
from flahax.measured_water import balance_water_analysis
from tests.test_ratio_recipe import REQUEST

BASIS = ('K+', 'Ca+2', 'Mg+2', 'NO3-', 'PO4-3', 'SO4-2')
NUTRIENTS = ('K', 'Ca', 'Mg', 'NO3', 'P', 'SO4')


def water(carbon=0):
    return dict(
        analysis_id='SYNTHETIC water analysis, not a lab result',
        totals_mol_kg=dict(
            zip(
                BASIS + ('Na+', 'Cl-', 'CO3-2'),
                [0.0001, 0.0004, 0.00015, 0.0002, 0.00002, 0.0001, 0.0003, 0.0004, carbon],
            )
        ),
        measured_ph=7.5 if carbon else 6.3,
        temperature_c=25,
        source_water_mass_kg=8,
    )


class RatioWaterTests(unittest.TestCase):
    def test_water_salt_and_koh_contributions_close_final_targets(self):
        w = water()
        original = copy.deepcopy(w)
        result = plan_ratio_recipe(**dict(REQUEST, water=w))
        self.assertEqual(w, original)
        audit = result['nutrient_accounting']
        for nutrient, basis in zip(NUTRIENTS, BASIS):
            expected_water = w['totals_mol_kg'][basis] * 8 * 1000 / 10
            self.assertAlmostEqual(audit['water_mmol_l'][nutrient], expected_water)
            combined = sum(
                audit[key][nutrient]
                for key in ('water_mmol_l', 'salts_mmol_l', 'ph_reagents_mmol_l')
            )
            self.assertAlmostEqual(combined, result['analytical_mmol_l'][nutrient], places=9)
        self.assertGreater(audit['ph_reagents_mmol_l']['K'], 0)
        self.assertAlmostEqual(result['counted_mmol_l'], 30, places=9)
        for actual, expected in zip(result['cation_percent'], [50, 30, 20]):
            self.assertAlmostEqual(actual, expected, places=8)
        for actual, expected in zip(result['anion_percent'], [500 / 9, 100 / 3, 100 / 9]):
            self.assertAlmostEqual(actual, expected, places=8)
        self.assertLess(abs(result['charge_closure_error_mol_kg']), 1e-10)

    def test_carbonated_water_counts_nitric_acid_nitrate(self):
        w = water(0.006)
        result = plan_ratio_recipe(**dict(REQUEST, water=w, ph_reagents=['KOH', 'HNO3']))
        audit = result['nutrient_accounting']
        self.assertGreater(audit['ph_reagents_mmol_l']['NO3'], 0)
        self.assertAlmostEqual(audit['ph_reagents_mmol_l']['K'], 0)
        nitrate = audit['water_mmol_l']['NO3'] + audit['salts_mmol_l']['NO3']
        self.assertLess(nitrate, result['analytical_mmol_l']['NO3'])
        self.assertAlmostEqual(
            nitrate + audit['ph_reagents_mmol_l']['NO3'],
            result['analytical_mmol_l']['NO3'],
            places=9,
        )
        self.assertAlmostEqual(sum(result['analytical_mmol_l'].values()), 30, places=9)
        with self.assertRaises(DeliveryError):
            plan_ratio_recipe(**dict(REQUEST, water=w))

    def test_extra_water_ions_and_measured_charge_are_preserved_after_rounding(self):
        w = water(0.006)
        result = plan_ratio_recipe(
            **dict(REQUEST, water=w, ph_reagents=['HNO3', 'KOH'], ph_range=[6.28, 6.32])
        )
        measured = balance_water_analysis(w['totals_mol_kg'], measured_ph=w['measured_ph'])
        for ion in ('Na+', 'Cl-', 'CO3-2'):
            self.assertAlmostEqual(
                result['aqueous_totals_mol_kg'][ion], w['totals_mol_kg'][ion] * 8 / 10
            )
        reference = measured.residual_charge_eq * 8 / 10
        self.assertAlmostEqual(result['water_accounting']['reference_charge_mol_kg'], reference)
        rounded = result['rounded_verification']
        self.assertTrue(rounded['rounded_ph_in_range'])
        state = solve(rounded['aqueous_totals_mol_kg'], rounded['rounded_ph'])
        self.assertAlmostEqual(state.charge_balance, reference, delta=1e-9)
        for nutrient in NUTRIENTS:
            self.assertAlmostEqual(
                rounded['analytical_mmol_l'][nutrient],
                result['analytical_mmol_l'][nutrient],
                delta=1e-5,
            )

    def test_alkalinity_reuses_measured_water_carbon_inference(self):
        w = water()
        w['totals_mol_kg'].pop('CO3-2')
        w['measured_ph'] = 7.5
        w['alkalinity_eq_per_kg'] = 0.002
        result = plan_ratio_recipe(**dict(REQUEST, water=w, ph_reagents=['KOH', 'HNO3']))
        self.assertGreater(result['aqueous_totals_mol_kg']['CO3-2'], 0)
        self.assertEqual(result['water_accounting']['carbon_source'], 'alkalinity')
        self.assertNotIn('CO3-2', result['water_accounting']['analytical_totals_mol_kg'])

    def test_water_floor_and_unsupported_or_ambiguous_inputs_fail_explicitly(self):
        w = water()
        w['totals_mol_kg']['Ca+2'] = 0.02
        with self.assertRaises(DeliveryError) as caught:
            plan_ratio_recipe(**dict(REQUEST, water=w))
        self.assertEqual(caught.exception.code, 'ratio_water_exceeds_target')
        cases = []
        for key in ('NO3-', 'CO3-2'):
            item = water()
            item['totals_mol_kg'].pop(key)
            cases.append(item)
        item = water()
        item['totals_mol_kg']['NH4+'] = 0.001
        cases.append(item)
        item = water()
        item['source_water_mass_kg'] = 11
        cases.append(item)
        item = water()
        item['alkalinity_eq_per_kg'] = 0.002
        cases.append(item)
        for item in cases:
            with self.subTest(item=item), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**dict(REQUEST, water=item))

    def test_demineralized_compatibility_and_batch_scaling(self):
        old = plan_ratio_recipe(**REQUEST)
        self.assertTrue(all(v == 0 for v in old['nutrient_accounting']['water_mmol_l'].values()))
        one = plan_ratio_recipe(**dict(REQUEST, water=water()))
        w = water()
        w['source_water_mass_kg'] *= 2
        two = plan_ratio_recipe(**dict(REQUEST, water=w, volume_litres=20, water_mass_kg=20))
        for a, b in zip(one['ingredients'], two['ingredients']):
            self.assertAlmostEqual(b['grams'], a['grams'] * 2, places=8)

    def test_real_water_uncertainty_is_not_silently_treated_as_verified(self):
        from tests.test_ratio_stocks import STOCKS, UNCERTAINTY

        with self.assertRaises(DeliveryError) as caught:
            plan_ratio_recipe(
                **dict(
                    REQUEST,
                    water=water(),
                    stock_dosing=STOCKS,
                    uncertainty=UNCERTAINTY,
                    ph_range=[6.28, 6.32],
                )
            )
        self.assertEqual(caught.exception.code, 'unsupported_ratio_water_uncertainty')

    def test_cli_real_water_and_search_preserve_accounting(self):
        from flahax.planning_cli import execute

        result = execute('ratio', dict(REQUEST, water=water(0.003), ph_reagents=['KOH', 'HNO3']))
        self.assertIn('water_accounting', result)
        w = water()
        w['source_water_mass_kg'] = 0.1
        options = dict(REQUEST, water=w, ph_range=[6.28, 6.32])
        options.pop('counted_mmol_l')
        result = search_ratio_recipe(strength_range=[1, 1.5], scan_points=3, **options)
        self.assertIsNotNone(result['recipe'])
        self.assertGreater(result['recipe']['nutrient_accounting']['water_mmol_l']['Ca'], 0)

    def test_reagent_permissions_and_invalid_water_values(self):
        for reagents in ([], ['KOH', 'KOH'], ['HCl'], 'KOH', ['HNO3']):
            with self.subTest(reagents=reagents), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**dict(REQUEST, water=water(), ph_reagents=reagents))
        for value in (True, -1, float('nan'), float('inf')):
            w = water()
            w['totals_mol_kg']['Ca+2'] = value
            with self.subTest(value=value), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**dict(REQUEST, water=w))
