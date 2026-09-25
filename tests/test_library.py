import unittest

from flahax import load_library, recommend
from flahax.composition import assay_conflict

LIBRARY = load_library()


class LibrarySuite(unittest.TestCase):
    def test_tables_match_the_database_export(self):
        self.assertEqual(len(LIBRARY["salts"]), 28)
        self.assertEqual(len(LIBRARY["waters"]), 3)
        self.assertEqual(len(LIBRARY["formulas"]), 26)
        self.assertIn("WC1", [water["name"] for water in LIBRARY["waters"]])

    def test_each_crop_formula_is_solved_from_the_whole_library(self):
        salts = [salt for salt in LIBRARY["salts"] if assay_conflict(salt) is None]
        known = {salt["id"] for salt in salts}
        misses = []
        for formula in LIBRARY["formulas"]:
            result = recommend(salts, formula["targets"], formula["water"])
            if not result["salts"]:
                misses.append(f"{formula['name']}: no salts")
                continue
            if any(salt_id not in known for salt_id in result["saltIds"]):
                misses.append(f"{formula['name']}: unknown salt")
            if result["loss"] != result["loss"]:
                misses.append(f"{formula['name']}: loss is not a number")
        self.assertEqual(misses, [])


if __name__ == "__main__":
    unittest.main()
