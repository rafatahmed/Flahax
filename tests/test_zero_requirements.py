# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent zero/maximum controls; synthetic assays are mathematical inputs."""

from fractions import Fraction
import math
import unittest

from flahax import recommend
from flahax.engine import forward, solve_weights
from flahax.nutrient_acceptance import assess_incidental, assess_water_basis


def product(name, **elements):
    return dict(id=name, name=name, elements=elements)


def final(result, symbol):
    return next((r['final'] for r in result['rows'] if r['symbol'] == symbol), 0)


class RequirementConstraintTests(unittest.TestCase):
    def test_zero_excludes_carriers_without_losing_clean_alternative(self):
        products = [product('mixed', K=10, Na=0.1), product('clean', K=10)]
        for ordered in (products, list(reversed(products))):
            result = recommend(ordered, {'K': 100, 'Na': 0}, ridge=0)
            self.assertTrue(result['feasible'])
            self.assertEqual(final(result, 'Na'), 0)
            self.assertEqual({s['id'] for s in result['salts']}, {'clean'})
            self.assertEqual(result['incidentalContributions'], [])

    def test_zero_is_structural_even_for_tiny_assay_and_low_level_solver(self):
        products = [product('mixed', K=10, Na=1e-20)]
        for call in (recommend, solve_weights):
            result = call(products, {'K': 100, 'Na': 0}, ridge=0)
            self.assertEqual(result['grams'], [0])
            self.assertEqual(final(result, 'Na'), 0)
            self.assertFalse(result['feasible'])
            if call is recommend:
                self.assertEqual(
                    result['unmetTargets'][0]['reason'], 'prohibited_by_zero_requirement'
                )

    def test_water_cannot_be_removed_to_satisfy_zero(self):
        # A declared zero is met within 1e-6 mg/L (G25): 2e-6 mg/L of water sodium breaks it.
        for value in (2e-6, 1):
            result = recommend(
                [product('clean', K=10)], {'K': 100, 'Na': 0}, {'Na': value}, ridge=0
            )
            self.assertFalse(result['feasible'])
            self.assertEqual(result['limitViolations'][0]['maximumPpm'], 0)
            self.assertEqual(result['requirementConflicts'][0]['reason'], 'water_above_maximum')
        met = recommend([product('clean', K=10)], {'K': 100, 'Na': 0}, {'Na': 1e-20}, ridge=0)
        self.assertTrue(met['feasible'])
        self.assertEqual((met['limitViolations'], met['requirementConflicts']), ([], []))

    def test_zero_maximum_cannot_be_overridden_by_positive_target_or_permission(self):
        result = recommend(
            [product('a', K=10, Cl=10)],
            {'K': 100, 'Cl': 100},
            maximum_concentrations={'Cl': 0},
            allow_ions={'Cl'},
            ridge=0,
        )
        self.assertEqual(result['grams'], [0])
        self.assertFalse(result['feasible'])
        self.assertEqual(result['requirementConflicts'][0]['reason'], 'target_above_maximum')

    def test_all_zero_targets_are_satisfied_by_no_addition(self):
        result = recommend([product('a', K=10)], {'K': 0})
        self.assertTrue(result['feasible'])
        self.assertEqual(result['salts'], [])

    def test_targeted_cap_matches_independent_one_variable_optimum(self):
        unconstrained = (Fraction(1, 80) + Fraction(1, 200)) / (
            Fraction(1, 80**2) + Fraction(1, 200**2)
        )
        self.assertGreater(unconstrained, 90)
        for background in (0, 20, 90, 95):
            result = recommend(
                [product('a', K=10, Ca=10)],
                {'K': 80, 'Ca': 200},
                {'K': background, 'Ca': background},
                maximum_concentrations={'K': 90},
                ridge=0,
            )
            optimum = max(0, Fraction(90 - background, 100))
            self.assertAlmostEqual(result['grams'][0], float(optimum), delta=1e-6)
            self.assertLessEqual(final(result, 'K'), max(90, background))
            self.assertEqual(bool(result['limitViolations']), background > 90)

    def test_multiple_targeted_caps_and_forward_reconstruction(self):
        products = [product('a', K=10), product('b', Ca=10)]
        result = recommend(
            products, {'K': 100, 'Ca': 200}, ridge=0, maximum_concentrations={'K': 80, 'Ca': 150}
        )
        actual = forward(products, result['grams'])
        for nutrient, cap in {'K': 80, 'Ca': 150}.items():
            self.assertLessEqual(actual[nutrient], cap)
            self.assertAlmostEqual(actual[nutrient], cap, delta=cap * 2e-6)
        self.assertFalse(result['feasible'])
        self.assertEqual(len(result['requirementConflicts']), 2)

    def test_positive_maximum_cannot_relax_explicit_zero(self):
        result = recommend(
            [product('a', K=10, Na=1)],
            {'K': 100, 'Na': 0},
            maximum_concentrations={'Na': 10},
            ridge=0,
        )
        self.assertEqual(final(result, 'Na'), 0)
        self.assertEqual(result['salts'], [])

    def test_exact_boundary_and_next_float_are_distinct(self):
        for limit in (0, 1e-20, 1):
            for amount, exceeds in ((limit, False), (math.nextafter(limit, math.inf), True)):
                rows = [dict(symbol='K', target=None, final=amount)]
                self.assertEqual(
                    bool(assess_incidental(rows, {'K': limit})['limitViolations']), exceeds
                )
        rows = [dict(symbol='K', target=None, final=1e-20)]
        self.assertTrue(assess_water_basis(rows, {'K': 0}, {'K': 1e-20}, {'K': 0}))

    def test_missing_requirement_remains_incidental(self):
        result = recommend([product('a', K=10, N_NH4=0.1)], {'K': 100}, ridge=0)
        self.assertGreater(final(result, 'N_NH4'), 0)
        self.assertTrue(result['requiresReview'])
