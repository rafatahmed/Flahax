# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Benchmark harness checks separate actual numerical comparisons from injected failures."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from benchmarks import cases, performance
from tools import benchmark_baseline as baseline


class BenchmarkHarnessTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("scipy"), "optional scipy dependency")
    def test_real_numerical_and_chemistry_scorecards(self):
        self.assertTrue(baseline.kernel()['passes'])
        chemistry = baseline.chemistry()
        self.assertGreater(chemistry['attempted'], 0)
        self.assertEqual(chemistry['attempted'], len(chemistry['cases']))
        # Failed model comparisons are retained, not relabeled as reference agreement.
        self.assertEqual(chemistry['passed'], sum(c['passes'] for c in chemistry['cases']))
        library = __import__('flahax').load_library()
        with patch(
            'flahax.load_library', return_value={**library, 'formulas': library['formulas'][:1]}
        ):
            report = baseline.formulation()
        self.assertEqual(report['attempted'], 2)
        self.assertEqual(len(report['cases']), 2)
        with (
            patch('flahax.recommend', side_effect=RuntimeError('synthetic solver failure')),
            patch(
                'flahax.load_library',
                return_value={**library, 'formulas': library['formulas'][:1]},
            ),
        ):
            report = baseline.formulation()
        self.assertEqual(len(report['failures']), 2)
        with patch('flahax.engine.nnls', side_effect=RuntimeError('injected')):
            self.assertFalse(baseline.kernel()['passes'])
        with patch.object(baseline, 'solve_fixture', side_effect=RuntimeError('injected')):
            report = baseline.chemistry()
        self.assertFalse(report['passes'])
        self.assertTrue(all(not c['passes'] for c in report['cases']))

    def test_hash_and_complementarity_failures(self):
        with (
            patch.object(cases, 'digest', return_value='changed'),
            self.assertRaisesRegex(ValueError, 'hash mismatch'),
        ):
            cases.read_fixture('products/mixed_products')
        data = cases.read_fixture('phases/calcite')
        result, acid = cases.solve_fixture(data)
        cases.require_chemistry(data, result, acid)
        with (
            patch.object(
                cases,
                'evaluate_chemistry',
                return_value={
                    'passes': False,
                    'checks': [{'quantity': 'injected', 'passes': False}],
                },
            ),
            self.assertRaisesRegex(ValueError, 'injected'),
        ):
            cases.require_chemistry(data, result)
        # An absent phase is a supported scorer boundary, independent of solver behavior.
        data['phases'].append('absent')
        data['selected_rows'][-1]['absent'] = 0
        report = cases.evaluate_chemistry(data, result)
        self.assertFalse(
            any(c['quantity'] == 'phase_complementarity:absent' for c in report['checks'])
        )

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "optional scipy dependency")
    def test_asv_lifecycle_and_rejecting_corrupt_results(self):
        performance.Import().time_fresh_process_import()
        obj = performance.Library()
        obj.teardown()
        obj.setup()
        obj.time_load_library()
        obj.teardown()
        obj.result = {'salts': []}
        with self.assertRaisesRegex(ValueError, 'Empty'):
            obj.teardown()
        with (
            patch('flahax.load_library', return_value={'salts': []}),
            self.assertRaisesRegex(ValueError, 'Empty'),
        ):
            performance.Library().setup()
        obj = performance.Kernel()
        for name in cases.NNLS_CASES:
            obj.setup(name)
            obj.time_nnls(name)
            obj.teardown(name)
        obj.result = [0] * len(obj.result)
        with self.assertRaisesRegex(ValueError, 'objective'):
            obj.teardown(name)
        obj = performance.Formulation()
        obj.setup(0)
        obj.time_recommend(0)
        self.assertIs(obj.peakmem_recommend(0), obj.result)
        obj.teardown(0)
        obj.result = {'salts': []}
        with self.assertRaisesRegex(ValueError, 'target tolerance'):
            obj.teardown(0)
        obj = performance.Equilibrium()
        fixture = 'products/mixed_products'
        obj.setup(fixture)
        obj.time_solve(fixture)
        self.assertIs(obj.peakmem_solve(fixture), obj.result)
        self.assertGreaterEqual(obj.track_final_state_iterations(fixture), 0)
        self.assertGreater(obj.track_search_solves(fixture), 0)
        from flahax import aqueous_model

        original = aqueous_model.solve
        with (
            patch.object(obj, 'solve', side_effect=RuntimeError('injected')),
            self.assertRaises(RuntimeError),
        ):
            obj.track_search_solves(fixture)
        self.assertIs(aqueous_model.solve, original)
        obj = performance.IrrigationEC()
        obj.setup()
        obj.time_experimental_ec()
        obj.teardown()
        obj.result = SimpleNamespace(status='unavailable', ec25_ms_cm=None)
        with self.assertRaisesRegex(ValueError, 'regression'):
            obj.teardown()
        obj = performance.Delivery()
        for present in (False, True):
            paths = [p for p in sys.path if p != str(cases.ROOT)]
            if present:
                paths.append(str(cases.ROOT))
            with patch.object(sys, 'path', paths):
                obj.setup()
        obj.time_composed_delivery_example()
        obj.teardown()
        obj.result = {
            'workflow': SimpleNamespace(stages={'nitric': SimpleNamespace(status='blocked')})
        }
        with self.assertRaisesRegex(ValueError, 'did not complete'):
            obj.teardown()

    def test_cli_records_errors_and_manifest_mismatch(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            output = Path(folder) / 'result.json'
            with (
                patch.object(baseline, 'kernel', side_effect=RuntimeError('injected')),
                patch.object(baseline, 'formulation', return_value={'passes': True}),
                patch.object(baseline, 'chemistry', return_value={'passes': True}),
            ):
                self.assertEqual(baseline.main(['--output', str(output)]), 1)
            self.assertEqual(json.loads(output.read_text())['kernel']['error'], 'RuntimeError')
            self.assertEqual(
                baseline.main(
                    [
                        '--output',
                        str(output),
                        '--metadata-only',
                        '--asv-results',
                        folder,
                        '--compare-inputs',
                        str(output),
                    ]
                ),
                0,
            )
            previous = json.loads(output.read_text())
            previous['metadata']['input_manifest_sha256'] = 'stale'
            output.write_text(json.dumps(previous))
            self.assertEqual(
                baseline.main(
                    ['--output', str(output), '--metadata-only', '--compare-inputs', str(output)]
                ),
                1,
            )
            history = Path(folder) / 'history.csv'
            history.write_text(
                'engine,scenario,formula,runtime_s,err_pct,err_mg\nx,w,f,1,0,0\nx,w,f,2,0,0\n'
            )
            with self.assertRaisesRegex(ValueError, 'Inconsistent'):
                baseline.historical(history)

    def test_provenance_records_missing_optional_package_without_inventing_version(self):
        packages = ('asv', 'scipy', 'numpy', 'asv-runner')
        for missing in packages:

            def version(name):
                if name == missing:
                    raise baseline.importlib.metadata.PackageNotFoundError(name)
                return 'test-version-' + name

            with (
                self.subTest(missing=missing),
                patch.object(
                    baseline.importlib.metadata, 'version', side_effect=version
                ) as lookup,
            ):
                report = baseline.provenance()
                self.assertEqual(
                    report['tool_versions'],
                    {
                        name: None if name == missing else 'test-version-' + name
                        for name in packages
                    },
                )
                self.assertEqual([call.args[0] for call in lookup.call_args_list], list(packages))
                self.assertTrue(report['input_sha256'])

    def test_installed_source_provenance_keeps_explicit_origin(self):
        import flahax

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'flahax'
            source.mkdir()
            (source / '__init__.py').write_text('')
            with patch.object(flahax, '__file__', str(source / '__init__.py')):
                report = baseline.provenance()
            self.assertFalse(report['source_checkout_import'])
            self.assertIn('installed/flahax/__init__.py', report['input_sha256'])
