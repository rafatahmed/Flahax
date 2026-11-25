# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Total nitrogen is a target, alone or with nitrogen forms (D2, contract Q11-Q13).

Total N alone imposes no form split. When the forms fully determine total N
the forms are scored once and the declared total is checked for consistency.
When only some forms are given with total N, both are scored and the overlap
is reported; no other form target is invented.
"""

import unittest

from flahax import InputError, load_library, recommend, solve_weights
from flahax.composition import fitted_targets, nitrogen_rows, validate_profile, validate_targets
from flahax.requirement_fit import met

SALTS = load_library()['salts']
BASE = {'P': 40.0, 'K': 250.0, 'Ca': 150.0, 'Mg': 50.0}


def row(result, symbol):
    return next((r for r in result['rows'] if r['symbol'] == symbol), None)


class TotalNitrogenRowsTests(unittest.TestCase):
    def test_total_alone_is_one_total_row_and_no_form_split(self):
        self.assertEqual(nitrogen_rows({'N': 150.0}), {'N': 150.0, 'N_UREA': 0})

    def test_total_with_some_forms_scores_both_and_invents_no_other_form(self):
        self.assertEqual(
            nitrogen_rows({'N': 150.0, 'N_NO3': 100.0}),
            {'N': 150.0, 'N_NO3': 100.0, 'N_UREA': 0},
        )

    def test_an_absent_urea_is_zero_so_nitrate_and_ammonium_determine_the_total(self):
        # Total N is nitrate + ammonium + urea; urea that is not asked for is a zero
        # requirement, not an unknown, so the total is fully determined.
        self.assertEqual(
            nitrogen_rows({'N': 130.0, 'N_NO3': 100.0, 'N_NH4': 30.0}),
            {'N_NO3': 100.0, 'N_NH4': 30.0, 'N_UREA': 0},
        )

    def test_a_total_that_disagrees_with_nitrate_plus_ammonium_plus_zero_urea_is_rejected(self):
        with self.assertRaisesRegex(InputError, 'total N 150.*= 130'):
            fitted_targets({'N': 150.0, 'N_NO3': 100.0, 'N_NH4': 30.0})

    def test_a_zero_ammonium_target_is_no_requirement_and_does_not_determine_the_total(self):
        # Decision G24: an explicit zero N_NH4 asks for nothing, so ammonium may supply the rest.
        self.assertEqual(
            nitrogen_rows({'N': 150.0, 'N_NO3': 140.0, 'N_NH4': 0.0}),
            {'N': 150.0, 'N_NO3': 140.0, 'N_UREA': 0},
        )

    def test_forms_that_determine_total_are_scored_once(self):
        forms = {'N_NO3': 100.0, 'N_NH4': 30.0, 'N_UREA': 20.0}
        self.assertEqual(
            nitrogen_rows({'N': 150.0, **forms}), {'N_NO3': 100.0, 'N_NH4': 30.0, 'N_UREA': 20.0}
        )

    def test_contradictory_total_and_forms_are_rejected_before_fitting(self):
        with self.assertRaisesRegex(InputError, 'N_NO3.*N_NH4.*N_UREA|total N'):
            fitted_targets({'N': 150.0, 'N_NO3': 100.0, 'N_NH4': 30.0, 'N_UREA': 10.0})

    def test_forms_exceeding_the_total_are_rejected(self):
        with self.assertRaisesRegex(InputError, 'exceed'):
            fitted_targets({'N': 90.0, 'N_NO3': 100.0})

    def test_a_zero_total_declares_no_nitrogen_row(self):
        self.assertNotIn('N', nitrogen_rows({'N': 0.0}))

    def test_total_is_accepted_for_targets_only(self):
        self.assertEqual(validate_targets({'N': 5.0}, 'targets'), {'N': 5.0})
        with self.assertRaises(InputError):
            validate_profile({'N': 5.0}, 'water')


class TotalNitrogenFitTests(unittest.TestCase):
    def test_total_alone_meets_the_total_with_no_urea(self):
        result = recommend(SALTS, {'N': 150.0, **BASE}, {})
        self.assertTrue(met(150.0, row(result, 'N')['final']))
        self.assertIsNone(row(result, 'N_NO3')['target'])
        self.assertTrue(
            all(item['name'].lower().find('urea') < 0 for item in result['salts']),
            [item['name'] for item in result['salts']],
        )
        self.assertEqual(result['totalN']['target'], 150.0)
        self.assertTrue(result['totalN']['fitted'])
        self.assertEqual(result['totalN']['overlapForms'], [])

    def test_total_with_a_nitrate_form_meets_both_and_discloses_the_overlap(self):
        result = recommend(SALTS, {'N': 150.0, 'N_NO3': 120.0, **BASE}, {})
        self.assertTrue(met(150.0, row(result, 'N')['final']))
        self.assertTrue(met(120.0, row(result, 'N_NO3')['final']))
        self.assertEqual(result['totalN']['overlapForms'], ['N_NO3'])

    def test_forms_that_determine_total_leave_no_total_row(self):
        result = recommend(
            SALTS, {'N': 150.0, 'N_NO3': 120.0, 'N_NH4': 30.0, 'N_UREA': 0.0, **BASE}, {}
        )
        self.assertIsNone(row(result, 'N'))
        self.assertFalse(result['totalN']['fitted'])
        self.assertEqual(result['totalN']['target'], 150.0)

    def test_solve_weights_accepts_the_total(self):
        solved = solve_weights(SALTS[:12], {'N': 100.0}, {})
        self.assertTrue(solved['totalN']['fitted'])

    def test_the_ammonium_preset_uses_the_total(self):
        result = recommend(SALTS, {'N': 150.0, **BASE}, {}, max_ammonium_fraction=0.10)
        self.assertEqual(result['ammoniumLimit']['mgPerL'], 15.0)


if __name__ == '__main__':
    unittest.main()
