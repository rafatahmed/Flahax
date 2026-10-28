# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The packaged fertilizer library and its crop formulas."""

import unittest

from flahax import load_library, recommend
from flahax.composition import assay_conflict

LIBRARY = load_library()


class LibrarySuite(unittest.TestCase):
    def test_tables_match_the_curated_catalogue(self):
        self.assertEqual(len(LIBRARY["salts"]), 32)
        self.assertEqual(len(LIBRARY["waters"]), 3)
        self.assertEqual(len(LIBRARY["formulas"]), 21)
        self.assertIn("WC1", [water["name"] for water in LIBRARY["waters"]])
        # UF tomato presets retired under #202; not restored for N provenance.
        self.assertEqual(
            [f["name"] for f in LIBRARY["formulas"] if "Florida" in f["name"]],
            [],
        )

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
