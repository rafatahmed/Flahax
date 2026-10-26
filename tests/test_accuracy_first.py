# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Primary objective controls using exact witnesses and rational normal equations."""

from fractions import Fraction
import unittest

from flahax import recommend
from flahax.composition import InputError
from flahax.engine import forward, score, solve_weights


def product(name, **elements):
    return dict(id=name, name=name, elements=elements)


class AccuracyFirstTests(unittest.TestCase):
    def test_default_has_exact_single_product_witness(self):
        result = recommend([product('a', K=10)], {'K': 100})
        self.assertEqual(result['grams'], [1])
        self.assertEqual(result['loss'], 0)

    def test_incidental_concentration_does_not_shrink_required_dose(self):
        for incidental in (0.1, 10, 80):
            result = recommend([product('a', K=10, S=incidental)], {'K': 100})
            self.assertEqual(result['grams'], [1])
            self.assertEqual(result['loss'], 0)
            self.assertTrue(result['requiresReview'])

    def test_score_contains_only_positive_target_relative_errors(self):
        loss, rows = score({'K': 90, 'S': 500, 'N_NH4': 1}, {'K': 100, 'N_NH4': 0})
        self.assertAlmostEqual(loss, float(Fraction(1, 100)), places=15)
        self.assertEqual({r['symbol'] for r in rows}, {'K', 'S', 'N_NH4'})

    def test_rational_compromise_and_independent_stationarity(self):
        # One product, A=(100/80, 100/200), b=(1,1). x=A.b/(A.A).
        a = [Fraction(100, 80), Fraction(100, 200)]
        expected = sum(a) / sum(v * v for v in a)
        result = solve_weights([product('a', K=10, Ca=10, S=30)], {'K': 80, 'Ca': 200})
        x = result['grams'][0]
        self.assertAlmostEqual(x, float(expected), places=13)
        self.assertAlmostEqual(sum(float(v) * (float(v) * x - 1) for v in a), 0, places=13)
        expected_loss = sum((v * expected - 1) ** 2 for v in a)
        self.assertAlmostEqual(result['loss'], float(expected_loss), places=14)

    def test_nonnegative_boundary_kkt(self):
        result = solve_weights([product('a', K=10, S=10)], {'K': 100}, {'K': 120})
        self.assertEqual(result['grams'], [0])
        # f'(0)/2 = (100/100)*(120/100-1) > 0: lower bound is optimal.
        self.assertGreater(Fraction(120, 100) - 1, 0)
        self.assertAlmostEqual(result['loss'], 0.04, places=14)

    def test_exact_multi_product_fit_under_order_and_assay_scaling(self):
        for scale in (0.5, 1, 2):
            products = [
                product('a', K=10 * scale, Ca=10 * scale, S=20 * scale),
                product('b', K=10 * scale),
            ]
            for ordered in (products, list(reversed(products))):
                result = solve_weights(ordered, {'K': 100, 'Ca': 99.5})
                achieved = forward(ordered, result['grams'])
                self.assertAlmostEqual(achieved['K'], 100, places=11)
                self.assertAlmostEqual(achieved['Ca'], 99.5, places=11)
                self.assertLess(result['loss'], 1e-25)

    def test_empty_objective_returns_full_zero_vector(self):
        products = [product('a', K=10), product('b', Ca=10)]
        for targets in ({}, {'S': 0}):
            result = solve_weights(products, targets)
            self.assertEqual(result['grams'], [0, 0])
            self.assertEqual(result['loss'], 0)

    def test_regularization_cannot_override_accuracy(self):
        for call in (recommend, solve_weights):
            for ridge in (0.02, -1, float('nan'), float('inf'), True, '0', None):
                with self.subTest(call=call.__name__, ridge=ridge):
                    with self.assertRaisesRegex(InputError, 'ridge'):
                        call([product('a', K=10)], {'K': 100}, ridge=ridge)


if __name__ == '__main__':
    unittest.main()
