# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Input and batch integration checks for Sonneveld target design."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from flahax.batch_request import BatchOptions, run_batch
from flahax.batch_cli import main
from flahax.delivery_contracts import DeliveryError
from flahax.sonneveld import design_targets


BASELINE = {'N_NH4': 1, 'K': 6.5, 'Ca': 2.75, 'Mg': 1, 'P': 1.25, 'N_NO3': 10.75, 'S': 1.5}
DESIGN = {
    'baseline_mmol_l': BASELINE,
    'adjustments_mmol_l': {'K': 2, 'N_NH4': 0.5},
    'irrigation_ec_ds_m': 1.8,
}


class SonneveldTargetTests(unittest.TestCase):
    def test_minimum_is_checked_after_scaling(self):
        design = design_targets(DESIGN | {'minimum_mmol_l': {'Ca': 2.8}})
        self.assertGreater(design['columns_mmol_l']['D']['Ca'], 2.8)
        self.assertAlmostEqual(design['columns_mmol_l']['D']['N_NH4'], 1.5)
        self.assertAlmostEqual(design['columns_mmol_l']['D']['P'], 1.25)
        with self.assertRaisesRegex(DeliveryError, 'Column D.*minimum.*Ca'):
            design_targets(DESIGN | {'minimum_mmol_l': {'Ca': 3.0}})

    def test_invalid_inputs_and_conflicting_charge_budgets(self):
        for request, message in (
            (None, 'Supply the Sonneveld'),
            ({}, 'Supply the Sonneveld'),
            (DESIGN | {'pH': 5.5}, 'Supply the Sonneveld'),
            (DESIGN | {'baseline_mmol_l': []}, 'supported nutrients'),
            (DESIGN | {'baseline_mmol_l': {}}, 'seven macronutrient'),
            (DESIGN | {'baseline_mmol_l': BASELINE | {'S': 2}}, 'equal positive'),
            (DESIGN | {'baseline_mmol_l': BASELINE | {'S': -1}}, 'invalid concentration'),
            (DESIGN | {'adjustments_mmol_l': {'Na': 2}}, 'supported nutrients'),
            (DESIGN | {'adjustments_mmol_l': {'K': True}}, 'invalid concentration'),
            (DESIGN | {'adjustments_mmol_l': {'K': float('inf')}}, 'invalid concentration'),
            (DESIGN | {'adjustments_mmol_l': {'K': -7}}, 'negative concentration'),
            (DESIGN | {'adjustments_mmol_l': {'N_NH4': 16}}, 'Column C cannot balance'),
            (
                DESIGN | {'adjustments_mmol_l': {'K': -6.5, 'Ca': -2.75, 'Mg': -1}},
                'Column C cannot balance',
            ),
            (DESIGN | {'irrigation_ec_ds_m': 0.1}, 'Column D cannot balance'),
            (DESIGN | {'irrigation_ec_ds_m': 0}, 'finite and positive'),
            (DESIGN | {'irrigation_ec_ds_m': float('nan')}, 'finite and positive'),
            (DESIGN | {'irrigation_ec_ds_m': '1.8'}, 'finite and positive'),
        ):
            with self.subTest(request=request), self.assertRaisesRegex(DeliveryError, message):
                design_targets(request)

    def test_zero_adjustable_charge_can_stay_zero(self):
        baseline = dict.fromkeys(BASELINE, 0) | {'N_NH4': 1, 'P': 1}
        design = design_targets(
            DESIGN
            | {'baseline_mmol_l': baseline, 'adjustments_mmol_l': {}, 'irrigation_ec_ds_m': 0.1}
        )
        self.assertEqual(design['columns_mmol_l']['D'], baseline)

    def test_batch_cli_passes_generated_targets_and_preserves_a_to_d(self):
        expected = design_targets(DESIGN)
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(temp)
            design_file = root / 'sonneveld.json'
            design_file.write_text(json.dumps(DESIGN), encoding='utf-8')
            reagents = root / 'reagents.json'
            reagents.write_text('[]', encoding='utf-8')
            out = root / 'batch'
            main(
                [
                    '--sonneveld-targets',
                    str(design_file),
                    '--water',
                    'ro',
                    '--reagents',
                    str(reagents),
                    '--output',
                    str(out),
                ]
            )
            summary = json.loads((out / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['sonneveld_target_design'], expected)
        self.assertEqual(summary['title'], 'sonneveld')
        targets = {
            row['symbol']: row['target']
            for row in summary['formulation']['rows']
            if row['symbol'] in expected['targets_mg_l']
        }
        self.assertEqual(targets, expected['targets_mg_l'])

    def test_programmatic_batch_rejects_two_target_sources(self):
        with self.assertRaisesRegex(DeliveryError, 'single source'):
            run_batch(
                BatchOptions(
                    water='ro', formula='Tomato (Howard Resh)', sonneveld_targets='design.json'
                )
            )

    def test_preview_prints_targets_without_running_batch(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'design.json'
            path.write_text(json.dumps(DESIGN), encoding='utf-8')
            argv = ['--sonneveld-targets', str(path), '--preview-targets']
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(argv), 0)
            self.assertEqual(json.loads(out.getvalue()), design_targets(DESIGN))
            path.write_text('{}', encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(argv), 1)
            self.assertIn('Supply the Sonneveld', err.getvalue())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['--preview-targets'])

    def test_root_zone_feedback_is_bound_to_approved_feed_design(self):
        feedback = {
            'sample_id': 'tomato-bed-1',
            'sampled_on': '2026-11-17',
            'measured_mmol_l': {'K': 6.5, 'Ca': 10.2, 'Mg': 4.0},
            'guide_mmol_l': {'K': 8.0, 'Ca': 10.0, 'P': 1.0},
        }
        request = DESIGN | {'root_zone_feedback': feedback}
        preview = design_targets(request)
        review = preview['root_zone_feedback']
        self.assertEqual(review['status'], 'awaiting_approval')
        self.assertEqual(review['without_guide'], ['Mg'])
        self.assertEqual(review['without_measurement'], ['P'])
        self.assertEqual(review['deviations_mmol_l']['K'], -1.5)
        self.assertAlmostEqual(review['deviations_mmol_l']['Ca'], 0.2)
        self.assertEqual(preview['columns_mmol_l']['A']['Ca'], 2.75)
        self.assertEqual(preview['columns_mmol_l']['B']['K'], 2)
        self.assertEqual(preview['targets_mg_l'], design_targets(DESIGN)['targets_mg_l'])

        approval = {
            'approved_by': 'Grower',
            'design_sha256': review['design_sha256'],
            'reason': 'Increase feed potassium after reviewing the root-zone sample.',
        }
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(temp)
            path = root / 'design.json'
            path.write_text(json.dumps(request), encoding='utf-8')
            options = BatchOptions(water='ro', sonneveld_targets=str(path))
            with self.assertRaisesRegex(DeliveryError, 'requires grower approval'):
                run_batch(options)

            reagents = root / 'reagents.json'
            reagents.write_text('[]', encoding='utf-8')
            approved = request | {'root_zone_feedback': feedback | {'approval': approval}}
            path.write_text(json.dumps(approved), encoding='utf-8')
            summary = run_batch(
                BatchOptions(water='ro', sonneveld_targets=str(path), reagents=str(reagents))
            )
            approved_review = summary['sonneveld_target_design']['root_zone_feedback']
            self.assertEqual(approved_review['approval'], approval)
            self.assertEqual(approved_review['status'], 'approved')
            snapshot = summary['sonneveld_target_design']
            self.assertEqual(snapshot['targets_mg_l'], preview['targets_mg_l'])

            for changed in (
                approved | {'adjustments_mmol_l': {'K': 1}},
                approved
                | {'root_zone_feedback': feedback | {'approval': approval, 'sample_id': 'later'}},
            ):
                path.write_text(json.dumps(changed), encoding='utf-8')
                with self.assertRaisesRegex(DeliveryError, 'does not match'):
                    run_batch(options)

    def test_invalid_root_zone_samples_and_approvals_are_rejected(self):
        feedback = {
            'sample_id': 'bed-1',
            'sampled_on': '2026-11-17',
            'measured_mmol_l': {'K': 6.5},
            'guide_mmol_l': {'K': 8.0},
        }
        for sample, message in (
            (None, 'sample ID'),
            ({}, 'sample ID'),
            (feedback | {'sample_id': ' '}, 'sample ID'),
            (feedback | {'sampled_on': '2026-02-31'}, 'sampled_on'),
            (feedback | {'sampled_on': 17}, 'sampled_on'),
            (feedback | {'measured_mmol_l': {'K': -1}}, 'invalid concentration'),
            (feedback | {'guide_mmol_l': {'Ca': 10}}, 'matching nutrient'),
            (feedback | {'approval': None}, 'Approval must'),
            (feedback | {'approval': {}}, 'Approval must'),
            (
                feedback
                | {
                    'approval': {
                        'approved_by': ' ',
                        'reason': 'test',
                        'design_sha256': 'ignored',
                    }
                },
                'Approval must',
            ),
        ):
            with self.subTest(sample=sample), self.assertRaisesRegex(DeliveryError, message):
                design_targets(DESIGN | {'root_zone_feedback': sample})
