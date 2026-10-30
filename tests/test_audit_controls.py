# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Preserved failing mathematical controls; these are not expected-failure tests.

Run explicitly while establishing the baseline. Their failures remain real failures
in discovery until the owning production fixes satisfy the unchanged contract.
Synthetic assays test the mathematical interface, not physical mixture suitability.
"""

from fractions import Fraction
import unittest

from flahax import recommend


def product(identifier, elements):
    return {'id': identifier, 'name': 'Synthetic audit product', 'elements': elements}


def final(result, symbol):
    return next(row['final'] for row in result['rows'] if row['symbol'] == symbol)


class IndependentOracleTests(unittest.TestCase):
    def test_zero_constraint_and_allowed_counterion_witness(self):
        # Positive dose supplies ammonium; dose zero cannot meet the positive K target.
        self.assertGreater(Fraction('0.1') * 10, 0)
        self.assertEqual(Fraction(0) * 10 * 10, 0)
        chloride = Fraction(100) * Fraction('47.555') / Fraction('52.445')
        self.assertLess(chloride, 100)

    def test_single_product_constrained_optimum(self):
        # Minimize (x/80-1)^2 + (x/200-1)^2 over 0 <= x <= 90.
        optimum = (Fraction(1, 80) + Fraction(1, 200)) / (Fraction(1, 80**2) + Fraction(1, 200**2))
        self.assertGreater(optimum, 90)
        self.assertEqual(min(optimum, 90), 90)
        self.assertEqual(Fraction(90) / (10 * 10), Fraction(9, 10))

    def test_trace_dose_and_exact_two_product_witness(self):
        self.assertEqual(Fraction('0.00001') / 100, Fraction(1, 10_000_000))
        a, b = Fraction('0.995'), Fraction('0.005')
        self.assertEqual((a + b) * 100, 100)
        self.assertEqual(a * 100, Fraction('99.5'))


class AuditRegressionTests(unittest.TestCase):
    def test_f01_explicit_zero_is_not_feasible_with_positive_contribution(self):
        result = recommend([product('a', {'K': 10, 'Na': 0.1})], {'K': 100, 'Na': 0}, {})
        self.assertFalse(result['feasible'] and final(result, 'Na') > 0)

    def test_f02_targeted_maximum_is_enforced(self):
        result = recommend(
            [product('a', {'K': 10, 'Ca': 10})],
            {'K': 80, 'Ca': 200},
            {},
            maximum_concentrations={'K': 90},
        )
        self.assertLessEqual(final(result, 'K'), 90)

    def test_f03_exact_single_product_has_no_hidden_ridge_miss(self):
        result = recommend([product('a', {'K': 10})], {'K': 100}, {})
        # This witness is exactly representable: 1 g/L * 10 percent * 10 = 100 mg/L.
        self.assertEqual(final(result, 'K'), 100)

    def test_f03_secondary_selection_preserves_attainable_targets(self):
        result = recommend(
            [product('a', {'K': 10, 'Ca': 10}), product('b', {'K': 10})],
            {'K': 100, 'Ca': 99.5},
            {},
            ridge=0,
        )
        # Distinct targets require distinct final concentrations, whatever solver ordering.
        self.assertGreater(final(result, 'K'), final(result, 'Ca'))

    def test_f04_reported_trace_matches_emitted_products(self):
        result = recommend([product('a', {'Mo': 10})], {'Mo': 0.00001}, {}, ridge=0)
        emitted = sum(Fraction(str(row['gramsPerLitre'])) * 100 for row in result['salts'])
        self.assertGreater(emitted, 0, 'an empty recipe cannot deliver the positive Mo target')

    def test_f05_permitted_counterion_does_not_prove_impossibility(self):
        result = recommend(
            [product('a', {'K': 52.445, 'Cl': 47.555})],
            {'K': 100},
            {},
            maximum_concentrations={'Cl': 100},
        )
        self.assertFalse(
            any(
                'No salt combination meets every target exactly' in warning
                for warning in result['warnings']
            )
        )


if __name__ == '__main__':
    unittest.main()
