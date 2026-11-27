# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Float sums give the same digits on every supported Python (#334)."""

import ast
from fractions import Fraction
from pathlib import Path
import random
import sys
import unittest

from flahax.float_sum import _compensated_sum, float_sum

ROOT = Path(__file__).resolve().parents[1]
INF = float('inf')
# Expected values come from the built-in sum of Python 3.13 (compensated).
VECTORS = [
    ('ten_tenths', [0.1] * 10, 0, '1.0'),
    ('cancel', [1e16, 1.0, -1e16], 0, '1.0'),
    ('cancel_small_first', [1.0, 1e16, -1e16], 0, '1.0'),
    ('many', [0.1, 0.2, 0.3, 1e-17, -0.6, 7e-16] * 5, 0, '3.688777878078145e-15'),
    ('ints_only', [1, 2, 3, True, 5], 0, '12'),
    ('int_then_float', [1, 2, 0.1, 0.2, 0.3], 0, '3.6'),
    ('bool_then_float', [True, 0.1, 0.7, 1e-17], 0, '1.8'),
    ('float_then_int', [0.1, 0.2, 3, 0.3], 0, '3.5999999999999996'),
    ('float_start', [0.1, 0.2, 0.3], 0.5, '1.1'),
    ('negative_zero', [-0.0, -0.0], 0, '0.0'),
    ('negative_zero_start', [-0.0], -0.0, '-0.0'),
    ('empty', [], 0, '0'),
    ('empty_float_start', [], 1.5, '1.5'),
    ('big_int_in_floats', [0.1, 0.2, 2**70, 0.3, 0.4, 1e-17], 0, '1.1805916207174113e+21'),
    ('fraction_in_floats', [0.1, 0.2, Fraction(1, 3), 0.3], 0, '0.9333333333333333'),
    ('fraction_without_compensation', [0.5, Fraction(1, 2)], 0, '1.0'),
    ('fraction_after_infinity', [INF, -INF, Fraction(1, 2)], 0, 'nan'),
    ('fraction_with_compensation', [0.1, 0.2, 0.3, Fraction(1, 2)], 0, '1.1'),
    ('fraction_start', [0.1, 0.2], Fraction(1, 3), '0.6333333333333333'),
    ('fraction_after_ints', [1, Fraction(1, 3), 2], 0, 'Fraction(10, 3)'),
    ('infinity', [1.0, INF, 2.0, 0.1], 0, 'inf'),
    ('infinity_cancel', [INF, -INF, 1.0], 0, 'nan'),
    ('nan', [1.0, float('nan'), 2.0], 0, 'nan'),
]


class FloatSumTests(unittest.TestCase):
    def test_both_implementations_give_the_python_3_13_value(self):
        for name, values, start, expected in VECTORS:
            for implementation in (float_sum, _compensated_sum):
                # Python 3.14 also compensates ints that follow a float; 3.12 and 3.13 add them
                # plainly, which is what the 3.11 replacement repeats.
                if (
                    name == 'float_then_int'
                    and implementation is sum
                    and sys.version_info >= (3, 14)
                ):
                    continue
                with self.subTest(case=name, implementation=implementation.__name__):
                    self.assertEqual(repr(implementation(iter(values), start)), expected)

    def test_default_start_is_zero(self):
        self.assertEqual(repr(float_sum([0.1] * 10)), '1.0')
        self.assertEqual(repr(_compensated_sum([0.1] * 10)), '1.0')

    @unittest.skipIf(sys.version_info < (3, 12), 'the built-in sum is not compensated')
    def test_the_replacement_matches_the_builtin_on_random_float_lists(self):
        rng = random.Random(334)
        for _ in range(500):
            values = [
                rng.uniform(-1, 1) * 10 ** rng.randint(-12, 12) for _ in range(rng.randint(0, 40))
            ]
            self.assertEqual(repr(_compensated_sum(values)), repr(sum(values)))

    def test_builtin_sum_is_used_where_it_already_compensates(self):
        if sys.version_info >= (3, 12):
            self.assertIs(float_sum, sum)
        else:
            self.assertIs(float_sum, _compensated_sum)

    def test_no_bare_sum_in_the_package(self):
        found = []
        for path in sorted((ROOT / 'src' / 'flahax').glob('*.py')):
            if path.name == 'float_sum.py':
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Name) and node.id == 'sum':
                    found.append(f'{path.name}:{node.lineno}')
        self.assertEqual(found, [], 'use float_sum so Python 3.11 and 3.12+ agree (#334)')


if __name__ == '__main__':
    unittest.main()
