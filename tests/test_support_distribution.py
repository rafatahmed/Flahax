# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Distribution verifier orchestration: synthetic archives and simulated subprocess results.

These tests validate refusal and provenance, not clean installed-package correctness.
The separate distribution verification stage performs real builds and installs.
"""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import tarfile
import zipfile

from tools import verify_distribution as distribution

ROOT = Path(__file__).resolve().parents[1]


class DistributionBoundaryTests(unittest.TestCase):
    def exercise(self, root, *, change=None, names=None, count=2, retain=True):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            self.assertNotIn('PYTHONPATH', kwargs['env'])
            self.assertNotIn('PYTHONHOME', kwargs['env'])
            if 'build' in command:
                output = Path(command[-1])
                output.mkdir()
                if count:
                    with zipfile.ZipFile(output / 'a.whl', 'w') as archive:
                        for name in names or ['flahax/__init__.py']:
                            archive.writestr(name, 'synthetic')
                if count == 2:
                    with tarfile.open(output / 'b.tar.gz', 'w:gz') as archive:
                        name = 'package/tests/fixtures/phreeqc/products/fe_dtpa/expected.json'
                        info = tarfile.TarInfo(name)
                        info.size = 2
                        archive.addfile(info, io.BytesIO(b'{}'))
                return SimpleNamespace(stdout='')
            if '-I' not in command:
                return SimpleNamespace(stdout='')
            install = Path(command[0]).parent.parent
            data = {
                key: hashlib.sha256((ROOT / 'src/flahax/data' / filename).read_bytes()).hexdigest()
                for key, filename in [
                    ('manual_sha256', 'USER_GUIDE.md'),
                    ('api_reference_sha256', 'API_REFERENCE.md'),
                    ('chemistry_sha256', 'chemistry_25c.json'),
                    ('library_sha256', 'library.json'),
                ]
            }
            data.update(
                catalogue_count=len(
                    json.loads((ROOT / 'src/flahax/data/library.json').read_bytes())['salts']
                ),
                module=str(install / 'flahax/__init__.py'),
            )
            if change:
                change(data, install)
            return SimpleNamespace(stdout=json.dumps(data))

        report = root / 'report.json'
        artifacts = root / 'retained' if retain else None
        with (
            patch.object(distribution.subprocess, 'run', side_effect=run),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            distribution.verify(report, 'synthetic-python', artifacts)
        return json.loads(report.read_text()), calls

    def test_success_preserves_both_artifacts_and_hashes(self):
        for retain in (False, True):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                report, calls = self.exercise(root, retain=retain)
                self.assertEqual(report['status'], 'passed')
                self.assertEqual(len(report['installs']), 2)
                self.assertEqual(len(calls), 7)
                if retain:
                    for item in report['installs']:
                        self.assertEqual(
                            hashlib.sha256(
                                (root / 'retained' / item['artifact']).read_bytes()
                            ).hexdigest(),
                            item['sha256'],
                        )

    def test_refuses_existing_output_binaries_and_manufacturer_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'retained').mkdir()
            (root / 'retained/keep').write_text('keep')
            with self.assertRaisesRegex(RuntimeError, 'not empty'):
                self.exercise(root)
        for name, fragment in [
            ('bad.exe', 'binary'),
            ('04_Fertilizer.pdf', 'manufacturer'),
            ('pkg/docs/sources/other.pdf', 'manufacturer'),
        ]:
            with (
                tempfile.TemporaryDirectory() as folder,
                self.assertRaisesRegex(RuntimeError, fragment),
            ):
                self.exercise(Path(folder), names=[name])

    def test_resource_and_import_mismatches_fail_before_report(self):
        for key, value, message in [
            ('manual_sha256', 'bad', 'manual'),
            ('module', str(ROOT / 'src/flahax/__init__.py'), 'checkout'),
            ('catalogue_count', -1, 'catalogue'),
            ('api_reference_sha256', 'bad', 'API reference'),
            ('chemistry_sha256', 'bad', 'chemistry'),
            ('library_sha256', 'bad', 'catalogue'),
        ]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                with self.assertRaisesRegex(RuntimeError, message):
                    self.exercise(root, change=lambda data, install: data.update({key: value}))
                self.assertFalse((root / 'report.json').exists())
        for count in (0, 1):
            with (
                tempfile.TemporaryDirectory() as folder,
                self.assertRaisesRegex(RuntimeError, 'differ'),
            ):
                self.exercise(Path(folder), count=count)
        with (
            tempfile.TemporaryDirectory() as folder,
            self.assertRaisesRegex(RuntimeError, 'differ'),
        ):
            self.exercise(
                Path(folder), change=lambda data, install: data.update(extra=install.name)
            )

    def test_sdist_missing_reference_is_rejected(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(tarfile.TarFile, 'getnames', return_value=['pkg/readme']),
            self.assertRaisesRegex(RuntimeError, 'reference evidence'),
        ):
            self.exercise(Path(folder))

    def test_command_propagates_failed_builder(self):
        import runpy
        import sys

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(sys, 'argv', ['verify', '--report', str(Path(folder) / 'result.json')]),
            patch.object(
                distribution.subprocess, 'run', side_effect=RuntimeError('synthetic build failure')
            ),
            self.assertRaisesRegex(RuntimeError, 'synthetic build failure'),
        ):
            runpy.run_module('tools.verify_distribution', run_name='__main__')
        self.assertEqual(
            __import__('tools.publish_competitor_snapshot', fromlist=['git']).git(
                'rev-parse', '--is-inside-work-tree'
            ),
            'true',
        )
