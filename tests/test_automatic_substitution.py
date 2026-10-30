# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Available inventory is searched without changing the requested problem."""

import copy
import unittest
from flahax import InputError, recommend, plan_fertilizer_workflow


def product(key, **elements):
    return dict(id=key, name=key, elements=elements)


class AutomaticSubstitutionTests(unittest.TestCase):
    def test_recoverable_single_source_needs_no_starter_product(self):
        result = recommend([product('mo', Mo=10, Na=1)], {'Mo': 0.01})
        self.assertTrue(result['feasible'])
        self.assertAlmostEqual(result['salts'][0]['gramsPerLitre'], 0.0001, places=15)
        self.assertEqual(result['substitutionSearch']['status'], 'candidate_found')
        self.assertEqual(result['substitutionSearch']['attemptedProductIds'], [[], ['mo']])

    def test_available_combinations_and_removal_preserve_inputs(self):
        pool = [product('both', K=10, Ca=10), product('k', K=10)]
        targets, water = {'K': 100, 'Ca': 50}, {}
        snapshot = copy.deepcopy((pool, targets, water))
        for available in (pool, list(reversed(pool))):
            result = recommend(available, targets, water)
            self.assertTrue(result['feasible'])
            self.assertEqual({s['id'] for s in result['salts']}, {'both', 'k'})
        restricted = recommend(pool[:1], targets, water)
        self.assertFalse(restricted['feasible'])
        self.assertEqual(restricted['substitutionSearch']['status'], 'search_incomplete')
        self.assertEqual(restricted['substitutionSearch']['availableProductIds'], ['both'])
        self.assertEqual((pool, targets, water), snapshot)

    def test_permissions_and_hard_limits_survive_recovery(self):
        for salt in (
            product('cl', K=10, Cl=1),
            dict(product('base', K=10), role='ph_reagent'),
            dict(product('carbonate', Ca=10), formula='CaCO3'),
        ):
            with self.assertRaises(InputError):
                recommend([salt], {'K': 100})
        permitted = recommend(
            [product('cl', K=10, Cl=1)], {'K': 100}, maximum_concentrations={'Cl': 20}
        )
        self.assertTrue(permitted['feasible'])
        for maxima in ({'Na': 0}, {'Na': 0.0005}):
            result = recommend(
                [product('mo', Mo=10, Na=1)], {'Mo': 0.01}, maximum_concentrations=maxima
            )
            self.assertFalse(result['feasible'])
            rows = {r['symbol']: r['final'] for r in result['rows']}
            self.assertLessEqual(rows.get('Na', 0), maxima['Na'])

    def test_workflow_uses_only_supplied_inventory(self):
        result = plan_fertilizer_workflow([product('mo', Mo=10, Na=1)], {'Mo': 0.01}, {}, 5.5)
        self.assertEqual(result.recommendation['saltIds'], ['mo'])
        self.assertEqual(
            result.recommendation['substitutionSearch']['availableProductIds'], ['mo']
        )

    def test_new_deficit_triggers_a_second_permitted_substitution(self):
        pool = [
            product('base', K=10, Ca=10, Mg=10),
            product('mg', Mg=10, Na=0.01),
            product('ca', Ca=10, Na=0.01),
        ]
        # Mg 120: the base-only fit overshoots Ca (+3.4 %), so Ca is short only after the Mg
        # substitution lowers the base dose (under the numerical tolerance, G25, a -0.21 %
        # Ca miss at Mg 104 is already short at the first fit).
        result = recommend(pool, {'K': 96, 'Ca': 100, 'Mg': 120})
        self.assertTrue(result['feasible'])
        self.assertEqual(
            result['substitutionSearch']['attemptedProductIds'],
            [['base'], ['base', 'mg'], ['base', 'mg', 'ca']],
        )
        expected = {'base': 0.96, 'mg': 0.24, 'ca': 0.04}
        for salt in result['salts']:
            self.assertAlmostEqual(salt['gramsPerLitre'], expected[salt['id']], places=12)
        # No available substitute: retain the residual, never draw from the catalogue.
        restricted = recommend(pool[:2], {'K': 96, 'Ca': 100, 'Mg': 120})
        self.assertFalse(restricted['feasible'])
        self.assertEqual(restricted['substitutionSearch']['status'], 'search_incomplete')
        self.assertNotIn('ca', restricted['saltIds'])
