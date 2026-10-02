import json
from pathlib import Path
import unittest

from flahax import (DeliveryError, VolumeLitres, InjectionRatio, TemperatureCelsius, StockTank,
                    load_library, recommend, solve_weights, calculate_equilibrium_ph,
                    plan_fertilizer_workflow, plan_acid_options)
from tests.test_ph_planning import record, inputs


NAMES = ['Boric Acid', 'Calcium Nitrate (ag grade)', 'Iron II Sulfate (Hepahydrate)',
         'Mg Nitrate', 'Mn EDTA', 'Potassium Nitrate', 'Copper Sulfate (pentahydrate)',
         'Potassium Sulfate', 'Zinc Sulfate (Monohydrate)', 'Sodium Molybdate (Dihydrate)',
         'Potassium Monobasic Phosphate', 'Phosphoric Acid (75%)']
TARGETS = {'N_NO3':128, 'N_NH4':0, 'P':58, 'K':211, 'Ca':104, 'Mg':40, 'S':54,
           'Fe':5, 'Mn':2, 'Zn':.3, 'B':.7, 'Cu':.1, 'Mo':.1, 'Na':0}


def products():
    library = {p['name']:p for p in load_library()['salts']}
    return [library[n] for n in NAMES]


def acid_products():
    return [dict(id=formula, chemicalFormula=formula, massFraction=.5, densityKgPerL=1.2,
                 source='synthetic regression only', revision='1', recordedAt='2026-09-28T00:00:00Z')
            for formula in ('HNO3','H3PO4','C6H8O7','H2SO4')]


class WaterWorkflowTests(unittest.TestCase):
    def test_pepper_water_is_separate_from_crop_and_cannot_determine_ph(self):
        water = {k: 20 if k == 'Ca' else 0 for k in TARGETS}
        result = plan_fertilizer_workflow(products(), TARGETS, water, 6.5)
        self.assertEqual(result.nutrient_gap['Ca'], 84)
        self.assertEqual(result.target_ph, 6.5)
        self.assertEqual(result.water['Ca'], 20)
        self.assertTrue(result.recommendation['feasible'])
        self.assertEqual(result.stages['formulation'].status, 'requires_review')
        violations = {r['symbol']: r['ppm'] for r in result.recommendation['incidentalContributions']}
        self.assertAlmostEqual(violations['N_NH4'], 4.84511367294, places=8)
        self.assertAlmostEqual(violations['Na'], .0479192828162, places=10)
        self.assertEqual(result.stages['chemistry'].status, 'needs_input')
        self.assertIsNone(result.stages['chemistry'].value)
        self.assertIn('water_totals', result.stages['chemistry'].required_inputs)
        self.assertEqual(TARGETS['Ca'], 104)

    def test_explicit_water_required_and_incidental_additions_are_separate(self):
        with self.assertRaises(DeliveryError):
            plan_fertilizer_workflow(products(), TARGETS, None, 6.5)
        for function in (recommend, solve_weights):
            result = function([products()[1]], {'Ca':84, 'N_NO3':84*14.4/19, 'N_NH4':0}, {})
            self.assertTrue(result['feasible'])
            self.assertTrue(result['incidentalContributions'])
            self.assertTrue(result['requiresReview'])
        result = recommend([products()[5]], {'K':10, 'N_NH4':0}, {})
        self.assertTrue(result['feasible'])
        self.assertNotIn('N_NH4', {r['symbol'] for r in result['incidentalContributions']})
        result = plan_fertilizer_workflow(products(), TARGETS, {'Ca':20}, 6.5,
                                         maximum_concentrations={'N_NH4':6, 'Na':.1})
        self.assertTrue(result.recommendation['feasible'])
        self.assertFalse(result.recommendation['requiresReview'])
        blocked = plan_fertilizer_workflow(products(), TARGETS, {'Ca':20}, 6.5,
                                          maximum_concentrations={'N_NH4':0})
        self.assertFalse(blocked.recommendation['feasible'])
        self.assertEqual(blocked.recommendation['limitViolations'][0]['symbol'], 'N_NH4')

    def test_calculated_ph_requires_explicit_boundary_and_conserves_components(self):
        totals = {'Na+':.002, 'Cl-':.002}
        for kwargs in ({'complete_analysis':False, 'carbon_boundary':'closed'},
                       {'complete_analysis':True, 'carbon_boundary':'open'}):
            with self.assertRaises(DeliveryError):
                calculate_equilibrium_ph(totals, phases=[], **kwargs)
        result = calculate_equilibrium_ph(totals, complete_analysis=True, carbon_boundary='closed', phases=[])
        self.assertAlmostEqual(result.ph, 7, delta=.01)
        self.assertLess(abs(result.charge_balance), 1e-12)
        self.assertEqual(result.totals, totals)
        self.assertTrue(all(abs(v) < 1e-12 for v in result.residuals.values()))
        with self.assertRaises(DeliveryError):
            calculate_equilibrium_ph({'Na+':.2,'Cl-':.2}, complete_analysis=True, carbon_boundary='closed', phases=[])
        for phases in (None, 1, 'Calcite'):
            with self.assertRaises(DeliveryError):
                calculate_equilibrium_ph(totals, complete_analysis=True, carbon_boundary='closed', phases=phases)

    def test_changed_catalogue_assay_cannot_be_used_as_unchanged_chemistry(self):
        salt = dict(products()[5])
        salt['elements'] = {'K': 30, 'N_NO3': 10}
        result = plan_fertilizer_workflow([salt], {'K':10}, {}, 6.5,
            final_volume=VolumeLitres(100), equilibrium=dict(water_totals={}, water_mass_kg=100,
            water_analysis_id='synthetic', complete_analysis=True, carbon_boundary='closed',
            temperature_c=25, phases=[]))
        self.assertEqual(result.stages['chemistry'].error_code, 'product_chemistry_mismatch')

    def test_incidental_limits_require_a_mapping(self):
        from flahax.nutrient_acceptance import assess_incidental
        from flahax.composition import InputError
        for invalid in ([], '', 0):
            with self.assertRaises(InputError):
                assess_incidental([], invalid)

    def test_calculated_ph_matches_existing_mixed_phreeqc_reference(self):
        fixture = Path(__file__).parent/'fixtures/phreeqc/products/mixed_target_ph_nitric/expected.json'
        data = json.loads(fixture.read_text())
        totals = dict(data['runtime_totals'])
        initial = calculate_equilibrium_ph(totals, complete_analysis=True, carbon_boundary='closed', phases=[])
        self.assertAlmostEqual(initial.ph, data['initial_ph'], delta=.01)
        totals['NO3-'] += data['nitric_acid_molal']
        final = calculate_equilibrium_ph(totals, complete_analysis=True, carbon_boundary='closed', phases=[])
        self.assertAlmostEqual(final.ph, data['selected_rows'][-1]['pH'], delta=.01)
        self.assertLess(abs(final.charge_balance), 1e-12)

    def test_full_calculated_ph_acid_and_stock_path(self):
        salt = products()[5]
        config = dict(water_totals={}, water_mass_kg=100, water_analysis_id='pure-synthetic-water',
                      complete_analysis=True, carbon_boundary='closed', temperature_c=25, phases=[])
        result = plan_fertilizer_workflow([salt], {'K':10}, {}, 6.5, final_volume=VolumeLitres(100),
            maximum_concentrations={'N_NO3':10, 'P':1, 'S':1},
            equilibrium=config,
            acids=dict(products=acid_products()[:2], maximum_nutrient_error_percent=1,
                       maximum_reagent_volume_litres=.1, preferred_product_id='HNO3'),
            nitric=dict(reagent=record('n', kind='acid', name='nitric', chemicalFormula='HNO3',
                                      elements={'N_NO3':13.8}, densityKgPerL=1.4),
                        reagent_channel_id='acid', maximum_reagent_volume=VolumeLitres(.1),
                        maximum_nutrient_error_percent=1),
            stocks=dict(injection_ratio=InjectionRatio(100), tanks=[StockTank('A',VolumeLitres(2))],
                        compatibility_rules=[], solubility_limits=[record('limit', productId=salt['id'],
                        maxGramsPerLitre=50, temperatureMinC=20, temperatureMaxC=30)], temperature=TemperatureCelsius(25)))
        for stage in ('formulation','batch','chemistry','nitric','acid_selection','stocks'):
            self.assertEqual(result.stages[stage].status, 'calculated', result.stages[stage])
        self.assertEqual(result.stages['acid_selection'].value.selected_product_id, 'HNO3')
        self.assertAlmostEqual(result.stages['nitric'].value.equilibrium.target.ph, 6.5)
        self.assertGreater(result.stages['nitric'].value.reagent_volume_litres, 0)
        self.assertGreater(result.stages['chemistry'].value['mixed'].ph, 6.5)
        bad = plan_fertilizer_workflow([salt], {'K':10}, {'Ca':20}, 6.5,
            final_volume=VolumeLitres(100), equilibrium=config)
        self.assertEqual(bad.stages['chemistry'].error_code, 'inconsistent_water_analysis')

    def test_measured_titration_and_missing_stock_evidence(self):
        water, curve, reagent = inputs()
        salt = products()[5]
        result = plan_fertilizer_workflow([salt], {'K':10}, water['ions'], 6.5,
            final_volume=VolumeLitres(100), titration=dict(water_analysis=water, curve=curve,
            reagent=reagent, maximum_reagent_volume=VolumeLitres(1)),
            stocks=dict(injection_ratio=InjectionRatio(100), tanks=[StockTank('A',VolumeLitres(2))],
                        compatibility_rules=[], solubility_limits=[], temperature=TemperatureCelsius(25)))
        self.assertEqual(result.stages['titration'].status, 'requires_review')
        self.assertEqual(result.stages['stocks'].error_code, 'missing_solubility_limit')


class AcidSelectionTests(unittest.TestCase):
    def arguments(self):
        totals = {'Na+':.002,'Cl-':.002}
        initial = calculate_equilibrium_ph(totals, complete_analysis=True, carbon_boundary='closed', phases=[])
        return dict(totals=totals, initial_ph=initial.ph, target_ph=6.5,
                    products=acid_products(), water_mass_kg=100, final_volume_litres=100,
                    achieved={'Na':45.979538,'Cl':70.906}, targets={'Na':45.979538},
                    maximum_nutrient_error_percent=1, maximum_reagent_volume_litres=.1,
                    maximum_concentrations={'Cl':80, 'N_NO3':1, 'P':1, 'S':1})

    def test_four_acids_conserve_charge_and_add_the_correct_nutrients(self):
        args = self.arguments()
        result = plan_acid_options(**args)
        self.assertEqual(result.selected_product_id, 'C6H8O7')
        for candidate in result.candidates:
            self.assertEqual(candidate.status, 'accepted', candidate)
            self.assertGreater(candidate.dose_molal, 0)
            self.assertLess(abs(candidate.target.charge_balance), 2e-12)
            self.assertAlmostEqual(candidate.reagent_volume_litres, candidate.reagent_mass_g/1200)
            self.assertTrue(all(abs(v) < 1e-12 for v in candidate.target.residuals.values()))
        self.assertEqual(set(result.candidates[0].nutrient_contribution), {'N_NO3'})
        self.assertEqual(set(result.candidates[1].nutrient_contribution), {'P'})
        self.assertEqual(result.candidates[2].nutrient_contribution, {})
        self.assertEqual(set(result.candidates[3].nutrient_contribution), {'S'})

    def test_user_choice_does_not_override_nutrient_prohibitions_or_fallback(self):
        args = self.arguments()
        args['targets']['P'] = 0
        args['maximum_concentrations']['P'] = 0
        result = plan_acid_options(**args, preferred_product_id='H3PO4')
        self.assertIsNone(result.selected_product_id)
        self.assertEqual(result.candidates[1].error_code, 'nutrient_limit_exceeded')
        self.assertEqual(result.candidates[2].status, 'accepted')
        with self.assertRaises(DeliveryError):
            plan_acid_options(**args, preferred_product_id='unknown')

    def test_assay_dose_direction_and_provenance_fail_closed(self):
        args = self.arguments()
        args['products'][0]['massFraction'] = 75
        del args['products'][1]['densityKgPerL']
        args['products'][2]['source'] = ''
        result = plan_acid_options(**args)
        self.assertTrue(all(c.status == 'rejected' for c in result.candidates[:3]))
        args = self.arguments()
        args['target_ph'] = 8
        self.assertTrue(all(c.error_code == 'wrong_reagent_direction' for c in plan_acid_options(**args).candidates))


if __name__ == '__main__':
    unittest.main()
