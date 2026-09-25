import math
import unittest

from flahax import InputError, gap_for, load_library, recommend
from flahax.composition import assay_conflict, assay_drift, theoretical_assay
from flahax.engine import _lstsq

TARGETS = {"N_NO3": 128, "P": 58, "K": 211, "Ca": 104, "Mg": 40, "S": 54}


class CompositionGuards(unittest.TestCase):
    def test_parseable_assays_match_their_formulas(self):
        conflicts = []
        for salt in load_library()["salts"]:
            if theoretical_assay(salt["formula"]) is None:
                continue
            reason = assay_conflict(salt)
            if reason and "placeholder" not in reason:
                conflicts.append(reason)
        self.assertEqual(conflicts, [])

    def test_total_nitrogen_is_rejected(self):
        with self.assertRaises(InputError):
            gap_for(TARGETS, {"N": 5, "Ca": 20})

    def test_negative_and_unknown_ppm_are_rejected(self):
        with self.assertRaises(InputError):
            recommend(load_library()["salts"], {"K": -1})
        with self.assertRaises(InputError):
            recommend(load_library()["salts"], {"K": 10}, {"Foo": 1})
        with self.assertRaises(InputError):
            recommend(load_library()["salts"], {"K": math.nan})

    def test_default_recipe_omits_restricted_and_carbonate_salts(self):
        result = recommend(load_library()["salts"], TARGETS, {"Ca": 20})
        names = {salt["name"] for salt in result["salts"]}
        self.assertNotIn("Sodium Nitrate", names)
        self.assertNotIn("Potassium Chloride", names)
        self.assertNotIn("Ammonium Chloride", names)
        self.assertNotIn("Calcium Carbonate", names)
        self.assertNotIn("Sodium Borate (Decahydrate) (borax)", names)
        self.assertTrue(result["feasible"])
        self.assertLess(result["maxAbsDeltaPct"], 1)

    def test_an_overshoot_does_not_admit_chloride_or_borax(self):
        formula = next(
            item for item in load_library()["formulas"] if item["name"] == "Pepper (Howard Resh)"
        )
        result = recommend(load_library()["salts"], formula["targets"], {"Ca": 20})
        names = {salt["name"] for salt in result["salts"]}
        self.assertNotIn("Potassium Chloride", names)
        self.assertNotIn("Ammonium Chloride", names)
        self.assertNotIn("Sodium Borate (Decahydrate) (borax)", names)
        self.assertIn("Sodium Molybdate (Dihydrate)", names)
        self.assertFalse(result["feasible"])
        self.assertAlmostEqual(result["maxAbsDeltaPct"], 37.4319, places=3)
        self.assertFalse(any("Potassium Chloride" in note for note in result["warnings"]))
        sulfur = next(row for row in result["rows"] if row["symbol"] == "S")
        self.assertLess(sulfur["deltaPct"], -30)

    def test_a_restricted_ion_is_admitted_only_as_the_sole_source(self):
        salts = [
            salt for salt in load_library()["salts"]
            if "Mo" not in salt["elements"] or "Na" in salt["elements"]
        ]
        result = recommend(salts, {**TARGETS, "Mo": 0.03}, {"Ca": 20})
        names = {salt["name"] for salt in result["salts"]}
        self.assertIn("Sodium Molybdate (Dihydrate)", names)
        self.assertTrue(any("only source of Mo" in note for note in result["warnings"]))
        self.assertIn("Na", {item["symbol"] for item in result["undesiredIons"]})

    def test_hydrate_formula_drift_is_reported_from_the_stored_assay(self):
        notes = [assay_drift(salt) for salt in load_library()["salts"]]
        self.assertTrue(any(note and note.startswith("Mg Nitrate") for note in notes))

    def test_the_fertilizer_list_has_no_chloride_salts(self):
        chloride = [
            salt["name"] for salt in load_library()["salts"]
            if float(salt["elements"].get("Cl") or 0) > 0
            and not str(salt["name"]).lower().startswith("test")
            and salt.get("formula") != "Input Formula Here"
        ]
        self.assertEqual(chloride, [])


class LeastSquares(unittest.TestCase):
    def test_householder_solves_a_known_system(self):
        # Columns [1, 1, 0] and [0, 1, 1], observation [1, 2, 1] -> [1, 1].
        solution = _lstsq([[1.0, 1.0, 0.0], [0.0, 1.0, 1.0]], [1.0, 2.0, 1.0])
        self.assertAlmostEqual(solution[0], 1.0, places=8)
        self.assertAlmostEqual(solution[1], 1.0, places=8)


if __name__ == "__main__":
    unittest.main()
