import hashlib
import json
from importlib.resources import files
from pathlib import Path
import unittest

from flahax.aqueous_model import chemistry
from flahax.delivery_contracts import DeliveryError
from flahax.irrigation_ec import (COEFFICIENTS_SHA256, QUALIFIER, DeclaredPureWater,
                                  assay_charge_residual, calculate_ec_from_totals,
                                  calculate_irrigation_ec, compare_measured_ec, covered_species,
                                  ionic_molal_conductivity,
                                  load_conductivity_coefficients)
from flahax import plan_equilibrium_delivery
from flahax.irrigation_ec import calculate_irrigation_ec_from_plan
from flahax.measured_water import balance_water_analysis

FIXTURES = Path(__file__).parent / 'fixtures' / 'conductivity'


class CoefficientTests(unittest.TestCase):
    def test_shipped_table_matches_independent_transcription(self):
        shipped = load_conductivity_coefficients()['ions']
        fixture = json.loads((FIXTURES / 'mccleskey2012_table1_independent.json').read_text())['ions']
        self.assertEqual(set(shipped), set(fixture))
        self.assertEqual(len(shipped), 28)
        for ion in shipped:
            self.assertEqual(shipped[ion], fixture[ion], ion)

    def test_species_map_targets_exist_and_cover_flahax_species(self):
        data = load_conductivity_coefficients()
        names = {r['name'] for r in chemistry()['aqueous']}
        self.assertEqual(len(data['species_map']), 21)
        self.assertEqual(covered_species(), frozenset(data['species_map']))
        for species, ion in data['species_map'].items():
            self.assertIn(species, names); self.assertIn(ion, data['ions'])

    def test_eq8_at_25c_by_hand(self):
        # K+: l0 = 0.003046*625 + 1.261*25 + 40.70 = 74.12875; A = 49.22375; B = 1.5
        self.assertAlmostEqual(ionic_molal_conductivity('K+', 0.0), 74.12875, places=9)
        self.assertAlmostEqual(ionic_molal_conductivity('K+', 0.01), 74.12875 - 49.22375*0.1/1.15, places=9)
        # Cl-: l0 = 76.800625; A = 49.51375
        self.assertAlmostEqual(ionic_molal_conductivity('Cl-', 0.01), 76.800625 - 49.51375*0.1/1.15, places=9)

    def test_coefficient_file_is_pinned(self):
        pinned = '3eecd89688f8be46ada86cd1d55763648b729167c74c88f9f36f897da4ae5c9b'
        self.assertEqual(COEFFICIENTS_SHA256, pinned)
        raw = files('flahax').joinpath('data/conductivity_mccleskey2012.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), pinned)

    def test_lambda_rejects_unknown_ion_and_bad_strength(self):
        for args in (('Li2+', .01), ('K+', -1.), ('K+', float('nan'))):
            with self.subTest(args=args), self.assertRaises(DeliveryError):
                ionic_molal_conductivity(*args)


class TotalsTests(unittest.TestCase):
    def calc(self, totals, **kw):
        kw.setdefault('ph_mode', 'calculated'); kw.setdefault('phase_policy', 'dissolved')
        return calculate_ec_from_totals(totals, solution_id='t', **kw)

    def test_kcl_001_is_estimated_by_hand_value(self):
        r = self.calc({'K+': .01, 'Cl-': .01})
        self.assertEqual(r.status, 'estimated')
        # Hand value 1.42343 for K+/Cl- plus pure-water H+/OH- (about 5.5e-5).
        self.assertAlmostEqual(r.ec25_ms_cm, 1.42349, places=4)
        self.assertEqual(r.qualifier, QUALIFIER)
        self.assertEqual(r.audit['conductivity_units'], 'mS kg cm-1 mol-1 x mol/kgw')
        self.assertEqual(r.audit['coefficientsSha256'], COEFFICIENTS_SHA256)
        self.assertAlmostEqual(sum(r.transport_numbers.values()), 1.0, places=12)

    def test_neutral_pair_carries_no_current_and_hydroxo_pair_is_partial(self):
        m = 1/246.47
        r = self.calc({'Mg+2': m, 'SO4-2': m})
        self.assertEqual((r.status, r.reason), ('partial', 'missing_species_contributions'))
        self.assertIn('MgOH+', [s['name'] for s in r.missing_species])
        self.assertAlmostEqual(r.known_species_subtotal_ms_cm, 0.725, delta=0.001)
        self.assertNotIn('MgSO4', r.contributions_ms_cm)

    def test_phosphate_is_partial_and_named(self):
        m = 1/136.09
        r = self.calc({'K+': m, 'PO4-3': m})
        self.assertEqual((r.status, r.reason), ('partial', 'missing_species_contributions'))
        self.assertIsNone(r.ec25_ms_cm)
        self.assertIn({'name': 'H2PO4-', 'charge': -1}, [{k: s[k] for k in ('name', 'charge')} for s in r.missing_species])
        self.assertAlmostEqual(r.known_species_subtotal_ms_cm, 0.524, delta=0.002)

    def test_ionic_strength_envelope(self):
        self.assertEqual(self.calc({'K+': .0995, 'Cl-': .0995}).status, 'estimated')
        # At 0.1: totals found by bisection give speciated I within 1e-6 of 0.1.
        at = self.calc({'K+': 0.09999975, 'Cl-': 0.09999975})
        self.assertEqual(at.status, 'estimated')
        self.assertLessEqual(at.ionic_strength, 0.1)
        self.assertLess(abs(at.ionic_strength - 0.1), 1e-6)
        r = self.calc({'K+': .12, 'Cl-': .12})
        self.assertEqual((r.status, r.reason, r.ec25_ms_cm), ('not_supported', 'ionic_strength_outside_domain', None))

    def test_temperature_and_carbon_not_supported(self):
        self.assertEqual(self.calc({'K+': .01, 'Cl-': .01}, temperature_c=20).reason, 'temperature_outside_reference')
        self.assertEqual(self.calc({'K+': .01, 'Cl-': .01}, carbon_boundary='open').reason, 'unsupported_carbon_boundary')

    def test_supplied_ph_with_unrecorded_acid_is_partial(self):
        self.assertEqual(self.calc({'K+': .01, 'Cl-': .01}, ph_mode='supplied', ph=7.0).status, 'estimated')
        r = self.calc({'K+': .01, 'Cl-': .01}, ph_mode='supplied', ph=4.0)
        self.assertEqual((r.status, r.reason), ('partial', 'unrecorded_counterions'))
        self.assertGreater(r.unrecorded_counterions_eq_per_kgw, 0)
        excess = r.audit['charge_balance'] - r.assay_charge_residual['eq_per_kgw']
        self.assertEqual(r.unrecorded_counterions_eq_per_kgw, excess)

    def test_unrecorded_counterions_by_status(self):
        tot = {'K+': .01, 'Cl-': .01}
        est = self.calc(tot, ph_mode='supplied', ph=7.0)
        self.assertEqual(est.status, 'estimated'); self.assertIsNone(est.unrecorded_counterions_eq_per_kgw)
        self.assertIsNone(self.calc(tot).unrecorded_counterions_eq_per_kgw)
        # Supplied-mode O5 gate: the whole speciated imbalance is reported.
        o5 = self.calc(tot, ph_mode='supplied', ph=7.0, assay_charge_residual_eq_per_kgw=1e-4)
        self.assertEqual((o5.status, o5.reason), ('partial', 'unrecorded_counterions'))
        self.assertEqual(o5.unrecorded_counterions_eq_per_kgw, o5.audit['charge_balance'])
        self.assertTrue(o5.contributions_ms_cm)

    def test_assay_residual_gate(self):
        tot = {'K+': .01, 'Cl-': .01}
        ok = self.calc(tot, assay_charge_residual_eq_per_kgw=1e-5)       # 0.05 %
        self.assertEqual(ok.status, 'estimated'); self.assertAlmostEqual(ok.assay_charge_residual['percent'], 0.05, places=3)
        self.assertEqual(self.calc(tot, assay_charge_residual_eq_per_kgw=1e-4).reason, 'assay_charge_residual_too_large')

    def test_not_supported_carries_no_contributions(self):
        r = self.calc({'K+': .01, 'Cl-': .01}, assay_charge_residual_eq_per_kgw=1e-4)
        self.assertEqual((r.status, r.reason), ('not_supported', 'assay_charge_residual_too_large'))
        self.assertEqual((r.contributions_ms_cm, r.transport_numbers), ({}, {}))
        self.assertIsNone(r.known_species_subtotal_ms_cm); self.assertIsNone(r.ec25_ms_cm)

    def test_declared_percent_overrides_speciated_percent(self):
        tot = {'K+': .01, 'Cl-': .01}
        r = self.calc(tot, assay_charge_residual_eq_per_kgw=1e-4, assay_charge_residual_percent=0.05)
        self.assertEqual(r.status, 'estimated')
        self.assertEqual(r.assay_charge_residual, {'eq_per_kgw': 1e-4, 'percent': 0.05})
        self.assertEqual(self.calc(tot, assay_charge_residual_percent=0.2).reason, 'assay_charge_residual_too_large')
        for bad in (float('nan'), True, '0.05'):
            with self.subTest(bad=bad), self.assertRaises(DeliveryError):
                self.calc(tot, assay_charge_residual_percent=bad)

    def test_solution_id_must_be_nonempty_string(self):
        for sid in ('', '  ', None, 3):
            with self.subTest(sid=sid), self.assertRaises(DeliveryError) as c:
                calculate_ec_from_totals({'K+': .01, 'Cl-': .01}, solution_id=sid,
                                         ph_mode='calculated', phase_policy='dissolved')
            self.assertEqual(c.exception.code, 'missing_field')

    def test_phase_policy_recorded_and_supersaturation_warned(self):
        tot = {'Ca+2': .004, 'SO4-2': .004, 'PO4-3': .001, 'K+': .003}
        r = self.calc(tot, ph_mode='supplied', ph=7.0)
        self.assertTrue(any('Hydroxylapatite' in w for w in r.warnings))
        e = self.calc(tot, ph_mode='supplied', ph=7.0, phase_policy='equilibrated', phases=('Hydroxylapatite',))
        self.assertEqual(e.audit['phases'], ('Hydroxylapatite',)); self.assertTrue(e.precipitated_molal)

    def test_invalid_mode_inputs_raise(self):
        for kw in ({'ph': 7.0}, {'ph_mode': 'supplied'}, {'ph_mode': 'supplied', 'ph': float('nan')},
                   {'ph_mode': 'guess'}, {'phase_policy': 'dissolved', 'phases': ('Gypsum',)},
                   {'phase_policy': 'equilibrated'}):
            with self.subTest(kw=kw), self.assertRaises(DeliveryError):
                self.calc({'K+': .01, 'Cl-': .01}, **kw)

PURE = DeclaredPureWater('ro-test')


class CatalogueTests(unittest.TestCase):
    # 2026-10-18 catalogue correction (Mg Nitrate D1 / phosphoric 75 %): the shipped Mg Nitrate is now
    # Mg(NO3)2.6H2O theory and charge-balanced. The retired row (N_NO3 11 / Mg 9.65) gave these totals
    # for 1 g/kg water, a declared residual of +8.7368e-5 eq/kgw (0.5532 %); the O5 tests below keep it.
    OLD_MG_NITRATE_1G = {'Mg+2': 0.003970376465747789, 'NO3-': 0.007853384451726673}
    OLD_MG_NITRATE_1G_RESIDUAL = {'eq_per_kgw': 8.736847976890429e-05, 'percent': 0.5531703166119969}

    def test_mg_nitrate_assay_residual(self):
        # 2026-10-18 catalogue correction (Mg Nitrate D1 / phosphoric 75 %): was 0.5532 %, now ~0.
        self.assertAlmostEqual(assay_charge_residual({'Mg Nitrate': 1.0})['percent'], 0.0, places=3)
        old = self.OLD_MG_NITRATE_1G
        net, absolute = 2 * old['Mg+2'] - old['NO3-'], 2 * old['Mg+2'] + old['NO3-']
        self.assertAlmostEqual(100 * net / absolute, 0.5532, places=3)

    def test_residual_gate_by_mode(self):
        # 2026-10-18 catalogue correction (Mg Nitrate D1 / phosphoric 75 %): the retired Mg Nitrate
        # totals and residual are passed explicitly, so the O5 gate by pH mode stays covered.
        residual = self.OLD_MG_NITRATE_1G_RESIDUAL
        kw = dict(solution_id='r', phase_policy='dissolved',
                  assay_charge_residual_eq_per_kgw=residual['eq_per_kgw'],
                  assay_charge_residual_percent=residual['percent'])
        c = calculate_ec_from_totals(self.OLD_MG_NITRATE_1G, ph_mode='calculated', **kw)
        self.assertEqual((c.status, c.reason), ('not_supported', 'assay_charge_residual_too_large'))
        s = calculate_ec_from_totals(self.OLD_MG_NITRATE_1G, ph_mode='supplied', ph=6.0, **kw)
        self.assertEqual((s.status, s.reason), ('partial', 'unrecorded_counterions'))

    def test_gate_uses_declared_form_percent(self):
        # 2026-10-18 catalogue correction (Mg Nitrate D1 / phosphoric 75 %): the mix below
        # (0.40 old Mg Nitrate + 1.0 MgSO4.7H2O + 0.5 K2SO4) had a declared residual of 0.0914 %;
        # its totals and residual are now passed explicitly to keep the declared-percent gate covered.
        totals = {'Mg+2': 0.005644929026949188, 'SO4-2': 0.0069279475982532744,
                  'K+': 0.005738484793456493, 'NO3-': 0.0031413537806906696}
        eq, declared = 3.1093870157648636e-05, 0.09138377465402972
        kw = dict(solution_id='r', ph_mode='calculated', phase_policy='dissolved',
                  assay_charge_residual_eq_per_kgw=eq)
        speciated = calculate_ec_from_totals(totals, **kw)
        self.assertEqual(speciated.reason, 'assay_charge_residual_too_large')  # speciated % > 0.1
        r = calculate_ec_from_totals(totals, assay_charge_residual_percent=declared, **kw)
        self.assertNotEqual(r.reason, 'assay_charge_residual_too_large')
        self.assertAlmostEqual(r.assay_charge_residual['percent'], 0.0914, places=4)
        # The catalogue path still records the declared-form percent it gated on.
        doses = {'Mg Nitrate': 0.40, 'Magnesium Sulfate (Heptahydrate)': 1.0, 'Potassium Sulfate': 0.5}
        c = calculate_irrigation_ec(doses, recipe_id='r', water=PURE, ph_mode='calculated', phase_policy='dissolved')
        self.assertEqual(c.assay_charge_residual['percent'], c.audit['assay_charge_residual_declared_percent'])
        self.assertAlmostEqual(c.audit['assay_charge_residual_declared_percent'],
                               assay_charge_residual(doses)['percent'], places=12)

    def test_recipe_and_reagent_ids_must_be_nonempty_strings(self):
        for rid in ('', ' ', None, 7):
            with self.subTest(recipe_id=rid), self.assertRaises(DeliveryError) as c:
                calculate_irrigation_ec({'Potassium Nitrate': .5}, recipe_id=rid, water=PURE,
                                        ph_mode='calculated', phase_policy='dissolved')
            self.assertEqual(c.exception.code, 'missing_field')
        for gid in ('', '  ', 5):
            with self.subTest(reagent_id=gid), self.assertRaises(DeliveryError) as c:
                calculate_irrigation_ec({'Potassium Nitrate': .5}, recipe_id='r', water=PURE,
                                        reagent_additions_molal={'NO3-': 1e-4}, reagent_id=gid,
                                        ph_mode='calculated', phase_policy='dissolved')
            self.assertEqual(c.exception.code, 'missing_field')

    def test_reagent_additions_recorded_as_copy(self):
        additions = {'NO3-': 1e-4}
        r = calculate_irrigation_ec({'Potassium Nitrate': .5}, recipe_id='r', water=PURE,
                                    reagent_additions_molal=additions, reagent_id='nitric',
                                    ph_mode='supplied', ph=6.0, phase_policy='dissolved')
        self.assertEqual(r.audit['reagent_additions_molal'], {'NO3-': 1e-4})
        self.assertIsNot(r.audit['reagent_additions_molal'], additions)
        none = calculate_irrigation_ec({}, recipe_id='r', water=PURE, ph_mode='calculated', phase_policy='dissolved')
        self.assertEqual(none.audit['reagent_additions_molal'], {})

    def test_chelate_residual_reported_not_crash(self):
        r = calculate_irrigation_ec({'Iron EDTA': 0.05, 'Potassium Nitrate': 0.5}, recipe_id='r', water=PURE,
                                    ph_mode='calculated', phase_policy='dissolved')
        self.assertEqual(r.status, 'not_supported'); self.assertEqual(r.reason, 'assay_charge_residual_too_large')
        self.assertLess(r.audit['assay_charge_residual_declared_percent'], -0.1)

    def test_zero_doses_in_pure_water(self):
        r = calculate_irrigation_ec({}, recipe_id='r', water=PURE, ph_mode='calculated', phase_policy='dissolved')
        self.assertEqual(r.status, 'estimated'); self.assertAlmostEqual(r.ec25_ms_cm, 5.48e-5, delta=2e-6)

    def test_water_input_contract(self):
        for water, wid in (({}, None), ({'K+': .001}, None), (PURE, 'x')):
            with self.subTest(water=water), self.assertRaises(DeliveryError):
                calculate_irrigation_ec({'Potassium Nitrate': .5}, recipe_id='r', water=water, water_analysis_id=wid,
                                        ph_mode='calculated', phase_policy='dissolved')
        with self.assertRaises(DeliveryError):
            DeclaredPureWater('')

    def test_balanced_water_and_reagent_recorded(self):
        bw = balance_water_analysis({'Na+': .002, 'Cl-': .002}, measured_ph=7.0, alkalinity_eq_per_kg=1e-4)
        r = calculate_irrigation_ec({'Potassium Nitrate': .5}, recipe_id='r', water=bw, water_analysis_id='lab-1',
                                    reagent_additions_molal={'NO3-': 1e-4}, reagent_id='nitric',
                                    ph_mode='calculated', phase_policy='dissolved')
        self.assertEqual(r.status, 'estimated')
        self.assertEqual((r.audit['water_id'], r.audit['reagent_id'], r.audit['water_kind']), ('lab-1', 'nitric', 'balanced_analysis'))
        self.assertLess(r.ph, 7.0)

    def test_unknown_product_and_bad_dose_raise(self):
        for doses in ({'Unobtainium': 1.}, {'Potassium Nitrate': -1.}, {'Potassium Nitrate': float('nan')}):
            with self.subTest(doses=doses), self.assertRaises(DeliveryError):
                calculate_irrigation_ec(doses, recipe_id='r', water=PURE, ph_mode='calculated', phase_policy='dissolved')


class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_equilibrium_delivery import arguments
        cls.plan = plan_equilibrium_delivery(**arguments())

    def test_plan_target_state_is_used_without_resolving(self):
        r = calculate_irrigation_ec_from_plan(self.plan)
        self.assertEqual(r.status, 'estimated')
        self.assertEqual(r.ph, self.plan.target_ph)
        self.assertEqual(r.audit['ph_mode'], 'supplied')
        self.assertEqual((r.audit['water_id'], r.audit['reagent_id']), ('synthetic-complete-water-v1', 'nitric'))
        self.assertAlmostEqual(r.ionic_strength, self.plan.equilibrium.target.ionic_strength, places=15)
        self.assertGreater(r.ec25_ms_cm, 0)

    def test_audit_identity_and_policy(self):
        r = calculate_irrigation_ec_from_plan(self.plan)
        self.assertTrue(r.audit['recipe_id'].startswith('plan-recipe:'))
        self.assertEqual(r.audit['solution_id'], r.audit['recipe_id'])
        self.assertEqual(r.audit['reagent_molal'], self.plan.equilibrium.nitric_acid_molal)
        self.assertEqual(r.audit['water_kind'], 'plan_water_totals')
        self.assertEqual(r.audit['doses_g_per_kg_water'], self.plan.audit['productDosesGPerKgWater'])
        for key in ('catalogueSha256', 'waterTotalsMolal', 'initialPh'):
            self.assertEqual(r.audit[key], self.plan.audit[key], key)
        self.assertEqual(r.assay_charge_residual['percent'], r.audit['assay_charge_residual_declared_percent'])
        with self.assertRaises(DeliveryError) as c:
            calculate_irrigation_ec_from_plan(self.plan, phase_policy='equilibrated')
        self.assertEqual(c.exception.code, 'invalid_phase_policy')


class ComparisonTests(unittest.TestCase):
    def test_difference_only_no_verdict(self):
        p = calculate_ec_from_totals({'K+': .01, 'Cl-': .01}, solution_id='kcl', ph_mode='calculated', phase_policy='dissolved')
        c = compare_measured_ec(p, measured_ec25_ms_cm=1.413, meter_reference_temperature_c=25)
        self.assertEqual(set(c), {'predicted_ec25_ms_cm', 'measured_ec25_ms_cm', 'difference_ms_cm',
                                  'relative_difference_percent', 'audit', 'qualifier'})
        self.assertAlmostEqual(c['difference_ms_cm'], 1.413 - p.ec25_ms_cm, places=12)
        self.assertAlmostEqual(c['relative_difference_percent'], 100 * (1.413 - p.ec25_ms_cm) / p.ec25_ms_cm, places=9)
        self.assertEqual(c['qualifier'], p.qualifier)
        self.assertEqual(c['audit'], p.audit)
        self.assertIsNot(c['audit'], p.audit)

    def test_refusals(self):                                         # Review Focus 5
        p = calculate_ec_from_totals({'K+': .01, 'Cl-': .01}, solution_id='kcl', ph_mode='calculated', phase_policy='dissolved')
        partial = calculate_ec_from_totals({'K+': .007, 'PO4-3': .007}, solution_id='mkp', ph_mode='calculated', phase_policy='dissolved')
        cases = [(partial, 1.0, 25), (p, 1.0, 20), (p, -1.0, 25), (p, float('nan'), 25), (p, True, 25)]
        for pred, measured, ref in cases:
            with self.subTest(measured=measured, ref=ref), self.assertRaises(DeliveryError):
                compare_measured_ec(pred, measured_ec25_ms_cm=measured, meter_reference_temperature_c=ref)

    def test_refusal_codes(self):
        p = calculate_ec_from_totals({'K+': .01, 'Cl-': .01}, solution_id='kcl', ph_mode='calculated', phase_policy='dissolved')
        partial = calculate_ec_from_totals({'K+': .007, 'PO4-3': .007}, solution_id='mkp', ph_mode='calculated', phase_policy='dissolved')
        for pred, measured, ref, code in [(partial, 1.0, 25, 'incomplete_prediction'),
                                          (p, 1.0, 20, 'temperature_reference_mismatch'),
                                          (p, -1.0, 25, 'invalid_value'), (p, True, 25, 'invalid_value')]:
            with self.assertRaises(DeliveryError) as c:
                compare_measured_ec(pred, measured_ec25_ms_cm=measured, meter_reference_temperature_c=ref)
            self.assertEqual(c.exception.code, code)


if __name__ == '__main__':
    unittest.main()
