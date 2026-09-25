import unittest
from flahax.ammonia import ammonia_speciation

class AmmoniaSpeciationTests(unittest.TestCase):
    def test_mass_balance_and_struvite_probe_ammonium(self):
        result = ammonia_speciation(.001, 8.5, .005168)
        self.assertAlmostEqual(result.ammonium_molal + result.ammonia_molal, .001, places=15)
        self.assertAlmostEqual(result.ammonium_molal, .0008575, places=5)

    def test_high_ph_increases_neutral_ammonia(self):
        self.assertGreater(ammonia_speciation(.001, 10, .01).ammonia_molal, ammonia_speciation(.001, 7, .01).ammonia_molal)
