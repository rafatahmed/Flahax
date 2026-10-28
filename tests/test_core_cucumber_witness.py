# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Frozen Cucumber (Howard Resh) + RO witness on origin/main tip (core-contract-spine)."""

import json
import unittest
from pathlib import Path

from flahax import load_library
from flahax.batch_cli import BatchOptions, run_batch

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'core_spine' / 'cucumber_ro_witness.json'


def load_witness():
    """Parsed cucumber RO witness fixture (inputs + tip-observed fields)."""
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def witness_inputs():
    """BatchOptions matching the frozen cucumber + RO witness session."""
    data = load_witness()['inputs']
    return BatchOptions(
        water=data['water'],
        formula=data['formula'],
        acid=list(data['acid']),
        tank_litres=dict(data['tank_litres']),
        ratio=data['ratio'],
        ph=data['ph'],
        temperature_c=data['temperature_c'],
        mode=data['mode'],
        limit=list(data['limit']),
    )


def nutrient_row(summary, symbol):
    """Formulation nutrient row for ``symbol``, or None."""
    for row in summary['formulation']['rows']:
        if row['symbol'] == symbol:
            return row
    return None


class CucumberRoWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.witness = load_witness()
        cls.summary = run_batch(witness_inputs())
        cls.targets = next(
            f['targets']
            for f in load_library()['formulas']
            if f['name'] == 'Cucumber (Howard Resh)'
        )

    def test_fixture_records_tip_sha(self):
        self.assertEqual(
            self.witness['metadata']['tip_sha'],
            '12afceece3585be783f7bee86afa2eca468c7afa',
        )
        self.assertEqual(self.witness['inputs']['formula'], 'Cucumber (Howard Resh)')
        self.assertEqual(self.witness['inputs']['water'], 'ro')
        self.assertEqual(self.witness['inputs']['ph'], 5.9)
        self.assertEqual(self.witness['inputs']['products'], 'catalogue')
        self.assertEqual(self.witness['inputs']['limit'], [])

    def test_formula_targets_nitrate_only_nitrogen(self):
        self.assertEqual(self.targets['N_NO3'], 140)
        self.assertNotIn('N', self.targets)
        self.assertNotIn('N_NH4', self.targets)
        self.assertEqual(self.witness['formula_targets']['N_NO3'], 140)
        self.assertNotIn('N', self.witness['formula_targets'])
        self.assertNotIn('N_NH4', self.witness['formula_targets'])

    def test_summary_exposes_nitrate_ammonium_and_total_n(self):
        no3 = nutrient_row(self.summary, 'N_NO3')
        nh4 = nutrient_row(self.summary, 'N_NH4')
        self.assertIsNotNone(no3)
        self.assertIsNotNone(nh4)
        self.assertEqual(no3['target'], 140.0)
        self.assertIsNone(nh4['target'])
        self.assertIsInstance(no3['final'], float)
        self.assertIsInstance(nh4['final'], float)
        total_n = no3['final'] + nh4['final']
        self.assertGreater(total_n, 0)
        observed = self.witness['observed']
        self.assertAlmostEqual(no3['final'], observed['n_no3_final'], places=10)
        self.assertAlmostEqual(nh4['final'], observed['n_nh4_final'], places=10)
        self.assertAlmostEqual(total_n, observed['total_n_sum'], places=10)

    def test_overall_not_ready_and_tip_statuses(self):
        observed = self.witness['observed']
        self.assertNotEqual(self.summary['status'], 'ready')
        self.assertNotEqual(self.summary['statuses']['overall'], 'ready')
        self.assertEqual(self.summary['status'], observed['status'])
        self.assertEqual(self.summary['statuses'], observed['statuses'])
        self.assertEqual(self.summary['statuses']['formulation'], 'infeasible')
        self.assertEqual(self.summary['statuses']['ph'], 'blocked')
        self.assertEqual(self.summary['statuses']['ec'], 'not_supported')
        self.assertEqual(self.summary['statuses']['overall'], 'blocked')
        self.assertFalse(self.summary['formulation']['feasible'])
        stages = {
            name: stage.get('status') if isinstance(stage, dict) else stage
            for name, stage in self.summary['stages'].items()
        }
        self.assertEqual(stages, observed['stages'])
        # Tip fragmentation: batch reports calculated while formulation is blocked.
        self.assertEqual(stages['batch'], 'calculated')
        self.assertEqual(stages['formulation'], 'blocked')


if __name__ == '__main__':
    unittest.main()
