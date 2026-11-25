# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The equipment check the batch hands to the workflow, and its input guards (D3, D4)."""

import argparse
import unittest

from flahax import VolumeLitres, load_library, plan_fertilizer_workflow
from flahax.batch_cli import int_at_least
from flahax.delivery_contracts import DeliveryError
from flahax.grower_report import EquipmentCheck, declared_tanks

LIBRARY = load_library()
SALTS = LIBRARY['salts']
TOMATO = {f['name']: f['targets'] for f in LIBRARY['formulas']}['Tomato (Howard Resh)']
FLOW = plan_fertilizer_workflow(SALTS, TOMATO, {}, 5.8, final_volume=VolumeLitres(1000))


def check(**changes):
    options = dict(
        products=SALTS,
        rules=(),
        injection_ratio=10,
        temperature_c=25,
        available_tanks=2,
        tank_capacities_litres=None,
        batch_litres=1000,
    )
    return EquipmentCheck(**(options | changes))(FLOW)


class EquipmentCheckTests(unittest.TestCase):
    def test_a_recipe_that_fits_has_no_problem(self):
        self.assertIsNone(check())

    def test_too_few_tanks(self):
        self.assertEqual(check(available_tanks=1)['error_code'], 'too_many_tanks')

    def test_a_tank_too_small_for_its_stock(self):
        problem = check(tank_capacities_litres=[1, 500])
        self.assertEqual(problem['error_code'], 'tank_too_small')
        self.assertIn('Tank A', problem['message'])

    def test_tanks_that_all_hold_their_stock_have_no_problem(self):
        self.assertIsNone(check(tank_capacities_litres=[500, 500]))

    def test_the_second_tank_can_be_the_one_too_small(self):
        problem = check(tank_capacities_litres=[500, 1])
        self.assertEqual(problem['error_code'], 'tank_too_small')
        self.assertIn('Tank B', problem['message'])

    def test_a_stock_above_its_recorded_solubility(self):
        self.assertEqual(check(injection_ratio=1000)['error_code'], 'solubility_exceeded')

    def test_a_recipe_product_that_was_not_supplied_is_reported_not_raised(self):
        self.assertEqual(check(products=[])['error_code'], 'unknown_product')

    def test_the_declaration_records_the_equipment(self):
        declaration = EquipmentCheck(
            SALTS,
            rules=(),
            injection_ratio=10,
            temperature_c=25,
            available_tanks=None,
            tank_capacities_litres=[5, 6],
            batch_litres=1000,
        ).declaration
        self.assertEqual(declaration['available_tanks'], 2)
        self.assertTrue(declaration['available_tanks_declared'])
        self.assertEqual(declaration['tank_capacities_litres'], [5.0, 6.0])


class InputGuardTests(unittest.TestCase):
    def test_capacities_must_be_a_list_of_numbers(self):
        for bad in ('20', b'20', 20):
            with self.subTest(bad=bad):
                with self.assertRaises(DeliveryError) as raised:
                    declared_tanks(2, bad)
                self.assertEqual(raised.exception.code, 'invalid_type')

    def test_the_equipment_check_must_be_callable(self):
        with self.assertRaises(DeliveryError) as raised:
            plan_fertilizer_workflow(
                SALTS, TOMATO, {}, 5.8, final_volume=VolumeLitres(1000), equipment_check='no'
            )
        self.assertEqual(raised.exception.code, 'invalid_type')

    def test_the_tank_count_flag_takes_a_whole_number_of_at_least_one(self):
        parse = int_at_least('--available-tanks', 1)
        self.assertEqual(parse('3'), 3)
        for bad in ('x', '1.5', '0', '-2'):
            with self.subTest(bad=bad):
                with self.assertRaises(argparse.ArgumentTypeError):
                    parse(bad)


if __name__ == '__main__':
    unittest.main()
