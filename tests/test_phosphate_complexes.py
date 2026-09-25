import unittest

from flahax.phosphate_complexes import calcium_magnesium_phosphate_speciation


class CalciumMagnesiumPhosphateTests(unittest.TestCase):
    def test_reference_mixture_forms_metal_phosphate_complexes(self):
        result = calcium_magnesium_phosphate_speciation(.002, .001, .001, .001, 6.5, .00985)
        self.assertGreater(result.calcium_hpo4_molal, 0)
        self.assertGreater(result.magnesium_hpo4_molal, 0)
        self.assertGreater(result.hydroxyapatite_si, 0)
