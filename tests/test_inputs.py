# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
"""The shared number check, exercised only through its interface."""

import math
import unittest

from flahax.delivery_contracts import DeliveryError as ReExported
from flahax.inputs import DeliveryError, number


class NumberTests(unittest.TestCase):
    def code(self, *args, **kwargs):
        with self.assertRaises(DeliveryError) as raised:
            number(*args, **kwargs)
        return raised.exception.code

    def test_delivery_error_is_one_class_under_both_import_paths(self):
        self.assertIs(DeliveryError, ReExported)
        self.assertTrue(issubclass(DeliveryError, ValueError))

    def test_int_and_float_return_a_float(self):
        self.assertEqual(number(3, 'x'), 3.0)
        self.assertIsInstance(number(3, 'x'), float)
        self.assertEqual(number(0, 'x'), 0.0)

    def test_none_is_a_missing_field(self):
        self.assertEqual(self.code(None, 'x'), 'missing_field')

    def test_bool_string_and_other_types_are_not_numbers(self):
        for value in (True, False, '1', '1.5', [1], {'v': 1}, 1 + 2j):
            with self.subTest(value=value):
                self.assertEqual(self.code(value, 'x'), 'invalid_value')

    def test_type_code_names_the_domain_code_for_wrong_types(self):
        self.assertEqual(self.code('1', 'x', type_code='invalid_type'), 'invalid_type')

    def test_nan_and_infinity_are_invalid_values(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                self.assertEqual(self.code(value, 'x'), 'invalid_value')
                self.assertEqual(self.code(value, 'x', minimum=None), 'invalid_value')

    def test_minimum_defaults_to_zero_inclusive(self):
        self.assertEqual(number(0, 'x'), 0.0)
        self.assertEqual(self.code(-0.1, 'x'), 'out_of_range')

    def test_minimum_none_allows_any_finite_value(self):
        self.assertEqual(number(-5, 'x', minimum=None), -5.0)

    def test_minimum_is_inclusive(self):
        self.assertEqual(number(2, 'x', minimum=2), 2.0)
        self.assertEqual(self.code(1.99, 'x', minimum=2), 'out_of_range')

    def test_positive_excludes_zero(self):
        self.assertEqual(number(1e-12, 'x', positive=True), 1e-12)
        self.assertEqual(self.code(0, 'x', positive=True), 'out_of_range')
        self.assertEqual(self.code(-1, 'x', positive=True, minimum=None), 'out_of_range')

    def test_maximum_is_inclusive(self):
        self.assertEqual(number(100, 'x', maximum=100), 100.0)
        self.assertEqual(self.code(100.01, 'x', maximum=100), 'out_of_range')

    def test_code_replaces_every_failure_code(self):
        for value in (None, True, math.nan, -1):
            with self.subTest(value=value):
                self.assertEqual(self.code(value, 'x', code='domain_code'), 'domain_code')

    def test_the_name_is_in_the_message(self):
        with self.assertRaises(DeliveryError) as raised:
            number(-1, 'water mass')
        self.assertIn('water mass', str(raised.exception))

    def test_only_malformed_or_out_of_bounds_input_blocks(self):
        # ADR 0001: no hidden threshold. A very large or very small finite
        # value passes when the caller declares no bound.
        self.assertEqual(number(1e300, 'x'), 1e300)
        self.assertEqual(number(5e-324, 'x'), 5e-324)


if __name__ == '__main__':
    unittest.main()
