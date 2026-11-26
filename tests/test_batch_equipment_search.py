# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The batch command runs the equipment-aware search too (D4, contract Q19, Q20, Q23).

Equipment is judged in the batch report, so the batch hands its check to the workflow.
The search runs only when asked for (--fit-equipment), keeps the declared equipment and
every separation rule, and records what it was held to.
"""

import json
import tempfile
import unittest
from pathlib import Path

from flahax.batch_request import BatchOptions, run_batch
from flahax.batch_cli import main
from flahax.delivery_contracts import DeliveryError
from flahax.engine import load_library

NITRIC = 'HNO3:0.65:1.39:Nitric acid 65%'


def alternative_file(directory):
    kno3 = next(p for p in load_library()['salts'] if p['formula'] == 'KNO3')
    path = Path(directory) / 'alternatives.json'
    path.write_text(json.dumps([dict(kno3, id='alt-kno3', name='Alternative potassium nitrate')]))
    return str(path)


def targets_file(directory):
    # Calcium nitrate and phosphate cannot share a tank, so this needs two tanks, and
    # the targets are met, so only the equipment can trigger a search.
    path = Path(directory) / 'targets.json'
    path.write_text(json.dumps({'N_NO3': 140, 'Ca': 100, 'K': 150, 'P': 30, 'Mg': 40}))
    return str(path)


def batch(directory, **changes):
    options = dict(
        water='ro',
        targets=targets_file(directory),
        acid=[NITRIC],
        volume=1000,
        ratio=100,
        alternative_products=alternative_file(directory),
    )
    return run_batch(BatchOptions(**(options | changes)))


class BatchEquipmentSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.too_few = batch(cls.directory.name, available_tanks=1, fit_equipment=True)

    def test_a_declared_tank_shortage_runs_the_requested_search(self):
        remedies = self.too_few['remedies']
        self.assertEqual(remedies['mode'], 'find_suitable_doses')
        self.assertGreaterEqual(remedies['evaluations'], 1)
        self.assertIn('equipment:fit', {r['id'] for r in remedies['requirements']})

    def test_the_search_is_held_to_the_declared_equipment(self):
        declared = self.too_few['remedies']['declared_equipment']
        self.assertEqual(declared['available_tanks'], 1)
        self.assertEqual(declared['injection_ratio'], 100)
        self.assertTrue(declared['available_tanks_declared'])
        self.assertEqual(self.too_few['tanks']['available_tanks'], 1)  # never changed

    def test_the_declared_equipment_is_saved_with_the_inputs(self):
        saved = self.too_few['supplied_inputs']['equipment_declaration']
        self.assertEqual(saved, self.too_few['remedies']['declared_equipment'])

    def test_without_the_flag_nothing_is_searched_for_equipment(self):
        result = batch(self.directory.name, available_tanks=1)
        self.assertEqual(result['remedies']['evaluations'], 0)
        self.assertEqual(result['remedies']['mode'], 'analyze_supplied_doses')

    def test_equipment_that_fits_runs_no_search(self):
        result = batch(self.directory.name, available_tanks=2, fit_equipment=True)
        self.assertEqual(result['remedies']['evaluations'], 0)

    def test_the_search_needs_products_to_search(self):
        with self.assertRaises(DeliveryError) as raised:
            run_batch(
                BatchOptions(
                    water='ro',
                    formula='Tomato (Howard Resh)',
                    acid=[NITRIC],
                    available_tanks=1,
                    fit_equipment=True,
                )
            )
        self.assertEqual(raised.exception.code, 'invalid_value')

    def test_the_command_takes_the_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'batch'
            main(
                [
                    '--formula',
                    'Tomato (Howard Resh)',
                    '--water',
                    'ro',
                    '--acid',
                    NITRIC,
                    '--available-tanks',
                    '1',
                    '--fit-equipment',
                    '--alternative-products',
                    alternative_file(temp),
                    '--output',
                    str(out),
                ]
            )
            summary = json.loads((out / 'summary.json').read_text())
        self.assertEqual(summary['remedies']['mode'], 'find_suitable_doses')


if __name__ == '__main__':
    unittest.main()
