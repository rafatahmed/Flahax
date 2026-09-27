import unittest

from flahax import (convert_catalogue_product_dose, convert_product_dose, solve_catalogue_product_doses,
                    chemistry_for_product, load_library)


class ProductConversionTests(unittest.TestCase):
    def test_every_catalogue_product_has_explicit_non_name_equilibrium_profile(self):
        for product in load_library()["salts"]:
            converted = convert_catalogue_product_dose(product, 1.0)
            self.assertIs(converted.chemistry, chemistry_for_product(product["name"]))
            self.assertGreaterEqual(converted.inert_mass_fraction, 0.0)
            self.assertTrue(converted.totals or converted.counterions or converted.ligands)

    def test_ch_micro_declares_edta_and_borax_molybdate_sodium(self):
        product = next(p for p in load_library()["salts"] if p["name"] == "CH - micro")
        result = convert_catalogue_product_dose(product, 1.0)
        self.assertAlmostEqual(result.ligands["EDTA"], sum(result.totals[k] for k in ("Fe", "Mn", "Zn", "Cu")))
        self.assertGreater(result.counterions["sodium"], 0.0)

    def test_profile_mismatch_fails_before_any_solver_can_use_label(self):
        product = next(p for p in load_library()["salts"] if p["name"] == "Urea")
        with self.assertRaises(Exception):
            convert_product_dose(product, chemistry_for_product("Iron EDTA"), 1.0)

    def test_actual_catalogue_chelate_doses_share_one_mixed_solver(self):
        result = solve_catalogue_product_doses({"Iron DTPA": .01, "Iron EDDHA": .01, "CH - micro": .01}, 6.0)
        self.assertIsNotNone(result.trace)
        self.assertGreater(result.trace.totals.dtpa, 0)
        self.assertGreater(result.trace.totals.eddha, 0)
