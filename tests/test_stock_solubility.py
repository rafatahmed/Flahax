# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Historical source values remain fixtures, not qualified dissolution limits."""

import unittest
from unittest import mock

from flahax import group_tanks, render_batch_sheet, render_report, summarize_batch
from flahax.stock_solubility import (
    SINGLE_SALT,
    SolubilityRow,
    check_stock_solubility,
    limit_at,
    load_solubility_table,
)
from tests.test_grower_outputs import PACKAGED, PACKAGED_PRODUCTS, PRODUCTS, rows, workflow

CRC = 'CRC Handbook of Chemistry and Physics, pp. 8-112 to 8-117'
TABLE = [
    dict(product=name, points=points, source=source, notes='test fixture from the draft table')
    for name, points, source in (
        ('Calcium Nitrate (ag grade)', [[20, 545.9]], 'Yara, YaraTera CALCINIT product sheet'),
        ('Boric Acid', [[10, 35.7], [20, 47.7]], CRC),
        ('Copper Sulfate (pentahydrate)', [[10, 262.3], [20, 311.0]], CRC),
        ('Iron II Sulfate (Hepahydrate)', [[10, 311.1], [20, 468.2]], CRC),
        ('Zinc Sulfate (Monohydrate)', [[10, 355.7], [20, 571.1]], CRC),
        ('Sodium Molybdate (Dihydrate)', [[10, 455.9], [20, 462.9]], CRC),
        ('Mg Nitrate', [[10, 934.4], [20, 971.1]], CRC),
        ('Potassium Sulfate', [[10, 90.6], [20, 107.5]], CRC),
        ('Magnesium Sulfate (Heptahydrate)', [[10, 551.7], [20, 659.8]], CRC),
        ('Potassium Dibasic Phosphate', [[10, 591.0], [20, 615.0]], CRC),
        ('Potassium Monobasic Phosphate', [[10, 149.1], [20, 206.9]], CRC),
    )
]
UNSOURCED = {'Mn EDTA', 'Potassium Citrate'}


def tomato(ratio, temperature):
    flow = workflow('Tomato (Howard Resh)')
    with mock.patch('flahax.grower_report.load_solubility_table', return_value=TABLE):
        return flow, summarize_batch(
            flow,
            PRODUCTS,
            title='Tomato',
            water_label='RO',
            injection_ratio=ratio,
            temperature_c=temperature,
        )


class LimitTests(unittest.TestCase):
    def test_linear_between_points_and_not_checked_outside(self):
        points = [[10, 90.6], [20, 107.5]]
        self.assertAlmostEqual(limit_at(points, 15), (90.6 + 107.5) / 2)
        self.assertEqual(limit_at(points, 10), 90.6)
        self.assertEqual(limit_at(points, 20), 107.5)
        self.assertIsNone(limit_at(points, 9.9))
        self.assertIsNone(limit_at(points, 20.1))
        self.assertEqual(limit_at([[20, 545.9]], 20), 545.9)
        self.assertIsNone(limit_at([[20, 545.9]], 25))

    def test_no_packaged_table_checks_nothing(self):
        self.assertEqual(load_solubility_table('no/such/solubility.json'), [])
        grouping = group_tanks(rows(('Potassium Sulfate', 0.5)), PRODUCTS)
        [row] = check_stock_solubility(grouping.tanks, 100, 20, table=[])
        self.assertEqual((row.status, row.limit_g_per_l, row.source), ('not_checked', None, None))


class StockSolubilityTests(unittest.TestCase):
    def test_legacy_table_does_not_claim_dissolution(self):
        flow, summary = tomato(100, 20)
        grouping = group_tanks(flow.recommendation['salts'], PRODUCTS)
        found = check_stock_solubility(grouping.tanks, 100, 20, table=TABLE)
        self.assertEqual(
            {r.product for r in found}, {p.name for t in grouping.tanks for p in t.products}
        )
        for row in found:
            self.assertIsInstance(row, SolubilityRow)
            self.assertEqual(
                row.status,
                'not_checked',
                row,
            )
            self.assertEqual(row.tank, grouping.tank_of(row.product))
        k2so4 = next(r for r in found if r.product == 'Potassium Sulfate')
        self.assertAlmostEqual(
            k2so4.stock_g_per_l,
            100
            * next(
                p.grams_per_litre
                for t in grouping.tanks
                for p in t.products
                if p.name == 'Potassium Sulfate'
            ),
        )
        self.assertEqual((k2so4.limit_g_per_l, k2so4.source), (None, CRC))
        # The summary checks the recipe it weighs (the pH plan's refit).
        self.assertFalse(summary['tanks']['solubility_checked'])
        weighed = {p['name'] for t in summary['tanks']['tanks'] for p in t['products']}
        self.assertEqual({r['product'] for r in summary['solubility']}, weighed)
        for row in summary['solubility']:
            self.assertEqual(
                row['status'],
                'not_checked',
                row,
            )
        self.assertTrue(all(r['note'] == SINGLE_SALT for r in summary['solubility']))
        self.assertFalse(any('does not dissolve' in w for w in summary['warnings']))

    def test_unqualified_cold_stock_is_not_a_proven_failure(self):
        _, summary = tomato(200, 10)
        row = next(r for r in summary['solubility'] if r['product'] == 'Potassium Sulfate')
        self.assertEqual(row['status'], 'not_checked')
        self.assertIsNone(row['limit_g_per_l'])
        self.assertGreater(row['stock_g_per_l'], 90.6)
        for render in (render_batch_sheet, render_report):
            self.assertNotIn('does not dissolve', render(summary))
            self.assertIn('not checked', render(summary))

    def test_a_block_elsewhere_is_never_downgraded(self):
        flow = workflow('Tomato (Howard Resh)')
        with (
            mock.patch('flahax.grower_report.load_solubility_table', return_value=TABLE),
            mock.patch(
                'flahax.grower_report._water_and_limits',
                return_value=(
                    {},
                    [
                        dict(
                            symbol='Na',
                            decision='exceeds_limit',
                            analyticalPpm=99.0,
                            maximumPpm=50.0,
                            balancingChangesDecision=False,
                            note='',
                        )
                    ],
                ),
            ),
        ):
            summary = summarize_batch(
                flow, PRODUCTS, title='T', water_label='RO', temperature_c=20
            )
        self.assertEqual(summary['status'], 'blocked')

    def test_a_product_without_a_record_is_not_checked_and_listed(self):
        mine = dict(
            id='my-kno3',
            name='My Potassium Nitrate',
            formula='KNO3',
            elements={'N_NO3': 13.8, 'K': 38.6},
        )
        grouping = group_tanks(
            [dict(id='my-kno3', name='My Potassium Nitrate', gramsPerLitre=0.5)], PRODUCTS + [mine]
        )
        [row] = check_stock_solubility(grouping.tanks, 100, 20, table=TABLE)
        self.assertEqual(
            (row.product, row.status, row.limit_g_per_l),
            ('My Potassium Nitrate', 'not_checked', None),
        )
        _, summary = tomato(100, 20)
        sheet = render_batch_sheet(summary)
        self.assertIn('Solubility not checked', sheet)
        missing = {r['product'] for r in summary['solubility'] if r['status'] == 'not_checked'}
        self.assertTrue(missing)
        for name in missing:
            self.assertIn(name, sheet.split('Solubility not checked', 1)[1])
        self.assertFalse(summary['tanks']['solubility_checked'])


class PackagedTableTests(unittest.TestCase):
    """Historical density-one values remain unchanged, without certifying applicability."""

    def setUp(self):
        self.table = load_solubility_table()

    def test_twenty_sourced_products_and_no_others(self):
        self.assertEqual(len(self.table), 20)
        for record in self.table:
            self.assertTrue(record['source'])
            points = record['points']
            self.assertTrue(
                all(a[0] < b[0] and a[1] <= b[1] for a, b in zip(points, points[1:])),
                record['product'],
            )
        names = {r['product'] for r in self.table}
        self.assertFalse(names & {'Mn EDTA', 'Iron EDTA', 'Potassium Citrate', 'CH - micro'})

    def test_historical_density_one_values_are_retained(self):
        records = {r['product']: r for r in self.table}
        self.assertEqual(limit_at(records['Potassium Sulfate']['points'], 20), 99.5)  # CRC 9.95 %
        self.assertAlmostEqual(
            limit_at(records['Magnesium Sulfate (Heptahydrate)']['points'], 25), 538.6
        )

    def test_historical_calcium_values_remain_unchanged(self):
        points = next(r for r in self.table if r['product'] == 'Calcium Nitrate (ag grade)')[
            'points'
        ]
        self.assertEqual([limit_at(points, t) for t in (20, 25, 40)], [545.9] * 3)
        self.assertIsNone(limit_at(points, 15))

    def test_packaged_floor_comparisons_are_inconclusive(self):
        flow = workflow('Tomato (Howard Resh)', library=PACKAGED)

        def packaged(ratio, temperature):  # the packaged table, not the test fixture
            return summarize_batch(
                flow,
                PACKAGED_PRODUCTS,
                title='Tomato',
                water_label='RO',
                injection_ratio=ratio,
                temperature_c=temperature,
            )

        summary = packaged(100, 25)
        status = {r['product']: r['status'] for r in summary['solubility']}
        self.assertEqual(status['Calcium Nitrate (ag grade)'], 'not_checked')
        self.assertTrue(
            all(s in {'screening_only', 'inconclusive', 'not_checked'} for s in status.values())
        )
        self.assertTrue(all(not r['mixture_approved'] for r in summary['solubility']))
        cold = packaged(200, 10)
        row = next(r for r in cold['solubility'] if r['product'] == 'Potassium Sulfate')
        self.assertEqual(row['status'], 'inconclusive')
        self.assertEqual(cold['status'], 'blocked')


if __name__ == '__main__':
    unittest.main()
