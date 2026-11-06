# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""EC as a range, never refused and never blocking (decisions G6-G9).

The covered species give the low end. Species without a conductivity coefficient, phosphate
beyond its fit domain and charge the recorded ions do not carry are bounded at 80 mS/cm per
charge per mol/kg, which gives the high end. There is no midpoint.
"""

from dataclasses import asdict
import json
import unittest

from flahax.irrigation_ec import LAMBDA_MAX_PER_CHARGE, calculate_ec_from_totals


def ec(totals, **kw):
    kw = dict(solution_id='range', phase_policy='dissolved', ph_mode='calculated') | kw
    return calculate_ec_from_totals(totals, **kw)


class EcRangeTests(unittest.TestCase):
    def test_the_physical_bound_per_charge_is_80(self):
        self.assertEqual(LAMBDA_MAX_PER_CHARGE, 80.0)

    def test_a_solution_of_covered_species_is_a_single_estimate(self):
        result = ec({'K+': 1e-3, 'Cl-': 1e-3})
        self.assertEqual(result.status, 'estimated')
        low, high = result.ec25_range_ms_cm
        self.assertEqual(low, high)
        self.assertEqual(result.ec25_ms_cm, low)
        self.assertAlmostEqual(result.ec25_ms_cm, 0.1480046, places=6)
        self.assertEqual(result.missing_species, ())

    def test_species_without_a_coefficient_make_a_range_not_a_refusal(self):
        result = ec({'Ca+2': 2e-3, 'Edta-4': 1e-3, 'K+': 1e-3, 'Cl-': 3e-3})
        self.assertEqual(result.status, 'range')
        low, high = result.ec25_range_ms_cm
        self.assertGreater(low, 0)
        self.assertGreater(high, low)
        self.assertIsNone(result.ec25_ms_cm)
        self.assertGreater(len(result.missing_species), 0)
        bound = sum(
            LAMBDA_MAX_PER_CHARGE * abs(s['charge']) * s['molal'] for s in result.missing_species
        )
        self.assertAlmostEqual(high - low, bound, places=12)
        self.assertAlmostEqual(result.uncovered_bound_ms_cm, bound, places=12)
        self.assertTrue(result.bounded)

    def test_phosphate_beyond_its_fit_domain_is_bounded_and_the_rest_still_counts(self):
        result = ec({'K+': 0.03, 'PO4-3': 0.01})
        self.assertEqual(result.status, 'range')
        self.assertIsNone(result.reason)
        low, high = result.ec25_range_ms_cm
        self.assertGreater(low, 0)  # potassium is covered and still contributes
        self.assertGreater(high, low)
        self.assertIn('K+', result.contributions_ms_cm)
        self.assertTrue(
            any('phosphate' in w.lower() and 'fit domain' in w for w in result.warnings),
            result.warnings,
        )

    def test_the_assay_residual_is_reported_and_never_changes_the_status(self):
        result = ec({'K+': 1e-3, 'Cl-': 1e-3}, assay_charge_residual_percent=5.0)
        self.assertEqual(result.status, 'estimated')
        self.assertIsNone(result.reason)
        self.assertEqual(result.assay_charge_residual['percent'], 5.0)

    def test_charge_the_recorded_ions_do_not_carry_is_bounded(self):
        result = ec({'K+': 1e-3, 'Cl-': 0.5e-3}, ph_mode='supplied', ph=7.0)
        self.assertEqual(result.status, 'range')
        low, high = result.ec25_range_ms_cm
        self.assertAlmostEqual(
            high - low, LAMBDA_MAX_PER_CHARGE * abs(result.unrecorded_counterions_eq_per_kgw)
        )
        self.assertGreater(result.unrecorded_counterions_eq_per_kgw, 0)

    def test_there_is_no_midpoint_in_any_field(self):
        result = ec({'Ca+2': 2e-3, 'Edta-4': 1e-3, 'K+': 1e-3, 'Cl-': 3e-3})
        low, high = result.ec25_range_ms_cm
        text = json.dumps(asdict(result), default=str)
        self.assertNotIn(
            'midpoint', text.lower().replace('not a total estimate, bound or midpoint', '')
        )
        self.assertNotIn(repr((low + high) / 2), text)

    def test_an_unsolvable_state_is_still_not_supported(self):
        result = ec({'Na+': 2.0, 'Cl-': 2.0})
        self.assertEqual(result.status, 'not_supported')
        self.assertIsNone(result.ec25_range_ms_cm)


if __name__ == '__main__':
    unittest.main()
