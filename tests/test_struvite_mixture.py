# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.struvite_mixture."""

import unittest
from flahax.struvite_mixture import (
    solve_charge_balanced_struvite_mixture,
    struvite_mixture_speciation,
)


class StruviteMixtureTests(unittest.TestCase):
    def test_phreeqc_probe_direction(self):
        r = struvite_mixture_speciation(0.001, 0.001, 0.001, 0.001, 8.5, 0.005168)
        self.assertAlmostEqual(r.ammonium_molal, 0.0008575, places=5)
        self.assertLess(r.struvite_si, 0)
        self.assertAlmostEqual(r.struvite_si, -0.30, places=1)

    def test_reduced_system_solves_charge_balance(self):
        r = solve_charge_balanced_struvite_mixture(0.001, 0.001, 0.001, 0.001, 0.003)
        self.assertAlmostEqual(r.charge_residual, 0, places=9)
        self.assertGreaterEqual(r.ph, 0)
        self.assertLessEqual(r.ph, 14)

    def test_calcium_sulfate_are_explicit_charge_and_phase_inputs(self):
        r = solve_charge_balanced_struvite_mixture(0.001, 0.001, 0.001, 0.002, 0.005, 0.001, 0.001)
        self.assertAlmostEqual(r.charge_residual, 0, places=9)
        self.assertIsNotNone(r.gypsum_si)
        self.assertGreater(r.calcium_sulfate_molal, 0)
        self.assertLess(r.free_calcium_molal, 0.001)
