# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.stock_volumes."""

import unittest

from flahax.delivery_contracts import DeliveryError
from flahax.stock_volumes import StockVolumes, prepare_stocks


class FillModeTests(unittest.TestCase):
    def test_equal_tanks_fill_full(self):
        volumes = prepare_stocks(
            tank_litres={'A': 20, 'B': 20, 'acid': 20}, ratio=100, mode='fill'
        )
        self.assertIsInstance(volumes, StockVolumes)
        self.assertEqual(volumes.irrigation_litres, 2000)
        self.assertEqual(volumes.prepared_litres, {'A': 20, 'B': 20, 'acid': 20})
        self.assertEqual(volumes.capacity_litres, {'A': 20, 'B': 20, 'acid': 20})

    def test_smallest_tank_limits_irrigation_and_larger_tank_is_part_filled(self):
        # Review Focus 2: B holds 30 L but only 20 L of it can be prepared.
        volumes = prepare_stocks(
            tank_litres={'A': 20, 'B': 30, 'acid': 20}, ratio=100, mode='fill'
        )
        self.assertEqual(volumes.irrigation_litres, 2000)
        self.assertEqual(volumes.prepared_litres['B'], 20)
        self.assertEqual(volumes.capacity_litres['B'], 30)

    def test_fill_never_prepares_more_than_the_tank_holds(self):
        # 487.3 * 150.5 / 150.5 is 1 ulp above 487.3 in floating point.
        volumes = prepare_stocks(
            tank_litres={'A': 487.3, 'B': 600, 'acid': 600}, ratio=150.5, mode='fill'
        )
        for name, litres in volumes.prepared_litres.items():
            self.assertLessEqual(litres, volumes.capacity_litres[name])
        self.assertEqual(volumes.prepared_litres, {'A': 487.3, 'B': 487.3, 'acid': 487.3})


class OnceModeTests(unittest.TestCase):
    def test_one_irrigation_divides_by_ratio(self):
        volumes = prepare_stocks(
            tank_litres={'A': 20, 'B': 20, 'acid': 20},
            ratio=100,
            mode='once',
            irrigation_litres=1000,
        )
        self.assertEqual(volumes.irrigation_litres, 1000)
        self.assertEqual(volumes.prepared_litres, {'A': 10, 'B': 10, 'acid': 10})

    def test_too_small_tanks_are_named(self):
        with self.assertRaises(DeliveryError) as raised:
            prepare_stocks(
                tank_litres={'A': 20, 'B': 20, 'acid': 20},
                ratio=100,
                mode='once',
                irrigation_litres=3000,
            )
        self.assertEqual(raised.exception.code, 'tank_too_small')
        for name in ('A', 'B', 'acid'):
            self.assertIn(name, str(raised.exception))

    def test_exact_fit_passes(self):
        # irrigation / ratio equals the capacity exactly: not too small.
        volumes = prepare_stocks(
            tank_litres={'A': 10, 'B': 10, 'acid': 10},
            ratio=100,
            mode='once',
            irrigation_litres=1000,
        )
        self.assertEqual(volumes.prepared_litres, {'A': 10, 'B': 10, 'acid': 10})

    def test_only_the_too_small_container_is_named(self):
        with self.assertRaises(DeliveryError) as raised:
            prepare_stocks(
                tank_litres={'A': 20, 'B': 5, 'acid': 20},
                ratio=100,
                mode='once',
                irrigation_litres=1000,
            )
        self.assertEqual(raised.exception.code, 'tank_too_small')
        self.assertTrue(str(raised.exception).startswith('B cannot hold'), str(raised.exception))
        self.assertNotIn('acid', str(raised.exception))


class ValidationTests(unittest.TestCase):
    def assertInvalid(self, **overrides):
        arguments = dict(tank_litres={'A': 20, 'B': 20, 'acid': 20}, ratio=100, mode='fill')
        arguments.update(overrides)
        with self.assertRaises(DeliveryError) as raised:
            prepare_stocks(**arguments)
        self.assertEqual(raised.exception.code, 'invalid_value')

    def test_capacity_must_be_positive_finite(self):
        for bad in (0, -5, float('nan'), float('inf'), True, None, 'twenty'):
            with self.subTest(bad=bad):
                self.assertInvalid(tank_litres={'A': bad, 'B': 20, 'acid': 20})

    def test_ratio_must_be_positive_finite(self):
        for bad in (0, -100, float('nan'), float('inf'), True):
            with self.subTest(bad=bad):
                self.assertInvalid(ratio=bad)

    def test_mode_must_be_known(self):
        self.assertInvalid(mode='weekly')

    def test_once_needs_positive_irrigation(self):
        for bad in (None, 0, -1, float('nan')):
            with self.subTest(bad=bad):
                self.assertInvalid(mode='once', irrigation_litres=bad)

    def test_tanks_must_be_a_b_and_acid(self):
        self.assertInvalid(tank_litres={'A': 20, 'B': 20})


if __name__ == '__main__':
    unittest.main()
