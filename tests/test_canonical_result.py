# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent recomputation and immutable result/export contract witnesses."""

import copy
from dataclasses import FrozenInstanceError
from fractions import Fraction
import json
import unittest
from unittest.mock import patch

from flahax import load_library, plan_fertilizer_workflow, VolumeLitres, summarize_batch
from flahax.delivery_contracts import DeliveryError
from flahax.canonical_result import CanonicalResult, seal_summary, verify_summary, result_statuses
from flahax.grower_report import render_report, render_batch_sheet
from flahax.grower_sheet import render_mix_sheet
from flahax.batch_cli import render


class CanonicalResultTests(unittest.TestCase):
    def setUp(self):
        self.product = next(p for p in load_library()['salts'] if p['name'] == 'Potassium Nitrate')
        self.workflow = plan_fertilizer_workflow(
            [self.product], {'K': 38.672}, {}, 6, final_volume=VolumeLitres(100)
        )

    def summary(self):
        return summarize_batch(self.workflow, [self.product], title='Witness', water_label='Zero')

    def test_immutable_snapshot_and_detached_copy(self):
        record = self.workflow.canonical_result
        before = record.result_id
        with self.assertRaises(FrozenInstanceError):
            record.payload = '{}'
        exported = record.to_dict()
        exported['workflow']['recommendation']['salts'][0]['gramsPerLitre'] = 500
        self.assertEqual(before, record.result_id)
        self.assertNotEqual(exported, record.to_dict())
        self.assertIn('chemistry_25c.json', ''.join(record.to_dict()['sources']))

    def test_changed_dose_and_product_are_rejected(self):
        self.workflow.recommendation['salts'][0]['gramsPerLitre'] *= 2
        with self.assertRaises(DeliveryError):
            self.summary()
        self.setUp()
        self.product['elements']['K'] *= 2
        with self.assertRaises(DeliveryError):
            self.summary()

    def test_source_change_and_duplicate_products_rejected(self):
        with patch('flahax.canonical_result._sources', return_value={}):
            with self.assertRaises(DeliveryError):
                self.summary()
        with self.assertRaises(DeliveryError):
            self.workflow.canonical_result.verify(self.workflow, [self.product, self.product])

    def test_independent_mass_assay_and_output_identity(self):
        s = self.summary()
        salt = s['formulation']['salts'][0]
        dose = Fraction(str(salt['gramsPerLitre']))
        self.assertAlmostEqual(salt['gramsPerBatch'], float(dose * 100), places=12)
        for row in s['formulation']['rows']:
            oracle = dose * Fraction(str(self.product['elements'][row['symbol']])) * 10
            self.assertAlmostEqual(row['final'], float(oracle), places=12)
        for fn in (render_report, render_batch_sheet, render_mix_sheet):
            self.assertIn('Witness', fn(s))
            self.assertIn(self.workflow.canonical_result.result_id, fn(s))
        exported = json.loads(render(s)['summary.json'])
        self.assertEqual(exported['export_identity'], s['export_identity'])
        self.assertEqual(
            exported['calculation_identity']['result_id'], self.workflow.canonical_result.result_id
        )
        self.assertEqual(s['statuses']['delivery'], 'not_validated')
        self.assertEqual(s['statuses']['physical'], 'not_validated')
        self.assertEqual(s['statuses']['overall'], s['status'])

    def test_mutated_exports_fail_all_renderers(self):
        s = self.summary()
        missing = copy.deepcopy(s)
        del missing['export_identity']
        with self.assertRaises(DeliveryError):
            verify_summary(missing)
        s['formulation']['salts'][0]['gramsPerBatch'] *= 2
        for fn in (verify_summary, render_report, render_batch_sheet, render_mix_sheet, render):
            with self.subTest(renderer=fn.__name__), self.assertRaises(DeliveryError):
                fn(s)

    def test_legacy_and_block_precedence_remain_explicit(self):
        self.workflow.canonical_result = None
        s = self.summary()
        self.assertEqual(s['calculation_identity']['status'], 'legacy_unverified')
        self.assertNotEqual(s['status'], 'ready')
        s['status'] = 'blocked'
        s['formulation']['feasible'] = False
        s['tanks']['available_tanks'] = 0
        statuses = result_statuses(s)
        self.assertEqual(statuses['formulation'], 'infeasible')
        self.assertEqual(statuses['overall'], 'blocked')
        self.assertEqual(statuses['stock'], 'blocked')
        verify_summary(seal_summary(s))
        verify_summary({})

    def test_phase_qualification_and_stock_limit_statuses(self):
        s = self.summary()
        for blocks, review, expected in (
            (True, [], 'blocked'),
            (False, ['condition-qualified'], 'requires_review'),
            (False, [], 'assessed'),
        ):
            s['chemistry'] = {'phase_assessment': {'blocks': blocks, 'review': review}}
            self.assertEqual(result_statuses(s)['phase'], expected)
        s['solubility'] = [{'status': 'exceeds'}]
        self.assertEqual(result_statuses(s)['stock'], 'blocked')
        from flahax.grower_report import result_reference

        self.assertIn('legacy unverified', result_reference({}))

    def test_nonfinite_diagnostics_keep_export_identity_on_json_roundtrip(self):
        summary = seal_summary({'diagnostics': [float('inf'), (float('-inf'), None)]})
        self.assertEqual(summary['diagnostics'][0], 'inf')
        verify_summary(json.loads(json.dumps(summary, allow_nan=False)))

    def test_normalization_and_stable_identity(self):
        from flahax.canonical_result import _json

        self.assertEqual(_json({'b': (1, 2), 'a': {3, 2}}), _json({'a': [2, 3], 'b': [1, 2]}))
        self.assertIn('nonfinite', _json(float('inf')))
        self.assertIn('callback', _json(result_statuses))

        class Model:
            def __call__(self):
                return None

        self.assertIn('Model', _json(Model()))
        a = CanonicalResult.capture(self.workflow, {'salts': [self.product]})
        b = CanonicalResult.capture(copy.deepcopy(self.workflow), {'salts': [self.product]})
        self.assertEqual(a.result_id, b.result_id)
