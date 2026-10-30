# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.product_conversion."""

import unittest

from flahax import (
    convert_catalogue_product_dose,
    convert_product_dose,
    solve_catalogue_product_doses,
    chemistry_for_product,
    load_library,
)
from tests.catalogue_history import historical_catalogue


class ProductConversionTests(unittest.TestCase):
    def test_every_catalogue_product_has_explicit_non_name_equilibrium_profile(self):
        for product in load_library()["salts"]:
            converted = convert_catalogue_product_dose(product, 1.0)
            self.assertIs(converted.chemistry, chemistry_for_product(product["name"]))
            self.assertGreaterEqual(converted.inert_mass_fraction, 0.0)
            self.assertTrue(converted.totals or converted.counterions or converted.ligands)

    def test_ch_micro_declares_edta_and_borax_molybdate_sodium(self):
        self.enterContext(historical_catalogue())
        product = next(p for p in load_library()["salts"] if p["name"] == "CH - micro")
        result = convert_catalogue_product_dose(product, 1.0)
        self.assertAlmostEqual(
            result.ligands["EDTA"], sum(result.totals[k] for k in ("Fe", "Mn", "Zn", "Cu"))
        )
        self.assertGreater(result.counterions["sodium"], 0.0)

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_chelate_sodium_counterions(self):
        # D2: sodium counterions per formula unit, in chemistry totals only.
        self.enterContext(historical_catalogue())
        library = {p["name"]: p for p in load_library()["salts"]}

        def convert(name):
            return convert_catalogue_product_dose(library[name], 1.0)

        fe = convert("Iron EDTA")
        self.assertAlmostEqual(fe.counterions["sodium"], fe.totals["Fe"], places=15)
        for name, metal in (("Zn EDTA", "Zn"), ("Mn EDTA", "Mn"), ("Copper EDTA", "Cu")):
            r = convert(name)
            self.assertAlmostEqual(
                r.counterions["sodium"], 2 * r.totals[metal], places=15, msg=name
            )
        dtpa = convert("Iron DTPA")
        self.assertAlmostEqual(dtpa.counterions["sodium"], 2 * dtpa.totals["Fe"], places=15)
        eddha = convert("Iron EDDHA")
        self.assertAlmostEqual(eddha.counterions["sodium"], eddha.totals["Fe"], places=15)
        micro = convert("CH - micro")
        t = micro.totals
        expected = (
            t["Fe"] + 2 * (t["Mn"] + t["Zn"] + t["Cu"]) + 0.5 * t["boron"] + 2 * t["molybdate"]
        )
        self.assertAlmostEqual(micro.counterions["sodium"], expected, places=15)
        for name in ("Iron EDTA", "Zn EDTA", "Mn EDTA", "Copper EDTA", "Iron DTPA", "Iron EDDHA"):
            self.assertNotIn("Na", library[name]["elements"], name)  # never added to elements
            self.assertIn("Na+", chemistry_for_product(name).components, name)
        self.assertEqual(chemistry_for_product("Iron EDTA").components, ("Na+", "Fe(III)-EDTA"))
        self.assertEqual(
            chemistry_for_product("Sodium Borate (Decahydrate) (borax)").components,
            ("Na+", "B(OH)4-", "B(OH)3"),
        )

    def test_borax_equilibrium_totals_unchanged(self):
        from flahax.product_conversion import catalogue_dose_totals

        totals = catalogue_dose_totals({"Sodium Borate (Decahydrate) (borax)": 1.0})
        self.assertEqual(set(totals), {"Na+", "H3BO3"})
        self.assertAlmostEqual(totals["H3BO3"], 1.0 * 11.34 / 100 / 10.81, places=15)
        self.assertAlmostEqual(totals["Na+"], 1.0 * 12.06 / 100 / 22.989769, places=15)

    def test_profile_mismatch_fails_before_any_solver_can_use_label(self):
        product = next(p for p in load_library()["salts"] if p["name"] == "Urea")
        with self.assertRaises(Exception):
            convert_product_dose(product, chemistry_for_product("Iron EDTA"), 1.0)

    def test_actual_catalogue_chelate_doses_share_one_mixed_solver(self):
        self.enterContext(historical_catalogue())
        result = solve_catalogue_product_doses(
            {"Iron DTPA": 0.01, "Iron EDDHA": 0.01, "CH - micro": 0.01}, 6.0
        )
        self.assertIsNotNone(result.trace)
        self.assertGreater(result.trace.totals.dtpa, 0)
        self.assertGreater(result.trace.totals.eddha, 0)
