"""Fixed-ratio recipe conservation and public command checks."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from flahax import plan_ratio_recipe
from flahax.delivery_contracts import DeliveryError

REQUEST = dict(
    cation_shares=[50, 30, 20],
    anion_shares=[5, 3, 1],
    ph=6.3,
    counted_mmol_l=30,
    volume_litres=10,
    water="demineralized",
    water_mass_kg=10,
)


class RatioRecipeTests(unittest.TestCase):
    def test_steiner_example_and_potassium_accounting(self):
        result = plan_ratio_recipe(**REQUEST)
        for actual, expected in zip(result["cation_percent"], [50, 30, 20]):
            self.assertAlmostEqual(actual, expected, places=8)
        for actual, expected in zip(result["anion_percent"], [500 / 9, 100 / 3, 100 / 9]):
            self.assertAlmostEqual(actual, expected, places=8)
        self.assertAlmostEqual(result["counted_mmol_l"], 30, places=9)
        self.assertLess(abs(result["charge_residual_mol_kg"]), 1e-10)
        potassium = sum(row["contributions_mmol_l"]["K"] for row in result["ingredients"])
        self.assertAlmostEqual(potassium, result["analytical_mmol_l"]["K"], places=10)
        koh = next(row for row in result["ingredients"] if row["formula"] == "KOH")
        self.assertAlmostEqual(koh["contributions_mmol_l"]["K"], 1.316738, places=5)
        self.assertIn("6.45", " ".join(result["qualifications"]))
        self.assertGreater(result["saturation_indices"]["CaHPO4:2H2O"], 0)

    def test_scaling_ratios_and_batch_size(self):
        a = plan_ratio_recipe(**REQUEST)
        b = plan_ratio_recipe(
            **dict(
                REQUEST,
                cation_shares=[5, 3, 2],
                anion_shares=[10, 6, 2],
                volume_litres=20,
                water_mass_kg=20,
            )
        )
        for x, y in zip(a["ingredients"], b["ingredients"]):
            self.assertAlmostEqual(y["grams"], 2 * x["grams"], places=9)

    def test_invalid_inputs(self):
        for changes in (
            {"ph": float("nan")},
            {"ph": 15},
            {"volume_litres": 0},
            {"counted_mmol_l": -1},
            {"water_mass_kg": 0},
            {"cation_shares": [0, 0, 0]},
            {"anion_shares": [5, -3, 1]},
            {"cation_shares": [True, 3, 2]},
            {"anion_shares": [1, 2]},
            {"water": "well"},
        ):
            with self.subTest(changes=changes), self.assertRaises(DeliveryError):
                plan_ratio_recipe(**dict(REQUEST, **changes))

    def test_unavailable_six_salt_allocation_is_explicit(self):
        with self.assertRaises(DeliveryError):
            plan_ratio_recipe(**dict(REQUEST, cation_shares=[0, 50, 50]))

    def test_grams_reconstruct_targets_and_independent_ph(self):
        from flahax.composition import ATOMIC, parse_formula
        from tests.test_steiner_reference import predicted_ph

        result = plan_ratio_recipe(**REQUEST)
        atoms = dict.fromkeys(("K", "Ca", "Mg", "N", "P", "S"), 0.0)
        for row in result["ingredients"]:
            parsed = parse_formula(row["formula"])["atoms"]
            mass = sum(ATOMIC[key] * value for key, value in parsed.items())
            mol = row["grams"] / mass
            for key in atoms:
                atoms[key] += mol * parsed.get(key, 0) * 1000 / 10
        for key, element in zip(("K", "Ca", "Mg", "NO3", "P", "SO4"), atoms):
            self.assertAlmostEqual(atoms[element], result["analytical_mmol_l"][key], places=9)
        equivalents = [atoms[k] * z for k, z in zip(atoms, (1, 2, 2, 1, 1, 2))]
        ph, _ = predicted_ph(equivalents)
        self.assertAlmostEqual(ph, 6.3, places=7)

    def test_explicit_water_mass_and_zero_shares(self):
        from flahax.aqueous_model import solve

        result = plan_ratio_recipe(**dict(REQUEST, water_mass_kg=9.9))
        totals = {
            key: result["analytical_mmol_l"][nutrient] * 10 / 9.9 / 1000
            for key, nutrient in zip(
                ("K+", "Ca+2", "Mg+2", "NO3-", "PO4-3", "SO4-2"),
                ("K", "Ca", "Mg", "NO3", "P", "SO4"),
            )
        }
        self.assertLess(abs(solve(totals, 6.3).charge_balance), 1e-10)
        zero = plan_ratio_recipe(
            **dict(REQUEST, cation_shares=[100, 0, 0], anion_shares=[5, 3, 0])
        )
        self.assertAlmostEqual(zero["analytical_mmol_l"]["Ca"], 0)
        self.assertAlmostEqual(zero["analytical_mmol_l"]["Mg"], 0)

    def test_cli_round_trip(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        run = subprocess.run(
            [sys.executable, "-m", "flahax", "ratio"],
            input=json.dumps(REQUEST),
            text=True,
            capture_output=True,
            env=env,
            cwd=root,
            timeout=30,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertAlmostEqual(json.loads(run.stdout)["counted_mmol_l"], 30, places=9)

    def test_cli_rejects_unknown_fields(self):
        from flahax.planning_cli import execute

        with self.assertRaises(DeliveryError):
            execute("ratio", dict(REQUEST, unknown=True))
