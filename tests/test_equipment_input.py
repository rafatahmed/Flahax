# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Declared equipment: tank count and capacities (D3, contract Q19).

The recipe is the same however many tanks the grower has. Equipment is
reported against the required grouping, a mismatch is explained, and
equipment is never changed or assumed without saying so.
"""

import json
import tempfile
import unittest
from pathlib import Path

from flahax import VolumeLitres, load_library, plan_fertilizer_workflow, summarize_batch
from flahax.batch_cli import main
from flahax.delivery_contracts import DeliveryError

NITRIC = 'HNO3:0.65:1.39:Nitric acid 65%'
BASE = dict(water='ro', formula='Tomato (Howard Resh)', acid=[NITRIC], volume=1000, ratio=100)


LIBRARY = load_library()
SALTS = LIBRARY['salts']
TOMATO = {f['name']: f['targets'] for f in LIBRARY['formulas']}['Tomato (Howard Resh)']
FLOW = plan_fertilizer_workflow(SALTS, TOMATO, {}, 5.8, final_volume=VolumeLitres(1000))


def summary(**changes):
    """The report for one recipe without pH planning: fast, for input handling."""
    return summarize_batch(FLOW, SALTS, title='T', water_label='RO', **changes)


def doses(summary):
    return sorted(
        (p['name'], round(p['gramsPerBatch'], 9))
        for tank in summary['tanks']['tanks']
        for p in tank['products']
    )


class DeclaredTankCountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_count = {n: summary(available_tanks=n) for n in (1, 2, 3)}

    def test_the_declared_count_is_reported_as_declared(self):
        for n, summary in self.by_count.items():
            with self.subTest(tanks=n):
                tanks = summary['tanks']
                self.assertEqual(tanks['available_tanks'], n)
                self.assertTrue(tanks['available_tanks_declared'])

    def test_the_recipe_and_grouping_do_not_depend_on_the_tank_count(self):
        reference = doses(self.by_count[2])
        self.assertEqual(doses(self.by_count[1]), reference)
        self.assertEqual(doses(self.by_count[3]), reference)
        self.assertEqual(self.by_count[1]['tanks']['required_tanks'], 2)

    def test_one_tank_is_a_reported_mismatch_and_two_or_three_fit(self):
        def second_tank_notes(summary):
            return [w for w in summary['warnings'] if 'second tank' in w]

        self.assertEqual(len(second_tank_notes(self.by_count[1])), 1)
        self.assertEqual(second_tank_notes(self.by_count[2]), [])
        self.assertEqual(second_tank_notes(self.by_count[3]), [])

    def test_undeclared_equipment_is_disclosed_not_silently_assumed(self):
        tanks = summary()['tanks']
        self.assertEqual(tanks['available_tanks'], 2)
        self.assertFalse(tanks['available_tanks_declared'])


class DeclaredCapacityTests(unittest.TestCase):
    def test_capacities_that_hold_the_stock_fit(self):
        report = summary(available_tanks=2, tank_capacities_litres=[20, 20])
        fit = report['tanks']['equipment']['fit']
        self.assertEqual([row['tank'] for row in fit], ['A', 'B'])
        self.assertEqual([row['stock_litres'] for row in fit], [10.0, 10.0])
        self.assertEqual([row['capacity_litres'] for row in fit], [20.0, 20.0])
        self.assertTrue(all(row['fits'] for row in fit))
        self.assertFalse([w for w in report['warnings'] if 'cannot hold' in w])

    def test_a_tank_too_small_is_explained_and_the_recipe_is_kept(self):
        fits = summary(available_tanks=2, tank_capacities_litres=[20, 20])
        small = summary(available_tanks=2, tank_capacities_litres=[5, 20])
        fit = small['tanks']['equipment']['fit']
        self.assertEqual([row['fits'] for row in fit], [False, True])
        notes = [w for w in small['warnings'] if 'cannot hold' in w]
        self.assertEqual(len(notes), 1)
        self.assertIn('Tank A', notes[0])
        self.assertIn('10', notes[0])
        self.assertEqual(doses(small), doses(fits))
        self.assertEqual(small['tanks']['injection_ratio'], 100)

    def test_capacities_are_validated(self):
        for capacities in ([20], [20, 0], [20, -1], [20, float('nan')], [20, True]):
            with self.subTest(capacities=capacities):
                with self.assertRaises(DeliveryError) as raised:
                    summary(available_tanks=2, tank_capacities_litres=capacities)
                self.assertEqual(raised.exception.code, 'invalid_value')

    def test_capacities_without_a_count_use_their_length(self):
        tanks = summary(tank_capacities_litres=[20, 20, 20])['tanks']
        self.assertEqual(tanks['available_tanks'], 3)
        self.assertTrue(tanks['available_tanks_declared'])


class EquipmentFlagTests(unittest.TestCase):
    def test_the_command_takes_tank_count_and_capacities(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'batch'
            code = main(
                [
                    '--formula',
                    BASE['formula'],
                    '--water',
                    'ro',
                    '--acid',
                    NITRIC,
                    '--available-tanks',
                    '2',
                    '--tank-capacity',
                    '5',
                    '--tank-capacity',
                    '20',
                    '--output',
                    str(out),
                ]
            )
            self.assertEqual(code, 3)  # blocked: the 5 L tank cannot hold the stock
            summary = json.loads((out / 'summary.json').read_text())
        self.assertEqual(summary['tanks']['available_tanks'], 2)
        self.assertEqual(
            [row['fits'] for row in summary['tanks']['equipment']['fit']], [False, True]
        )


if __name__ == '__main__':
    unittest.main()
