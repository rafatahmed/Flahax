import unittest
from flahax.struvite import struvite_saturation_index

class StruviteTests(unittest.TestCase):
    def test_phreeqc_reference_activity_product(self):
        self.assertAlmostEqual(struvite_saturation_index(5.027e-4, 7.918e-4, 6.845e-8), -0.30, places=2)
