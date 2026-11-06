# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Stock solubility from measured data: catalogue value first, historical table second."""

import unittest

from flahax import group_tanks, render_batch_sheet, render_report, summarize_batch
from flahax.delivery_contracts import DeliveryError
from flahax.stock_solubility import (
    NO_DATA,
    SINGLE_SALT,
    SOLUTION_BASIS,
    SolubilityRow,
    check_stock_solubility,
    exceeds_message,
    load_solubility_table,
)
from tests.test_grower_outputs import PACKAGED, PACKAGED_PRODUCTS, workflow

BY_NAME = {p['name']: p for p in PACKAGED_PRODUCTS}
VOLUME_UNSPECIFIED = 'g/L (volume basis unspecified by source)'


def packaged_rows(*pairs):
    return [dict(id=BY_NAME[n]['id'], name=n, gramsPerLitre=g) for n, g in pairs]


def check(name, dose, *, ratio=100, temperature=25, **kwargs):
    grouping = group_tanks(packaged_rows((name, dose)), PACKAGED_PRODUCTS)
    kwargs.setdefault('products', PACKAGED_PRODUCTS)
    [row] = check_stock_solubility(grouping.tanks, ratio, temperature, **kwargs)
    return row


def own_record(**water_solubility):
    return dict(
        BY_NAME['Potassium Nitrate'], physicalProperties=dict(waterSolubility=water_solubility)
    )


class CatalogueValueTests(unittest.TestCase):
    """The packaged catalogue's measured values, in their own basis (G16-G18)."""

    def test_edta_chelates_are_compared_with_their_20c_values_at_a_25c_tank(self):
        for name, limit in (('Mn EDTA', 400), ('Iron EDTA', 45)):
            with self.subTest(product=name):
                row = check(name, 0.3)  # 30 g/L of stock
                self.assertIsInstance(row, SolubilityRow)
                self.assertEqual((row.status, row.limit_g_per_l), ('ok', limit))
                self.assertAlmostEqual(row.stock_g_per_l, 30.0)
                self.assertEqual(row.basis, VOLUME_UNSPECIFIED)
                self.assertEqual((row.source_temperature_c, row.tank_temperature_c), (20, 25))
                self.assertIn('Flaha Agri Tech', row.source)

    def test_potassium_nitrate_uses_the_water_basis_and_says_so(self):
        row = check('Potassium Nitrate', 1.0)
        self.assertEqual((row.status, row.limit_g_per_l), ('ok', 316))
        self.assertEqual(row.basis, 'g product/L water')

    def test_a_stock_above_the_value_exceeds(self):
        row = check('Potassium Nitrate', 3.2)  # 320 g/L against 316
        self.assertEqual((row.status, row.reason), ('exceeds', 'above_single_product_limit'))
        message = exceeds_message(row, 25)
        for text in ('320', '316', 'g product/L water', '20 °C source', 'tank at 25 °C'):
            self.assertIn(text, message)
        self.assertIn('mixture solubility is not established', message)

    def test_a_source_without_a_temperature_is_still_compared(self):
        row = check('Micro Combi Mix 2', 0.3)
        self.assertEqual((row.status, row.limit_g_per_l), ('ok', 45))
        self.assertIsNone(row.source_temperature_c)
        row = check('Micro Combi Mix 2', 0.6)
        self.assertIn('source temperature not stated', exceeds_message(row, 25))

    def test_a_product_with_no_data_is_not_checked_never_ok(self):
        row = check('Iron DTPA', 0.2)
        self.assertEqual((row.status, row.limit_g_per_l, row.source), ('not_checked', None, None))
        self.assertEqual(row.reason, NO_DATA)

    def test_the_catalogue_value_wins_over_the_historical_table(self):
        table = [dict(product='Potassium Nitrate', points=[[20, 100]], source='table')]
        row = check('Potassium Nitrate', 2.0, table=table)  # 200 g/L
        self.assertEqual((row.status, row.limit_g_per_l), ('ok', 316))

    def test_grades_do_not_select_a_value(self):
        row = check('Potassium Nitrate', 1.0, product_grades={'Potassium Nitrate': 'G1'})
        self.assertEqual((row.limit_g_per_l, row.qualification), (316, {}))
        with self.assertRaises(DeliveryError):
            check('Potassium Nitrate', 1.0, product_grades=['G1'])


class ConversionAndFallbackTests(unittest.TestCase):
    def test_an_unknown_unit_is_not_checked_and_says_why(self):
        own = own_record(value=36, unit='g/100 g water', basis='g/100 g water', temperatureC=20)
        row = check('Potassium Nitrate', 1.0, products=[own], table=[])
        self.assertEqual(row.status, 'not_checked')
        self.assertTrue(row.reason.startswith(NO_DATA))
        self.assertIn('unsupported solubility unit', row.reason)

    def test_unusable_catalogue_values_fall_back_to_the_table_then_to_none(self):
        for bad in (
            dict(value=-1, unit='g/L', basis='g product/L water', temperatureC=20),
            dict(value=True, unit='g/L', basis='g product/L water', temperatureC=20),
            dict(value=5, unit='mol/L', basis='x', temperatureC=20),
        ):
            with self.subTest(bad=bad):
                row = check('Potassium Nitrate', 1.0, products=[own_record(**bad)], table=[])
                self.assertEqual(row.status, 'not_checked')
                table = [dict(product='Potassium Nitrate', points=[[25, 200]], source='table')]
                row = check('Potassium Nitrate', 1.0, products=[own_record(**bad)], table=table)
                self.assertEqual((row.status, row.limit_g_per_l), ('ok', 200))

    def test_the_table_uses_the_nearest_point_without_interpolation(self):
        table = [dict(product='Potassium Nitrate', points=[[10, 90], [20, 110]], source='table')]
        for temperature, limit in ((14, 90), (15, 90), (16, 110), (35, 110), (0, 90)):
            with self.subTest(temperature=temperature):
                row = check(
                    'Potassium Nitrate', 1.0, temperature=temperature, products=None, table=table
                )
                self.assertEqual(row.limit_g_per_l, limit)
                self.assertEqual(row.basis, SOLUTION_BASIS)
                self.assertEqual(row.source, 'table')
                self.assertEqual(row.tank_temperature_c, temperature)

    def test_the_historical_table_is_unchanged_data(self):
        table = load_solubility_table()
        self.assertEqual(len(table), 20)
        self.assertTrue(all(set(r) <= {'product', 'points', 'source', 'notes'} for r in table))
        self.assertEqual(load_solubility_table('no/such/solubility.json'), [])


class BatchSolubilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flow = workflow('Tomato (Howard Resh)', library=PACKAGED)

    def summary(self, ratio=100, temperature=25):
        return summarize_batch(
            self.flow,
            PACKAGED_PRODUCTS,
            title='Tomato',
            water_label='RO',
            injection_ratio=ratio,
            temperature_c=temperature,
        )

    def test_rows_carry_basis_temperatures_and_the_single_product_note(self):
        summary = self.summary()
        self.assertTrue(summary['solubility'])
        for row in summary['solubility']:
            self.assertEqual(row['note'], SINGLE_SALT)
            self.assertIn(row['status'], {'ok', 'exceeds', 'not_checked'})
            self.assertEqual(row['tank_temperature_c'], 25)
            self.assertFalse(row['mixture_approved'])
        self.assertEqual(SINGLE_SALT, 'single-product check; the mixed tank is not assessed')

    def test_a_stock_far_above_a_value_blocks_with_the_exceedance_stated(self):
        summary = self.summary(ratio=2000)
        self.assertEqual(summary['status'], 'blocked')
        self.assertTrue(
            any('exceeds the recorded single-product limit' in w for w in summary['warnings'])
        )
        self.assertTrue(any(r['status'] == 'exceeds' for r in summary['solubility']))

    def test_unchecked_products_are_listed_on_the_sheet_and_the_report(self):
        summary = self.summary()
        missing = {r['product'] for r in summary['solubility'] if r['status'] == 'not_checked'}
        sheet, report = render_batch_sheet(summary), render_report(summary)
        if missing:
            self.assertIn('Solubility not checked (no solubility data)', sheet)
            for name in missing:
                self.assertIn(name, sheet.split('Solubility not checked', 1)[1])
        for page in (sheet, report):
            self.assertNotIn('conditional', page)
            self.assertNotIn('screening', page.lower().replace('precipitation screen', ''))
        self.assertIn('single-product limit', report)
        self.assertIn('°C source', report)


if __name__ == '__main__':
    unittest.main()
