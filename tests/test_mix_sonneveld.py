# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Regression for the complete Appendix I workflow through the mix wizard."""

import json
from pathlib import Path
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
from tests.test_sonneveld_appendix_i import COLUMN_D, COLUMN_E, GRADES, ppm


def appendix_profile():
    """Inputs for the source-water, fertilizer and preparation evidence in Appendix I."""
    formulas = (
        'Ca(NO3)2.4H2O',
        'NH4NO3',
        'MgSO4.7H2O',
        'KH2PO4',
        'KNO3',
        'K2SO4',
        '',
        'MnSO4.H2O',
        'ZnSO4.7H2O',
        'H3BO3',
        'CuSO4.5H2O',
        'Na2MoO4.2H2O',
    )
    products = [
        dict(
            id=name,
            name=name,
            formula=formula,
            elements=ppm({key: 100 * count / mass for key, count in ions.items()}),
        )
        for (name, mass, ions), formula in zip(GRADES, formulas, strict=True)
    ]
    products[6]['identityId'] = 'idn-disodium-iron-dtpa'
    stocks = ('copper sulfate pentahydrate', 'sodium molybdate dihydrate')
    dry = [p['name'] for p in products if p['name'] not in stocks]
    sulfate = 'sodium sulfate anhydrous'
    dry.append(sulfate)
    return {
        'title': 'Appendix I',
        'sonneveld': {
            'baseline_mmol_l': dict(
                COLUMN_D, Ca=2.75, Mg=1, K=6.5, N_NO3=10.75, N_NH4=1, S=1.5, B=0.020
            ),
            'adjustments_mmol_l': {'K': 2, 'N_NH4': 0.5, 'B': 0.010},
            'irrigation_ec_ds_m': 1.8,
            'root_zone_feedback': {
                'sample_id': 'illustrative-appendix-i',
                'sampled_on': '2026-11-17',
                'measured_mmol_l': {'K': 6.5, 'Ca': 10, 'B': 0.035},
                'guide_mmol_l': {'K': 8, 'Ca': 10, 'B': 0.050},
            },
        },
        'final_volume_litres': 1000,
        'target_ph': 5.5,
        'water': ppm(COLUMN_E),
        'equilibrium': {
            'water_totals': {'Ca+2': 0.001, 'Mg+2': 0.0004, 'SO4-2': 0.0003, 'CO3-2': 0.0022},
            'water_mass_kg': 1000,
            'water_analysis_id': 'Sonneveld Appendix I',
            'temperature_c': 25,
            'carbon_boundary': 'closed',
            'phases': [],
        },
        'salts': products,
        'alternative_products': [
            dict(
                id=sulfate,
                name=sulfate,
                formula='Na2SO4',
                elements=ppm({'Na': 200 / 142.04, 'S': 100 / 142.04}),
            )
        ],
        'maximum_concentrations': {'Na': 9.0},
        'ph_adjustment': {
            'products': [
                dict(
                    id='appendix-nitric-acid',
                    chemicalFormula='HNO3',
                    massFraction=0.65,
                    densityKgPerL=1.39,
                    source='Example grade',
                    revision='1',
                    recordedAt='2026-11-17T00:00:00Z',
                )
            ],
            'maximum_reagent_volume_litres': 1,
        },
        'volumetric_stocks': {
            'stock': {
                'basis': 'product_mass',
                'carrier': 'demineralized_water',
                'concentrations_g_l': dict.fromkeys(stocks, 1.0),
                'density_kg_l': dict.fromkeys(stocks, [0.998, 1.002]),
                'concentration_relative_error': 0.0003,
                'dose_error_ml': 0.05,
                'dose_decimals': 2,
            },
            'dry_mass_decimals': 3,
            'reagent_volume_decimals': 2,
            'nutrient_tolerance_percent': 0.1,
            'ph_tolerance': 0.002,
            'nutrient_ceiling_reserve': 0.05,
            'uncertainty': {
                'dry_product_error_g': {
                    name: 0.01 if name in dry[:6] or name == sulfate else 0.0001 for name in dry
                },
                'dry_product_assay_relative_error': dict.fromkeys(dry, 0.0002),
                'reagent_volume_error_ml': 0.025,
                'reagent_mass_fraction_bounds': [0.6499, 0.6501],
                'reagent_density_kg_l_bounds': [1.3899, 1.3901],
            },
        },
    }


class ReviewTerm(IdleTerm):
    """Wait for calculation before sending keys for the adoption prompt."""

    def read_key(self, timeout=0.1):
        if self.frames and any('Calculating the recipe' in row for row in self.frames[-1]):
            return None
        return super().read_key(timeout)


class SonneveldTuiTests(unittest.TestCase):
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
            self.assertLess(rounded['nutrient_bounds_mg_l']['Na'][1], 8.55)
            self.assertAlmostEqual(rounded['nutrient_bounds_mg_l']['Na'][1], 8.499246, places=6)
            self.assertTrue(rounded['ph_within_tolerance'])
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
