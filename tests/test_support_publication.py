# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Publication helpers render synthetic captures only into temporary sites."""

import contextlib
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import publish_benchmark_report as publication
from tools import publish_competitor_snapshot as competitor
from tools.benchmark_baseline import asv_samples, metrics

ROOT = Path(__file__).resolve().parents[1]


class SupportPublicationTests(unittest.TestCase):
    def make_capture(self, root):
        capture = root / 'capture'
        capture.mkdir()
        asv = root / 'asv'
        asv.mkdir()
        (asv / 'machine.json').write_text('{"cpu":"synthetic", "ram":1024}')
        (asv / 'data.json').write_text(
            json.dumps(
                {
                    'commit_hash': 'synthetic',
                    'result_columns': ['result', 'samples', 'params'],
                    'results': {
                        'performance.Kernel.time_nnls': [
                            [0.002],
                            [[0.001, 0.002, 0.003]],
                            [['case']],
                        ],
                        'performance.Empty.time_missing': [None, None, []],
                        'performance.Memory.peakmem_solve': [[1024], None, []],
                    },
                }
            )
        )
        inputs = {'pyproject.toml': publication.sha((ROOT / 'pyproject.toml').read_bytes())}
        meta = dict(
            dirty_tree=False,
            source_checkout_import=True,
            git_commit='synthetic',
            python='test',
            tool_versions={'asv': 'synthetic'},
            input_sha256=inputs,
            input_manifest_sha256=publication.sha(json.dumps(inputs, sort_keys=True).encode()),
            os='Windows',
            architecture='synthetic',
            processor='synthetic',
            logical_cpus=1,
            utc='test',
        )
        rows = [
            dict(
                ion='K',
                target_mg_l=100,
                delivered_mg_l=90,
                error_mg_l=-10,
                error_percent=-10,
                tolerance_mg_l=1,
                passes=False,
            )
        ]
        report = dict(
            metadata=meta,
            kernel={'cases': [{'case': 'synthetic', 'passes': False}]},
            formulation={
                'cases': [{'id': 'synthetic:water', 'rows': rows, 'whole_recipe_passes': False}],
                'attempted': 1,
                'summary': metrics(rows),
                'failures': [],
            },
            chemistry={'attempted': 1, 'passed': 0},
        )
        (capture / 'before.json').write_text(json.dumps(report))
        (capture / 'after.json').write_text(
            json.dumps(
                dict(metadata=meta, input_manifest_matches=True, performance=asv_samples(asv))
            )
        )
        (capture / 'hosted-ci.json').write_text(
            json.dumps(dict(headSha='synthetic', url='https://example.invalid', jobs=[]))
        )
        (capture / 'manual-workflow.json').write_text(
            json.dumps(
                dict(
                    headSha='synthetic',
                    status='completed',
                    conclusion='failure',
                    url='https://example.invalid',
                )
            )
        )
        (capture / 'ignored.bin').write_bytes(b'ignored')
        (capture / 'subdir').mkdir()
        site = root / 'site'
        (site / 'evidence').mkdir(parents=True)
        return capture, asv, site

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "optional matplotlib dependency")
    def test_real_renderer_preserves_failures_and_bundle_checksums(self):
        with tempfile.TemporaryDirectory() as folder:
            capture, asv, site = self.make_capture(Path(folder))
            destination = publication.render(
                capture,
                asv,
                site,
                'synthetic-test',
                ROOT,
                related_page='other.md',
                capture_kind='local',
            )
            page = (site / 'evidence/benchmark-results.md').read_text(encoding='utf-8')
            self.assertIn('not fully passing', page)
            self.assertIn('local supplement', page)
            with zipfile.ZipFile(destination / 'evidence.zip') as bundle:
                for line in bundle.read('CHECKSUMS.sha256').decode().splitlines():
                    digest, name = line.split('  ', 1)
                    self.assertEqual(hashlib.sha256(bundle.read(name)).hexdigest(), digest)
            self.assertTrue((destination / 'formulation.png').read_bytes().startswith(b'\x89PNG'))
            with self.assertRaisesRegex(ValueError, 'already exists'):
                publication.render(capture, asv, site, 'synthetic-test', ROOT)

    def test_renderer_rejects_bad_provenance_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            capture, asv, site = self.make_capture(Path(folder))
            for kwargs, fragment in (
                ({'capture_kind': 'invalid'}, 'Capture kind'),
                ({'snapshot': '../bad'}, 'safe lowercase'),
                ({'page_stem': '../bad'}, 'page identifier'),
            ):
                args = dict(snapshot='new', source=ROOT)
                args.update(kwargs)
                with self.assertRaisesRegex(ValueError, fragment):
                    publication.render(capture, asv, site, **args)
            for filename, key, value, fragment in (
                ('hosted-ci.json', 'headSha', 'other', 'different revision'),
                ('manual-workflow.json', 'status', 'running', 'must have completed'),
            ):
                p = capture / filename
                original = p.read_bytes()
                data = json.loads(original)
                data[key] = value
                p.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, fragment):
                    publication.render(capture, asv, site, 'new', ROOT)
                p.write_bytes(original)
            with (
                patch('tools.benchmark_baseline.asv_samples', return_value={}),
                self.assertRaisesRegex(ValueError, 'ASV source'),
            ):
                publication.render(capture, asv, site, 'new', ROOT)
            machine = asv / 'machine.json'
            machine.unlink()
            with self.assertRaisesRegex(ValueError, 'exactly one'):
                publication.render(capture, asv, site, 'new', ROOT)
            self.assertFalse((site / '_static').exists())

    def test_capture_import_and_stability_gates(self):
        with tempfile.TemporaryDirectory() as folder:
            capture, _, _ = self.make_capture(Path(folder))
            for key, value, fragment in (('source_checkout_import', False, 'not imported'),):
                p = capture / 'before.json'
                data = json.loads(p.read_text())
                data['metadata'][key] = value
                p.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, fragment):
                    publication.load_capture(capture)
                data['metadata'][key] = True
                p.write_text(json.dumps(data))
            p = capture / 'after.json'
            data = json.loads(p.read_text())
            data['input_manifest_matches'] = False
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'stability'):
                publication.load_capture(capture)

    def test_competitor_bundle_is_reproducible_and_rejects_changed_sources(self):
        with (
            patch.object(competitor, 'git', side_effect=['sha', 'changed']),
            patch.object(competitor.subprocess, 'run'),
            self.assertRaisesRegex(ValueError, 'changed since'),
        ):
            competitor.measured_commit('ref')
        with (
            patch.object(competitor, 'git', side_effect=['sha', '', 'dirty']),
            patch.object(competitor.subprocess, 'run'),
            self.assertRaisesRegex(ValueError, 'uncommitted'),
        ):
            competitor.measured_commit('ref')
        with (
            patch.object(competitor, 'git', side_effect=['sha', '', '']),
            patch.object(competitor.subprocess, 'run'),
        ):
            self.assertEqual(competitor.measured_commit('ref'), 'sha')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run = root / 'run'
            run.mkdir()
            freeze = root / 'freeze.txt'
            freeze.write_text('synthetic==1\n')
            for name in competitor.TRACKS:
                (run / name).write_text('{"synthetic": true}')
            with patch.object(competitor, 'measured_commit', return_value='synthetic'):
                first = competitor.publish(run, 'ref', freeze, root / 'one')
                second = competitor.publish(run, 'ref', freeze, root / 'two')
            self.assertEqual(first, second)
            with zipfile.ZipFile(root / 'one/evidence.zip') as bundle:
                self.assertEqual(json.loads(bundle.read('formulation.json')), {'synthetic': True})

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "optional matplotlib dependency")
    def test_command_wrappers_and_changed_source_refusal(self):
        import sys

        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            capture, asv, site = self.make_capture(root)
            changed = root / 'changed'
            changed.mkdir()
            (changed / 'pyproject.toml').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'Measured source/input changed'):
                publication.render(capture, asv, site, 'new', changed)
            argv = [
                'publication',
                '--capture',
                str(capture),
                '--asv-results',
                str(asv),
                '--site',
                str(site),
                '--snapshot',
                'via-command',
                '--source-checkout',
                str(ROOT),
            ]
            with patch.object(sys, 'argv', argv):
                publication.main()
            self.assertTrue((site / '_static/benchmarks/via-command/evidence.zip').exists())
            for name in competitor.TRACKS:
                (capture / name).write_text('{}')
            freeze = root / 'freeze'
            freeze.write_text('synthetic')
            with (
                patch.object(competitor, 'ROOT', root),
                patch.object(competitor, 'measured_commit', return_value='test'),
                patch.object(
                    sys,
                    'argv',
                    [
                        'competitor',
                        '--run',
                        str(capture),
                        '--commit',
                        'test',
                        '--freeze',
                        str(freeze),
                        '--snapshot',
                        'test',
                    ],
                ),
            ):
                competitor.main()
            self.assertTrue((root / 'docs/site/_static/benchmarks/test/evidence.zip').exists())
