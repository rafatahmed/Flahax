# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Rounded delivered recipes must satisfy every selected phase across
the pH grid.
"""

import unittest

from flahax import plan_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from tests.test_ratio_recipe import REQUEST


class RatioSaturationTests(unittest.TestCase):
    def recipe(self, strength, **options):
        return plan_ratio_recipe(
            **dict(REQUEST, counted_mmol_l=strength, ph_range=[6.28, 6.32], **options)
        )

    def test_monetite_crossing_blocks_pass(self):
        check = self.recipe(11.392)["rounded_verification"]
        self.assertEqual(check["status"], "failed")
        self.assertLess(check["target_ph_saturation_indices"]["CaHPO4"], 0)
        self.assertGreater(check["phase_maxima"]["CaHPO4"]["si"], 0)
        self.assertAlmostEqual(check["phase_maxima"]["CaHPO4"]["ph"], 6.32)

    def test_hydroxyapatite_crossing_blocks_pass(self):
        check = self.recipe(1.94968)["rounded_verification"]
        self.assertLess(check["target_ph_saturation_indices"]["Hydroxylapatite"], 0)
        self.assertGreater(check["phase_maxima"]["Hydroxylapatite"]["si"], 0)
        self.assertEqual(check["status"], "failed")

    def test_dilute_recipe_passes_all_checks(self):
        check = self.recipe(1.8)["rounded_verification"]
        self.assertEqual(check["status"], "passed")
        self.assertTrue(check["rounding_within_tolerance"])
        self.assertTrue(check["rounded_ph_in_range"])
        self.assertEqual(len(check["phase_maxima"]), 3)
        self.assertGreater(len(check["evaluated_ph"]), 3)
        self.assertLessEqual(check["max_grid_spacing"], 0.001000001)
        for row in check["phase_maxima"].values():
            self.assertLess(row["si"], 0)

    def test_rounding_changes_actual_evaluation(self):
        check = self.recipe(1.8, mass_decimals=1)["rounded_verification"]
        self.assertEqual(check["status"], "failed")
        self.assertFalse(check["rounding_within_tolerance"])
        self.assertNotEqual(
            check["analytical_mmol_l"]["K"], self.recipe(1.8)["analytical_mmol_l"]["K"]
        )

    def test_explicit_phase_selection_and_collapsed_range(self):
        result = plan_ratio_recipe(
            **dict(
                REQUEST,
                counted_mmol_l=11.392,
                ph_range=[6.3, 6.3],
                selected_phases=["Brushite", "Monetite"],
            )
        )
        check = result["rounded_verification"]
        self.assertEqual(check["evaluated_ph"], [6.3])
        self.assertEqual(set(check["phase_maxima"]), {"CaHPO4:2H2O", "CaHPO4"})

    def test_invalid_verification_options(self):
        for options in (
            {"ph_range": [6.32, 6.28]},
            {"ph_range": [6.4, 6.5]},
            {"ph_range": [float("nan"), 6.4]},
            {"ph_range": [-1, 6.4]},
            {"ph_range": [6.28, 6.32], "mass_decimals": True},
            {"ph_range": [6.28, 6.32], "selected_phases": ["unknown"]},
            {"ph_range": [6.28, 6.32], "selected_phases": []},
            {"selected_phases": ["Brushite"]},
        ):
            with self.subTest(options=options), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**dict(REQUEST, **options))

    def test_solver_failure_stays_incomplete(self):
        from unittest.mock import patch

        with patch(
            "flahax.ratio_verification.solve", side_effect=DeliveryError("nonconvergent", "test")
        ):
            check = self.recipe(1.8)["rounded_verification"]
        self.assertEqual(check["status"], "incomplete")
        self.assertEqual(check["error"]["code"], "nonconvergent")

    def test_interior_peak_is_checked(self):
        from dataclasses import replace
        from unittest.mock import patch
        from flahax.aqueous_model import solve

        def interior(totals, ph):
            state = solve(totals, ph)
            indices = dict(state.saturation_indices)
            indices["CaHPO4"] = 0.1 - 1000 * (ph - 6.3) ** 2
            return replace(state, saturation_indices=indices)

        with patch("flahax.ratio_verification.solve", side_effect=interior):
            check = self.recipe(1.8)["rounded_verification"]
        self.assertEqual(check["status"], "failed")
        self.assertEqual(check["phase_maxima"]["CaHPO4"]["ph"], 6.3)

    def test_missing_phase_stays_incomplete(self):
        from dataclasses import replace
        from unittest.mock import patch
        from flahax.aqueous_model import solve

        def missing(totals, ph):
            return replace(solve(totals, ph), saturation_indices={})

        with patch("flahax.ratio_verification.solve", side_effect=missing):
            check = self.recipe(1.8)["rounded_verification"]
        self.assertEqual(check["status"], "incomplete")

    def test_cli_includes_rounded_verification(self):
        import json
        import os
        from pathlib import Path
        import subprocess
        import sys

        root = Path(__file__).resolve().parents[1]
        request = dict(
            REQUEST,
            counted_mmol_l=1.8,
            ph_range=[6.28, 6.32],
            selected_phases=["Brushite", "Monetite", "Hydroxyapatite"],
        )
        result = subprocess.run(
            [sys.executable, "-m", "flahax", "ratio"],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            cwd=root,
            env=dict(os.environ, PYTHONPATH=str(root / "src")),
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["rounded_verification"]["status"], "passed")
