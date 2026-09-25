import unittest

from flahax import gap_for, load_library, recommend
from flahax.composition import assay_conflict
from flahax.engine import forward, score

SALTS = [salt for salt in load_library()["salts"] if assay_conflict(salt) is None]

# Project Test01. Pepper (Howard Resh), season 2026. Water calcium 20 ppm.
TARGETS = {
    "N_NO3": 128,
    "P": 58,
    "K": 211,
    "Ca": 104,
    "Mg": 40,
    "S": 54,
}
WATER = {"Ca": 20}


def row(result, symbol):
    return next(item for item in result["rows"] if item["symbol"] == symbol)


class PepperProof(unittest.TestCase):
    def test_gap_removes_season_water(self):
        gap = gap_for(TARGETS, WATER)
        self.assertEqual(gap["Ca"], 84)
        self.assertEqual(gap["P"], 58)

    def test_recommendation_hits_phosphorus_and_potassium(self):
        result = recommend(SALTS, TARGETS, WATER)
        for symbol in ("P", "K", "Ca", "Mg", "S", "N_NO3"):
            self.assertLess(abs(row(result, symbol)["deltaPct"]), 1, symbol)

    def test_zinc_copper_and_molybdenum_stay_in_the_combination(self):
        targets = {
            **TARGETS,
            "Fe": 5, "Mn": 0.8, "Zn": 0.1, "B": 0.3, "Cu": 0.07, "Mo": 0.03,
        }
        result = recommend(SALTS, targets, WATER)
        covered = set()
        for item in result["salts"]:
            elements = next(s for s in SALTS if s["id"] == item["id"])["elements"]
            covered.update(elements)
        for symbol in ("Zn", "Cu", "Mo"):
            self.assertIn(symbol, covered, symbol)
            self.assertLess(abs(row(result, symbol)["deltaPct"]), 1, symbol)

    def test_forced_map_and_mkp_is_the_pepper_miss(self):
        """The published run stacked both phosphorus salts. That is not the optimum."""
        def named(fragment):
            return next(salt for salt in SALTS if fragment.lower() in salt["name"].lower())

        salts = [named(name) for name in (
            "Calcium Nitrate",
            "Potassium Nitrate",
            "Potassium Monobasic",
            "Ammonium Monobasic",
            "Magnesium Sulfate",
        )]
        # Grams reconstructed from the published balance, not from the solver.
        grams = [0.605, 0.587, 0.549, 0.213, 0.406]
        achieved = forward(salts, grams, WATER)
        _loss, rows = score(achieved, TARGETS)
        phosphorus = next(item for item in rows if item["symbol"] == "P")
        self.assertGreater(phosphorus["deltaPct"], 100)

        good = recommend(SALTS, TARGETS, WATER)
        self.assertLess(abs(row(good, "P")["deltaPct"]), phosphorus["deltaPct"])


if __name__ == "__main__":
    unittest.main()
