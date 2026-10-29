# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The packaged data is the owner catalogue Flaha Agri Tech Analysis Ver 0.0."""

import json
from pathlib import Path
import unittest

from flahax import load_library

LIBRARY_FILE = Path(__file__).resolve().parents[1] / 'src' / 'flahax' / 'data' / 'library.json'
TITLE = 'Flaha Agri Tech Analysis Ver 0.0'

# Every target of the 13 owner formulas, in catalogue order; explicit zeros included.
FORMULAS = [
    ('Cucumber (Howard Resh)', {'N_NO3': 140, 'N_NH4': 0, 'P': 50, 'K': 350, 'Ca': 200, 'Mg': 50, 'S': 150, 'Si': 0, 'Fe': 3, 'B': 0.3, 'Mn': 0.8, 'Zn': 0.1, 'Cu': 0.07, 'Mo': 0.03}),
    ('DEFAULT', {'N_NO3': 210, 'N_NH4': 0, 'P': 31, 'K': 235, 'Ca': 200, 'Mg': 49, 'S': 64, 'Si': 0, 'Fe': 2.9, 'B': 0.5, 'Mn': 0.5, 'Zn': 0.05, 'Cu': 0.02, 'Mo': 0.05}),
    ('Hoagland solution', {'N_NO3': 210, 'N_NH4': 0, 'P': 31, 'K': 235, 'Ca': 200, 'Mg': 49, 'S': 64, 'Si': 0, 'Fe': 2.9, 'B': 0.5, 'Mn': 0.5, 'Zn': 0.05, 'Cu': 0.02, 'Mo': 0.05}),
    ('Lettuce 2 (Howard Resh)', {'N_NO3': 165, 'N_NH4': 15, 'P': 50, 'K': 210, 'Ca': 190, 'Mg': 45, 'S': 113, 'Si': 0, 'Fe': 4, 'B': 0.5, 'Mn': 0.5, 'Zn': 0.1, 'Cu': 0.1, 'Mo': 0.05}),
    ('Lettuce General (Howard Resh)', {'N_NO3': 165, 'N_NH4': 15, 'P': 50, 'K': 210, 'Ca': 190, 'Mg': 45, 'S': 65, 'Si': 0, 'Fe': 4, 'B': 0.5, 'Mn': 0.5, 'Zn': 0.1, 'Cu': 0.1, 'Mo': 0.05}),
    ('Melons (Douglas Peckenpaugh)', {'N_NO3': 215, 'N_NH4': 0, 'P': 86, 'K': 343, 'Ca': 175, 'Mg': 85, 'S': 113, 'Si': 0, 'Fe': 6.8, 'B': 0.7, 'Mn': 1.97, 'Zn': 0.25, 'Cu': 0.07, 'Mo': 0.05}),
    ('Pepper (Howard Resh)', {'N_NO3': 190, 'N_NH4': 18, 'P': 40, 'K': 340, 'Ca': 170, 'Mg': 50, 'S': 360, 'Si': 0, 'Fe': 5, 'B': 0.33, 'Mn': 0.55, 'Zn': 0.33, 'Cu': 0.05, 'Mo': 0.05}),
    ('Strawberry Drip Irrigation (schundler.com)', {'N_NO3': 80, 'N_NH4': 0, 'P': 45, 'K': 100, 'Ca': 200, 'Mg': 50, 'S': 180, 'Si': 0, 'Fe': 3, 'B': 0.5, 'Mn': 0.5, 'Zn': 0.5, 'Cu': 0.05, 'Mo': 0.05}),
    ('Strawberry Fruiting (growing edge)', {'N_NO3': 128, 'N_NH4': 0, 'P': 58, 'K': 211, 'Ca': 104, 'Mg': 40, 'S': 54, 'Si': 0, 'Fe': 5, 'B': 0.7, 'Mn': 2, 'Zn': 0.25, 'Cu': 0.07, 'Mo': 0.05}),
    ('Tomato (Howard Resh)', {'N_NO3': 140, 'N_NH4': 0, 'P': 50, 'K': 352, 'Ca': 180, 'Mg': 50, 'S': 168, 'Si': 0, 'Fe': 5, 'B': 0.3, 'Mn': 0.8, 'Zn': 0.1, 'Cu': 0.07, 'Mo': 0.03}),
    ('Tomato Stage.1 - 10-14 days (Howard Resh)', {'N_NO3': 100, 'N_NH4': 0, 'P': 40, 'K': 200, 'Ca': 100, 'Mg': 20, 'S': 53, 'Si': 0, 'Fe': 3, 'B': 0.3, 'Mn': 0.8, 'Zn': 0.1, 'Cu': 0.07, 'Mo': 0.03}),
    ('Tomato Stage.2 - first cluster (Howard Resh)', {'N_NO3': 130, 'N_NH4': 0, 'P': 55, 'K': 300, 'Ca': 150, 'Mg': 33, 'S': 109, 'Si': 0, 'Fe': 3, 'B': 0.3, 'Mn': 0.8, 'Zn': 0.1, 'Cu': 0.07, 'Mo': 0.03}),
    ('Tomato Stage.3 - to plant maturity (Howard Resh)', {'N_NO3': 180, 'N_NH4': 0, 'P': 65, 'K': 400, 'Ca': 400, 'Mg': 45, 'S': 144, 'Si': 0, 'Fe': 3, 'B': 0.3, 'Mn': 0.8, 'Zn': 0.1, 'Cu': 0.07, 'Mo': 0.03}),
]

ASSAYS = {
    'Copper EDTA': {'Cu': 15},
    'Mn EDTA': {'Mn': 13},
    'Zn EDTA': {'Zn': 15},
    'Iron EDTA': {'Fe': 13},
    'Potassium Nitrate': {'N_NO3': 13, 'K': 38.2},
    'Ammonium Monobasic Phosphate': {'N_NH4': 12, 'P': 27},
    'Potassium Monobasic Phosphate': {'P': 22.7, 'K': 28.7},
    'Micro Combi Mix 1': {'Fe': 7.2, 'Cu': 0.9, 'Mn': 3.6, 'Zn': 1.2, 'Mo': 0.6},
    'Micro Combi Mix 2': {'Fe': 3.7, 'Cu': 0.2, 'Mn': 2.4, 'Zn': 1.5, 'Mo': 0.2, 'B': 1.4},
}

# product -> (g/L water, temperature in the data; None where the owner gave none)
SOLUBILITY = {
    'Copper EDTA': (400, 20),
    'Mn EDTA': (400, 20),
    'Zn EDTA': (450, 20),
    'Iron EDTA': (45, 20),
    'Micro Combi Mix 1': (45, None),
    'Micro Combi Mix 2': (45, None),
    'Potassium Nitrate': (316, 20),
    'Ammonium Monobasic Phosphate': (374, 20),
    'Potassium Monobasic Phosphate': (226, 20),
}

PH_PRODUCTS = [
    'Potassium Hydroxide (45% solution)',
    'Phosphoric Acid (75%)',
    'Nitric Acid (65% solution)',
    'Potassium Bicarbonate',
    'Potassium Carbonate',
]


class OwnerCatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load_library()
        cls.salts = {s['name']: s for s in cls.library['salts']}

    def test_counts_and_ph_products(self):
        salts = self.library['salts']
        self.assertEqual(len(salts), 29)
        reagents = [s['name'] for s in salts if s.get('role') == 'ph_reagent']
        self.assertEqual(len(reagents), 5)
        self.assertEqual(sorted(reagents), sorted(PH_PRODUCTS))

    def test_formula_names_and_all_values(self):
        formulas = self.library['formulas']
        self.assertEqual([f['name'] for f in formulas], [n for n, _ in FORMULAS])
        self.assertEqual(sum(len(t) for _, t in FORMULAS), 182)
        for formula, (name, targets) in zip(formulas, FORMULAS):
            with self.subTest(formula=name):
                self.assertEqual(formula['targets'], targets)

    def test_assays(self):
        for name, elements in ASSAYS.items():
            with self.subTest(product=name):
                self.assertEqual(self.salts[name]['elements'], elements)
        mix1 = self.salts['Micro Combi Mix 1']
        self.assertNotIn('B', mix1['elements'])
        self.assertEqual(mix1['undeclaredElements'], ['B'])

    def test_water_solubility(self):
        for name, (value, temperature) in SOLUBILITY.items():
            with self.subTest(product=name):
                found = self.salts[name]['physicalProperties']['waterSolubility']
                self.assertEqual(found['value'], value)
                self.assertEqual(found['unit'], 'g/L')
                self.assertEqual(found['temperatureC'], temperature)
        grades = self.salts['Iron EDDHA']['gradeVariants']
        self.assertEqual(len(grades), 3)
        for grade in grades:
            with self.subTest(grade=grade['name']):
                found = grade['physicalProperties']['waterSolubility']
                self.assertEqual((found['value'], found['unit'], found['temperatureC']),
                                 (30, 'g/L', 20))

    def test_every_salt_carries_the_review_stamp(self):
        for salt in self.library['salts']:
            with self.subTest(product=salt['name']):
                self.assertEqual(salt['analysisReview']['title'], TITLE)

    def test_no_gypsum_product(self):
        for salt in self.library['salts']:
            with self.subTest(product=salt['name']):
                self.assertNotIn(salt['formula'].replace('·', '.'),
                                 ('CaSO4', 'CaSO4.2H2O'))
                self.assertNotIn('gypsum', salt['name'].lower())

    def test_file_is_one_lf_json_line(self):
        raw = LIBRARY_FILE.read_bytes()
        self.assertNotIn(bytes([13]), raw)
        self.assertEqual(raw.count(bytes([10])), 1)
        self.assertTrue(raw.endswith(bytes([10])))
        json.loads(raw.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
