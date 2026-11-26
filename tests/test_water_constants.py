# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The lab-water prompts (mix_water) and the water reader (water_input) agree on the
water keys and the molar masses they share (#323).
"""

import unittest

from flahax import mix_water, water_input
from flahax.product_conversion import MOLAR_MASS


class WaterConstantsTests(unittest.TestCase):
    def test_the_hco3_molar_mass_has_one_definition(self):
        self.assertEqual(water_input.HCO3_MOLAR_MASS, 61.0168)
        self.assertIs(mix_water.HCO3_MOLAR_MASS, water_input.HCO3_MOLAR_MASS)
        self.assertEqual(water_input.WATER_KEYS['HCO3'][1], water_input.HCO3_MOLAR_MASS)

    def test_every_water_key_the_prompts_can_produce_is_one_the_reader_accepts(self):
        produced = {key for key, *_ in mix_water.IONS.values()} | set(mix_water.MICROS)
        self.assertLessEqual(produced, set(water_input.WATER_KEYS))

    def test_the_prompts_and_the_reader_use_the_same_mass_for_each_water_key(self):
        for lab_name, (key, _, _, key_mass) in mix_water.IONS.items():
            with self.subTest(lab_name=lab_name, water_key=key):
                self.assertEqual(key_mass, water_input.WATER_KEYS[key][1])

    def test_the_element_masses_come_from_the_shared_table(self):
        self.assertEqual(mix_water.IONS['SO4'][3], MOLAR_MASS['S'])
        self.assertEqual(mix_water.IONS['PO4'][3], MOLAR_MASS['P'])
        self.assertEqual(mix_water.IONS['NH4'][3], MOLAR_MASS['N'])
        self.assertEqual(mix_water.IONS['NO3'][3], MOLAR_MASS['N'])


if __name__ == '__main__':
    unittest.main()
