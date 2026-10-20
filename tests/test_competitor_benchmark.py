"""#40 competitor harness: the parts that run without the competitor packages."""
import json
import unittest
from pathlib import Path

from benchmarks.competitors.chemistry_track import reference_input, replay_difference
from benchmarks.competitors.ec_track import MACRO, STANDARDS, inputs
from benchmarks.competitors.formulation_track import CL_LIMIT, incidental

ROOT = Path(__file__).resolve().parents[1]


class IupacStandardTests(unittest.TestCase):
    def test_table_1_matches_the_table_2_polynomial(self):
        # Pratt et al. (2001) Eq. 5 with the Table 2 parameters (ITS-90) reproduces the
        # Table 1 values at 25 C: an internal check of the transcription.
        table2 = {0.01: (7.72921e-2, 2.30846e-3, 1.07715e-5, -5.84094e-8),
                  0.1: (0.711685, 2.09002e-2, 8.99144e-5, -5.07124e-7),
                  1.0: (6.34882, 0.167913, 6.00781e-4, -3.83702e-6)}
        data = json.loads(STANDARDS.read_text())
        self.assertEqual(data["temperature_c"], 25.0)
        for row in data["kcl"]:
            a, b, c, d = table2[row["molality"]]
            t = data["temperature_c"]
            kappa = 1e4 * (a + b * t + c * t * t + d * t ** 3)  # S/m to uS/cm
            self.assertLess(abs(kappa - row["kappa"]), row["expanded_uncertainty"], row)


class ChemistryReplayTests(unittest.TestCase):
    def test_residuals_are_skipped_and_logs_compare_absolutely(self):
        stored = {"pH": 6.0, "charge": 1e-18, "pct_err": 1e-14, "si_Gypsum": 0.0,
                  "m_Ca+2": 1e-3, "m_tiny": 1e-25}
        live = {"pH": 6.0 + 2e-9, "charge": -5e-18, "pct_err": -3e-14, "si_Gypsum": 4e-15,
                "m_Ca+2": 1e-3 * (1 + 3e-12), "m_tiny": 9e-25}
        self.assertAlmostEqual(replay_difference(stored, live), 2e-9, delta=1e-15)

    def test_acid_target_fixtures_replay_their_target_input(self):
        folder = ROOT / "tests/fixtures/phreeqc/products/mixed_target_ph_nitric"
        data = json.loads((folder / "expected.json").read_text())
        self.assertEqual(reference_input(folder, data).name, "mixed_target_ph_nitric_target.pqi")
        folder = ROOT / "tests/fixtures/phreeqc/phases/gypsum"
        self.assertEqual(reference_input(folder, json.loads((folder / "expected.json").read_text())).name,
                         "gypsum.pqi")


class EcInputTests(unittest.TestCase):
    def test_every_tool_gets_the_same_macronutrient_amounts(self):
        totals = {"K+": .006, "NO3-": .01, "PO4-3": .001, "Fe+3": 2e-5, "Edta-4": 2e-5}
        macro, ions, elements = inputs(totals)
        self.assertEqual(macro, {"K+": .006, "NO3-": .01, "PO4-3": .001})
        self.assertEqual(ions, {"K+": .006, "NO3-": .01, "H2PO4-": .001})
        self.assertEqual(elements, {"K": .006, "N(5)": .01, "P": .001})
        self.assertEqual(len({v[0] for v in MACRO.values()}), len(MACRO))


class IncidentalLimitTests(unittest.TestCase):
    def test_limits_apply_only_to_untargeted_ions(self):
        salts = [{"id": "kcl", "elements": {"K": 52.4, "Cl": 47.6}}]
        recipe = {"salts": [{"id": "kcl", "gramsPerLitre": .3}]}
        out = incidental(salts, recipe, {"K": 157.2, "N_NO3": 100.}, {})
        self.assertAlmostEqual(out["Cl"], 142.8)
        self.assertGreater(out["Cl"], CL_LIMIT)
        self.assertFalse(out["within_limits"])
        self.assertEqual(incidental(salts, recipe, {"K": 157.2, "Cl": 142.8}, {})["Cl"], 0.)


if __name__ == "__main__":
    unittest.main()
