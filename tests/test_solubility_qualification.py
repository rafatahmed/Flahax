# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Exact arithmetic witnesses and adversarial source-qualification controls."""

from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
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


def record(kind='limit'):
    return dict(
        product='X',
        source='synthetic exact arithmetic witness',
        points=[[10, 400], [20, 500]],
        qualification=dict(
            kind=kind,
            basis='g_product_per_l_solution',
            reviewed=True,
            review_id='synthetic-only',
            grade_id='synthetic-grade',
        ),
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


class QualificationTests(unittest.TestCase):
    def test_limits_require_grade_and_review(self):
        self.assertEqual(check().reason, 'grade_not_matched')
        for dose, status in [(4, 'ok'), (5, 'ok'), (6, 'exceeds')]:
            row = check(dose=dose, product_grades={'X': 'synthetic-grade'})
            self.assertEqual(row.status, status)
            self.assertEqual(row.limit_g_per_l, 500)
            self.assertIsNone(row.screening_g_per_l)
            self.assertFalse(row.mixture_approved)
            if status == 'exceeds':
                self.assertIn('single-product limit', exceeds_message(row, 20))
            else:
                with self.assertRaises(DeliveryError):
                    exceeds_message(row, 20)
        for key, value, reason in [
            ('reviewed', False, 'unreviewed_source'),
            ('review_id', ' ', 'unreviewed_source'),
            ('review_id', 5, 'unreviewed_source'),
            ('grade_id', '', 'grade_not_matched'),
            ('kind', 'unknown', 'unknown_qualification'),
            ('kind', [], 'unknown_qualification'),
            ('basis', 'g_per_l_water', 'missing_or_unsupported_basis'),
        ]:
            r = record()
            r['qualification'][key] = value
            self.assertEqual(check(r).reason, reason)
        r = record()
        del r['qualification']
        self.assertEqual(check(r).reason, 'missing_or_unsupported_basis')

    def test_floor_never_proves_failure_or_mixture_success(self):
        for kind in ('lower_bound', 'assumed_density_floor'):
            for dose, status in [
                (4, 'screening_only'),
                (5, 'screening_only'),
                (6, 'inconclusive'),
            ]:
                row = check(record(kind), dose=dose, product_grades={'X': 'synthetic-grade'})
                self.assertEqual(row.status, status)
                self.assertIsNone(row.limit_g_per_l)
                self.assertEqual(row.screening_g_per_l, 500)
                self.assertFalse(row.mixture_approved)
                with self.assertRaises(DeliveryError):
                    exceeds_message(row, 20)

    def test_historical_false_failure_and_temperature_extension(self):
        for temp, status in [(20, 'inconclusive'), (25, 'not_checked'), (40, 'not_checked')]:
            row = check_stock_solubility(tanks(name='Calcium Nitrate (ag grade)'), 100, temp)[0]
            self.assertEqual(row.status, status)
            self.assertIsNone(row.limit_g_per_l)
            if temp == 20:
                self.assertEqual(row.screening_g_per_l, 545.9)
                self.assertEqual(row.stock_g_per_l, 600)

    def test_interpolation_requires_review_and_never_extrapolates(self):
        r = record('assumed_density_floor')
        self.assertEqual(check(r, 15).reason, 'interpolation_not_qualified')
        r['qualification'].update(interpolation='linear', interpolation_review_id='synthetic')
        self.assertEqual(check(r, 15).screening_g_per_l, 450)
        self.assertEqual(check(r, 21).reason, 'temperature_outside_source')
        r['qualification']['source_temperatures_c'] = [15]
        self.assertEqual(check(r, 20).reason, 'temperature_not_qualified')
        r['qualification']['source_temperatures_c'] = 15
        with self.assertRaises(DeliveryError):
            check(r)
        r['qualification']['source_temperatures_c'] = [float('inf')]
        with self.assertRaises(DeliveryError):
            check(r)
        del r['qualification']['source_temperatures_c']
        for invalid in (None, 5, ' '):
            r['qualification']['interpolation_review_id'] = invalid
            self.assertEqual(check(r, 15).reason, 'interpolation_not_qualified')
        self.assertIsNone(limit_at([], 20))

    def test_invalid_records_and_inputs_fail_explicitly(self):
        for points in (None, [1], [[1]], [[10, -1]], [[10, 1], [10, 2]], [[float('inf'), 1]]):
            with self.subTest(points=points), self.assertRaises(DeliveryError):
                limit_at(points, 20)
        for table in ({}, [None], [{'product': 'X'}], [record(), record()]):
            with self.subTest(table=table), self.assertRaises(DeliveryError):
                check_stock_solubility(tanks(), 100, 20, table=table)
        for ratio, temp, dose, grades in [
            (0, 20, 1, None),
            (100, float('inf'), 1, None),
            (100, 20, -1, None),
            (100, 20, 1e308, None),
            (100, 20, 1, []),
        ]:
            with self.assertRaises(DeliveryError):
                check_stock_solubility(tanks(dose), ratio, temp, product_grades=grades)
        self.assertEqual(
            check_stock_solubility(tanks(), 100, 20, table=[])[0].reason, 'missing_source'
        )

    def test_custom_json_does_not_inherit_historical_qualification(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'table.json'
            r = deepcopy(record())
            del r['qualification']
            path.write_text(json.dumps([r]), encoding='utf-8')
            self.assertNotIn('qualification', load_solubility_table(path)[0])
        self.assertEqual(load_solubility_table('missing.json'), [])
