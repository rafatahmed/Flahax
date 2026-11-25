# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Stock solubility is qualified by its temperature and scope (D5, D6, contract Q21).

A product's own solubility is not mixed-stock compatibility. A value recorded
at another temperature than the tank's is kept and used, but its temperature
is stated as unverified rather than silently accepted; quantities never change.
"""

import unittest

from flahax import VolumeLitres, load_library, plan_fertilizer_workflow, summarize_batch
from flahax.stock_solubility import check_stock_solubility
from flahax.tank_grouping import ConcentrateTank, TankProduct

LIBRARY = load_library()
SALTS = LIBRARY['salts']
TOMATO = {f['name']: f['targets'] for f in LIBRARY['formulas']}['Tomato (Howard Resh)']
FLOW = plan_fertilizer_workflow(SALTS, TOMATO, {}, 5.8, final_volume=VolumeLitres(1000))


def summary(temperature_c):
    return summarize_batch(FLOW, SALTS, title='T', water_label='RO', temperature_c=temperature_c)


def rows(result, product):
    return [r for r in result['solubility'] if r['product'] == product]


class SingleProductScopeTests(unittest.TestCase):
    def test_every_row_says_it_is_a_single_product_value_and_the_mixture_is_unverified(self):
        for row in summary(25)['solubility']:
            with self.subTest(product=row['product']):
                self.assertEqual(row['qualification']['scope'], 'single_product')
                self.assertIn('mixture', row['qualification']['unverified'])
                self.assertFalse(row['mixture_approved'])


class TemperatureQualificationTests(unittest.TestCase):
    def test_a_value_recorded_at_another_temperature_is_unverified_at_the_tank_temperature(self):
        (row,) = rows(summary(45), 'Iron EDTA')
        self.assertEqual(row['status'], 'ok')  # the quantity is kept and the check still runs
        qualification = row['qualification']
        self.assertFalse(qualification['temperature_matched'])
        self.assertEqual(qualification['source_temperature_c'], 20)
        self.assertEqual(qualification['tank_temperature_c'], 45)
        self.assertIn('temperature', qualification['unverified'])

    def test_a_value_at_the_tank_temperature_is_matched(self):
        (row,) = rows(summary(20), 'Iron EDTA')
        self.assertTrue(row['qualification']['temperature_matched'])
        self.assertNotIn('temperature', row['qualification']['unverified'])

    def test_a_table_point_that_is_not_the_tank_temperature_is_unverified(self):
        (row,) = rows(summary(45), 'Boric Acid')
        self.assertEqual(row['source_temperature_c'], 40)
        self.assertFalse(row['qualification']['temperature_matched'])
        (row,) = rows(summary(25), 'Boric Acid')
        self.assertTrue(row['qualification']['temperature_matched'])

    def test_the_report_names_the_products_and_temperatures_that_are_unverified(self):
        notes = [w for w in summary(45)['warnings'] if 'not verified at 45' in w]
        self.assertEqual(len(notes), 1)
        self.assertIn('Iron EDTA', notes[0])
        self.assertIn('20', notes[0])
        at_source = [w for w in summary(20)['warnings'] if 'not verified at 20' in w]
        self.assertEqual(len(at_source), 1)
        self.assertNotIn('Iron EDTA', at_source[0])  # matched at 20 C
        self.assertIn('source temperature not stated', at_source[0])

    def test_qualifying_the_temperature_changes_neither_doses_nor_limits(self):
        cold, warm = summary(5), summary(45)
        self.assertEqual(
            [
                (p['name'], p['gramsPerBatch'])
                for t in cold['tanks']['tanks']
                for p in t['products']
            ],
            [
                (p['name'], p['gramsPerBatch'])
                for t in warm['tanks']['tanks']
                for p in t['products']
            ],
        )

    def test_an_unstated_source_temperature_is_unverified(self):
        product = {
            'name': 'Test salt',
            'physicalProperties': {'waterSolubility': {'value': 100, 'unit': 'g/L'}},
        }
        tank = ConcentrateTank('A', (TankProduct('t', 'Test salt', 1.0, 'x'),), True, ())
        (row,) = check_stock_solubility([tank], 100, 25, products=[product])
        self.assertIsNone(row.qualification['temperature_matched'])
        self.assertIn('temperature', row.qualification['unverified'])


if __name__ == '__main__':
    unittest.main()
