# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.competition."""

import unittest
from flahax.competition import calcium_sulfate_struvite_competition


class CompetitionTests(unittest.TestCase):
    def test_phreeqc_calcium_sulfate_struvite_probe(self):
        r = calcium_sulfate_struvite_competition(5.162e-4, 5.799e-4, 4.695e-4, 7.647e-4, 5.272e-8)
        self.assertAlmostEqual(r.gypsum_si, -1.98, places=1)
        self.assertAlmostEqual(r.struvite_si, -0.46, places=2)
