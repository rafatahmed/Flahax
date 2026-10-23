# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Shared bracketed root finding used by the dose, pH and alkalinity searches."""

import unittest

from flahax.root_finding import shrink_bracket


class ShrinkBracketTests(unittest.TestCase):
    def test_reaches_the_requested_width_in_few_evaluations(self):
        calls = []

        def g(x):
            calls.append(x)
            return 2.0 - x * x

        lo, hi = shrink_bracket(g, 0.0, 2.0, 2.0, -2.0, width=2.0 * 2.0**-40)
        self.assertLessEqual(hi - lo, 2.0 * 2.0**-40)
        self.assertAlmostEqual((lo + hi) / 2, 2**0.5, places=12)
        self.assertLess(len(calls), 20)  # bisection needs 40

    def test_relative_width_and_decreasing_functions(self):
        lo, hi = shrink_bracket(lambda x: 1e-3 - x, 0.0, 1e-3, 1.0, 1e-3 - 1.0, relative=1e-12)
        self.assertLessEqual(hi - lo, 1e-12 * hi + 1e-18)
        self.assertAlmostEqual(lo, 1e-3, delta=1e-14)

    def test_exact_zero_and_zero_endpoint(self):
        self.assertEqual(
            shrink_bracket(lambda x: x - 0.5, 0.0, -0.5, 1.0, 0.5, width=1e-9), (0.5, 0.5)
        )
        self.assertEqual(shrink_bracket(lambda x: x, 0.0, 0.0, 1.0, 1.0), (0.0, 0.0))

    def test_accept_ends_at_an_evaluated_point(self):
        seen = []

        def g(x):
            seen.append(x)
            return x - 0.3

        lo, hi = shrink_bracket(
            g, 0.0, -0.3, 1.0, 0.7, accept=lambda x, gx, lo, hi: abs(gx) < 1e-6
        )
        self.assertEqual(lo, hi)
        self.assertIn(lo, seen)

    def test_stray_secant_steps_fall_back_to_bisection(self):
        # A steep step function defeats false position; the bracket must still shrink.
        lo, hi = shrink_bracket(
            lambda x: -1.0 if x < 0.123456 else 1e9, 0.0, -1.0, 1.0, 1e9, width=1e-9
        )
        self.assertLessEqual(hi - lo, 1e-9)
        self.assertTrue(lo <= 0.123456 <= hi)


if __name__ == "__main__":
    unittest.main()
