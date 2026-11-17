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

from flahax.batch_cli import BatchOptions, main, run_batch
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
