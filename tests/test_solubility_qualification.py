# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Exact arithmetic witnesses and adversarial source-qualification controls."""

from fractions import Fraction
from types import SimpleNamespace
import unittest

from flahax.delivery_contracts import DeliveryError
from flahax.stock_solubility import (
    check_stock_solubility,
    exceeds_message,
    limit_at,
    load_solubility_table,
    source_concentration_g_per_l as convert,
)


def tanks(dose=6, name='X'):
    return [SimpleNamespace(name='A', products=[SimpleNamespace(name=name, grams_per_litre=dose)])]


def record():
    return dict(
        product='X',
        source='synthetic exact arithmetic witness',
        points=[[10, 400], [20, 500]],
    )


def check(r=None, temperature=20, dose=6, **kwargs):
    return check_stock_solubility(
        tanks(dose), 100, temperature, table=[record() if r is None else r], **kwargs
    )[0]


class ConversionTests(unittest.TestCase):
    def test_independent_rational_mass_balance(self):
        # Source mass divided by final volume; densities here are synthetic inputs.
        cases = [
            (25, 'mass_percent', {}, Fraction(300)),
            (25, 'g_per_100g_water', {}, Fraction(240)),
            (
                1200,
                'g_per_l_water',
                {'water_density_g_per_ml': 0.9982},
                Fraction(1200) * 1200 / (1200 + Fraction(9982, 10)),
            ),
        ]
        for value, basis, extra, expected in cases:
            with self.subTest(basis=basis):
                actual = convert(value, basis, solution_density_g_per_ml=1.2, **extra)
                self.assertAlmostEqual(actual, float(expected), places=12)
        self.assertEqual(convert(50, 'g_per_l_solution', product_to_solute_mass_ratio=2), 100)
        self.assertEqual(
            convert(
                25, 'mass_percent', solution_density_g_per_ml=1.2, product_to_solute_mass_ratio=2
            ),
            600,
        )
        self.assertEqual(convert(0, 'mass_percent', solution_density_g_per_ml=1), 0)

    def test_invalid_and_missing_conversions(self):
        for value, basis, kw in [
            (-1, 'g_per_l_solution', {}),
            (True, 'g_per_l_solution', {}),
            (float('nan'), 'g_per_l_solution', {}),
            ('2', 'g_per_l_solution', {}),
            (25, 'mass_percent', {}),
            (101, 'mass_percent', {'solution_density_g_per_ml': 1}),
            (1, 'g_per_l_water', {'solution_density_g_per_ml': 1}),
            (1, 'unknown', {'solution_density_g_per_ml': 1}),
            (1, 'mass_percent', {'solution_density_g_per_ml': 0}),
            (1, 'g_per_l_solution', {'product_to_solute_mass_ratio': -1}),
            (1e308, 'g_per_l_solution', {'product_to_solute_mass_ratio': 2}),
            (
                1,
                'g_per_l_water',
                {'solution_density_g_per_ml': 1, 'water_density_g_per_ml': 1e308},
            ),
        ]:
            with self.subTest(value=value, basis=basis, kw=kw), self.assertRaises(DeliveryError):
                convert(value, basis, **kw)


class SourceTests(unittest.TestCase):
    def test_a_table_value_is_compared_as_recorded_at_the_nearest_point(self):
        row = check(temperature=20, dose=4.9)  # 490 g/L against 500
        self.assertEqual(
            (row.status, row.limit_g_per_l, row.source_temperature_c), ('ok', 500, 20)
        )
        row = check(temperature=20, dose=5.1)
        self.assertEqual((row.status, row.limit_g_per_l), ('exceeds', 500))
        self.assertIn('510', exceeds_message(row, 20))
        # 15 C lies between the points: no blending, the lower one on a tie.
        row = check(temperature=15, dose=3.9)
        self.assertEqual((row.limit_g_per_l, row.source_temperature_c), (400, 10))

    def test_the_historical_calcium_value_is_the_same_at_every_recorded_temperature(self):
        points = next(
            r for r in load_solubility_table() if r['product'] == 'Calcium Nitrate (ag grade)'
        )['points']
        self.assertEqual([limit_at(points, t) for t in (20, 25, 40)], [545.9] * 3)
        self.assertIsNone(limit_at(points, 15))
        for temperature, nearest in ((15, 20), (20, 20), (25, 20), (40, 40)):
            row = check_stock_solubility(
                tanks(name='Calcium Nitrate (ag grade)'), 100, temperature
            )[0]
            self.assertEqual((row.limit_g_per_l, row.source_temperature_c), (545.9, nearest))

    def test_interpolation_helper_never_extrapolates(self):
        points = [[10, 400], [20, 500]]
        self.assertEqual(limit_at(points, 15), 450)
        self.assertIsNone(limit_at(points, 9.9))
        self.assertIsNone(limit_at(points, 20.1))

    def test_a_product_without_a_record_has_no_solubility_data(self):
        self.assertEqual(
            check_stock_solubility(tanks(), 100, 20, table=[])[0].status, 'not_checked'
        )
        self.assertEqual(
            check_stock_solubility(tanks(), 100, 20, table=[])[0].reason, 'no solubility data'
        )

    def test_invalid_records_and_inputs_fail_explicitly(self):
        for points in ([], [[1]], [[1, -2]], [[1, 2], [1, 3]], 'x', [[True, 2]]):
            table = [dict(record(), points=points)]
            with self.subTest(points=points), self.assertRaises(DeliveryError):
                check_stock_solubility(tanks(), 100, 20, table=table)
        with self.assertRaises(DeliveryError):
            limit_at('x', 20)
        for table in ('x', [dict(record(), source=' ')], [record(), record()], [None]):
            with self.subTest(table=table), self.assertRaises(DeliveryError):
                check_stock_solubility(tanks(), 100, 20, table=table)
        for dose, ratio, temp in (
            (-1, 100, 20),
            (6, 0, 20),
            (6, 100, float('nan')),
            (True, 100, 20),
        ):
            with self.subTest(dose=dose, ratio=ratio, temp=temp), self.assertRaises(DeliveryError):
                check_stock_solubility(tanks(dose), ratio, temp, table=[record()])
        with self.assertRaises(DeliveryError):
            exceeds_message(check(dose=1), 20)


if __name__ == '__main__':
    unittest.main()
