# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.fertilizer_equilibrium."""

import unittest
from pathlib import Path

from flahax import (
    DeliveryError,
    FertilizerTotals,
    solve_fertilizer_equilibrium,
)
from flahax.reference_fixtures import assert_reference_result, load_reference_fixture
from flahax.fertilizer_equilibrium import solve_legacy_phreeqc_macro, plan_legacy_phreeqc_nitric


TOTALS = FertilizerTotals(
    calcium=0.001,
    magnesium=0.001,
    phosphate=0.001,
    carbonate=0.0024,
    sulfate=0.001,
    nitrate=0.003,
    potassium=0.002,
    sodium=0.003,
    chloride=0.007,
)


class FertilizerEquilibriumTests(unittest.TestCase):
    def test_target_ph_reference_fixture(self):
        fixture = load_reference_fixture(
            Path(__file__).parent / "fixtures" / "phreeqc" / "target_ph_nitric_dose.json"
        )
        # Historical phreeqc.dat golden case remains bound to its original
        # reduced kernel; public planning now uses the pinned MINTEQ model.
        target = solve_legacy_phreeqc_macro(TOTALS, 6.0, allow_precipitation=False)
        dose = plan_legacy_phreeqc_nitric(TOTALS, 7.4, 6.0)
        assert_reference_result(
            fixture,
            {
                "ph": target.ph,
                "ionicStrength": target.ionic_strength,
                "nitricAcidMolal": dose.nitric_acid_molal,
                "freeCalciumMolal": target.species["Ca+2"],
                "freeMagnesiumMolal": target.species["Mg+2"],
                "freePhosphateMolal": target.species["PO4-3"],
                "hpo4Molal": target.species["HPO4-2"],
                "h2po4Molal": target.species["H2PO4-"],
                "freeCarbonateMolal": target.species["CO3-2"],
                "bicarbonateMolal": target.species["HCO3-"],
                "freeSulfateMolal": target.species["SO4-2"],
                "si.Calcite": target.saturation_indices["Calcite"],
                "si.Gypsum": target.saturation_indices["Gypsum"],
                "si.Hydroxyapatite": target.saturation_indices["Hydroxyapatite"],
            },
        )
        self.assertAlmostEqual(target.ph, 6.0, places=12)
        self.assertLess(abs(dose.nitric_acid_molal - 0.0020866), 0.0005)

    def test_precipitation_allocation_conserves_named_elements(self):
        supersaturated = FertilizerTotals(
            calcium=0.001,
            magnesium=0.001,
            phosphate=0.001,
            carbonate=0.001,
            sulfate=0.001,
            ammonium=0.001,
            nitrate=0.003,
            potassium=0.002,
            sodium=0.003,
            chloride=0.007,
        )
        result = solve_fertilizer_equilibrium(supersaturated, 8.5)
        self.assertTrue(result.phase_allocations)
        self.assertTrue(all(value >= 0 for value in result.precipitation_moles.values()))
        self.assertLessEqual(max(result.saturation_indices.values()), 1e-5)

    def test_rejects_davies_extrapolation(self):
        with self.assertRaises(DeliveryError) as caught:
            solve_fertilizer_equilibrium(FertilizerTotals(nitrate=0.2, potassium=0.2), 6)
        self.assertEqual(caught.exception.code, "activity_model_out_of_range")
