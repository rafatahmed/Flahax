# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.ammonia."""

import unittest
from flahax.ammonia import ammonia_speciation


class AmmoniaSpeciationTests(unittest.TestCase):
    def test_mass_balance_and_struvite_probe_ammonium(self):
        result = ammonia_speciation(0.001, 8.5, 0.005168)
        self.assertAlmostEqual(result.ammonium_molal + result.ammonia_molal, 0.001, places=15)
        self.assertAlmostEqual(result.ammonium_molal, 0.0008575, places=5)

    def test_high_ph_increases_neutral_ammonia(self):
        self.assertGreater(
            ammonia_speciation(0.001, 10, 0.01).ammonia_molal,
            ammonia_speciation(0.001, 7, 0.01).ammonia_molal,
        )
