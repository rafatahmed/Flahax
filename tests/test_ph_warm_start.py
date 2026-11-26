# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""A warm-started pH grid agrees with cold solves within the solver
tolerance and seeds each point from its nearest solved pH (#339).
"""

import unittest

from flahax.aqueous_model import solve
from flahax.ratio_ph_refinement import warm_started

TOTALS = {'Ca+2': 2e-3, 'PO4-3': 1e-3, 'K+': 3e-3, 'NO3-': 5e-3, 'Mg+2': 1e-3, 'SO4-2': 1e-3}
# The solver stops at a log residual of 2e-10, so warm and cold states can differ by about that.
TOLERANCE = 1e-9


class WarmStartTests(unittest.TestCase):
    def test_first_point_is_cold_and_each_next_point_starts_from_the_nearest(self):
        seen = []

        def record(ph, start):
            seen.append((ph, None if start is None else start.ph))
            return solve(TOTALS, ph, start=start)

        solve_at = warm_started(record)
        for ph in (6.0, 7.0, 6.9, 6.2):
            solve_at(ph)
        self.assertEqual(seen, [(6.0, None), (7.0, 6.0), (6.9, 7.0), (6.2, 6.0)])

    def test_warm_states_agree_with_cold_states_within_solver_tolerance(self):
        solve_at = warm_started(lambda ph, start: solve(TOTALS, ph, start=start))
        for ph in (6.0, 6.1, 6.3, 6.25, 7.0):
            warm, cold = solve_at(ph), solve(TOTALS, ph)
            self.assertLess(warm.iterations, cold.iterations + 1)
            for phase, value in cold.saturation_indices.items():
                self.assertAlmostEqual(warm.saturation_indices[phase], value, delta=TOLERANCE)
            self.assertAlmostEqual(warm.charge_balance, cold.charge_balance, delta=TOLERANCE)
            self.assertAlmostEqual(warm.ionic_strength, cold.ionic_strength, delta=TOLERANCE)


if __name__ == '__main__':
    unittest.main()
