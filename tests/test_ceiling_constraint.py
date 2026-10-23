# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""#68: binding ceilings are met as constraints, and NNLS optimality is tested per column."""

import unittest

from flahax import load_library, recommend
from flahax.engine import CEILING_MARGIN, CEILING_TOLERANCE, _fit_within, nnls

LIBRARY = load_library()
SALTS = LIBRARY["salts"]
# Generic Grow needs more ammonium than the default limit allows, so the limit binds.
GROW = next(f for f in LIBRARY["formulas"] if f["name"] == "Generic Grow (maximumyield)")


def final(result, symbol):
    return next((row["final"] for row in result["rows"] if row["symbol"] == symbol), 0.0)


class NnlsOptimalityTests(unittest.TestCase):
    def test_a_large_row_does_not_hide_a_small_column(self):
        # The second column's dual weight (1e-8) was below the old global tolerance
        # 10 max(m, n) eps |A| |b| (about 4.4e-7), so NNLS stopped with x2 = 0.
        x = nnls([[1e4, 0.0], [0.0, 1e-4]], [1e4, 1e-4])
        self.assertAlmostEqual(x[0], 1.0, places=12)
        self.assertAlmostEqual(x[1], 1.0, places=9)

    def test_scale_invariance_is_kept(self):
        # #36: a problem scaled by 1e-8 has the same solution.
        for scale in (1.0, 1e-8, 1e8):
            x = nnls([[scale, scale], [scale, -scale], [0.0, scale]], [2 * scale, 0.0, scale])
            self.assertAlmostEqual(x[0], 1.0, places=10, msg=scale)
            self.assertAlmostEqual(x[1], 1.0, places=10, msg=scale)


class CeilingConstraintTests(unittest.TestCase):
    def test_binding_ammonium_limit_lands_on_its_aim(self):
        result = recommend(SALTS, GROW["targets"], {})
        limit = result["ammoniumLimit"]["mgPerL"]
        self.assertTrue(any(miss["bindingLimits"] == ["N_NH4"] for miss in result["unmetTargets"]))
        self.assertAlmostEqual(
            final(result, "N_NH4"),
            limit * (1 - CEILING_MARGIN),
            delta=2 * CEILING_TOLERANCE * limit,
        )
        self.assertLessEqual(final(result, "N_NH4"), limit)

    def test_result_does_not_depend_on_the_starting_point(self):
        # The old 1024-weight penalty fixed doses only to ~4e-3 g/L, so warm and cold
        # starts disagreed; the constrained optimum is unique (ridge > 0).
        limit = recommend(SALTS, GROW["targets"], {})["ammoniumLimit"]["mgPerL"]
        cold = _fit_within(SALTS, GROW["targets"], {}, 0.02, {"N_NH4": limit})
        warm = _fit_within(
            SALTS,
            GROW["targets"],
            {},
            0.02,
            {"N_NH4": limit},
            x0=[g * 1.5 + 0.01 for g in cold["grams"]],
        )
        self.assertLess(max(abs(a - b) for a, b in zip(cold["grams"], warm["grams"])), 1e-7)


if __name__ == "__main__":
    unittest.main()
