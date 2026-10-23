# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.catalogue_chemistry."""

import unittest

from flahax import assert_catalogue_coverage, chemistry_for_product, load_library
from flahax.catalogue_chemistry import LIGAND_PROFILES


class CatalogueChemistryTests(unittest.TestCase):
    def test_every_shipped_fertilizer_has_one_explicit_chemistry_record(self):
        assert_catalogue_coverage(load_library()["salts"])

    def test_trace_blend_uses_declared_chelate_sources(self):
        record = chemistry_for_product("CH - micro")
        self.assertEqual(record.family, "edta_borax_molybdate_blend")
        self.assertIn("Fe(III)-EDTA", record.components)
        self.assertIn("sodium molybdate", record.components)

    def test_remaining_catalogue_chelate_families_have_source_profiles(self):
        self.assertGreater(LIGAND_PROFILES["DTPA"]["metal_log_beta"]["Fe+3"], 28)
        self.assertGreater(LIGAND_PROFILES["o,o-EDDHA"]["metal_log_beta"]["Fe+3"], 35)

    def test_iron_dtpa_and_eddha_do_not_invent_other_metal_products(self):
        self.assertEqual(set(LIGAND_PROFILES["DTPA"]["metal_log_beta"]), {"Fe+3"})
        self.assertEqual(set(LIGAND_PROFILES["o,o-EDDHA"]["metal_log_beta"]), {"Fe+3"})
