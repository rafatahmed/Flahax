# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Secondary preferences must preserve the original numerical fit and hard limits."""

import math
import unittest
from unittest.mock import patch
from flahax import recommend
from flahax.engine import _simplify, _still_within, score


def product(name, **elements):
    return dict(id=name, name=name, elements=elements)


def fit(grams, achieved, targets):
    loss, rows = score(achieved, targets)
    return dict(grams=grams, rows=rows, loss=loss)


class SecondaryFitTests(unittest.TestCase):
    def test_exact_two_product_witness_survives_simplification(self):
        for products in (
            [product('a', K=10, Ca=10), product('b', K=10)],
            [product('b', K=10), product('a', K=10, Ca=10)],
        ):
            result = recommend(products, {'K': 100, 'Ca': 99.5})
            rows = {r['symbol']: r for r in result['rows']}
            self.assertAlmostEqual(rows['K']['final'], 100, places=11)
            self.assertAlmostEqual(rows['Ca']['final'], 99.5, places=11)
            self.assertEqual(len(result['salts']), 2)

    def test_assay_scaling_preserves_attainable_targets(self):
        for scale in (0.5, 1, 2):
            result = recommend(
                [product('a', K=10 * scale, Ca=10 * scale), product('b', K=10 * scale)],
                {'K': 100, 'Ca': 99.5},
            )
            for row in result['rows']:
                self.assertAlmostEqual(row['final'], row['target'], places=11)

    def test_three_successive_drops_cannot_reset_the_accuracy_anchor(self):
        products = [product(str(i), K=10, Ca=10) for i in range(6)]
        targets = {'K': 100, 'Ca': 100}
        original = fit([1] * 6, {'K': 99, 'Ca': 99}, targets)
        snapshot = [dict(r) for r in original['rows']]

        def trial(pool, *_args, **_kwargs):
            achieved = {
                5: {'K': 99.2, 'Ca': 99},
                4: {'K': 99.4, 'Ca': 99},
                3: {'K': 100, 'Ca': 99},
                2: {'K': 100, 'Ca': 98.9999999},
            }[len(pool)]
            return fit([1] * len(pool), achieved, targets)

        with patch('flahax.engine._fit_within', side_effect=trial):
            result = _simplify(products, targets, {}, original, 0)
        self.assertEqual(sum(g > 0 for g in result['grams']), 3)
        self.assertEqual(result['rows'][1]['final'], 99)
        self.assertEqual(original['rows'], snapshot)

    def test_feasibility_band_is_not_a_simplification_allowance(self):
        original = fit([1], {'K': 100}, {'K': 100})
        for value in (99.9, math.nextafter(100, 0)):
            trial = fit([1], {'K': value}, {'K': 100})
            self.assertFalse(_still_within(trial['rows'], original['rows']))
        self.assertFalse(_still_within([], original['rows']))

    def test_each_removal_is_compared_with_original_not_previous_fit(self):
        products = [product(str(i), K=10, Ca=10) for i in range(3)]
        targets = {'K': 100, 'Ca': 100}
        original = fit([1, 1, 1], {'K': 99, 'Ca': 99}, targets)
        # First removal improves K, retaining Ca; second attempts to worsen Ca.
        trials = [
            fit([1, 1], {'K': 100, 'Ca': 99}, targets),
            fit([1], {'K': 100, 'Ca': 98.9999999}, targets),
        ]
        with patch(
            'flahax.engine._fit_within',
            side_effect=lambda *a, **k: trials.pop(0) if len(trials) > 1 else trials[0],
        ):
            result = _simplify(products, targets, {}, original, 0)
        self.assertEqual(sum(g > 0 for g in result['grams']), 2)
        self.assertEqual(result['rows'][1]['final'], 99)

    def test_lower_product_count_cannot_increase_primary_loss(self):
        products = [product(str(i), K=10, Ca=10) for i in range(3)]
        targets = {'K': 100, 'Ca': 100}
        original = fit([1, 1, 1], {'K': 99, 'Ca': 99}, targets)
        first = fit([1, 1], {'K': 100, 'Ca': 99}, targets)
        later = fit([1], {'K': 99, 'Ca': 99}, targets)
        with patch('flahax.engine._fit_within', side_effect=[first, later, later]):
            result = _simplify(products, targets, {}, original, 0)
        self.assertEqual(result['loss'], first['loss'])
        self.assertEqual(sum(g > 0 for g in result['grams']), 2)

    def test_zero_and_maximum_are_checked_after_secondary_refit(self):
        for targets, maxima, achieved in [
            ({'K': 100, 'S': 0}, {}, {'K': 100, 'S': 1e-20}),
            ({'K': 100}, {'Ca': 10}, {'K': 100, 'Ca': 11}),
        ]:
            products = [product('a', K=10), product('b', K=10)]
            original = fit([0.5, 0.5], {'K': 100}, targets)
            trial = fit([1], achieved, targets)
            with patch('flahax.engine._fit_within', return_value=trial):
                result = _simplify(products, targets, {}, original, 0, maxima)
            self.assertEqual(result['grams'], [0.5, 0.5])

    def test_exact_equivalent_redundant_product_can_be_removed(self):
        products = [product('a', K=10), product('b', K=10)]
        original = fit([0.5, 0.5], {'K': 100}, {'K': 100})
        result = _simplify(products, {'K': 100}, {}, original, 0)
        self.assertEqual(sum(g > 0 for g in result['grams']), 1)
        self.assertEqual(result['loss'], 0)


if __name__ == '__main__':
    unittest.main()
