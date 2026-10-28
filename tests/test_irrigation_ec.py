# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.irrigation_ec."""

import hashlib
import json
from importlib.resources import files
from pathlib import Path
import unittest

from flahax.aqueous_model import chemistry
from flahax.delivery_contracts import DeliveryError
from flahax.irrigation_ec import (
    COEFFICIENTS_SHA256,
    LAMBDA_MAX_PER_CHARGE,
    QUALIFIER,
    DeclaredPureWater,
    assay_charge_residual,
    calculate_ec_from_totals,
    calculate_irrigation_ec,
    calculate_irrigation_ec_band,
    compare_measured_ec,
    covered_species,
    ionic_molal_conductivity,
    load_conductivity_coefficients,
)
from flahax import make_grade, plan_equilibrium_delivery, resolve_material
from flahax.irrigation_ec import calculate_irrigation_ec_from_plan
from flahax.measured_water import balance_water_analysis

FIXTURES = Path(__file__).parent / 'fixtures' / 'conductivity'
# 1/136.09 mol/kgw KH2PO4 at calculated pH: K+, H+ and (M2b) H2PO4- / HPO4-2 contributions.
KH2PO4_SUBTOTAL = 0.738


class CoefficientTests(unittest.TestCase):
    def test_shipped_table_matches_independent_transcription(self):
        shipped = load_conductivity_coefficients()['ions']
        fixture = json.loads((FIXTURES / 'mccleskey2012_table1_independent.json').read_text())[
            'ions'
        ]
        self.assertEqual(set(shipped), set(fixture))
        self.assertEqual(len(shipped), 28)
        for ion in shipped:
            self.assertEqual(shipped[ion], fixture[ion], ion)

    def test_species_map_targets_exist_and_cover_flahax_species(self):
        data = load_conductivity_coefficients()
        names = {r['name'] for r in chemistry()['aqueous']}
        self.assertEqual(len(data['species_map']), 21)
        # M2b: plus the supplementary 25 C phosphate ions (decision O1).
        self.assertEqual(covered_species(), frozenset(data['species_map']) | {'H2PO4-', 'HPO4-2'})
        for species, ion in data['species_map'].items():
            self.assertIn(species, names)
            self.assertIn(ion, data['ions'])

    def test_eq8_at_25c_by_hand(self):
        # K+: l0 = 0.003046*625 + 1.261*25 + 40.70 = 74.12875; A = 49.22375; B = 1.5
        self.assertAlmostEqual(ionic_molal_conductivity('K+', 0.0), 74.12875, places=9)
        self.assertAlmostEqual(
            ionic_molal_conductivity('K+', 0.01), 74.12875 - 49.22375 * 0.1 / 1.15, places=9
        )
        # Cl-: l0 = 76.800625; A = 49.51375
        self.assertAlmostEqual(
            ionic_molal_conductivity('Cl-', 0.01), 76.800625 - 49.51375 * 0.1 / 1.15, places=9
        )

    def test_coefficient_file_is_pinned(self):
        pinned = '7f5e88deb3d23798588113988611e7d729318f570651655051a1e3d08024a3ca'
        self.assertEqual(COEFFICIENTS_SHA256, pinned)
        raw = files('flahax').joinpath('data/conductivity_mccleskey2012.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), pinned)

    def test_lambda_rejects_unknown_ion_and_bad_strength(self):
        for args in (('Li2+', 0.01), ('K+', -1.0), ('K+', float('nan'))):
            with self.subTest(args=args), self.assertRaises(DeliveryError):
                ionic_molal_conductivity(*args)


class TotalsTests(unittest.TestCase):
    def calc(self, totals, **kw):
        kw.setdefault('ph_mode', 'calculated')
        kw.setdefault('phase_policy', 'dissolved')
        return calculate_ec_from_totals(totals, solution_id='t', **kw)

    def test_kcl_001_is_estimated_by_hand_value(self):
        r = self.calc({'K+': 0.01, 'Cl-': 0.01})
        self.assertEqual(r.status, 'estimated')
        # Hand value 1.42343 for K+/Cl- plus pure-water H+/OH- (about 5.5e-5).
        self.assertAlmostEqual(r.ec25_ms_cm, 1.42349, places=4)
        self.assertEqual(r.qualifier, QUALIFIER)
        self.assertEqual(r.audit['conductivity_units'], 'mS kg cm-1 mol-1 x mol/kgw')
        self.assertEqual(r.audit['coefficientsSha256'], COEFFICIENTS_SHA256)
        self.assertAlmostEqual(sum(r.transport_numbers.values()), 1.0, places=12)

    def test_neutral_pair_carries_no_current_and_hydroxo_pair_is_unknown(self):
        m = 1 / 246.47
        r = self.calc({'Mg+2': m, 'SO4-2': m})
        # M2a O2 bound: was ('partial', 'missing_species_contributions').
        self.assertEqual(
            (r.status, r.reason, r.bounded), ('partial', 'missing_species_contributions', False)
        )
        self.assertIn('MgOH+', [s['name'] for s in r.missing_species])
        self.assertAlmostEqual(r.known_species_subtotal_ms_cm, 0.725, delta=0.001)
        self.assertIsNone(r.ec25_range_ms_cm)
        self.assertNotIn('MgSO4', r.contributions_ms_cm)

    def test_phosphate_is_partial_and_missing_species_named(self):
        m = 1 / 136.09
        r = self.calc({'K+': m, 'PO4-3': m})
        # M2a O2 bound: was ('partial', 'missing_species_contributions') with ec25_ms_cm None.
        # M2b: H2PO4- is now covered (subtotal was 0.524); the minor pair KHPO4- remains unknown.
        self.assertEqual(
            (r.status, r.reason, r.bounded), ('partial', 'missing_species_contributions', False)
        )
        self.assertIsNone(r.ec25_ms_cm)
        self.assertIn(
            {'name': 'KHPO4-', 'charge': -1},
            [{k: s[k] for k in ('name', 'charge')} for s in r.missing_species],
        )
        self.assertIn('H2PO4-', r.contributions_ms_cm)
        self.assertAlmostEqual(r.known_species_subtotal_ms_cm, KH2PO4_SUBTOTAL, delta=0.002)

    def test_ionic_strength_envelope(self):
        self.assertEqual(self.calc({'K+': 0.0995, 'Cl-': 0.0995}).status, 'estimated')
        # At 0.1: totals found by bisection give speciated I within 1e-6 of 0.1.
        at = self.calc({'K+': 0.09999975, 'Cl-': 0.09999975})
        self.assertEqual(at.status, 'estimated')
        self.assertLessEqual(at.ionic_strength, 0.1)
        self.assertLess(abs(at.ionic_strength - 0.1), 1e-6)
        r = self.calc({'K+': 0.12, 'Cl-': 0.12})
        self.assertEqual(
            (r.status, r.reason, r.ec25_ms_cm),
            ('not_supported', 'ionic_strength_outside_domain', None),
        )

    def test_temperature_and_carbon_not_supported(self):
        self.assertEqual(
            self.calc({'K+': 0.01, 'Cl-': 0.01}, temperature_c=20).reason,
            'temperature_outside_reference',
        )
        self.assertEqual(
            self.calc({'K+': 0.01, 'Cl-': 0.01}, carbon_boundary='open').reason,
            'unsupported_carbon_boundary',
        )

    def test_supplied_ph_with_unrecorded_acid_is_partial(self):
        self.assertEqual(
            self.calc({'K+': 0.01, 'Cl-': 0.01}, ph_mode='supplied', ph=7.0).status, 'estimated'
        )
        r = self.calc({'K+': 0.01, 'Cl-': 0.01}, ph_mode='supplied', ph=4.0)
        self.assertEqual((r.status, r.reason), ('partial', 'unrecorded_counterions'))
        self.assertGreater(r.unrecorded_counterions_eq_per_kgw, 0)
        excess = r.audit['charge_balance'] - r.assay_charge_residual['eq_per_kgw']
        self.assertEqual(r.unrecorded_counterions_eq_per_kgw, excess)

    def test_unrecorded_counterions_by_status(self):
        tot = {'K+': 0.01, 'Cl-': 0.01}
        est = self.calc(tot, ph_mode='supplied', ph=7.0)
        self.assertEqual(est.status, 'estimated')
        self.assertIsNone(est.unrecorded_counterions_eq_per_kgw)
        self.assertIsNone(self.calc(tot).unrecorded_counterions_eq_per_kgw)
        # Supplied-mode O5 gate: the whole speciated imbalance is reported.
        o5 = self.calc(tot, ph_mode='supplied', ph=7.0, assay_charge_residual_eq_per_kgw=1e-4)
        self.assertEqual((o5.status, o5.reason), ('partial', 'unrecorded_counterions'))
        self.assertEqual(o5.unrecorded_counterions_eq_per_kgw, o5.audit['charge_balance'])
        self.assertTrue(o5.contributions_ms_cm)

    def test_assay_residual_gate(self):
        tot = {'K+': 0.01, 'Cl-': 0.01}
        ok = self.calc(tot, assay_charge_residual_eq_per_kgw=1e-5)  # 0.05 %
        self.assertEqual(ok.status, 'estimated')
        self.assertAlmostEqual(ok.assay_charge_residual['percent'], 0.05, places=3)
        self.assertEqual(
            self.calc(tot, assay_charge_residual_eq_per_kgw=1e-4).reason,
            'assay_charge_residual_too_large',
        )

    def test_not_supported_carries_no_contributions(self):
        r = self.calc({'K+': 0.01, 'Cl-': 0.01}, assay_charge_residual_eq_per_kgw=1e-4)
        self.assertEqual(
            (r.status, r.reason), ('not_supported', 'assay_charge_residual_too_large')
        )
        self.assertEqual((r.contributions_ms_cm, r.transport_numbers), ({}, {}))
        self.assertIsNone(r.known_species_subtotal_ms_cm)
        self.assertIsNone(r.ec25_ms_cm)

    def test_declared_percent_overrides_speciated_percent(self):
        tot = {'K+': 0.01, 'Cl-': 0.01}
        r = self.calc(
            tot, assay_charge_residual_eq_per_kgw=1e-4, assay_charge_residual_percent=0.05
        )
        self.assertEqual(r.status, 'estimated')
        self.assertEqual(r.assay_charge_residual, {'eq_per_kgw': 1e-4, 'percent': 0.05})
        self.assertEqual(
            self.calc(tot, assay_charge_residual_percent=0.2).reason,
            'assay_charge_residual_too_large',
        )
        for bad in (float('nan'), True, '0.05'):
            with self.subTest(bad=bad), self.assertRaises(DeliveryError):
                self.calc(tot, assay_charge_residual_percent=bad)

    def test_solution_id_must_be_nonempty_string(self):
        for sid in ('', '  ', None, 3):
            with self.subTest(sid=sid), self.assertRaises(DeliveryError) as c:
                calculate_ec_from_totals(
                    {'K+': 0.01, 'Cl-': 0.01},
                    solution_id=sid,
                    ph_mode='calculated',
                    phase_policy='dissolved',
                )
            self.assertEqual(c.exception.code, 'missing_field')

    def test_phase_policy_recorded_and_supersaturation_warned(self):
        tot = {'Ca+2': 0.004, 'SO4-2': 0.004, 'PO4-3': 0.001, 'K+': 0.003}
        r = self.calc(tot, ph_mode='supplied', ph=7.0)
        self.assertTrue(any('Hydroxylapatite' in w for w in r.warnings))
        e = self.calc(
            tot,
            ph_mode='supplied',
            ph=7.0,
            phase_policy='equilibrated',
            phases=('Hydroxylapatite',),
        )
        self.assertEqual(e.audit['phases'], ('Hydroxylapatite',))
        self.assertTrue(e.precipitated_molal)

    def test_invalid_mode_inputs_raise(self):
        for kw in (
            {'ph': 7.0},
            {'ph_mode': 'supplied'},
            {'ph_mode': 'supplied', 'ph': float('nan')},
            {'ph_mode': 'guess'},
            {'phase_policy': 'dissolved', 'phases': ('Gypsum',)},
            {'phase_policy': 'equilibrated'},
        ):
            with self.subTest(kw=kw), self.assertRaises(DeliveryError):
                self.calc({'K+': 0.01, 'Cl-': 0.01}, **kw)


class BoundTests(unittest.TestCase):
    """Unknown contributions cannot be replaced by the historical universal bound."""

    KH2PO4 = {'K+': 1 / 136.09, 'PO4-3': 1 / 136.09}

    def calc(self, totals, **kw):
        kw.setdefault('ph_mode', 'calculated')
        kw.setdefault('phase_policy', 'dissolved')
        return calculate_ec_from_totals(totals, solution_id='b', **kw)

    def test_lambda_max_constant(self):
        self.assertEqual(LAMBDA_MAX_PER_CHARGE, 80.0)

    def test_kh2po4_has_partial_subtotal_without_unproven_bound(self):
        r = self.calc(self.KH2PO4)
        self.assertEqual((r.status, r.reason), ('partial', 'missing_species_contributions'))
        self.assertAlmostEqual(r.known_species_subtotal_ms_cm, KH2PO4_SUBTOTAL, delta=0.002)
        self.assertEqual(r.known_species_subtotal_ms_cm, sum(r.contributions_ms_cm.values()))
        self.assertFalse(r.bounded)
        for value in (
            r.ec25_ms_cm,
            r.ec25_range_ms_cm,
            r.uncertainty_ms_cm,
            r.uncovered_bound_ms_cm,
            r.audit['lambda_max_per_charge'],
        ):
            self.assertIsNone(value)
        self.assertIn('KHPO4-', [s['name'] for s in r.missing_species])
        self.assertNotIn('H2PO4-', [s['name'] for s in r.missing_species])
        self.assertTrue(all(s['molal'] > 1e-12 for s in r.missing_species))
        self.assertEqual(r.transport_numbers, {})
        self.assertEqual(r.qualifier, QUALIFIER)

    def test_unbounded_result_unchanged(self):  # Review Focus 2
        r = self.calc({'K+': 0.01, 'Cl-': 0.01})
        self.assertEqual(r.status, 'estimated')
        self.assertFalse(r.bounded)
        self.assertIsNone(r.ec25_range_ms_cm)
        self.assertIsNone(r.uncertainty_ms_cm)
        self.assertIsNone(r.uncovered_bound_ms_cm)
        self.assertIsNone(r.known_species_subtotal_ms_cm)
        self.assertEqual(r.missing_species, ())
        self.assertAlmostEqual(r.ec25_ms_cm, 1.42349, places=4)
        self.assertAlmostEqual(sum(r.transport_numbers.values()), 1.0, places=12)
        self.assertIsNone(r.audit['uncovered_bound_ms_cm'])
        self.assertIsNone(r.audit['lambda_max_per_charge'])

    def test_unrecorded_counterions_still_partial(self):  # Review Focus 1
        r = self.calc(self.KH2PO4, ph_mode='supplied', ph=4.0)
        self.assertEqual((r.status, r.reason), ('partial', 'unrecorded_counterions'))
        self.assertFalse(r.bounded)
        self.assertIsNone(r.ec25_ms_cm)
        self.assertIsNone(r.ec25_range_ms_cm)
        self.assertIsNone(r.uncertainty_ms_cm)
        self.assertIsNone(r.uncovered_bound_ms_cm)
        self.assertIsNone(r.audit['uncovered_bound_ms_cm'])
        self.assertTrue(r.missing_species)

    def test_other_rules_not_overridden(self):
        o5 = self.calc(self.KH2PO4, assay_charge_residual_eq_per_kgw=1e-3)
        self.assertEqual(
            (o5.status, o5.reason, o5.bounded),
            ('not_supported', 'assay_charge_residual_too_large', False),
        )
        self.assertIsNone(o5.ec25_range_ms_cm)
        for kw, reason in (
            ({'temperature_c': 20}, 'temperature_outside_reference'),
            ({'carbon_boundary': 'open'}, 'unsupported_carbon_boundary'),
        ):
            r = self.calc(self.KH2PO4, **kw)
            self.assertEqual((r.status, r.reason, r.bounded), ('not_supported', reason, False))
            self.assertIsNone(r.audit['uncovered_bound_ms_cm'])
        big = self.calc({'K+': 0.12, 'PO4-3': 0.12})
        self.assertEqual(
            (big.status, big.reason, big.bounded),
            ('not_supported', 'ionic_strength_outside_domain', False),
        )

    def test_audit_inputs_cannot_override_bound_keys(self):
        for key in ('uncovered_bound_ms_cm', 'lambda_max_per_charge'):
            with self.subTest(key=key), self.assertRaises(DeliveryError) as c:
                self.calc(self.KH2PO4, audit_inputs={key: 0.0})
            self.assertEqual(c.exception.code, 'invalid_audit_inputs')

    def test_open_band_end_drops_nominal_bound(self):
        result = calculate_irrigation_ec_band(
            {'Potassium Monobasic Phosphate': 1.0},
            recipe_id='band',
            water=DeclaredPureWater('ro-1'),
            ph_mode='calculated',
            phase_policy='dissolved',
        )
        self.assertFalse(result['nominal'].bounded)
        self.assertEqual(result['nominal'].status, 'partial')
        for end in ('minimum', 'maximum'):
            r = result[end]
            self.assertEqual(
                (r.status, r.reason, r.bounded), ('not_supported', 'band_end_open', False)
            )
            self.assertIsNone(r.ec25_range_ms_cm)
            self.assertIsNone(r.uncertainty_ms_cm)
            self.assertIsNone(r.uncovered_bound_ms_cm)
            self.assertIsNone(r.audit['uncovered_bound_ms_cm'])

    def test_all_shipped_formulas_respect_phosphate_fit_domain(self):
        # Historical raw failures are retained in conductivity-qualification/tests.log.
        # F08's independent oracle forbids an unqualified out-of-fit prediction.
        from flahax.engine import load_library, recommend

        library = load_library()
        limit = load_conductivity_coefficients()['supplementary']['fit']['max_ionic_strength']
        checked = 0
        for formula in library['formulas']:
            fit = recommend(library['salts'], formula['targets'])
            doses = {s['name']: s['gramsPerLitre'] for s in fit['salts']}
            r = calculate_irrigation_ec(
                doses,
                recipe_id=formula['id'],
                water=DeclaredPureWater('ro'),
                ph_mode='calculated',
                phase_policy='dissolved',
            )
            with self.subTest(formula=formula['name']):
                self.assertGreater(r.ionic_strength, limit)
                self.assertEqual(r.status, 'not_supported')
                self.assertEqual(r.reason, 'ionic_strength_outside_phosphate_fit')
                self.assertTrue(r.audit['supplementaryCoefficients'])
                self.assertIsNone(r.ec25_ms_cm)
                self.assertIsNone(r.ec25_range_ms_cm)
                self.assertFalse(r.bounded)
                self.assertEqual(r.contributions_ms_cm, {})
                checked += 1
        self.assertEqual(checked, 26)


def _assert_close_tree(case, got, want, path='supplementary'):
    """Equal structure; numbers within 1e-7 relative (1e-9 absolute floor), everything else equal.

    The fit speciates through calculated pH, which returns the midpoint of a bisection
    bracket up to 1e-7 pH wide; any change in the solver's iteration path (#61) moves
    the refit in the ninth digit, far below the ~1e-4 precision of Table III."""
    if isinstance(want, dict):
        case.assertEqual(set(got), set(want), path)
        for key in want:
            _assert_close_tree(case, got[key], want[key], f'{path}.{key}')
    elif isinstance(want, (int, float)) and not isinstance(want, bool):
        # Percentages (fit residuals, gaps to other lambda0 sources) inherit the 1e-7
        # relative bound of the conductivities they compare: 1e-5 percentage points.
        floor = 1e-5 if path.endswith('percent') else 1e-9
        case.assertAlmostEqual(got, want, delta=max(floor, 1e-7 * abs(want)), msg=path)
    else:
        case.assertEqual(got, want, path)


class PhosphateCoefficientTests(unittest.TestCase):
    """M2b, decision O1: H2PO4- and HPO4-2 fitted to Pethybridge et al. (2006) Table III."""

    KH2PO4 = {'K+': 1 / 136.09, 'PO4-3': 1 / 136.09}

    @classmethod
    def setUpClass(cls):
        from tools.fit_phosphate_conductivity import fit

        cls.block, cls.residuals = fit(FIXTURES / 'pethybridge2006_table3.json')
        cls.shipped = load_conductivity_coefficients()['supplementary']

    def calc(self, totals, **kw):
        kw.setdefault('ph_mode', 'calculated')
        kw.setdefault('phase_policy', 'dissolved')
        return calculate_ec_from_totals(totals, solution_id='p', **kw)

    def test_fit_reproduces_table3(self):
        _assert_close_tree(self, self.shipped, self.block)
        self.assertEqual(len(self.residuals), 22)
        self.assertEqual(self.shipped['fit']['points'], 22)
        for point in self.residuals:
            with self.subTest(salt=point['salt'], c=point['c_mmol_dm3']):
                self.assertLessEqual(abs(point['residual_percent']), 0.5)
        for ion in ('H2PO4-', 'HPO4-2'):
            self.assertEqual(self.shipped[ion]['B'], 1.5)
        self.assertEqual(self.shipped['fit']['density_kg_dm3'], 0.997047)
        self.assertLess(self.shipped['fit']['max_ionic_strength'], 0.015)

    def test_cross_checks_reported(self):
        references = {
            'CRC': (36.0, 114.0),
            'Pethybridge_Lee_Wheaton': (33.33, 115.14),
            'phreeqc_dat': (31.8, 103.6),
        }
        checks = self.shipped['cross_checks']
        self.assertEqual(set(checks), set(references))
        for name, values in references.items():
            for ion, reference in zip(('H2PO4-', 'HPO4-2'), values):
                with self.subTest(source=name, ion=ion):
                    entry = checks[name][ion]
                    gap = 100 * (self.shipped[ion]['lambda0_25c'] - reference) / reference
                    self.assertEqual(entry['lambda0'], reference)
                    self.assertAlmostEqual(entry['gap_percent'], gap, places=9)
                    if abs(gap) > 15:
                        self.assertIn('note', entry)
                    else:
                        self.assertNotIn('note', entry)

    def test_kh2po4_now_mostly_covered(self):
        r = self.calc(self.KH2PO4)
        self.assertEqual(
            (r.status, r.reason, r.bounded), ('partial', 'missing_species_contributions', False)
        )
        for ion in ('H2PO4-', 'HPO4-2'):
            self.assertIn(ion, r.contributions_ms_cm)
        names = {s['name'] for s in r.missing_species}
        self.assertNotIn('H2PO4-', names)
        self.assertNotIn('HPO4-2', names)
        # Only minor species remain: each under 0.1 % of total phosphate.
        self.assertTrue(names)
        for s in r.missing_species:
            self.assertLess(s['molal'], 1e-3 * self.KH2PO4['PO4-3'], s['name'])
        self.assertIsNone(r.ec25_range_ms_cm)
        self.assertIsNone(r.ec25_ms_cm)
        self.assertTrue(r.audit['supplementaryCoefficients'])
        self.assertEqual(
            r.audit['phosphate_fit_max_ionic_strength'], self.shipped['fit']['max_ionic_strength']
        )

    def test_supplementary_not_in_mcCleskey_table(self):
        data = load_conductivity_coefficients()
        self.assertEqual(len(data['ions']), 28)
        for ion in ('H2PO4-', 'HPO4-2'):
            self.assertNotIn(ion, data['ions'])
            self.assertNotIn(ion, data['species_map'])
        self.assertEqual(self.shipped['source']['table'], 'III')
        self.assertEqual(self.shipped['source']['doi'], '10.1007/s10953-005-9003-z')
        self.assertIn('Pethybridge', self.shipped['source']['citation'])
        # The citation comes from the fixture (confirmed against the PDF in step 3b).
        fixture = json.loads(
            (FIXTURES / 'pethybridge2006_table3.json').read_text(encoding='utf-8')
        )
        self.assertEqual(self.shipped['source']['citation'], fixture['source']['citation'])
        self.assertIn('KHPO4-', self.shipped['fit']['note'])

    def test_table3_transcriptions_agree(self):
        first = json.loads((FIXTURES / 'pethybridge2006_table3.json').read_text(encoding='utf-8'))
        second = json.loads(
            (FIXTURES / 'pethybridge2006_table3_independent.json').read_text(encoding='utf-8')
        )
        for key in ('KH2PO4', 'K2HPO4_half', 'table_iv_lee_wheaton_lambda0'):
            with self.subTest(key=key):
                self.assertEqual(first[key], second[key])

    def test_supplementary_lambda_is_25c_only(self):
        row = self.shipped['H2PO4-']
        self.assertEqual(ionic_molal_conductivity('H2PO4-', 0.0), row['lambda0_25c'])
        self.assertAlmostEqual(
            ionic_molal_conductivity('H2PO4-', 0.01),
            row['lambda0_25c'] - row['A_25c'] * 0.1 / 1.15,
            places=12,
        )
        for ion in ('H2PO4-', 'HPO4-2'):
            with self.subTest(ion=ion), self.assertRaises(DeliveryError) as c:
                ionic_molal_conductivity(ion, 0.01, temperature_c=20.0)
            self.assertEqual(c.exception.code, 'temperature_outside_reference')
        for name in ('source', 'fit', 'cross_checks', 'units'):
            with self.subTest(name=name), self.assertRaises(DeliveryError):
                ionic_molal_conductivity(name, 0.01)

    def test_audit_without_phosphate(self):
        r = self.calc({'K+': 0.01, 'Cl-': 0.01})
        self.assertFalse(r.audit['supplementaryCoefficients'])
        self.assertIsNone(r.audit['phosphate_fit_max_ionic_strength'])
        for key in ('supplementaryCoefficients', 'phosphate_fit_max_ionic_strength'):
            with self.subTest(key=key), self.assertRaises(DeliveryError) as c:
                self.calc(self.KH2PO4, audit_inputs={key: 0.0})
            self.assertEqual(c.exception.code, 'invalid_audit_inputs')


PURE = DeclaredPureWater('ro-test')


class CatalogueTests(unittest.TestCase):
    # 2026-10-18 catalogue correction (Mg Nitrate D1 / phosphoric 75 %): the shipped Mg Nitrate is
    # now Mg(NO3)2.6H2O theory and charge-balanced. The retired row (N_NO3 11 / Mg 9.65) gave these
    # totals for 1 g/kg water, a declared residual of +8.7368e-5 eq/kgw (0.5532 %); the O5 tests
    # below keep it.
    OLD_MG_NITRATE_1G = {'Mg+2': 0.003970376465747789, 'NO3-': 0.007853384451726673}
    OLD_MG_NITRATE_1G_RESIDUAL = {
        'eq_per_kgw': 8.736847976890429e-05,
        'percent': 0.5531703166119969,
    }

    def test_mg_nitrate_assay_residual(self):
        # 2026-10-18 catalogue correction (Mg Nitrate D1 / phosphoric 75 %): was 0.5532 %, now ~0.
        self.assertAlmostEqual(
            assay_charge_residual({'Mg Nitrate': 1.0})['percent'], 0.0, places=3
        )
        old = self.OLD_MG_NITRATE_1G
        net, absolute = 2 * old['Mg+2'] - old['NO3-'], 2 * old['Mg+2'] + old['NO3-']
        self.assertAlmostEqual(100 * net / absolute, 0.5532, places=3)

    def test_residual_gate_by_mode(self):
        # 2026-10-18 catalogue correction (Mg Nitrate D1 / phosphoric 75 %): the retired Mg Nitrate
        # totals and residual are passed explicitly, so the O5 gate by pH mode stays covered.
        residual = self.OLD_MG_NITRATE_1G_RESIDUAL
        kw = dict(
            solution_id='r',
            phase_policy='dissolved',
            assay_charge_residual_eq_per_kgw=residual['eq_per_kgw'],
            assay_charge_residual_percent=residual['percent'],
        )
        c = calculate_ec_from_totals(self.OLD_MG_NITRATE_1G, ph_mode='calculated', **kw)
        self.assertEqual(
            (c.status, c.reason), ('not_supported', 'assay_charge_residual_too_large')
        )
        s = calculate_ec_from_totals(self.OLD_MG_NITRATE_1G, ph_mode='supplied', ph=6.0, **kw)
        self.assertEqual((s.status, s.reason), ('partial', 'unrecorded_counterions'))

    def test_gate_uses_declared_form_percent(self):
        # 2026-10-18 catalogue correction (Mg Nitrate D1 / phosphoric 75 %): the mix below
        # (0.40 old Mg Nitrate + 1.0 MgSO4.7H2O + 0.5 K2SO4) had a declared residual of 0.0914 %;
        # its totals and residual are now passed explicitly to keep the declared-percent gate
        # covered.
        totals = {
            'Mg+2': 0.005644929026949188,
            'SO4-2': 0.0069279475982532744,
            'K+': 0.005738484793456493,
            'NO3-': 0.0031413537806906696,
        }
        eq, declared = 3.1093870157648636e-05, 0.09138377465402972
        kw = dict(
            solution_id='r',
            ph_mode='calculated',
            phase_policy='dissolved',
            assay_charge_residual_eq_per_kgw=eq,
        )
        speciated = calculate_ec_from_totals(totals, **kw)
        self.assertEqual(speciated.reason, 'assay_charge_residual_too_large')  # speciated % > 0.1
        r = calculate_ec_from_totals(totals, assay_charge_residual_percent=declared, **kw)
        self.assertNotEqual(r.reason, 'assay_charge_residual_too_large')
        self.assertAlmostEqual(r.assay_charge_residual['percent'], 0.0914, places=4)
        # The catalogue path still records the declared-form percent it gated on.
        doses = {
            'Mg Nitrate': 0.40,
            'Magnesium Sulfate (Heptahydrate)': 1.0,
            'Potassium Sulfate': 0.5,
        }
        c = calculate_irrigation_ec(
            doses, recipe_id='r', water=PURE, ph_mode='calculated', phase_policy='dissolved'
        )
        self.assertEqual(
            c.assay_charge_residual['percent'], c.audit['assay_charge_residual_declared_percent']
        )
        self.assertAlmostEqual(
            c.audit['assay_charge_residual_declared_percent'],
            assay_charge_residual(doses)['percent'],
            places=12,
        )

    def test_recipe_and_reagent_ids_must_be_nonempty_strings(self):
        for rid in ('', ' ', None, 7):
            with self.subTest(recipe_id=rid), self.assertRaises(DeliveryError) as c:
                calculate_irrigation_ec(
                    {'Potassium Nitrate': 0.5},
                    recipe_id=rid,
                    water=PURE,
                    ph_mode='calculated',
                    phase_policy='dissolved',
                )
            self.assertEqual(c.exception.code, 'missing_field')
        for gid in ('', '  ', 5):
            with self.subTest(reagent_id=gid), self.assertRaises(DeliveryError) as c:
                calculate_irrigation_ec(
                    {'Potassium Nitrate': 0.5},
                    recipe_id='r',
                    water=PURE,
                    reagent_additions_molal={'NO3-': 1e-4},
                    reagent_id=gid,
                    ph_mode='calculated',
                    phase_policy='dissolved',
                )
            self.assertEqual(c.exception.code, 'missing_field')

    def test_reagent_additions_recorded_as_copy(self):
        additions = {'NO3-': 1e-4}
        r = calculate_irrigation_ec(
            {'Potassium Nitrate': 0.5},
            recipe_id='r',
            water=PURE,
            reagent_additions_molal=additions,
            reagent_id='nitric',
            ph_mode='supplied',
            ph=6.0,
            phase_policy='dissolved',
        )
        self.assertEqual(r.audit['reagent_additions_molal'], {'NO3-': 1e-4})
        self.assertIsNot(r.audit['reagent_additions_molal'], additions)
        none = calculate_irrigation_ec(
            {}, recipe_id='r', water=PURE, ph_mode='calculated', phase_policy='dissolved'
        )
        self.assertEqual(none.audit['reagent_additions_molal'], {})

    def test_chelate_residual_reported_not_crash(self):
        # 2026-10-18 chelate sodium counterions (D2): was not_supported /
        # assay_charge_residual_too_large (declared percent < -0.1) because the
        # chelate sodium was missing; the residual is still reported in the audit.
        r = calculate_irrigation_ec(
            {'Iron EDTA': 0.05, 'Potassium Nitrate': 0.5},
            recipe_id='r',
            water=PURE,
            ph_mode='calculated',
            phase_policy='dissolved',
        )
        self.assertNotEqual(r.reason, 'assay_charge_residual_too_large')
        self.assertIn('assay_charge_residual_declared_percent', r.audit)
        self.assertLessEqual(abs(r.audit['assay_charge_residual_declared_percent']), 0.1)
        self.assertEqual(
            r.assay_charge_residual['percent'], r.audit['assay_charge_residual_declared_percent']
        )

    def test_borax_declared_residual_near_zero(self):
        # Borax boron is declared at -0.5 per B (Na2B4O7 -> 2 Na+ + 2 B(OH)4- + 2 B(OH)3).
        r = assay_charge_residual({'Sodium Borate (Decahydrate) (borax)': 1.0})
        self.assertLessEqual(abs(r['percent']), 0.1)

    def test_chelate_residuals_within_limit(self):
        for name in (
            'Iron EDTA',
            'Zn EDTA',
            'Mn EDTA',
            'Copper EDTA',
            'Iron DTPA',
            'Iron EDDHA',
            'CH - micro',
        ):
            with self.subTest(name=name):
                self.assertLessEqual(abs(assay_charge_residual({name: 1.0})['percent']), 0.1)
        r = calculate_irrigation_ec(
            {'Iron EDTA': 0.05, 'Potassium Nitrate': 0.5},
            recipe_id='r',
            water=PURE,
            ph_mode='calculated',
            phase_policy='dissolved',
        )
        self.assertNotEqual(r.reason, 'assay_charge_residual_too_large')

    def test_zero_doses_in_pure_water(self):
        r = calculate_irrigation_ec(
            {}, recipe_id='r', water=PURE, ph_mode='calculated', phase_policy='dissolved'
        )
        self.assertEqual(r.status, 'estimated')
        self.assertAlmostEqual(r.ec25_ms_cm, 5.48e-5, delta=2e-6)

    def test_water_input_contract(self):
        for water, wid in (({}, None), ({'K+': 0.001}, None), (PURE, 'x')):
            with self.subTest(water=water), self.assertRaises(DeliveryError):
                calculate_irrigation_ec(
                    {'Potassium Nitrate': 0.5},
                    recipe_id='r',
                    water=water,
                    water_analysis_id=wid,
                    ph_mode='calculated',
                    phase_policy='dissolved',
                )
        with self.assertRaises(DeliveryError):
            DeclaredPureWater('')

    def test_balanced_water_and_reagent_recorded(self):
        bw = balance_water_analysis(
            {'Na+': 0.002, 'Cl-': 0.002}, measured_ph=7.0, alkalinity_eq_per_kg=1e-4
        )
        r = calculate_irrigation_ec(
            {'Potassium Nitrate': 0.5},
            recipe_id='r',
            water=bw,
            water_analysis_id='lab-1',
            reagent_additions_molal={'NO3-': 1e-4},
            reagent_id='nitric',
            ph_mode='calculated',
            phase_policy='dissolved',
        )
        self.assertEqual(r.status, 'estimated')
        self.assertEqual(
            (r.audit['water_id'], r.audit['reagent_id'], r.audit['water_kind']),
            ('lab-1', 'nitric', 'balanced_analysis'),
        )
        self.assertLess(r.ph, 7.0)

    def test_unknown_product_and_bad_dose_raise(self):
        for doses in (
            {'Unobtainium': 1.0},
            {'Potassium Nitrate': -1.0},
            {'Potassium Nitrate': float('nan')},
        ):
            with self.subTest(doses=doses), self.assertRaises(DeliveryError):
                calculate_irrigation_ec(
                    doses,
                    recipe_id='r',
                    water=PURE,
                    ph_mode='calculated',
                    phase_policy='dissolved',
                )


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
        self.assertEqual(
            (r.audit['water_id'], r.audit['reagent_id']), ('synthetic-complete-water-v1', 'nitric')
        )
        self.assertAlmostEqual(
            r.ionic_strength, self.plan.equilibrium.target.ionic_strength, places=15
        )
        self.assertGreater(r.ec25_ms_cm, 0)

    def test_audit_identity_and_policy(self):
        r = calculate_irrigation_ec_from_plan(self.plan)
        self.assertTrue(r.audit['recipe_id'].startswith('plan-recipe:'))
        self.assertEqual(r.audit['solution_id'], r.audit['recipe_id'])
        self.assertEqual(r.audit['reagent_molal'], self.plan.equilibrium.nitric_acid_molal)
        self.assertEqual(r.audit['water_kind'], 'plan_water_totals')
        self.assertEqual(
            r.audit['doses_g_per_kg_water'], self.plan.audit['productDosesGPerKgWater']
        )
        for key in ('catalogueSha256', 'waterTotalsMolal', 'initialPh'):
            self.assertEqual(r.audit[key], self.plan.audit[key], key)
        self.assertEqual(
            r.assay_charge_residual['percent'], r.audit['assay_charge_residual_declared_percent']
        )
        # Material provenance travels from the plan into the EC audit, as a copy.
        self.assertEqual(r.audit['materials'], self.plan.audit['materials'])
        self.assertIsNot(r.audit['materials'], self.plan.audit['materials'])
        self.assertEqual(r.audit['identitiesSha256'], self.plan.audit['identitiesSha256'])
        with self.assertRaises(DeliveryError) as c:
            calculate_irrigation_ec_from_plan(self.plan, phase_policy='equilibrated')
        self.assertEqual(c.exception.code, 'invalid_phase_policy')


class ComparisonTests(unittest.TestCase):
    def test_difference_only_no_verdict(self):
        p = calculate_ec_from_totals(
            {'K+': 0.01, 'Cl-': 0.01},
            solution_id='kcl',
            ph_mode='calculated',
            phase_policy='dissolved',
        )
        c = compare_measured_ec(p, measured_ec25_ms_cm=1.413, meter_reference_temperature_c=25)
        self.assertEqual(
            set(c),
            {
                'predicted_ec25_ms_cm',
                'measured_ec25_ms_cm',
                'difference_ms_cm',
                'relative_difference_percent',
                'audit',
                'qualifier',
                'ec25_range_ms_cm',
                'within_range',
            },
        )
        self.assertIsNone(c['ec25_range_ms_cm'])
        self.assertIsNone(c['within_range'])
        self.assertAlmostEqual(c['difference_ms_cm'], 1.413 - p.ec25_ms_cm, places=12)
        self.assertAlmostEqual(
            c['relative_difference_percent'], 100 * (1.413 - p.ec25_ms_cm) / p.ec25_ms_cm, places=9
        )
        self.assertEqual(c['qualifier'], p.qualifier)
        self.assertEqual(c['audit'], p.audit)
        self.assertIsNot(c['audit'], p.audit)

    def test_compare_incomplete_coverage_is_refused(self):
        p = calculate_ec_from_totals(
            {'K+': 1 / 136.09, 'PO4-3': 1 / 136.09},
            solution_id='kh2po4',
            ph_mode='calculated',
            phase_policy='dissolved',
        )
        for measured in (0.0, 0.738, 0.80):
            with self.subTest(measured=measured), self.assertRaises(DeliveryError) as error:
                compare_measured_ec(
                    p, measured_ec25_ms_cm=measured, meter_reference_temperature_c=25
                )
            self.assertEqual(error.exception.code, 'incomplete_prediction')

    def test_compare_unbounded_has_none_within_range(self):
        p = calculate_ec_from_totals(
            {'K+': 0.01, 'Cl-': 0.01},
            solution_id='kcl',
            ph_mode='calculated',
            phase_policy='dissolved',
        )
        c = compare_measured_ec(p, measured_ec25_ms_cm=5.0, meter_reference_temperature_c=25)
        self.assertIsNone(c['within_range'])
        self.assertIsNone(c['ec25_range_ms_cm'])

    # M2a O2 bound: the K+/PO4-3 totals used here are now a bounded estimate, so the
    # partial prediction is an unrecorded-counterions case (KCl at supplied pH 4).
    PARTIAL = dict(solution_id='kcl-ph4', ph_mode='supplied', ph=4.0, phase_policy='dissolved')

    def test_refusals(self):  # Review Focus 5
        p = calculate_ec_from_totals(
            {'K+': 0.01, 'Cl-': 0.01},
            solution_id='kcl',
            ph_mode='calculated',
            phase_policy='dissolved',
        )
        partial = calculate_ec_from_totals(
            {'K+': 0.01, 'Cl-': 0.01}, **self.PARTIAL
        )  # M2a O2 bound
        self.assertEqual(partial.status, 'partial')  # M2a O2 bound
        cases = [
            (partial, 1.0, 25),
            (p, 1.0, 20),
            (p, -1.0, 25),
            (p, float('nan'), 25),
            (p, True, 25),
        ]
        for pred, measured, ref in cases:
            with self.subTest(measured=measured, ref=ref), self.assertRaises(DeliveryError):
                compare_measured_ec(
                    pred, measured_ec25_ms_cm=measured, meter_reference_temperature_c=ref
                )

    def test_refusal_codes(self):
        p = calculate_ec_from_totals(
            {'K+': 0.01, 'Cl-': 0.01},
            solution_id='kcl',
            ph_mode='calculated',
            phase_policy='dissolved',
        )
        partial = calculate_ec_from_totals(
            {'K+': 0.01, 'Cl-': 0.01}, **self.PARTIAL
        )  # M2a O2 bound
        for pred, measured, ref, code in [
            (partial, 1.0, 25, 'incomplete_prediction'),
            (p, 1.0, 20, 'temperature_reference_mismatch'),
            (p, -1.0, 25, 'invalid_value'),
            (p, True, 25, 'invalid_value'),
        ]:
            with self.assertRaises(DeliveryError) as c:
                compare_measured_ec(
                    pred, measured_ec25_ms_cm=measured, meter_reference_temperature_c=ref
                )
            self.assertEqual(c.exception.code, code)


class BandChemistryTests(unittest.TestCase):
    PURE = dict(
        recipe_id='band',
        water=DeclaredPureWater('ro-1'),
        ph_mode='calculated',
        phase_policy='dissolved',
    )

    @staticmethod
    def _material(name, identity_id, product, nutrients):
        # Each nutrient moves by the same fraction at its band ends, so both ends stay charge
        # balanced.
        analysis = {
            key: {'minimum': v * 0.98, 'typical': v, 'maximum': v * 1.02}
            for key, v in nutrients.items()
        }
        grade = make_grade(
            {
                'grade_id': 'band-' + product,
                'identity_id': identity_id,
                'supplier': 'S',
                'product': product,
                'analysis': analysis,
                'document': {
                    'supplier': 'S',
                    'title': 'TDS',
                    'issued': '2026-01-01',
                    'entered': '2026-10-19',
                },
            }
        )
        return resolve_material(name, grade=grade)

    def _materials(self):
        return {
            'Potassium Nitrate': self._material(
                'Potassium Nitrate', 'idn-potassium-nitrate', 'KNO3', {'K': 38.67, 'N_NO3': 13.856}
            ),
            'Potassium Sulfate': self._material(
                'Potassium Sulfate', 'idn-potassium-sulfate', 'K2SO4', {'K': 44.873, 'S': 18.402}
            ),
        }

    def test_shipped_only_band_ends_open(self):
        result = calculate_irrigation_ec_band({'Potassium Nitrate': 1.0}, **self.PURE)
        self.assertEqual(result['nominal'].status, 'estimated')
        for end in ('minimum', 'maximum'):
            r = result[end]
            self.assertEqual((r.status, r.reason), ('not_supported', 'band_end_open'))
            self.assertIsNone(r.ec25_ms_cm)
            self.assertIsNone(r.ph)
            self.assertIsNone(r.ionic_strength)
            self.assertEqual(r.audit['band_end'], end)
            self.assertIsNone(r.audit['assay_charge_residual_declared_percent'])
        self.assertIsNotNone(result['nominal'].audit['assay_charge_residual_declared_percent'])

    def test_graded_plus_shipped_band_ends_open(self):
        doses = {'Potassium Nitrate': 1.0, 'Potassium Sulfate': 0.5}
        materials = {'Potassium Nitrate': self._materials()['Potassium Nitrate']}
        result = calculate_irrigation_ec_band(doses, materials=materials, **self.PURE)
        self.assertEqual(result['nominal'].status, 'estimated')
        for end in ('minimum', 'maximum'):
            r = result[end]
            self.assertEqual((r.status, r.reason), ('not_supported', 'band_end_open'))
            self.assertIsNone(r.ec25_ms_cm)
            self.assertEqual(r.audit['band_end'], end)

    def test_open_end_still_validates_inputs(self):
        with self.assertRaises(DeliveryError) as caught:
            calculate_irrigation_ec_band(
                {'Potassium Nitrate': 1.0}, **{**self.PURE, 'ph_mode': 'bogus'}
            )
        self.assertEqual(caught.exception.code, 'invalid_ph_input')

    def test_band_ends_bracket_ec(self):
        doses = {'Potassium Nitrate': 1.0, 'Potassium Sulfate': 0.5}
        result = calculate_irrigation_ec_band(doses, materials=self._materials(), **self.PURE)
        low, mid, high = (result[k] for k in ('minimum', 'nominal', 'maximum'))
        for r in (low, mid, high):
            self.assertEqual(r.status, 'estimated')
        self.assertLess(low.ec25_ms_cm, mid.ec25_ms_cm)
        self.assertLess(mid.ec25_ms_cm, high.ec25_ms_cm)
        self.assertEqual((low.audit['band_end'], high.audit['band_end']), ('minimum', 'maximum'))
        self.assertNotIn('band_end', mid.audit)
        self.assertEqual(
            mid.ec25_ms_cm,
            calculate_irrigation_ec(doses, materials=self._materials(), **self.PURE).ec25_ms_cm,
        )

    def test_band_ends_preserve_incomplete_coverage(self):  # Review Focus 4
        material = self._material(
            'Potassium Monobasic Phosphate',
            'idn-monopotassium-phosphate',
            'KH2PO4',
            {'K': 28.731, 'P': 22.761},
        )
        result = calculate_irrigation_ec_band(
            {'Potassium Monobasic Phosphate': 1.0},
            materials={'Potassium Monobasic Phosphate': material},
            **self.PURE,
        )
        subtotals = {}
        for end in ('minimum', 'nominal', 'maximum'):
            r = result[end]
            self.assertEqual((r.status, r.bounded), ('partial', False), end)
            self.assertIsNone(r.ec25_range_ms_cm)
            self.assertIsNone(r.uncovered_bound_ms_cm)
            self.assertIsNone(r.ec25_ms_cm)
            subtotals[end] = r.known_species_subtotal_ms_cm
        self.assertLess(subtotals['minimum'], subtotals['nominal'])
        self.assertLess(subtotals['nominal'], subtotals['maximum'])

    def test_band_end_outside_domain(self):
        # Empirical doses: nominal I 0.0982 and minimum I 0.0963 are inside the I < 0.1 domain,
        # maximum is not.
        doses = {'Potassium Nitrate': 4.4, 'Potassium Sulfate': 3.6}
        result = calculate_irrigation_ec_band(doses, materials=self._materials(), **self.PURE)
        self.assertEqual(result['nominal'].status, 'estimated')
        self.assertEqual(result['minimum'].status, 'estimated')
        high = result['maximum']
        self.assertEqual(
            (high.status, high.reason), ('not_supported', 'ionic_strength_outside_domain')
        )
        self.assertIsNone(high.ec25_ms_cm)
        self.assertEqual(high.audit['band_end'], 'maximum')

    def test_note_text(self):
        result = calculate_irrigation_ec_band({'Potassium Nitrate': 1.0}, **self.PURE)
        self.assertEqual(
            result['note'],
            'Band ends are corner cases (every product at its minimum, or every '
            'product at its maximum), not statistical bounds.',
        )


if __name__ == '__main__':
    unittest.main()
