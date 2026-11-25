# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""One solubility qualification for the batch report and the stock-planning API
(D5, D6, contract Q21 and Q23).

The same product and the same conditions go through both paths; the qualification
fields must be identical. A value is labelled verified only where its recorded
temperature range and concentration basis support it.
"""

import unittest

from flahax import InjectionRatio, StockTank, TemperatureCelsius, VolumeLitres, plan_stocks
from flahax.stock_solubility import SOLUTION_BASIS, check_stock_solubility, qualify_single_product
from flahax.tank_grouping import ConcentrateTank, TankProduct
from tests.test_stock_planning import limits, recipe, rule

BASIS = SOLUTION_BASIS
PRODUCTS = {'calcium-nitrate': 0.5, 'phosphate': 0.25}
FIELDS = ('scope', 'verified', 'temperature_matched', 'tank_temperature_c', 'basis', 'unverified')


def report_rows(temperature_c, recorded_c=20.0):
    table = [
        dict(product=name, source='bench-validation', points=[[recorded_c, 100.0]])
        for name in PRODUCTS
    ]
    tank = ConcentrateTank(
        'A', tuple(TankProduct(n, n, g, 'test') for n, g in PRODUCTS.items()), False
    )
    rows = check_stock_solubility([tank], 100, temperature_c, table=table)
    # The table basis is the report's; the API record below states the same one.
    return {row.product: row.qualification for row in rows}


def api_plan(temperature_c, recorded_c=20.0):
    records = [
        dict(r, temperatureMinC=recorded_c, temperatureMaxC=recorded_c, basis=BASIS)
        for r in limits()
    ]
    return plan_stocks(
        recipe(),
        InjectionRatio(100),
        [StockTank('A', VolumeLitres(2)), StockTank('B', VolumeLitres(2))],
        [rule()],
        records,
        TemperatureCelsius(temperature_c),
    )


def api_qualifications(stock):
    return {q['salt_id']: q for q in stock.qualification}


class SharedFunctionTests(unittest.TestCase):
    def test_a_range_that_contains_the_tank_temperature_with_a_stated_basis_is_verified(self):
        result = qualify_single_product('ok', (10.0, 30.0), 20.0, BASIS)
        self.assertTrue(result['verified'])
        self.assertTrue(result['temperature_matched'])
        self.assertEqual(result['unverified'], ['mixture'])

    def test_a_range_that_does_not_contain_it_is_not_verified(self):
        result = qualify_single_product('ok', (10.0, 30.0), 40.0, BASIS)
        self.assertFalse(result['verified'])
        self.assertFalse(result['temperature_matched'])
        self.assertEqual(result['unverified'], ['temperature', 'mixture'])

    def test_a_missing_basis_is_not_verified_even_at_a_matching_temperature(self):
        result = qualify_single_product('ok', (10.0, 30.0), 20.0, None)
        self.assertFalse(result['verified'])
        self.assertEqual(result['unverified'], ['concentration basis', 'mixture'])

    def test_a_missing_value_is_never_verified(self):
        result = qualify_single_product('not_checked', None, 20.0, None)
        self.assertFalse(result['verified'])
        self.assertIsNone(result['temperature_matched'])
        self.assertEqual(result['unverified'], ['solubility value', 'mixture'])

    def test_an_unstated_source_temperature_is_unverified(self):
        result = qualify_single_product('ok', None, 20.0, BASIS)
        self.assertIsNone(result['temperature_matched'])
        self.assertEqual(result['unverified'], ['temperature', 'mixture'])


class ReportAndApiAgreeTests(unittest.TestCase):
    def test_the_qualification_fields_are_identical_when_the_temperature_is_covered(self):
        report, api = report_rows(20), api_qualifications(api_plan(20))
        self.assertEqual(set(report), set(api))
        for name in report:
            with self.subTest(product=name):
                self.assertEqual(
                    {k: report[name][k] for k in FIELDS}, {k: api[name][k] for k in FIELDS}
                )
                self.assertTrue(api[name]['verified'])

    def test_the_qualification_fields_are_identical_when_the_temperature_is_not_covered(self):
        report, api = report_rows(40), api_qualifications(api_plan(40))
        for name in report:
            with self.subTest(product=name):
                self.assertEqual(
                    {k: report[name][k] for k in FIELDS}, {k: api[name][k] for k in FIELDS}
                )
                self.assertFalse(api[name]['verified'])
                self.assertIn('temperature', api[name]['unverified'])

    def test_the_unsupported_temperature_keeps_the_quantities_in_both_paths(self):
        stock = api_plan(40)
        self.assertEqual(
            sorted((s.salt_id, s.concentration.value) for t in stock.tanks for s in t.salts),
            [('calcium-nitrate', 50.0), ('phosphate', 25.0)],
        )
        tank = ConcentrateTank(
            'A', tuple(TankProduct(n, n, g, 'test') for n, g in PRODUCTS.items()), False
        )
        table = [dict(product=n, source='bench', points=[[20.0, 100.0]]) for n in PRODUCTS]
        rows = check_stock_solubility([tank], 100, 40, table=table)
        self.assertEqual(
            sorted((r.product, r.stock_g_per_l) for r in rows),
            [('calcium-nitrate', 50.0), ('phosphate', 25.0)],
        )

    def test_a_limit_with_no_stated_basis_is_not_verified_in_the_api(self):
        records = [dict(r, temperatureMinC=10, temperatureMaxC=30) for r in limits()]
        stock = plan_stocks(
            recipe(),
            InjectionRatio(100),
            [StockTank('A', VolumeLitres(2)), StockTank('B', VolumeLitres(2))],
            [rule()],
            records,
            TemperatureCelsius(20),
        )
        for q in stock.qualification:
            self.assertFalse(q['verified'])
            self.assertIn('concentration basis', q['unverified'])


if __name__ == '__main__':
    unittest.main()
