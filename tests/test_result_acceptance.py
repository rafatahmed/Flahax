# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Exact-result consent and saved-input drift regression witnesses (#179)."""

from copy import deepcopy
import tempfile
import unittest
from unittest.mock import patch

from flahax import load_library, plan_fertilizer_workflow, VolumeLitres, summarize_batch
from flahax.canonical_result import seal_summary
from flahax.delivery_contracts import DeliveryError
from flahax.result_acceptance import accept_result, verify_acceptance, save_result, load_result
from flahax.mix_store import Store, bind_session, verify_session, check_saved_state
from flahax.mix_cli import options_for, check_session
from flahax.mix_store import migrate_session
from flahax.batch_cli import render_saved_result
from tests.test_mix_cli import GOOD_SESSION


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        product = next(p for p in load_library()['salts'] if p['name'] == 'Potassium Nitrate')
        workflow = plan_fertilizer_workflow(
            [product], {'K': 38.672}, {}, 6, final_volume=VolumeLitres(100)
        )
        self.summary = summarize_batch(workflow, [product], title='Witness', water_label='Zero')
        self.acceptance = accept_result(self.summary, actor='Owner', reason='Review proposal')

    def test_roundtrip_preserves_all_guards_and_is_detached(self):
        import hashlib
        import json

        content = {k: v for k, v in self.summary.items() if k != 'export_identity'}
        expected = hashlib.sha256(
            json.dumps(content, sort_keys=True, separators=(',', ':'), allow_nan=False).encode(
                'utf-8'
            )
        ).hexdigest()
        self.assertEqual(self.acceptance['export_sha256'], expected)
        before = deepcopy(self.summary)
        verify_acceptance(self.summary, self.acceptance)
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            record = save_result(self.summary, self.acceptance)
            store.save('results', 'witness', record)
            payload = load_result(store.load('results', 'witness'))
            self.assertEqual(payload['summary'], self.summary)
            self.assertEqual(payload['acceptance'], self.acceptance)
            self.assertIn('summary.json', render_saved_result(record))
            payload['summary']['status'] = 'invented'
        self.assertEqual(self.summary, before)
        self.assertEqual(load_result(save_result(self.summary))['acceptance'], None)

    def test_changed_grams_inputs_source_evidence_invalidate_even_resealed_result(self):
        variants = []
        for key in ('input_sha256', 'source_sha256', 'state_sha256', 'result_id'):
            s = deepcopy(self.summary)
            s['calculation_identity'][key] = 'changed'
            variants.append(s)
        s = deepcopy(self.summary)
        s['formulation']['salts'][0]['gramsPerLitre'] *= 2
        variants.append(s)
        s = deepcopy(self.summary)
        s['warnings'].append('new evidence')
        variants.append(s)
        for value in variants:
            with self.subTest(value=value['calculation_identity']):
                with self.assertRaises(DeliveryError):
                    verify_acceptance(value, self.acceptance)
                with self.assertRaises(DeliveryError):
                    verify_acceptance(seal_summary(value), self.acceptance)

    def test_zero_and_unassessed_remain_unwaived(self):
        product = next(p for p in load_library()['salts'] if p['name'] == 'Potassium Nitrate')
        workflow = plan_fertilizer_workflow(
            [product], {'K': 0}, {'K': 1}, 6, final_volume=VolumeLitres(100)
        )
        summary = summarize_batch(workflow, [product], title='Zero', water_label='Water')
        self.assertEqual(summary['status'], 'blocked')
        self.assertNotEqual(summary['statuses']['ec'], 'verified')
        before = deepcopy(summary)
        verify_acceptance(summary, accept_result(summary, actor='Owner', reason='Reviewed'))
        self.assertEqual(summary, before)
        self.assertEqual(summary['status'], 'blocked')

    def test_malformed_and_legacy_records_rejected(self):
        for summary in (
            None,
            {},
            {'calculation_identity': {'status': 'legacy_unverified'}},
            {'calculation_identity': 'malformed'},
        ):
            with self.assertRaises(DeliveryError):
                accept_result(summary, actor='Owner', reason='Reviewed')
        for actor, reason in [('', 'x'), ('x', None), (False, 'x')]:
            with self.assertRaises(DeliveryError):
                accept_result(self.summary, actor=actor, reason=reason)
        for record in (
            None,
            {},
            {**self.acceptance, 'schema_version': True},
            {**self.acceptance, 'scope': 'waive_limits'},
            {**self.acceptance, 'actor': ''},
            {**self.acceptance, 'recorded_at': 'bad'},
            {**self.acceptance, 'recorded_at': '2026-10-27'},
        ):
            with self.assertRaises(DeliveryError):
                verify_acceptance(self.summary, record)
        good = save_result(self.summary)
        for record in (
            None,
            {},
            {**good, 'schema_version': True},
            {**good, 'payload': []},
            {**good, 'sha256': 'changed'},
        ):
            with self.assertRaises(DeliveryError):
                load_result(record)


class SavedSessionTests(unittest.TestCase):
    def test_legacy_remains_inputs_only_and_explicit_save_migrates(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            data = deepcopy(GOOD_SESSION)
            check_session(data, 'legacy')
            verify_session(store, data)
            self.assertNotIn('saved_state', data)
            store.save('sessions', 'legacy', data)
            saved = store.load('sessions', 'legacy')
            self.assertEqual(saved['saved_state']['schema_version'], 1)
            self.assertNotIn('acceptance', saved)
            self.assertEqual(bind_session(store, saved), saved)
            options_for(store, saved)

    def test_input_reference_and_source_drift(self):
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            store.save('waters', 'well', {'K': 1})
            store.save('formulas', 'own', {'K': 10})
            store.save('stores', 'own', [])
            store.save('acids', 'acid', {'formula': 'HNO3'})
            data = {
                **deepcopy(GOOD_SESSION),
                'water': 'well',
                'formula': 'own',
                'store': 'own',
                'acids': ['acid'],
            }
            saved = bind_session(store, data)
            verify_session(store, saved)
            changed = deepcopy(saved)
            changed['ph'] = 7
            with self.assertRaises(DeliveryError):
                check_session(changed, 'changed')
            with patch('flahax.canonical_result._sources', return_value={}):
                with self.assertRaises(DeliveryError):
                    verify_session(store, saved)
            store.save('waters', 'well', {'K': 2})
            with self.assertRaises(DeliveryError):
                options_for(store, saved)
            with self.assertRaises(DeliveryError):
                bind_session(store, saved)
            migrated = migrate_session(store, {**saved, 'accepted': True})
            verify_session(store, migrated)
            self.assertNotIn('accepted', migrated)
            self.assertNotEqual(migrated['saved_state'], saved['saved_state'])

    def test_malformed_state_and_legacy_consent_rejected(self):
        with self.assertRaises(DeliveryError):
            migrate_session(None, [])
        for value in (None, {}, {'schema_version': 99}):
            with self.assertRaises(DeliveryError):
                check_saved_state({**GOOD_SESSION, 'saved_state': value})
        for key, value in [('ph', float('nan')), ('water_share', float('inf')), ('depth', True)]:
            with self.assertRaises(DeliveryError):
                check_session({**GOOD_SESSION, key: value}, 'malformed')
        for key in ('acceptance', 'accepted'):
            with self.assertRaises(DeliveryError):
                check_session({**GOOD_SESSION, key: True}, 'legacy')


class StoreBoundaryTests(unittest.TestCase):
    def test_missing_invalid_and_atomic_write_failure(self):
        from flahax.mix_store import slug

        with self.assertRaises(DeliveryError):
            slug('!!!')
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            with self.assertRaises(DeliveryError):
                store.path('unknown', 'x')
            with self.assertRaises(DeliveryError):
                store.load('waters', 'missing')
            store.save('waters', 'old', {'K': 1})
            with patch('flahax.mix_store.os.replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    store.save('waters', 'old', {'K': 2})
            self.assertEqual(store.load('waters', 'old'), {'K': 1})
            self.assertEqual(list(store.path('waters', 'old').parent.glob('*.tmp')), [])

    def test_public_session_load_rejects_drift_before_calculation(self):
        from flahax.mix_cli import main
        from pathlib import Path

        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            store.save('sessions', 'saved', GOOD_SESSION)
            with patch('flahax.mix_cli.run_batch') as run:
                with patch('flahax.canonical_result._sources', return_value={}):
                    lines = []
                    code = main(
                        ['sessions/saved', '--plain', '--output', str(Path(root) / 'out')],
                        ask=lambda _: self.fail('unexpected prompt'),
                        say=lines.append,
                        store=store,
                    )
                self.assertEqual(code, 1)
                run.assert_not_called()
                self.assertIn('saved inputs or model changed', lines[-1])
