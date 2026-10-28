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


class FeedPhGuidanceTests(unittest.TestCase):
    def test_caller_ph_has_no_implicit_crop_range(self):
        for ph in (4.5, 5.5, 6.5, 7.5):
            with self.subTest(ph=ph):
                self.assertFalse(any('Target pH' in w for w in notes(ph)))

    def test_retired_presets_are_not_selectable(self):
        self.assertFalse(any('Florida' in f['name'] for f in LIBRARY['formulas']))


if __name__ == "__main__":
    unittest.main()
