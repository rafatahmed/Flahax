# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.phase_allocation."""

import unittest
from flahax.phase_allocation import phase_allocation


class PhaseAllocationTests(unittest.TestCase):
    def test_phreeqc_calcite_allocation_probe(self):
        r = phase_allocation("Calcite", 0.1, 0.10003)
        self.assertAlmostEqual(r.dissolved_moles, 0)
        self.assertAlmostEqual(r.precipitated_moles, 0.00003)
