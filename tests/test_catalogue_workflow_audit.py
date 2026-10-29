# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
"""Regression for #204: screening must not silently enable review-only solids."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import json
from pathlib import Path

from tools.catalogue_workflow_audit import phase_screen, audit


class PhaseAuditTests(unittest.TestCase):
    def test_unqualified_phase_blocks_without_allocating_solids(self):
        state = SimpleNamespace(ph=5, ionic_strength=.02, charge_balance=0,
                                saturation_indices={'MnHPO4': 2.17}, precipitated={}, totals={})
        with patch('tools.catalogue_workflow_audit.calculate_equilibrium_ph',
                   return_value=state) as solve:
            result = phase_screen({'Mn+2': 1e-5})
        self.assertEqual(solve.call_args.kwargs['phases'], [])
        self.assertTrue(result['assessment']['blocks'])
        self.assertEqual(result['assessment']['review'][0][0], 'MnHPO4')
        self.assertEqual(result['precipitated'], {})

    def test_hard_phase_still_blocks(self):
        state = SimpleNamespace(ph=5, ionic_strength=.02, charge_balance=0,
                                saturation_indices={'Gypsum': .5}, precipitated={}, totals={})
        with patch('tools.catalogue_workflow_audit.calculate_equilibrium_ph', return_value=state):
            result = phase_screen({})
        self.assertTrue(result['assessment']['blocks'])
        self.assertEqual(result['assessment']['blocking'], [('Gypsum', .5)])

    def test_updated_lettuce_recipe_keeps_review_and_stock_gaps(self):
        library = json.loads((Path(__file__).parent / 'fixtures' /
                              'catalogue-audit-2026-10-29.json').read_text(encoding='utf-8'))
        library['formulas'] = [f for f in library['formulas']
                               if f['name'] == 'Lettuce 2 (Howard Resh)']
        result = audit(library, edta_only=True)['results'][0]['all_available']
        self.assertTrue(result['nutrient_pass'])
        self.assertTrue(result['chemistry']['assessment']['blocks'])
        self.assertIn('MnHPO4', [x[0] for x in result['chemistry']['assessment']['review']])
        self.assertEqual(result['chemistry']['precipitated'], {})
        self.assertIn(result['ec']['status'], {'partial', 'not_supported'})
        self.assertIsNone(result['ec']['ec25_ms_cm'])
        missing = {r['product'] for r in result['stock_solubility']
                   if r['limit_g_per_l'] is None}
        self.assertTrue({'Iron EDTA', 'Mn EDTA', 'Copper EDTA', 'Zn EDTA'} <= missing)
