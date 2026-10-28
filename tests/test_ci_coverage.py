# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Synthetic native labels exercise provenance; actual tiny-program arcs exercise merging."""

import contextlib
import copy
import importlib.util
import io
import os
import runpy
from pathlib import Path
import sys
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import ci_coverage as ci
from tools.check_coverage import inventory


@unittest.skipUnless(importlib.util.find_spec('coverage'), 'coverage tooling unavailable')
class NativeCoverageTests(unittest.TestCase):
    def fixture(self, folder, *, complete=True):
        root = Path(folder)
        for name in ('src/flahax', 'tools', 'examples', 'benchmarks', 'docs/site'):
            (root / name).mkdir(parents=True)
        (root / 'src/flahax/model.py').write_text(
            'def choose(x):\n    if x:\n        return 1\n    return 2\n', encoding='utf-8'
        )
        (root / 'docs/site/conf.py').write_text('VALUE = 1\n', encoding='utf-8')
        (root / 'pyproject.toml').write_text(
            '[tool.coverage.run]\nbranch=true\nrelative_files=true\n'
            'source=["src/flahax", "docs/site"]\n'
            '[tool.coverage.report]\nexclude_lines=[]\npartial_branches=[]\n',
            encoding='utf-8',
        )
        current = dict(
            source_revision='a' * 40,
            files=inventory(root),
            inputs={'fixture': 'hash'},
            configuration_sha256=ci.digest(root / 'pyproject.toml'),
            run_id='1',
            run_attempt='1',
        )
        inputs = root / 'inputs'
        # Measuring a tiny program in subprocesses avoids replacing the outer test collector.
        script = """
import coverage, pathlib, runpy, sys
inputs = pathlib.Path(sys.argv[1])
for index, system in enumerate(('Linux', 'Windows', 'Darwin')):
    path = inputs / system
    path.mkdir(parents=True)
    c = coverage.Coverage(data_file=str(path / '.coverage'))
    c.start()
    ns = runpy.run_path('src/flahax/model.py')
    ns['choose'](index != 1 or sys.argv[2] == 'False')
    runpy.run_path('docs/site/conf.py')
    c.stop()
    c.save()
    c.json_report(morfs=[str(pathlib.Path(p)) for p in
                  ('src/flahax/model.py', 'docs/site/conf.py')],
                  outfile=str(path / 'coverage.json'))
"""
        subprocess.run(
            [sys.executable, '-c', script, str(inputs), str(complete)],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        for system in ci.PLATFORMS:
            path = inputs / system
            ci.write(path / 'manifest.json', dict(current, platform=system, python='3.13.9'))
            ci.write(
                path / 'tests.json', dict(tests=1, passed=True, failures=0, errors=0, skipped=[])
            )
            self.seal(path)
        return root, inputs, current

    def seal(self, path):
        ci.write(
            path / 'bundle.json',
            {
                n: ci.digest(path / n)
                for n in ('manifest.json', 'tests.json', '.coverage', 'coverage.json')
            },
        )

    def aggregate(self, root, inputs, current):
        with contextlib.chdir(root), patch.object(ci, 'identity', return_value=current):
            ci.aggregate(root, inputs, root / 'aggregate', current['source_revision'])

    def test_real_branch_union_and_xml_have_exact_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            root, inputs, current = self.fixture(folder)
            self.aggregate(root, inputs, current)
            result = ci.read(root / 'aggregate/provenance.json')
            self.assertEqual((result['statements'], result['branches']), (5, 2))
            self.assertEqual(len(result['shards']), 3)
            self.assertTrue(ci.read(root / 'aggregate/gate.json')['passed'])
            with self.assertRaisesRegex(ValueError, 'preserve'):
                self.aggregate(root, inputs, current)

    def test_rounded_percentage_cannot_hide_a_real_branch_gap(self):
        with tempfile.TemporaryDirectory() as folder:
            root, inputs, current = self.fixture(folder, complete=False)
            with self.assertRaisesRegex(ValueError, 'exact coverage gate'):
                self.aggregate(root, inputs, current)
            result = ci.read(root / 'aggregate/gate.json')
            self.assertEqual(result['totals']['runtime']['missing_branches'], 1)
            self.assertFalse((root / 'aggregate/coverage.xml').exists())

    def test_missing_duplicate_wrong_revision_run_and_failed_shards(self):
        changes = [
            ('manifest.json', 'source_revision', 'b' * 40, 'stale'),
            ('manifest.json', 'run_id', 'old', 'stale'),
            ('manifest.json', 'run_attempt', '2', 'stale'),
            ('manifest.json', 'inputs', {}, 'stale'),
            ('manifest.json', 'files', {}, 'stale'),
            ('manifest.json', 'configuration_sha256', 'bad', 'stale'),
            ('manifest.json', 'python', '3.14.0', 'interpreter'),
            ('manifest.json', 'platform', 'Windows', 'platform'),
            ('manifest.json', 'platform', 'CYGWIN_NT', 'platform'),
            ('tests.json', 'passed', False, 'test shard'),
            ('tests.json', 'tests', 0, 'test shard'),
            ('tests.json', 'tests', True, 'test shard'),
            ('tests.json', 'failures', 1, 'test shard'),
            ('tests.json', 'errors', 1, 'test shard'),
            ('tests.json', 'skipped', [['x', 'optional scipy dependency']], 'dependency'),
        ]
        for file, key, value, message in changes:
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as folder:
                root, inputs, current = self.fixture(folder)
                path = inputs / 'Linux'
                data = ci.read(path / file)
                data[key] = value
                ci.write(path / file, data)
                self.seal(path)
                with self.assertRaisesRegex(ValueError, message):
                    self.aggregate(root, inputs, current)
        with tempfile.TemporaryDirectory() as folder:
            root, inputs, current = self.fixture(folder)
            (inputs / 'Linux/bundle.json').unlink()
            with self.assertRaisesRegex(ValueError, 'three'):
                self.aggregate(root, inputs, current)

    def test_tampered_bundle_missing_metadata_and_statement_only_data(self):
        import coverage

        for mode in ('tamper', 'missing', 'lines'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                root, inputs, current = self.fixture(folder)
                path = inputs / 'Linux'
                if mode == 'tamper':
                    (path / 'coverage.json').write_text('{}')
                elif mode == 'missing':
                    ci.write(path / 'bundle.json', {})
                else:
                    (path / '.coverage').unlink()
                    data = coverage.CoverageData(basename=str(path / '.coverage'))
                    data.add_lines({'src/flahax/model.py': [1]})
                    data.write()
                    self.seal(path)
                with self.assertRaisesRegex(ValueError, 'bundle|branch measurement'):
                    self.aggregate(root, inputs, current)

    def test_xml_disagreement_cannot_be_uploaded(self):
        with tempfile.TemporaryDirectory() as folder:
            root, inputs, current = self.fixture(folder)
            fake = SimpleNamespace(
                getroot=lambda: SimpleNamespace(
                    attrib={
                        'lines-valid': '999',
                        'lines-covered': '0',
                        'branches-valid': '2',
                        'branches-covered': '2',
                    }
                )
            )
            with patch.object(ci.ET, 'parse', return_value=fake):
                with self.assertRaisesRegex(ValueError, 'XML differs'):
                    self.aggregate(root, inputs, current)

    def test_manifest_recording_and_report_recheck(self):
        with tempfile.TemporaryDirectory() as folder:
            root, inputs, current = self.fixture(folder)
            path = root / 'recorded'
            with patch.object(ci, 'identity', return_value=copy.deepcopy(current)):
                with (
                    patch.object(ci.sys, 'version_info', (3, 13)),
                    patch.object(ci.platform, 'system', return_value='Linux'),
                ):
                    ci.record(root, path, current['source_revision'])
                with self.assertRaisesRegex(ValueError, 'preserve'):
                    ci.record(root, path, current['source_revision'])
                with patch.object(ci.platform, 'system', return_value='CYGWIN_NT'):
                    with self.assertRaisesRegex(ValueError, 'native'):
                        ci.record(root, root / 'invalid', current['source_revision'])
                with (
                    patch.object(ci.platform, 'system', return_value='Linux'),
                    patch.object(ci.sys, 'version_info', (3, 14)),
                ):
                    with self.assertRaisesRegex(ValueError, '3.13'):
                        ci.record(root, root / 'wrong-version', current['source_revision'])
                raw = inputs / 'Linux/.coverage'
                (path / '.coverage.test').write_bytes(raw.read_bytes())
                ci.write(path / 'tests.json', dict(tests=1, passed=True))
                with contextlib.chdir(root):
                    ci.report(root, path, current['source_revision'])
                self.assertIn('.coverage', ci.read(path / 'bundle.json'))
            changed = dict(current, run_id='changed')
            with patch.object(ci, 'identity', return_value=changed):
                with self.assertRaisesRegex(ValueError, 'changed during tests'):
                    ci.report(root, path, current['source_revision'])

    def test_candidate_identity_and_dirty_checkout_refusal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'a.py').write_text('a=1')
            with patch.object(
                ci.subprocess, 'check_output', side_effect=['a' * 40, '', b'a.py\0']
            ):
                self.assertEqual(ci.candidate(root, 'a' * 40), {'a.py': ci.digest(root / 'a.py')})
            for expected, responses in [
                ('bad', ['a' * 40]),
                ('b' * 40, ['a' * 40]),
                ('a' * 40, ['a' * 40, ' M a.py']),
            ]:
                with patch.object(ci.subprocess, 'check_output', side_effect=responses):
                    with self.assertRaises(ValueError):
                        ci.candidate(root, expected)
            with (
                patch.object(ci, 'candidate', return_value={'a.py': 'hash'}),
                patch.object(ci, 'inventory', return_value={'a.py': 'hash'}),
                patch.object(ci, 'digest', return_value='config'),
                patch.dict(os.environ, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='2'),
            ):
                self.assertEqual(ci.identity(root, 'a' * 40)['run_attempt'], '2')

    def test_test_runner_retains_failure_empty_and_skip_outcomes(self):
        for count, success in ((1, True), (1, False), (0, True)):
            with tempfile.TemporaryDirectory() as folder:
                fake = SimpleNamespace(
                    testsRun=count,
                    failures=[],
                    errors=[],
                    skipped=[],
                    wasSuccessful=lambda: success,
                )
                with (
                    patch.object(ci.unittest.defaultTestLoader, 'discover'),
                    patch.object(ci.unittest, 'TextTestRunner') as runner,
                ):
                    runner.return_value.run.return_value = fake
                    self.assertEqual(ci.run_tests(Path(folder)), int(not (count and success)))
                    self.assertEqual(
                        ci.read(Path(folder) / 'tests.json')['passed'], bool(count and success)
                    )

    def test_upload_integrity_rejects_regeneration_and_wrong_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            root, inputs, current = self.fixture(folder)
            self.aggregate(root, inputs, current)
            output = root / 'aggregate'
            revision = current['source_revision']
            ci.verify_upload(root, output, revision)
            with self.assertRaisesRegex(ValueError, 'candidate'):
                ci.verify_upload(root, output, 'b' * 40)
            for name in ('coverage.xml', 'coverage.json'):
                original = (output / name).read_bytes()
                (output / name).write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'changed'):
                    ci.verify_upload(root, output, revision)
                (output / name).write_bytes(original)
            provenance = ci.read(output / 'provenance.json')
            for key, value in (('statements', 0), ('statements', 999), ('branches', 999)):
                ci.write(output / 'provenance.json', dict(provenance, **{key: value}))
                with self.assertRaisesRegex(ValueError, 'counts'):
                    ci.verify_upload(root, output, revision)
            ci.write(output / 'provenance.json', provenance)
            ci.verify_upload(root, output, revision)

    def test_module_help_entrypoint(self):
        with (
            patch.object(sys, 'argv', ['ci', '--help']),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(SystemExit) as caught:
                runpy.run_path(str(Path(ci.__file__)), run_name='__main__')
            self.assertEqual(caught.exception.code, 0)

    def test_cli_dispatch_and_required_aggregation_input(self):
        for action in ('record', 'report', 'run', 'aggregate', 'verify-upload'):
            args = ['ci', action, '--output', 'out', '--candidate', 'a' * 40]
            if action == 'aggregate':
                args += ['--inputs', 'in']
            with (
                patch.object(sys, 'argv', args),
                patch.object(ci, 'verify_upload'),
                patch.object(ci, 'record'),
                patch.object(ci, 'report'),
                patch.object(ci, 'run_tests', return_value=1),
                patch.object(ci, 'aggregate'),
            ):
                self.assertEqual(ci.main(), 1 if action == 'run' else 0)
        with (
            patch.object(
                sys, 'argv', ['ci', 'aggregate', '--output', 'out', '--candidate', 'a' * 40]
            ),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            with self.assertRaises(SystemExit):
                ci.main()


@unittest.skipUnless(importlib.util.find_spec('yaml'), 'YAML tooling unavailable')
class WorkflowEnforcementTests(unittest.TestCase):
    def test_candidate_dependency_and_upload_contract(self):
        import yaml

        root = Path(__file__).resolve().parents[1]
        workflow = yaml.load(
            (root / '.github/workflows/test.yml').read_text(encoding='utf-8'),
            Loader=yaml.BaseLoader,
        )
        self.assertEqual(set(workflow['on']), {'push', 'pull_request', 'workflow_dispatch'})
        candidate = '${{ github.event.pull_request.head.sha || github.sha }}'
        self.assertEqual(workflow['env']['CANDIDATE_SHA'], candidate)
        for job in workflow['jobs'].values():
            checkout = next(
                s for s in job['steps'] if s.get('uses', '').startswith('actions/checkout@')
            )
            self.assertEqual(checkout['with']['ref'], candidate)
        gate = workflow['jobs']['coverage-gate']
        self.assertEqual(set(gate['needs']), {'style', 'test', 'phreeqc-live', 'docs'})
        self.assertEqual(gate['if'], 'always() && !cancelled()')
        self.assertIn('all(v["result"] == "success"', gate['steps'][0]['run'])
        steps = gate['steps']
        upload = next(s for s in steps if s.get('uses', '').startswith('codecov/'))
        self.assertEqual(upload['with']['fail_ci_if_error'], 'true')
        self.assertEqual(upload['with']['plugins'], 'noop')
        self.assertEqual(upload['with']['disable_search'], 'true')
        self.assertEqual(upload['with']['disable_file_fixes'], 'true')
        self.assertEqual(upload['with']['override_commit'], '${{ env.CANDIDATE_SHA }}')
        self.assertEqual(upload['with']['files'], 'build/coverage-gate/coverage.xml')
        self.assertLess(
            next(i for i, s in enumerate(steps) if 'ci_coverage aggregate' in s.get('run', '')),
            steps.index(upload),
        )
        integrity = [
            i for i, step in enumerate(steps) if 'ci_coverage verify-upload' in step.get('run', '')
        ]
        self.assertEqual(len(integrity), 2)
        self.assertLess(integrity[0], steps.index(upload))
        self.assertGreater(integrity[1], steps.index(upload))
        self.assertEqual(
            steps[integrity[1]]['if'], "always() && steps.aggregate.outcome == 'success'"
        )
        download = next(
            s for s in steps if s.get('uses', '').startswith('actions/download-artifact@')
        )
        self.assertNotIn('run-id', download['with'])
        self.assertNotIn('merge-multiple', download['with'])
        test = workflow['jobs']['test']
        self.assertIn("format('test ({0})'", test['name'])
        self.assertEqual(len(test['strategy']['matrix']['include']), 2)
        measure = next(
            s for s in test['steps'] if s.get('name') == 'Candidate-bound native coverage'
        )
        self.assertIn('test_status=${PIPESTATUS[0]}', measure['run'])
        self.assertIn('exit "$test_status"', measure['run'])
        self.assertEqual(measure['if'], "matrix.python-version == '3.13'")
        self.assertFalse(any(s.get('uses', '').startswith('codecov/') for s in test['steps']))
        config = yaml.load(
            (root / 'codecov.yml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader
        )
        self.assertEqual(config['codecov']['require_ci_to_pass'], 'true')
        for kind in ('project', 'patch'):
            status = config['coverage']['status'][kind]['default']
            self.assertEqual(
                status, {'target': '100%', 'threshold': '0%', 'informational': 'false'}
            )
        self.assertEqual(config['flags']['unittests']['carryforward'], 'false')
