# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Regression for the complete Appendix I workflow through the mix wizard."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from flahax.mix_store import Store
from flahax.mix_tui import run_tui
from flahax.mix_cli import main, summarize, write_sheets
from flahax.mix_sonneveld import calculate_batch
from flahax.delivery_contracts import DeliveryError
from flahax.canonical_result import seal_summary
from flahax.mix_results import results_lines
from flahax.terminal import glyphs
from tests.test_mix_tui import IdleTerm, entry


def appendix_profile():
    """Load the downloadable, self-contained walkthrough inputs exercised by the wizard."""
    path = Path(__file__).resolve().parents[1] / 'examples' / 'sonneveld-appendix-i.json'
    return json.loads(path.read_text(encoding='utf-8'))


class ReviewTerm(IdleTerm):
    """Wait for calculation before sending keys for the adoption prompt."""

    def read_key(self, timeout=0.1):
        if self.frames and any('Calculating the recipe' in row for row in self.frames[-1]):
            return None
        return super().read_key(timeout)


class SonneveldTuiTests(unittest.TestCase):
    def test_public_appendix_i_import_and_replay_across_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / 'appendix.json'
            profile.write_text(json.dumps(appendix_profile()), encoding='utf-8')
            source = Path(__file__).resolve().parents[1] / 'src'

            def run(seed, *args, answers=''):
                return subprocess.run(
                    [sys.executable, '-X', 'utf8', '-m', 'flahax', 'mix', '--plain', *args],
                    input=answers,
                    capture_output=True,
                    encoding='utf-8',
                    cwd=root,
                    env=dict(
                        os.environ,
                        PYTHONPATH=str(source),
                        PYTHONHASHSEED=str(seed),
                        FLAHAX_HOME=str(root / 'home'),
                    ),
                    timeout=600,
                )

            answers = '\n'.join([''] * 4 + ['Test grower', 'Appendix I review', 'Appendix I', '2'])
            imported = run(
                1,
                '--sonneveld-batch',
                str(profile),
                '--output',
                'original',
                answers=answers + '\n',
            )
            self.assertEqual(imported.returncode, 0, imported.stdout + imported.stderr)
            original = (root / 'original' / 'summary.json').read_bytes()
            summary = json.loads(original)
            rounded = summary['volumetric_stocks']
            targets = summary['sonneveld_target_design']['targets_mg_l']
            self.assertEqual(len(targets), 13)
            for nutrient, target in targets.items():
                low, high = rounded['nutrient_bounds_mg_l'][nutrient]
                self.assertGreaterEqual(low, target * 0.999, nutrient)
                self.assertLessEqual(high, target * 1.001, nutrient)
            self.assertGreaterEqual(rounded['sampled_ph_range'][0], 5.498)
            self.assertLessEqual(rounded['sampled_ph_range'][1], 5.502)
            self.assertLess(rounded['nutrient_bounds_mg_l']['Na'][1], 8.55)
            self.assertNotIn('sodium nitrate', rounded['dry_product_grams'])
            profile.unlink()  # saved replay must not depend on the original import file
            for seed in (2, 17):
                with self.subTest(seed=seed):
                    replay = run(seed, 'sessions/appendix-i', '--output', f'replay-{seed}')
                    self.assertEqual(replay.returncode, 0, replay.stdout + replay.stderr)
                    output = root / f'replay-{seed}'
                    self.assertEqual((output / 'summary.json').read_bytes(), original)
                    self.assertTrue((output / 'batch-sheet.html').is_file())
            saved = root / 'home' / 'sessions' / 'appendix-i.json'
            session = json.loads(saved.read_text(encoding='utf-8'))
            session['selected_candidate'] = 'changed'
            saved.write_text(json.dumps(session), encoding='utf-8')
            refused = run(3, 'sessions/appendix-i', '--output', 'refused')
            self.assertEqual(refused.returncode, 1)
            self.assertIn(
                'saved session metadata or inputs changed', refused.stdout + refused.stderr
            )
            self.assertFalse((root / 'refused').exists())

    def test_appendix_i_preview_search_rounded_delivery_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / 'appendix.json'
            profile.write_text(json.dumps(appendix_profile()), encoding='utf-8')
            store = Store(root / 'home')
            keys = (
                ['ENTER'] * 4
                + entry('Example grower')
                + entry('Appendix I review')
                + entry('Appendix I')
                + ['DOWN', 'ENTER']
                + ['DOWN'] * 5
                + ['TAB', 'TAB', 'q', 'y']
            )
            term = ReviewTerm(keys)
            code, lines = run_tui(
                store,
                None,
                str(root / 'out'),
                term_factory=lambda: term,
                sonneveld_batch=str(profile),
            )
            self.assertEqual(code, 0, lines)
            self.assertTrue(term.exited)
            frames = '\n'.join('\n'.join(frame) for frame in term.frames)
            for text in (
                'Review root-zone sample',
                'Use verified alternative',
                'Rounded batch doses',
                '187.26 mL',
                '120.98 mL',
                '127.76 mL',
                'Rounded finished nutrients',
                '5% reserve',
            ):
                self.assertIn(text, frames)
            summary = json.loads((root / 'out' / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(
                summary['sonneveld_target_design']['root_zone_feedback']['status'], 'approved'
            )
            rounded = summary['volumetric_stocks']
            self.assertEqual(rounded['dry_product_grams']['sodium sulfate anhydrous'], 24.039)
            self.assertNotIn('sodium nitrate', rounded['dry_product_grams'])
            self.assertEqual(rounded['missed_targets'], [])
            targets = summary['sonneveld_target_design']['targets_mg_l']
            self.assertEqual(len(targets), 13)
            for nutrient, target in targets.items():
                low, high = rounded['nutrient_bounds_mg_l'][nutrient]
                self.assertGreaterEqual(low, target * 0.999, nutrient)
                self.assertLessEqual(high, target * 1.001, nutrient)
            self.assertGreaterEqual(rounded['sampled_ph_range'][0], 5.498)
            self.assertLessEqual(rounded['sampled_ph_range'][1], 5.502)
            self.assertAlmostEqual(rounded['effective_maximum_concentrations']['Na'], 8.55)
            self.assertEqual(rounded['rounding_search']['status'], 'nearest_passed')
            self.assertLess(rounded['nutrient_bounds_mg_l']['Na'][1], 8.55)
            self.assertAlmostEqual(rounded['nutrient_bounds_mg_l']['Na'][1], 8.499246, places=6)
            self.assertTrue(rounded['ph_within_tolerance'])
            saved = store.load('sessions', 'appendix-i')
            self.assertEqual(set(saved), {'sonneveld_batch', 'selected_candidate', 'saved_state'})
            self.assertEqual(saved['saved_state']['schema_version'], 1)
            self.assertEqual(saved['saved_state']['references'], {})
            self.assertEqual(
                saved['selected_candidate'], summary['calculation_identity']['result_id']
            )
            with patch('flahax.mix_sonneveld.calculate_batch', return_value=summary):
                for decision, expected in (('1', 1), ('2', 0)):
                    answers = iter([''] * 4 + ['Test grower', 'Review', 'Plain', decision])
                    code = main(
                        [
                            '--plain',
                            '--sonneveld-batch',
                            str(profile),
                            '--output',
                            str(root / f'plain-{decision}'),
                        ],
                        ask=lambda _: next(answers),
                        say=lambda _: None,
                        store=store,
                    )
                    self.assertEqual(code, expected)
                    self.assertEqual((root / f'plain-{decision}').exists(), expected == 0)
                code = main(
                    ['--plain', 'plain', '--output', str(root / 'plain-replay')],
                    say=lambda _: None,
                    store=store,
                )
                self.assertEqual(code, 0)
            sheet = (root / 'out' / 'batch-sheet.html').read_text(encoding='utf-8')
            self.assertIn('120.98', sheet)
            self.assertNotIn('Weigh and dissolve', sheet)
            profile.unlink()
            replay = IdleTerm(['q', 'y'])
            code, lines = run_tui(
                store, 'appendix-i', str(root / 'replay'), term_factory=lambda: replay
            )
            self.assertEqual(code, 0, lines)
            self.assertEqual(
                (root / 'out' / 'summary.json').read_bytes(),
                (root / 'replay' / 'summary.json').read_bytes(),
            )
            term = IdleTerm([])
            code, lines = run_tui(
                store, 'appendix-i', None, term_factory=lambda: term, review_availability=True
            )
            self.assertEqual(code, 1)
            self.assertIn('Reimport', lines[0])
            messages = []
            self.assertEqual(
                main(
                    ['appendix-i', '--plain', '--review-reagents'],
                    say=messages.append,
                    store=store,
                ),
                1,
            )
            self.assertIn('Reimport', messages[-1])
            lines = []
            for mode, measurement in (('point', 2.1), ('unavailable', None)):
                with self.subTest(mode=mode):
                    rounded['ec25_range_ms_cm'] = None
                    rounded['ec25_ms_cm'] = measurement
                    rounded['missed_targets'] = ['Mo']
                    summary['status'] = 'blocked'
                    evidence = seal_summary(summary)
                    for view in range(3):
                        lines.extend(
                            results_lines(evidence, view, 100, 30, 0, glyphs('utf8'), 'out')
                        )
                    summarize(evidence, lines.append)
            self.assertTrue(any('Diagnostic quantities only' in line for line in lines))
            self.assertTrue(any('2.10000 mS/cm' in line for line in lines))
            summary['volumetric_stocks'] = None
            summary['warnings'] = []
            summary.pop('calculation_identity')
            evidence = seal_summary(summary)
            summarize(evidence, lines.append)
            results_lines(evidence, 0, 100, 30, 0, glyphs('utf8'), 'out')
            self.assertEqual(len(write_sheets(evidence, {'depth': 3}, root / 'diagnostic')), 3)

    def test_invalid_profiles_and_declined_review_leave_no_saved_session(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / 'appendix.json'
            store = Store(root / 'home')
            profile.write_text('{}', encoding='utf-8')
            code, lines = run_tui(
                store, None, None, term_factory=lambda: IdleTerm([]), sonneveld_batch=str(profile)
            )
            self.assertEqual(code, 1)
            self.assertIn('Invalid Sonneveld batch profile', lines[0])
            profile.write_text(json.dumps(appendix_profile()), encoding='utf-8')
            term = IdleTerm(['DOWN', 'ENTER'])
            code, lines = run_tui(
                store, None, None, term_factory=lambda: term, sonneveld_batch=str(profile)
            )
            self.assertEqual((code, lines), (1, ['Stopped; nothing saved.']))
            self.assertEqual(store.list('sessions'), [])
            with self.assertRaises(SystemExit):
                main(['existing', '--sonneveld-batch', str(profile)], store=store)
            unbound = root / 'unbound.json'
            unbound.write_text(
                json.dumps({'sonneveld_batch': appendix_profile()}), encoding='utf-8'
            )
            messages = []
            code = main(['--plain', str(unbound)], store=store, say=messages.append)
            self.assertEqual(code, 1)
            self.assertIn('Import the Sonneveld batch profile', messages[-1])
            unbound.write_text(
                json.dumps({'sonneveld_batch': appendix_profile(), 'saved_state': {}}),
                encoding='utf-8',
            )
            self.assertEqual(main(['--plain', str(unbound)], say=messages.append, store=store), 1)
            self.assertIn('needs a reviewed candidate', messages[-1])
            bad_sample = appendix_profile()
            bad_sample['sonneveld']['root_zone_feedback'] = None
            profile.write_text(json.dumps(bad_sample), encoding='utf-8')
            code, lines = run_tui(
                store, None, None, term_factory=lambda: IdleTerm([]), sonneveld_batch=str(profile)
            )
            self.assertEqual(code, 1)
            self.assertIn('sample', lines[0])

    def test_no_alternative_and_changed_candidate_are_qualified(self):
        from flahax.sonneveld import design_targets

        profile = appendix_profile()
        profile['alternative_products'] = []
        design = profile['sonneveld']
        preview = design_targets(design)
        design['root_zone_feedback']['approval'] = {
            'approved_by': 'Example grower',
            'reason': 'Check',
            'design_sha256': preview['root_zone_feedback']['design_sha256'],
        }
        stage = SimpleNamespace(status='blocked', message='No rounded candidate')
        workflow = SimpleNamespace(
            remedies={},
            stages={'volumetric_stocks': stage},
            canonical_result=SimpleNamespace(result_id='new'),
        )
        with patch('flahax.mix_sonneveld.plan_fertilizer_workflow', return_value=workflow):
            with self.assertRaisesRegex(DeliveryError, 'No rounded candidate'):
                calculate_batch({'sonneveld_batch': profile})
            stage.status = 'calculated'
            with self.assertRaisesRegex(DeliveryError, 'Rounded candidate changed'):
                calculate_batch({'sonneveld_batch': profile, 'selected_candidate': 'old'})
            with patch('flahax.mix_sonneveld.summarize_batch', return_value={}):
                self.assertEqual(
                    calculate_batch({'sonneveld_batch': profile})[
                        'selected_preparation_candidate'
                    ],
                    'original',
                )
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                'flahax.mix_sonneveld.calculate_batch',
                return_value={
                    'selected_preparation_candidate': 'original',
                    'volumetric_stocks': {'ph': 5.5},
                },
            ):
                root = Path(directory)
                profile_file = root / 'input.json'
                profile_file.write_text(json.dumps(profile), encoding='utf-8')
                term = ReviewTerm(
                    ['ENTER'] * 4 + entry('Name') + entry('Review') + ['ENTER', 'ENTER']
                )
                code, lines = run_tui(
                    Store(root / 'store'),
                    None,
                    None,
                    term_factory=lambda: term,
                    sonneveld_batch=str(profile_file),
                )
                self.assertEqual((code, lines), (1, ['Stopped; nothing saved.']))
