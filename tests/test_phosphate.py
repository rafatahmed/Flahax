import unittest

from flahax import DeliveryError, orthophosphate_speciation


class OrthophosphateSpeciationTests(unittest.TestCase):
    def test_species_obey_mass_balance_and_acid_base_order(self):
        result = orthophosphate_speciation(0.001, 7.0, 0.01)
        self.assertAlmostEqual(
            result.po4_molal + result.hpo4_molal + result.h2po4_molal + result.h3po4_molal,
            0.001,
            places=15,
        )
        self.assertGreater(result.h2po4_molal, result.hpo4_molal)
        self.assertGreater(result.hpo4_molal, result.po4_molal)

    def test_pH_moves_the_dominant_species(self):
        acidic = orthophosphate_speciation(0.001, 5.0, 0.01)
        alkaline = orthophosphate_speciation(0.001, 10.0, 0.01)
        self.assertGreater(acidic.h2po4_molal, acidic.hpo4_molal)
        self.assertGreater(alkaline.hpo4_molal, alkaline.h2po4_molal)

    def test_rejects_ionic_strength_outside_declared_davies_domain(self):
        with self.assertRaises(DeliveryError) as caught:
            orthophosphate_speciation(0.001, 7.0, 0.11)
        self.assertEqual(caught.exception.code, "unsupported_ionic_strength")


if __name__ == "__main__":
    unittest.main()
