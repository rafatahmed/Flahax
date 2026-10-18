import hashlib
import json
from importlib.resources import files
from pathlib import Path
import unittest

from flahax.aqueous_model import chemistry
from flahax.delivery_contracts import DeliveryError
from flahax.irrigation_ec import (COEFFICIENTS_SHA256, QUALIFIER,
                                  calculate_ec_from_totals, covered_species,
                                  ionic_molal_conductivity,
                                  load_conductivity_coefficients)

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
        raw = files('flahax').joinpath('data/conductivity_mccleskey2012.json').read_bytes()
        self.assertEqual(COEFFICIENTS_SHA256, hashlib.sha256(raw).hexdigest())

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

    def test_assay_residual_gate(self):
        tot = {'K+': .01, 'Cl-': .01}
        ok = self.calc(tot, assay_charge_residual_eq_per_kgw=1e-5)       # 0.05 %
        self.assertEqual(ok.status, 'estimated'); self.assertAlmostEqual(ok.assay_charge_residual['percent'], 0.05, places=3)
        self.assertEqual(self.calc(tot, assay_charge_residual_eq_per_kgw=1e-4).reason, 'assay_charge_residual_too_large')

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


if __name__ == '__main__':
    unittest.main()
