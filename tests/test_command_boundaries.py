# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Public command input boundary checks for runtime coverage closure (#186)."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from flahax import DeliveryError, load_library
from flahax import planning_cli as planning, batch_cli as batch


class PlanningInputBoundaryTests(unittest.TestCase):
    def test_interactive_workflow_keeps_explicit_zeros_and_optional_absence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'salts.json'
            path.write_text(json.dumps([{'id': 'x', 'elements': {'K': 10}}]))
            answers = [str(path), json.dumps({'K': 0}), '{}', '6', '100', '', '', '', '']
            output, error = StringIO(), StringIO()
            with (
                patch('builtins.input', side_effect=answers),
                redirect_stderr(error),
                redirect_stdout(output),
            ):
                result = planning.interactive('workflow')
        self.assertEqual(result['targets'], {'K': 0})
        self.assertEqual(result['water'], {})
        self.assertIsNone(result['maximum_concentrations'])
        self.assertIsNone(result['equilibrium'])
        self.assertIsNone(result['acids'])
        self.assertIsNone(result['stocks'])
        self.assertEqual(result['final_volume_litres'], 100)
        self.assertEqual(output.getvalue(), '')
        self.assertIn('Optional hard nutrient maxima', error.getvalue())

    def test_interactive_tds_and_equipment_volume_modes(self):
        cases = [
            (
                'ec',
                ['{}', 'tds', '500', '.5', '25', 'irrigation', 'false'],
                {'water_tds_ppm': 500, 'tds_factor': 0.5, 'acid_added': False},
            ),
            ('size', ['dosing_pump', '2', 'batch', '100', '{}'], {'final_volume_litres': 100}),
            (
                'size',
                ['venturi', '2', 'area', '100', '5', '{}'],
                {'active_area_m2': 100, 'gross_depth_mm': 5},
            ),
        ]
        for command, answers, expected in cases:
            with patch('builtins.input', side_effect=answers), redirect_stderr(StringIO()):
                result = planning.interactive(command)
            for k, v in expected.items():
                self.assertEqual(result[k], v)
        for command, answers in [('ec', ['{}', 'unknown']), ('size', ['venturi', '2', 'unknown'])]:
            with patch('builtins.input', side_effect=answers), redirect_stderr(StringIO()):
                with self.assertRaises(DeliveryError) as caught:
                    planning.interactive(command)
            self.assertEqual(caught.exception.code, 'invalid_value')

    def test_workflow_shape_and_serialization_boundaries(self):
        payload = dict(
            salts=[{'id': 'x', 'elements': {'K': 10}}],
            targets={'K': 10},
            water={},
            target_ph=6,
            final_volume_litres=100,
        )
        for change, code in [
            (dict(extra=True), 'unknown_field'),
            (dict(salts=[]), 'missing_field'),
            (dict(targets=[]), 'invalid_type'),
            (dict(stocks=[]), 'invalid_type'),
        ]:
            with self.assertRaises(DeliveryError) as caught:
                planning.execute('workflow', payload | change)
            self.assertEqual(caught.exception.code, code)
        with self.assertRaises(DeliveryError) as caught:
            planning.execute('unknown', {})
        self.assertEqual(caught.exception.code, 'unknown_command')
        self.assertEqual(planning.serializable(float('inf')), 'inf')
        # Parser passes an invalid remedy shape through to the workflow's own validator.
        with patch.object(planning, 'plan_fertilizer_workflow', return_value='sentinel') as target:
            self.assertEqual(
                planning.execute('workflow', payload | dict(remedy_options=None)), 'sentinel'
            )
            self.assertIsNone(target.call_args.kwargs['remedy_options'])
            planning.execute(
                'workflow', payload | dict(remedy_options=[{'kind': 'equipment', 'changes': {}}])
            )
            self.assertEqual(
                target.call_args.kwargs['remedy_options'], [{'kind': 'equipment', 'changes': {}}]
            )


class BatchInputBoundaryTests(unittest.TestCase):
    def test_unreadable_and_malformed_water_records(self):
        with patch.object(Path, 'read_text', side_effect=PermissionError(13, 'denied')):
            with self.assertRaises(DeliveryError) as caught:
                batch.read_json('water.json', 'water')
        self.assertEqual(caught.exception.code, 'missing_file')
        cases = [
            ([], 'invalid_type'),
            ({'mg_per_litre': {}}, 'missing_field'),
            ({'mg_per_litre': {'Xx': 1}, 'measured_ph': 7}, 'unknown_field'),
            ({'mg_per_litre': {'Na': True}, 'measured_ph': 7}, 'invalid_value'),
            ({'mg_per_litre': {'Na': -1}, 'measured_ph': 7}, 'invalid_value'),
            ({'mg_per_litre': {}, 'measured_ph': '7'}, 'invalid_value'),
            (
                {'mg_per_litre': {}, 'measured_ph': 7, 'below_detection': {'Xx': 1}},
                'unknown_field',
            ),
            (
                {'mg_per_litre': {'HCO3': 0}, 'measured_ph': 7, 'balance_ion': 'K'},
                'unsupported_balance_ion',
            ),
        ]
        for payload, code in cases:
            with (
                self.subTest(payload=payload),
                patch.object(batch, 'read_json', return_value=payload),
            ):
                with self.assertRaises(DeliveryError) as caught:
                    batch.read_water('water.json')
                self.assertEqual(caught.exception.code, code)
        payload = dict(
            mg_per_litre={'HCO3': 0},
            measured_ph=7,
            balance_ion='Na',
            balance_ion_uncertainty_percent=2,
        )
        with patch.object(batch, 'read_json', return_value=payload):
            _, _, config = batch.read_water('water.json')
        self.assertEqual(config['balance_ion'], 'Na+')
        self.assertEqual(config['balance_ion_uncertainty_percent'], 2)

    def test_invalid_blends_do_not_modify_nutrient_inventory(self):
        for chemistry, percent in [({}, 10), ({'measured_ph': 7}, 0), ({'measured_ph': 7}, 101)]:
            with self.assertRaises(DeliveryError) as caught:
                batch.blend('Water', {}, chemistry, percent)
            self.assertEqual(caught.exception.code, 'invalid_value')
        chemistry = dict(measured_ph=7, water_totals={'unknown': 1}, water_analysis_id='test')
        label, water, result = batch.blend('Water', {'K': 20}, chemistry, 100)
        self.assertIn('Chemistry not calculated', label)
        self.assertEqual(water, {'K': 20})
        self.assertIsNone(result)

    def test_limit_acid_formula_and_command_diagnostics(self):
        import argparse

        for text in ('Cl', 'Cl=not-a-number'):
            with self.assertRaises(argparse.ArgumentTypeError):
                batch.limit_entry(text)
        for text in ('HNO3', 'HNO3:2:1'):
            with self.assertRaises(DeliveryError) as caught:
                batch.acid_record(text)
            self.assertEqual(caught.exception.code, 'invalid_value')
        with self.assertRaises(DeliveryError) as caught:
            batch.choose_formula(load_library(), 'missing', None)
        self.assertEqual(caught.exception.code, 'unknown_formula')
        out = StringIO()
        with redirect_stdout(out):
            self.assertEqual(batch.main(['--list-formulas']), 0)
        self.assertIn('Tomato (Howard Resh)', out.getvalue())
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
            batch.main([])
        self.assertEqual(caught.exception.code, 2)


class BatchOutputBoundaryTests(unittest.TestCase):
    def test_printed_selected_volume_and_written_content_agree(self):
        # Command formatting fixture; build qualification is tested separately.
        summary = dict(
            title='Rendering fixture',
            status='requires_review',
            batch_litres=100,
            tanks={'tanks': []},
            ph={'selected': {'volume_ml_per_batch': 2, 'product': 'Example'}},
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'batch'
            stdout = StringIO()
            with patch.object(batch, 'build', return_value=({'summary.json': '{}'}, summary)):
                with redirect_stdout(stdout):
                    code = batch.main(
                        ['--formula', 'fixture', '--water', 'ro', '--output', str(out)]
                    )
            self.assertEqual(code, 0)
            self.assertEqual((out / 'summary.json').read_text(), '{}')
            self.assertIn('2 mL Example per 100 L', stdout.getvalue())

    def test_missing_chemistry_and_water_notes_remain_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            targets = Path(tmp) / 'targets.json'
            targets.write_text('{"K": 10}')
            label, ions, chemistry = batch.read_water('ro')
            opts = batch.BatchOptions(water='ro', targets=str(targets))
            with patch.object(batch, 'read_water', return_value=(label, ions, None)):
                no_chemistry = batch.run_batch(opts)
            self.assertIsNone(no_chemistry['chemistry'])
            chemistry = chemistry | {'water_input_notes': ['Synthetic laboratory input note']}
            with patch.object(batch, 'read_water', return_value=(label, ions, chemistry)):
                notes = batch.run_batch(opts)
            self.assertEqual(notes['warnings'].count('Synthetic laboratory input note'), 1)
            original = batch.summarize_batch

            def missing_note(*args, **kwargs):
                result = original(*args, **kwargs)
                result['warnings'] = [
                    w for w in result['warnings'] if w != 'Synthetic laboratory input note'
                ]
                return result

            # Adapter fault injection: the batch boundary restores omitted input provenance.
            with patch.object(batch, 'summarize_batch', missing_note):
                with patch.object(batch, 'read_water', return_value=(label, ions, chemistry)):
                    restored = batch.run_batch(opts)
            self.assertEqual(restored['warnings'].count('Synthetic laboratory input note'), 1)
