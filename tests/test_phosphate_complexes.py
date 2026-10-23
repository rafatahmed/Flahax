# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.phosphate_complexes."""

import unittest

from flahax.phosphate_complexes import (
    calcium_magnesium_phosphate_speciation,
    hydroxyapatite_hpo4_activity_at_equilibrium,
)
from flahax.equilibrium import davies_gamma


class CalciumMagnesiumPhosphateTests(unittest.TestCase):
    def test_reference_mixture_forms_metal_phosphate_complexes(self):
        result = calcium_magnesium_phosphate_speciation(0.002, 0.001, 0.001, 0.001, 6.5, 0.00985)
        self.assertGreater(result.calcium_hpo4_molal, 0)
        self.assertGreater(result.magnesium_hpo4_molal, 0)
        self.assertGreater(result.hydroxyapatite_si, 0)

    def test_hydroxyapatite_boundary_is_below_the_supersaturated_fixture(self):
        result = calcium_magnesium_phosphate_speciation(0.002, 0.001, 0.001, 0.001, 6.5, 0.00985)
        limit = hydroxyapatite_hpo4_activity_at_equilibrium(
            result.free_calcium_molal * davies_gamma(2, result.ionic_strength), result.ph
        )
        self.assertLess(limit, result.hpo4_molal * davies_gamma(2, result.ionic_strength))
