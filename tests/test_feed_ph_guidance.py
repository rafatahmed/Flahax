# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Caller-selected pH is not judged against an embedded agronomic range."""

import unittest

from flahax import load_library, plan_fertilizer_workflow

LIBRARY = load_library()
TARGETS = next(f for f in LIBRARY["formulas"] if f["name"] == "Hoagland solution")["targets"]


def notes(target_ph):
    return plan_fertilizer_workflow(LIBRARY["salts"], TARGETS, {}, target_ph).recommendation[
        "warnings"
    ]


# Pre-removal UF tomato N values were stored as N_NO3 but CV216 Table 1 labels
# them total N. Presets stay retired (#202); any future re-ship must use key N.
_UF_CV216_TOTAL_N_MISLABELED_AS_N_NO3 = {
    "Tomatoes - till First Cluster (U of Florida)": 70,
    "Tomatoes - Second Cluster (U of Florida)": 80,
    "Tomatoes - Third Cluster (U of Florida)": 100,
    "Tomatoes - Fourth Cluster (U of Florida)": 120,
    "Tomatoes - to termination (U of Florida)": 150,
}


class FeedPhGuidanceTests(unittest.TestCase):
    def test_caller_ph_has_no_implicit_crop_range(self):
        for ph in (4.5, 5.5, 6.5, 7.5):
            with self.subTest(ph=ph):
                self.assertFalse(any('Target pH' in w for w in notes(ph)))

    def test_retired_presets_are_not_selectable(self):
        # Historical mislabel record: CV216 total-N column was shipped as N_NO3.
        self.assertEqual(
            sorted(_UF_CV216_TOTAL_N_MISLABELED_AS_N_NO3.values()),
            [70, 80, 100, 120, 150],
        )
        florida = [f for f in LIBRARY["formulas"] if "Florida" in f["name"]]
        self.assertEqual(florida, [])
        names = {f["name"] for f in LIBRARY["formulas"]}
        for name in _UF_CV216_TOTAL_N_MISLABELED_AS_N_NO3:
            with self.subTest(name=name):
                self.assertNotIn(name, names)


if __name__ == "__main__":
    unittest.main()
