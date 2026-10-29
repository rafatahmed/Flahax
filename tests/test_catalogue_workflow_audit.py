# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Regression for #204: screening must not silently enable review-only solids."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch
import json
from pathlib import Path
from importlib.util import find_spec
import hashlib
import runpy
import sys
import tempfile

from tools.catalogue_workflow_audit import phase_screen, audit, fit, inspect_recipe

ROOT = Path(__file__).resolve().parents[1]


class PhaseAuditTests(unittest.TestCase):
    def test_failures_remain_visible_instead_of_becoming_passes(self):
        with (
            patch(
                'tools.catalogue_workflow_audit.phase_screen', side_effect=ValueError('chemistry')
            ),
            patch('tools.catalogue_workflow_audit.group_tanks', side_effect=ValueError('stock')),
        ):
            result = inspect_recipe({'salts': []}, [])
        self.assertEqual(result['chemistry_error'], {'code': 'ValueError', 'message': 'chemistry'})
        self.assertEqual(result['stock_error'], {'code': 'ValueError', 'message': 'stock'})
        self.assertNotIn('ec', result)

    def test_cli_records_input_hash_and_assumptions_without_optimizer(self):
        with tempfile.TemporaryDirectory() as directory:
            catalogue = Path(directory) / 'catalogue.json'
            output = Path(directory) / 'report.json'
            raw = b'{"salts": [], "formulas": []}'
            catalogue.write_bytes(raw)
            with patch.object(
                sys,
                'argv',
                ['audit', '--catalogue', str(catalogue), '--output', str(output), '--edta-only'],
            ):
                runpy.run_path(
                    str(ROOT / 'tools' / 'catalogue_workflow_audit.py'), run_name='__main__'
                )
            result = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(result['catalogue_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result['results'], [])
        self.assertTrue(result['edta_only'])
        self.assertIn('Pure ion-free water', result['assumptions'])
        self.assertEqual(len(result['runtime_revision']), 40)
        self.assertEqual(
            result['chemistry_sha256'],
            hashlib.sha256((ROOT / 'src/flahax/data/chemistry_25c.json').read_bytes()).hexdigest(),
        )

    @unittest.skipUnless(
        find_spec('numpy') and find_spec('scipy'),
        'optional audit optimizer dependencies are not installed',
    )
    def test_zero_target_and_solver_failure(self):
        products = [{'id': 1, 'name': 'coupled', 'elements': {'N_NO3': 10, 'Mg': 1}}]
        result = fit(products, {'N_NO3': 100, 'Mg': 0})
        self.assertAlmostEqual(result['minimum_error_pct'], 100)
        self.assertFalse(result['nutrient_pass'])
        self.assertEqual(result['salts'], [])
        self.assertEqual(result['ammonium_ceiling_mg_l'], 10)
        with patch(
            'scipy.optimize.linprog',
            return_value=SimpleNamespace(success=False, message='optimizer failure'),
        ):
            with self.assertRaisesRegex(ValueError, 'optimizer failure'):
                fit(products, {'N_NO3': 100})

    @unittest.skipUnless(
        find_spec('numpy') and find_spec('scipy'),
        'optional audit optimizer dependencies are not installed',
    )
    def test_unsupported_product_keeps_primary_and_alternative_separate(self):
        library = json.loads(
            (Path(__file__).parent / 'fixtures' / 'catalogue-audit-2026-10-29.json').read_text(
                encoding='utf-8'
            )
        )
        library['formulas'] = [f for f in library['formulas'] if f['name'] == 'DEFAULT']
        self.assertEqual(len(library['formulas']), 1)
        report = audit(library)
        row = report['results'][0]
        self.assertIn('chemistry_error', row['all_available'])
        self.assertIn('chemistry', row['chemistry_supported_alternative'])
        self.assertGreater(
            row['chemistry_supported_alternative']['minimum_error_pct'],
            row['all_available']['minimum_error_pct'],
        )
        self.assertTrue(report['chemistry_exclusions_for_alternatives'])

    def test_unqualified_phase_blocks_without_allocating_solids(self):
        state = SimpleNamespace(
            ph=5,
            ionic_strength=0.02,
            charge_balance=0,
            saturation_indices={'MnHPO4': 2.17},
            precipitated={},
            totals={},
        )
        with patch(
            'tools.catalogue_workflow_audit.calculate_equilibrium_ph', return_value=state
        ) as solve:
            result = phase_screen({'Mn+2': 1e-5})
        self.assertEqual(solve.call_args.kwargs['phases'], [])
        self.assertTrue(result['assessment']['blocks'])
        self.assertEqual(result['assessment']['review'][0][0], 'MnHPO4')
        self.assertEqual(result['precipitated'], {})

    def test_hard_phase_still_blocks(self):
        state = SimpleNamespace(
            ph=5,
            ionic_strength=0.02,
            charge_balance=0,
            saturation_indices={'Gypsum': 0.5},
            precipitated={},
            totals={},
        )
        with patch('tools.catalogue_workflow_audit.calculate_equilibrium_ph', return_value=state):
            result = phase_screen({})
        self.assertTrue(result['assessment']['blocks'])
        self.assertEqual(result['assessment']['blocking'], [('Gypsum', 0.5)])

    @unittest.skipUnless(
        find_spec('numpy') and find_spec('scipy'),
        'optional audit optimizer dependencies are not installed',
    )
    def test_updated_lettuce_recipe_keeps_review_and_stock_gaps(self):
        library = json.loads(
            (Path(__file__).parent / 'fixtures' / 'catalogue-audit-2026-10-29.json').read_text(
                encoding='utf-8'
            )
        )
        library['formulas'] = [
            f for f in library['formulas'] if f['name'] == 'Lettuce 2 (Howard Resh)'
        ]
        result = audit(library, edta_only=True)['results'][0]['all_available']
        self.assertTrue(result['nutrient_pass'])
        self.assertTrue(result['chemistry']['assessment']['blocks'])
        self.assertIn('MnHPO4', [x[0] for x in result['chemistry']['assessment']['review']])
        self.assertEqual(result['chemistry']['precipitated'], {})
        self.assertIn(result['ec']['status'], {'partial', 'not_supported'})
        self.assertIsNone(result['ec']['ec25_ms_cm'])
        missing = {r['product'] for r in result['stock_solubility'] if r['limit_g_per_l'] is None}
        self.assertTrue({'Iron EDTA', 'Mn EDTA', 'Copper EDTA', 'Zn EDTA'} <= missing)
