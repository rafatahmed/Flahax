# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""A separate reagent container does not shrink the nutrient stock batch."""

import unittest
from copy import deepcopy
import json
import tempfile
from pathlib import Path

from flahax.batch_cli import BatchOptions, run_batch
from flahax.grower_report import render_report, render_batch_sheet
from flahax.grower_sheet import render_mix_sheet
from flahax import load_library
from flahax.ph_adjustment import catalogue_ph_reagents


class IndependentReagentCapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = run_batch(
            BatchOptions(
                water='ro',
                formula='DEFAULT',
                tank_litres={'A': 100, 'B': 100, 'acid': 10},
                ratio=100,
                mode='fill',
            )
        )

    def test_reagent_capacity_does_not_reduce_nutrient_stock_fill(self):
        summary = self.summary
        self.assertEqual(summary['volumes']['prepared_litres']['A'], 100)
        self.assertEqual(summary['volumes']['prepared_litres']['B'], 100)
        self.assertEqual(summary['batch_litres'], 10000)

    def test_reagent_dose_is_split_across_ten_fills_at_the_same_ratio(self):
        summary = self.summary
        schedule = summary.get('reagent_preparation') or {}
        self.assertEqual(schedule.get('fills'), 10)
        self.assertEqual(schedule['refills'], 9)
        self.assertEqual(schedule['fill_litres'], 10)
        self.assertEqual(schedule['last_fill_litres'], 10)
        self.assertEqual(schedule['injection_ratio'], 100)
        total = summary['ph']['selected']['volume_ml_per_batch']
        self.assertAlmostEqual(schedule['dose_ml_per_fill'] * 10, total)
        self.assertAlmostEqual(schedule['dose_ml_last_fill'], total / 10)
        for render in (render_report, render_batch_sheet, render_mix_sheet):
            self.assertIn('10 fills total (9 refills)', render(summary))

    def test_once_mode_scales_the_last_partial_reagent_fill(self):
        summary = run_batch(
            BatchOptions(
                water='ro',
                formula='DEFAULT',
                tank_litres={'A': 100, 'B': 100, 'acid': 10},
                ratio=100,
                mode='once',
                irrigation_litres=2500,
            )
        )
        schedule = summary['reagent_preparation']
        self.assertEqual(summary['volumes']['prepared_litres'], {'A': 25, 'B': 25, 'acid': 10})
        self.assertEqual(schedule['fills'], 3)
        self.assertEqual(schedule['refills'], 2)
        self.assertEqual(schedule['last_fill_litres'], 5)
        self.assertAlmostEqual(schedule['dose_ml_last_fill'], schedule['dose_ml_per_fill'] / 2)
        self.assertAlmostEqual(
            2 * schedule['dose_ml_per_fill'] + schedule['dose_ml_last_fill'],
            summary['ph']['selected']['volume_ml_per_batch'],
        )
        for render in (render_report, render_batch_sheet, render_mix_sheet):
            self.assertIn('Final partial fill:', render(summary))
            self.assertIn('make up to 5 L', render(summary))

    def test_blocked_batch_has_no_reagent_preparation_schedule(self):
        summary = run_batch(
            BatchOptions(
                water='ro',
                formula='DEFAULT',
                tank_litres={'A': 100, 'B': 100, 'acid': 10},
                ratio=1e6,
                mode='fill',
            )
        )
        self.assertEqual(summary['status'], 'blocked')
        self.assertIsNotNone(summary['ph']['selected'])
        self.assertIsNone(summary['reagent_preparation'])
        for render in (render_report, render_batch_sheet, render_mix_sheet):
            self.assertNotIn('Each full fill:', render(summary))

    def test_impossible_liquid_concentrate_is_not_a_preparation_instruction(self):
        # Synthetic legacy report input tests rendering without claiming a valid recipe.
        summary = deepcopy(self.summary)
        summary.pop('export_identity')
        summary.pop('calculation_identity')
        summary['ph']['selected']['volume_ml_per_batch'] = 200000
        for render in (render_report, render_batch_sheet, render_mix_sheet):
            output = render(summary)
            self.assertIn('exceeds the available reagent stock volume', output)
            self.assertNotIn('Each full fill:', output)

    def test_otherwise_usable_batch_reports_reagent_stock_overflow_as_blocked_delivery(self):
        # Tiny nutrient stock concentration avoids a fertilizer-solubility block at this ratio.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            products = [p for p in load_library()['salts'] if p['formula'] == 'KNO3']
            nitric = next(p for p in catalogue_ph_reagents() if p['chemicalFormula'] == 'HNO3')
            for name, value in [
                ('targets', {'K': 0.00001}),
                ('products', products),
                ('reagents', [nitric]),
            ]:
                (root / (name + '.json')).write_text(json.dumps(value))
            summary = run_batch(
                BatchOptions(
                    water='ro',
                    targets=str(root / 'targets.json'),
                    products=str(root / 'products.json'),
                    reagents=str(root / 'reagents.json'),
                    tank_litres={'A': 100, 'B': 100, 'acid': 10},
                    ratio=1e8,
                    mode='fill',
                )
            )
        self.assertEqual(summary['status'], 'blocked')
        self.assertEqual(summary['statuses']['delivery'], 'blocked')
        self.assertEqual(summary['reagent_preparation']['status'], 'blocked')
        self.assertEqual(summary['stages']['reagent_preparation']['status'], 'blocked')
        self.assertNotIn('dose_ml_per_fill', summary['reagent_preparation'])
        self.assertTrue(any('reagent_preparation:' in w for w in summary['warnings']))
