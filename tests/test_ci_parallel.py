# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""CI partitions retain every public unittest case and its class fixtures."""

import contextlib
import io
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import ci_parallel

ROOT = Path(__file__).resolve().parents[1]


class ParallelRunnerTests(unittest.TestCase):
    def test_worker_timeout_is_reported_before_executor_cleanup(self):
        # Fault injection: a subprocess deadline, not a simulated chemistry result.
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'result.json'
            messages = io.StringIO()
            with (
                patch.object(
                    ci_parallel.subprocess,
                    'run',
                    side_effect=subprocess.TimeoutExpired('worker', 1800),
                ),
                contextlib.redirect_stdout(messages),
                self.assertRaises(subprocess.TimeoutExpired),
            ):
                ci_parallel.execute((output, ['fixture.Case.test_timeout']))
            self.assertIn('::error::', messages.getvalue())
            self.assertIn('fixture.Case.test_timeout', messages.getvalue())
            self.assertIn('1800', messages.getvalue())
            self.assertFalse(output.exists(), 'a timed-out worker cannot claim a test result')

    @unittest.skipUnless(importlib.util.find_spec('coverage'), 'coverage tooling unavailable')
    def test_measured_worker_retains_data_when_tests_construct_coverage(self):
        import coverage

        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            fixture = root / 'ci_measure_fixture.py'
            fixture.write_text(
                'import unittest\nimport coverage\nclass Probe(unittest.TestCase):\n'
                ' def test_probe(self):\n  coverage.Coverage()\n'
                '  marker = 123\n  self.assertEqual(marker, 123)\n',
                encoding='utf-8',
            )
            script = root / 'measure_worker.py'
            script.write_text(
                'import unittest\nfrom pathlib import Path\n'
                'from tools.ci_parallel import run\n'
                'raise SystemExit(run(Path(__file__).parent / "results", suite='
                'unittest.defaultTestLoader.loadTestsFromName("ci_measure_fixture"), '
                'weights={}))\n',
                encoding='utf-8',
            )
            config = root / 'coverage.ini'
            config.write_text(
                '[run]\nbranch = true\nparallel = true\npatch = subprocess\n'
                f'source = {folder}\n',
                encoding='utf-8',
            )
            data_file = root / '.coverage'
            env = dict(
                os.environ,
                COVERAGE_FILE=str(data_file),
                COVERAGE_RCFILE=str(config),
                PYTHONPATH=os.pathsep.join([folder, str(ROOT), str(ROOT / 'src')]),
            )
            result = subprocess.run(
                [sys.executable, '-m', 'coverage', 'run', str(script)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            c = coverage.Coverage(data_file=str(data_file), config_file=str(config))
            c.combine(data_paths=[folder], strict=True)
            data = c.get_data()
            measured = next(
                name for name in data.measured_files() if Path(name).name == fixture.name
            )
            self.assertIn(6, data.lines(measured), 'worker statement after Coverage() was lost')

    @unittest.skipUnless(importlib.util.find_spec('coverage'), 'coverage tooling unavailable')
    def test_worker_also_runs_without_an_active_measurement(self):
        import coverage

        # Fault injection: keep the outer test measurement alive while exposing
        # the public no-active-collector state to the worker launcher.
        with (
            tempfile.TemporaryDirectory(dir=ROOT) as folder,
            patch.object(coverage.Coverage, 'current', return_value=None),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = ci_parallel.execute(
                (
                    Path(folder) / 'result.json',
                    [
                        'tests.test_ci_parallel.ParallelRunnerTests.test_cli_help_and_default_dispatch'
                    ],
                )
            )
            self.assertTrue(result['passed'])

    def test_collection_retains_scientific_regressions(self):
        ids = [case.id() for case in ci_parallel.flatten(ci_parallel.collect())]
        self.assertIn(
            'tests.test_ratio_allocation_reliability.AllocationReliabilityTests.test_feasible_1_0',
            ids,
        )
        self.assertIn(
            'tests.test_ratio_solver_stress.RefinementBudgetTests.test_below_limit_samples_do_not_hide_exhausted_refinement',
            ids,
        )
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse(any('unittest.loader._FailedTest' in name for name in ids))

    def test_gate_refuses_missing_duplicate_and_inconsistent_test_partitions(self):
        from tools.ci_coverage import validate_partitions

        records = []
        for platform in ('Linux', 'Windows'):
            for index, selected in enumerate((['a'], ['b'])):
                records.append(
                    (
                        {'platform': platform},
                        dict(
                            shard_count=2,
                            shard_index=index,
                            inventory=['a', 'b'],
                            test_ids=selected,
                            tests=1,
                        ),
                    )
                )
        validate_partitions(records, ['a', 'b'])
        import copy

        for mode in ('missing', 'duplicate', 'inventory', 'selection', 'count'):
            changed = copy.deepcopy(records)
            if mode == 'missing':
                changed.pop()
            elif mode == 'duplicate':
                changed[1] = changed[0]
            elif mode == 'inventory':
                changed[0][1]['inventory'] = ['a']
            elif mode == 'selection':
                changed[1][1]['test_ids'] = ['a']
            else:
                changed[0][1]['tests'] = 2
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                validate_partitions(changed, ['a', 'b'])

    def test_real_processes_retain_pass_failure_skip_and_complete_ids(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            (root / 'ci_fixture.py').write_text(
                'import unittest\n'
                'class Pass(unittest.TestCase):\n'
                ' def test_pass(self): self.assertEqual(2 + 2, 4)\n'
                'class Fail(unittest.TestCase):\n'
                ' def test_fail(self): self.fail("intentional fixture failure")\n'
                'class Skip(unittest.TestCase):\n'
                ' @unittest.skip("fixture skip")\n'
                ' def test_skip(self): pass\n',
                encoding='utf-8',
            )
            import sys

            sys.path.insert(0, folder)
            try:
                suite = unittest.defaultTestLoader.loadTestsFromName('ci_fixture')
                with (
                    patch.dict(
                        os.environ,
                        PYTHONPATH=os.pathsep.join([folder, str(ROOT), str(ROOT / 'src')]),
                    ),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    code = ci_parallel.run(root / 'out', 0, 1, 2, suite=suite, weights={})
                result = json.loads((root / 'out/tests.json').read_text())
                self.assertEqual(code, 1)
                self.assertEqual(result['tests'], 3)
                self.assertEqual(result['failures'], 1)
                self.assertEqual(len(result['skipped']), 1)
                self.assertEqual(
                    sorted(result['test_ids']),
                    [
                        'ci_fixture.Fail.test_fail',
                        'ci_fixture.Pass.test_pass',
                        'ci_fixture.Skip.test_skip',
                    ],
                )
                passing = unittest.defaultTestLoader.loadTestsFromName('ci_fixture.Pass')
                with (
                    patch.dict(
                        os.environ,
                        PYTHONPATH=os.pathsep.join([folder, str(ROOT), str(ROOT / 'src')]),
                    ),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(ci_parallel.run(root / 'pass', suite=passing), 0)
                    with self.assertRaisesRegex(ValueError, 'inventory differs'):
                        ci_parallel.execute((root / 'wrong.json', ['ci_fixture.Missing.test_no']))
            finally:
                sys.path.remove(folder)
                sys.modules.pop('ci_fixture', None)

    def test_invalid_empty_and_duplicate_requests_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            for index, count, workers in ((-1, 2, 1), (2, 2, 1), (0, 0, 1), (0, 1, 0)):
                with self.assertRaisesRegex(ValueError, 'invalid shard'):
                    ci_parallel.run(Path(folder), index, count, workers)
            case = unittest.FunctionTestCase(lambda: None)
            for suite in (unittest.TestSuite(), unittest.TestSuite([case, case])):
                with self.assertRaisesRegex(ValueError, 'empty or duplicate'):
                    ci_parallel.run(Path(folder), suite=suite, weights={})
            with self.assertRaisesRegex(ValueError, 'empty or duplicate'):
                ci_parallel.run(Path(folder), 1, 2, suite=unittest.TestSuite([case]), weights={})

    def test_module_fixture_is_never_split(self):
        import sys

        class One(unittest.TestCase):
            def test_one(self):
                pass

        class Two(unittest.TestCase):
            def test_two(self):
                pass

        suite = unittest.TestSuite([One('test_one'), Two('test_two')])
        with patch.object(sys.modules[__name__], 'setUpModule', lambda: None, create=True):
            shards = ci_parallel.partition(suite, {}, 2)
        self.assertEqual(sorted(len(shard) for shard in shards), [0, 1])
        self.assertEqual(len(next(shard for shard in shards if shard)[0]), 2)

    def test_cli_help_and_default_dispatch(self):
        import sys
        import runpy

        with (
            patch.object(sys, 'argv', ['runner', '--help']),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(SystemExit) as caught:
                runpy.run_path(str(Path(ci_parallel.__file__)), run_name='__main__')
        self.assertEqual(caught.exception.code, 0)
        # Fault injection: command dispatch preserves an unsuccessful runner result.
        with (
            patch.object(sys, 'argv', ['runner', '--output', 'out']),
            patch.object(ci_parallel, 'run', return_value=1),
        ):
            self.assertEqual(ci_parallel.main(), 1)

    def test_partition_covers_every_case_once_and_preserves_class_fixtures(self):
        class SharedFixture(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                cls.shared = True

            def test_a(self):
                self.assertTrue(self.shared)

            def test_b(self):
                self.assertTrue(self.shared)

        class Independent(unittest.TestCase):
            def test_a(self):
                pass

            def test_b(self):
                pass

        suite = unittest.TestSuite(
            unittest.defaultTestLoader.loadTestsFromTestCase(cls)
            for cls in (SharedFixture, Independent)
        )
        weights = {
            SharedFixture.__module__ + '.' + SharedFixture.__qualname__: 300,
            Independent.__module__ + '.' + Independent.__qualname__: 300,
        }
        groups = ci_parallel.partition(suite, weights, 2)
        ids = [case for shard in groups for group in shard for case in group]
        self.assertEqual(len(ids), 4)
        self.assertEqual(len(set(ids)), 4)
        shared = [group for shard in groups for group in shard if 'SharedFixture' in group[0]]
        self.assertEqual(len(shared), 1)
        self.assertEqual(len(shared[0]), 2)
        self.assertTrue(all(groups))
        independent = [group for shard in groups for group in shard if 'Independent' in group[0]]
        self.assertEqual([len(group) for group in independent], [1, 1])
