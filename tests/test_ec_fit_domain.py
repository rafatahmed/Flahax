# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Recorded phosphate fit limits and independent numerical reproduction."""

from dataclasses import replace
import math
import unittest

from flahax.calculated_ph import calculate_equilibrium_ph
from flahax.delivery_contracts import DeliveryError
from flahax.irrigation_ec import (
    _ec_from_state,
    calculate_ec_from_totals,
    ionic_molal_conductivity,
    load_conductivity_coefficients,
)
from tools.verify_conductivity import phosphate_refit, withheld_kcl


class FitDomainTests(unittest.TestCase):
    def test_independent_qr_reproduces_shipped_coefficients(self):
        block = load_conductivity_coefficients()['supplementary']
        expected = [
            block[ion][key] for ion in ('H2PO4-', 'HPO4-2') for key in ('lambda0_25c', 'A_25c')
        ]
        for got, want in zip(phosphate_refit(), expected):
            # Existing refit tolerance: 1e-7 relative, 1e-9 absolute floor.
            self.assertAlmostEqual(got, want, delta=max(1e-9, abs(want) * 1e-7))

    def test_ionic_boundary_and_limiting_value(self):
        block = load_conductivity_coefficients()['supplementary']
        limit = block['fit']['max_ionic_strength']
        for ion in ('H2PO4-', 'HPO4-2'):
            for strength in (0.0, math.nextafter(limit, 0), limit):
                self.assertTrue(math.isfinite(ionic_molal_conductivity(ion, strength)))
            with self.assertRaises(DeliveryError) as caught:
                ionic_molal_conductivity(ion, math.nextafter(limit, math.inf))
            self.assertEqual(caught.exception.code, 'ionic_strength_outside_phosphate_fit')

    def test_public_out_of_fit_has_no_estimate_or_interval(self):
        for mode, extra in (('calculated', {}), ('supplied', {'ph': 6.0})):
            result = calculate_ec_from_totals(
                {'Na+': 0.02, 'PO4-3': 0.02},
                solution_id='outside',
                ph_mode=mode,
                phase_policy='dissolved',
                **extra,
            )
            self.assertEqual(result.status, 'not_supported')
            self.assertEqual(result.reason, 'ionic_strength_outside_phosphate_fit')
            self.assertIsNone(result.ec25_ms_cm)
            self.assertIsNone(result.ec25_range_ms_cm)
            self.assertEqual(result.contributions_ms_cm, {})
            self.assertFalse(result.bounded)
            self.assertTrue(result.audit['supplementaryCoefficients'])
            self.assertGreater(
                result.ionic_strength, result.audit['phosphate_fit_max_ionic_strength']
            )
            self.assertTrue(result.warnings)

    def test_state_boundary_and_reporting_cutoff(self):
        state = calculate_equilibrium_ph(
            {'K+': 0.001, 'PO4-3': 0.001},
            complete_analysis=True,
            carbon_boundary='closed',
            phases=[],
        )
        limit = load_conductivity_coefficients()['supplementary']['fit']['max_ionic_strength']
        for strength, expected in (
            (limit, 'estimated'),
            (math.nextafter(limit, math.inf), 'not_supported'),
        ):
            result = _ec_from_state(
                replace(state, ionic_strength=strength),
                ph_mode='calculated',
                phase_policy='dissolved',
                phases=[],
                assay_residual_eq=0,
                assay_residual_percent=0,
                audit_inputs=None,
            )
            self.assertEqual(result.status, expected)
        for amount, expected in (
            (1e-12, 'estimated'),
            (math.nextafter(1e-12, math.inf), 'not_supported'),
        ):
            species = {'K+': 0.02, 'Cl-': 0.02, 'H2PO4-': amount}
            result = _ec_from_state(
                replace(state, species=species, ionic_strength=0.02),
                ph_mode='calculated',
                phase_policy='dissolved',
                phases=[],
                assay_residual_eq=0,
                assay_residual_percent=0,
                audit_inputs=None,
            )
            self.assertEqual(result.status, expected)

    def test_phosphate_free_keeps_existing_domain(self):
        for strength, expected in (
            (0.02, 'estimated'),
            (0.09, 'estimated'),
            (0.12, 'not_supported'),
        ):
            result = calculate_ec_from_totals(
                {'K+': strength, 'Cl-': strength},
                solution_id='kcl',
                ph_mode='calculated',
                phase_policy='dissolved',
            )
            self.assertEqual(result.status, expected)
            self.assertFalse(result.audit['supplementaryCoefficients'])


class WithheldReferenceTests(unittest.TestCase):
    def test_withheld_kcl_is_reported_without_refitting_or_expanding_domain(self):
        rows = withheld_kcl()
        self.assertEqual([r['molality'] for r in rows], [0.01, 0.1, 1.0])
        self.assertEqual(rows[0]['public_status'], 'estimated')
        # Existing Eq. 8 hand calculation, not a new measured accuracy tolerance.
        expected = 0.01 * (74.12875 + 76.800625 - (49.22375 + 49.51375) * 0.1 / 1.15)
        self.assertAlmostEqual(rows[0]['table1_ms_cm'], expected, places=9)
        for row in rows[1:]:
            self.assertEqual(row['public_status'], 'not_supported')
            self.assertEqual(row['public_reason'], 'ionic_strength_outside_domain')
            self.assertIsNone(row['public_ec25_ms_cm'])
        for row in rows:
            self.assertTrue(math.isfinite(row['table1_gap_percent']))
