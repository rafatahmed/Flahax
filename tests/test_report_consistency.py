# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Final recipe evidence agrees across public batch outputs."""

import unittest
import re
import json
from copy import deepcopy

from flahax.batch_cli import BatchOptions, run_batch, render as render_outputs
from flahax.grower_report import render_report, render_batch_sheet
from flahax.grower_sheet import render_mix_sheet
from flahax.mix_results import results_lines
from flahax.terminal import glyphs


class FinalRecipeReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = run_batch(
            BatchOptions(
                water='ro',
                formula='DEFAULT',
                acid=['HNO3:0.65:1.3'],
                tank_litres={'A': 100, 'B': 100, 'acid': 10},
                ratio=100,
                mode='once',
                irrigation_litres=1000,
            )
        )

    def test_remedy_stage_evidence_describes_the_final_recipe(self):
        summary = self.summary
        nitrate = next(r for r in summary['formulation']['rows'] if r['symbol'] == 'N_NO3')
        self.assertAlmostEqual(nitrate['final'], 214.12848, places=4)
        stage = summary['stages']['formulation']
        remedy = next(
            r for r in summary['remedies']['requirements'] if r['id'] == 'stage:formulation'
        )
        self.assertEqual(remedy['evidence']['message'], stage['message'])
        self.assertEqual(remedy['status'], stage['status'])
        for requirement in summary['remedies']['requirements']:
            kind, _, name = requirement['id'].partition(':')
            if kind == 'stage':
                final_stage = summary['stages'][name]
                self.assertEqual(requirement['status'], final_stage['status'])
                self.assertEqual(
                    requirement['evidence'],
                    {'message': final_stage['message'], 'error_code': final_stage['error_code']},
                )

    def test_search_and_nutrient_diagnosis_have_separate_explanations(self):
        summary = self.summary
        self.assertEqual(summary['statuses']['numerical'], 'stationary_point')
        self.assertFalse(summary['formulation']['targets_met'])
        explanations = summary.get('status_explanations', {})
        self.assertIn('local stationarity', explanations.get('numerical', ''))
        self.assertIn('does not prove', explanations.get('formulation', ''))
        self.assertIn('separate nutrient feasibility diagnosis', explanations.get('nutrients', ''))
        for render in (render_report, render_batch_sheet, render_mix_sheet):
            output = render(summary)
            for explanation in explanations.values():
                self.assertIn(explanation, output)

    def test_numerical_residue_is_retained_but_not_a_weighing_instruction(self):
        summary = self.summary
        original = deepcopy(summary)
        residue = next(
            r for r in summary['formulation']['salts'] if r['name'] == 'Potassium Sulfate'
        )
        self.assertGreater(residue['gramsPerBatch'], 0)
        self.assertLess(residue['gramsPerBatch'], 1e-9)
        for render in (render_report, render_batch_sheet, render_mix_sheet):
            output = render(summary)
            rows = [
                row
                for row in re.findall(r'<tr\b.*?</tr>', output, re.S)
                if 'Potassium Sulfate' in row
            ]
            self.assertTrue(rows)
            self.assertTrue(any('numerical residue' in row for row in rows))
            for row in rows:
                self.assertNotIn('class="tick"', row)
            self.assertGreater(residue['gramsPerBatch'], 0)
        self.assertEqual(summary, original)
        exported = json.loads(render_outputs(summary)['summary.json'])
        self.assertEqual(exported, json.loads(json.dumps(original)))

    def test_positive_doses_at_and_above_display_zero_keep_weighing_checkboxes(self):
        # Synthetic legacy report inputs exercise formatting, not the chemistry calculation.
        for mass in (1e-9, 1.001e-9, 1e-6):
            summary = deepcopy(self.summary)
            summary.pop('export_identity')
            summary.pop('calculation_identity')
            for tank in summary['tanks']['tanks']:
                for product in tank['products']:
                    if product['name'] == 'Potassium Sulfate':
                        product['gramsPerBatch'] = mass
            for render in (render_batch_sheet, render_mix_sheet):
                with self.subTest(mass=mass, output=render.__name__):
                    row = next(
                        row
                        for row in re.findall(r'<tr\b.*?</tr>', render(summary), re.S)
                        if 'Potassium Sulfate' in row
                    )
                    self.assertNotIn('numerical residue', row)
                    self.assertIn('class="tick"', row)

    def test_one_irrigation_preserves_capacities_without_an_acid_capacity_limit(self):
        summary = self.summary
        self.assertEqual(summary['volumes']['capacity_litres'], {'A': 100, 'B': 100, 'acid': 10})
        self.assertEqual(summary['volumes']['prepared_litres'], {'A': 10, 'B': 10, 'acid': 10})
        self.assertEqual(summary['batch_litres'], 1000)
        sheet = render_mix_sheet(summary)
        self.assertIn('1 fill total (0 refills)', sheet)
        self.assertNotIn('acid container sets the batch', sheet)

    def test_terminal_residue_keeps_the_product_name_without_a_weighing_checkbox(self):
        lines = results_lines(self.summary, 0, 100, 100, 0, glyphs('utf-8'), 'output')
        row = next(line for line in lines if 'Potassium Sulfate' in line)
        self.assertIn('numerical residue', row)
        self.assertNotIn('[ ]', row)
