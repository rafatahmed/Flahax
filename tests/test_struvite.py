# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.struvite."""

import unittest
from flahax.struvite import struvite_saturation_index


class StruviteTests(unittest.TestCase):
    def test_phreeqc_reference_activity_product(self):
        self.assertAlmostEqual(
            struvite_saturation_index(5.027e-4, 7.918e-4, 6.845e-8), -0.30, places=2
        )
