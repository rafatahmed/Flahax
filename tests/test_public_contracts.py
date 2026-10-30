# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Real subprocess and top-level API contract checks (#181)."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import flahax
from flahax.planning_cli import recommend_request, execute, serializable
from flahax.canonical_result import verify_summary

ROOT = Path(__file__).resolve().parents[1]


class PublicContractTests(unittest.TestCase):
    def setUp(self):
        self.product = next(
            s for s in flahax.load_library()['salts'] if s['name'] == 'Potassium Nitrate'
        )
        self.request = dict(salts=[self.product], targets={'K': 100}, water={})

    def cli(self, command, payload=None, *args):
        return subprocess.run(
            [sys.executable, '-m', 'flahax', command, *args],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')),
            cwd=ROOT,
            timeout=90,
        )

    def test_recommend_preserves_zero_maximum_and_api_options(self):
        for options in (
            {'maximum_concentrations': {'K': 0}},
            {'maximum_concentrations': {'K': 50}, 'ridge': 0.0},
            {'max_ammonium_fraction': 0.1},
            {'allow_ions': ['Cl'], 'allow_carbonates': False},
        ):
            with self.subTest(options=options):
                request = {**self.request, **options}
                result = self.cli('recommend', request)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = flahax.recommend([self.product], {'K': 100}, {}, **options)
                self.assertEqual(json.loads(result.stdout), serializable(expected))
                if options.get('maximum_concentrations') == {'K': 0}:
                    self.assertFalse(expected['feasible'])
                    self.assertEqual(expected['salts'], [])

    def test_legacy_aliases_and_strict_permissions(self):
        old = recommend_request({**self.request, 'allowIons': ['Cl'], 'allowCarbonates': False})
        new = recommend_request({**self.request, 'allow_ions': ['Cl'], 'allow_carbonates': False})
        self.assertEqual(old, new)
        for option in (
            {'ridge': 0.001},
            {'maximum_concentrations': []},
            {'allowCarbonates': 'false'},
            {'allowIons': [[]]},
            {'allowIons': [], 'allow_ions': []},
            {'allowCarbonates': False, 'allow_carbonates': False},
            {'maximumConcentrations': {'K': 0}},
            {'maxium_concentrations': {'K': 0}},
        ):
            with self.subTest(option=option):
                result = self.cli('recommend', {**self.request, **option})
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, '')
                self.assertNotIn('Traceback', result.stderr)

    def test_workflow_roundtrip_keeps_canonical_state_and_missing_input_statuses(self):
        request = dict(
            self.request, target_ph=6, final_volume_litres=100, maximum_concentrations={'K': 0}
        )
        result = self.cli('workflow', request)
        self.assertEqual(result.returncode, 0, result.stderr)
        workflow = execute('workflow', request)
        actual = json.loads(result.stdout)
        self.assertEqual(actual, serializable(workflow))
        snapshot = flahax.CanonicalResult(actual['canonical_result']['payload'])
        self.assertEqual(snapshot.result_id, workflow.canonical_result.result_id)
        self.assertFalse(actual['recommendation']['feasible'])
        self.assertEqual(actual['stages']['chemistry']['status'], 'needs_input')

    def test_top_level_archive_exports_preserve_qualifications(self):
        for name in (
            'CanonicalResult',
            'accept_result',
            'verify_acceptance',
            'save_result',
            'load_result',
        ):
            self.assertIn(name, flahax.__all__)
            self.assertTrue(callable(getattr(flahax, name)))
        workflow = flahax.plan_fertilizer_workflow(
            [self.product], {'K': 100}, {}, 6, final_volume=flahax.VolumeLitres(100)
        )
        summary = flahax.summarize_batch(
            workflow, [self.product], title='Witness', water_label='Zero'
        )
        consent = flahax.accept_result(summary, actor='Owner', reason='Proposal reviewed')
        payload = flahax.load_result(flahax.save_result(summary, consent))
        flahax.verify_acceptance(payload['summary'], payload['acceptance'])
        self.assertEqual(summary, payload['summary'])

    def test_batch_file_contract_preserves_hard_zero_and_output_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            products, targets = root / 'products.json', root / 'targets.json'
            products.write_text(json.dumps([self.product]), encoding='utf-8')
            targets.write_text(json.dumps({'K': 100}), encoding='utf-8')
            result = self.cli(
                'batch',
                None,
                '--targets',
                str(targets),
                '--products',
                str(products),
                '--water',
                'ro',
                '--limit',
                'K=0',
                '--output',
                str(root / 'out'),
            )
            # Owner decision 2026-10-30: with the owner catalogue's acid reagents the run ends
            # "requires review" (exit 0) and reports the K shortfall the zero maximum forces.
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((root / 'out/summary.json').read_text(encoding='utf-8'))
            verify_summary(summary)
            self.assertEqual(summary['status'], 'requires_review')
            self.assertEqual(summary['formulation']['salts'], [])
            k = next(r for r in summary['formulation']['rows'] if r['symbol'] == 'K')
            self.assertEqual((k['target'], k['final'], k['deltaPct']), (100.0, 0.0, -100.0))
            reference = summary['calculation_identity']['result_id']
            for name in ('report.html', 'batch-sheet.html'):
                self.assertIn(reference, (root / 'out' / name).read_text(encoding='utf-8'))
            targets.write_text('{broken', encoding='utf-8')
            bad = self.cli(
                'batch',
                None,
                '--targets',
                str(targets),
                '--water',
                'ro',
                '--output',
                str(root / 'bad'),
            )
            self.assertEqual(bad.returncode, 1)
            self.assertNotIn('Traceback', bad.stderr)
            self.assertFalse((root / 'bad').exists())

    def test_plain_mix_subprocess_replays_bound_session_without_waiving_limits(self):
        from flahax.mix_store import Store
        from tests.test_mix_cli import GOOD_SESSION

        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            store.save('stores', 'supplied', [self.product])
            store.save('formulas', 'custom', {'K': 100})
            session = {
                **GOOD_SESSION,
                'store': 'supplied',
                'formula': 'custom',
                'limits': {'K': 0},
                'formula_title': 'Hard zero',
            }
            path = store.save('sessions', 'zero', session)
            result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'flahax',
                    'mix',
                    '--plain',
                    str(path),
                    '--output',
                    str(Path(tmp) / 'out'),
                ],
                input='',
                capture_output=True,
                text=True,
                cwd=ROOT,
                env=dict(os.environ, PYTHONPATH=str(ROOT / 'src'), FLAHAX_HOME=tmp),
                timeout=90,
            )
            # Owner decision 2026-10-30: "requires review" (exit 0) with the forced K shortfall.
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            summary = json.loads((Path(tmp) / 'out/summary.json').read_text(encoding='utf-8'))
            verify_summary(summary)
            self.assertEqual(summary['formulation']['salts'], [])
            self.assertEqual(summary['status'], 'requires_review')
            k = next(r for r in summary['formulation']['rows'] if r['symbol'] == 'K')
            self.assertEqual((k['target'], k['final'], k['deltaPct']), (100.0, 0.0, -100.0))
            self.assertNotIn('  [ ] ', result.stdout)
            self.assertIn(summary['calculation_identity']['result_id'], result.stdout)

    def test_ec_and_size_subprocesses_preserve_scope_and_volume(self):
        ec = self.cli(
            'ec',
            dict(doses_g_per_litre={'Ultrasol K Plus': 0.5}, water_ec_ms_cm=0.5, acid_added=True),
        )
        self.assertEqual(ec.returncode, 0, ec.stderr)
        result = json.loads(ec.stdout)
        self.assertIsNone(result['ec_ms_cm'])
        self.assertEqual(result['error_code'], 'acid_reaction_model_unavailable')
        size = self.cli(
            'size',
            dict(
                duration_hours=2,
                equipment_type='dosing_pump',
                final_volume_litres=10000,
                channels={'A': dict(final_litres_per_stock_litre=100, available_stock_litres=100)},
            ),
        )
        self.assertEqual(size.returncode, 0, size.stderr)
        result = json.loads(size.stdout)
        self.assertEqual(result['final_flow_litres_per_hour'], 10000 / 2)
        self.assertEqual(result['carrier_water_litres'], 10000 - 100)
        self.assertIsNone(result['selected_model'])
        for command in ('workflow', 'ec', 'size'):
            invalid = self.cli(command, [])
            self.assertEqual(invalid.returncode, 1)
            self.assertNotIn('Traceback', invalid.stderr)

    def test_all_documented_commands_offer_help(self):
        for command in ('recommend', 'workflow', 'ec', 'size', 'batch', 'mix'):
            with self.subTest(command=command):
                result = self.cli(command, None, '--help')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('usage:', result.stdout)


class RecommendationAdapterTests(unittest.TestCase):
    def test_strict_input_shapes_and_alias_collisions(self):
        product = next(
            s for s in flahax.load_library()['salts'] if s['name'] == 'Potassium Nitrate'
        )
        base = dict(salts=[product], targets={'K': 100}, water={})
        for bad in (
            None,
            [],
            {},
            {**base, 'water': []},
            {**base, 'maximum_concentrations': []},
            {**base, 'allow_ions': False},
            {**base, 'allow_ions': [[]]},
            {**base, 'allow_carbonates': 'false'},
            {**base, 'unknown': 1},
            {**base, 'allowIons': [], 'allow_ions': []},
            {**base, 'allowCarbonates': False, 'allow_carbonates': False},
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(flahax.DeliveryError):
                    recommend_request(bad)
        request = {
            **base,
            'allowIons': ['Cl'],
            'allowCarbonates': False,
            'maximum_concentrations': {'K': 0},
            'max_ammonium_fraction': None,
            'ridge': 0,
        }
        before = json.dumps(request, sort_keys=True)
        result = recommend_request(request)
        self.assertFalse(result['feasible'])
        self.assertEqual(result['salts'], [])
        self.assertEqual(before, json.dumps(request, sort_keys=True))
        self.assertTrue(recommend_request(base)['feasible'])
