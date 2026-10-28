# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Audit CLI refusal paths and hash-bound evidence; no external ledger dependence."""

import contextlib
import copy
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import check_coverage, check_numeric_review, check_requirements, check_traceability
from tests import test_traceability, test_numeric_review

ROOT = Path(__file__).resolve().parents[1]


def invoke(module, args):
    with (
        patch.object(sys, 'argv', [module.__name__, *map(str, args)]),
        contextlib.redirect_stdout(io.StringIO()) as out,
        contextlib.redirect_stderr(io.StringIO()),
    ):
        try:
            code = module.main()
        except SystemExit as e:
            code = e.code
    return code, out.getvalue()


class AuditCommandTests(unittest.TestCase):
    def test_coverage_manifest_lifecycle_and_failed_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = root / 'manifest.json'
            report = root / 'report.json'
            output = root / 'result.json'
            code, _ = invoke(check_coverage, ['--manifest', manifest, '--record-manifest'])
            self.assertEqual(code, 0)
            self.assertEqual(
                invoke(check_coverage, ['--manifest', manifest, '--record-manifest'])[0], 2
            )
            self.assertEqual(invoke(check_coverage, ['--manifest', manifest])[0], 2)
            report.write_text('{}')
            args = ['--manifest', manifest, '--report', report]
            self.assertEqual(invoke(check_coverage, args)[0], 1)
            self.assertEqual(invoke(check_coverage, [*args, '--output', output])[0], 1)
            self.assertFalse(json.loads(output.read_text())['passed'])
            from tests import test_coverage_gate

            fixture = test_coverage_gate.CoverageGateTests()
            fixture.setUp()
            with (
                patch.object(check_coverage, 'inventory', return_value=fixture.current),
                patch.object(check_coverage.subprocess, 'check_output', return_value='head'),
                patch.object(check_coverage.hashlib, 'sha256') as digest,
            ):
                digest.return_value.hexdigest.return_value = 'config'
                manifest.write_text(json.dumps(fixture.manifest))
                report.write_text(json.dumps(fixture.report))
                self.assertEqual(invoke(check_coverage, args)[0], 0)

    def test_requirement_register_source_scan_and_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'src/flahax').mkdir(parents=True)
            (root / 'src/flahax/__init__.py').write_text('"doc"\nx=1\n__all__=["example"]\n')
            surface = check_requirements.source_surface(root)
            self.assertEqual(surface['exports'], ['example'])
            register = dict(
                requirements=[
                    dict(id='R', contract='c', independent_evidence='e', owner_tasks=['T'])
                ],
                required_ids=['R'],
                task_ids=['T'],
                findings={'F': ['R']},
                required_findings=['F'],
                exports={'example': ['R']},
                runtime_files={'src/flahax/__init__.py': ['R']},
                physical_stage_blocks_math=False,
                numerical_criteria=[],
            )
            self.assertEqual(check_requirements.validate(register, surface), [])
            p = root / 'register.json'
            p.write_text(json.dumps(register))
            self.assertEqual(invoke(check_requirements, [p, '--root', root])[0], 0)
            register['required_findings'] = []
            register['numerical_criteria'] = [{'status': 'structural_exact'}]
            errors = check_requirements.validate(register, surface)
            self.assertIn('finding inventory mismatch', errors)
            self.assertIn('numerical criterion lacks meaning or qualification owner', errors)

    def test_numeric_review_malformed_groups_fail_explicitly(self):
        fixture = test_numeric_review.NumericReviewTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for mutate, fragment in (
            (lambda r: r.update(schema_version=0), 'schema'),
            (lambda r: r['groups'].update(unused={}), 'exactly match'),
            (lambda r: r['entries'][0].update(group='absent'), 'missing semantic'),
            (lambda r: r['groups']['domain'].update(categories=['unknown']), 'classification'),
        ):
            register = copy.deepcopy(fixture.register)
            mutate(register)
            self.assertTrue(
                any(
                    fragment in e
                    for e in check_numeric_review.validate(register, fixture.root, fixture.root)
                )
            )
        self.assertIn(
            'invalid numeric review',
            check_numeric_review.validate(None, fixture.root, fixture.root)[0],
        )

    def test_traceability_invalid_completions_controls_and_policy(self):
        fixture = test_traceability.TraceabilityTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.fixed()
        base = copy.deepcopy(fixture.ledger)
        for mutate, fragment in (
            (lambda ledger: ledger['tasks'][3].update(kind='foundation'), 'wrong kind'),
            (lambda ledger: ledger['tasks'][1].update(kind='foundation'), 'wrong kind'),
            (lambda ledger: ledger['tasks'][2].update(status='invalid'), 'invalid status'),
            (
                lambda ledger: ledger['tasks'][2]['completion'].update(documentation=''),
                'documentation missing',
            ),
            (lambda ledger: ledger['tasks'][2].update(test_outcome='failed'), 'passing tests'),
            (
                lambda ledger: ledger['tasks'][2]['completion']['evidence'].update(exit_code=1),
                'evidence failed',
            ),
            (
                lambda ledger: ledger['controls'].append(copy.deepcopy(ledger['controls'][0])),
                'duplicate control',
            ),
            (lambda ledger: ledger['controls'][0].update(fix_task='absent'), 'invalid fix owner'),
            (
                lambda ledger: ledger['controls'][0].update(input_sha256=''),
                'frozen input hash missing',
            ),
            (
                lambda ledger: ledger['controls'][0]['baseline'].update(test_id='wrong'),
                'baseline assertion',
            ),
        ):
            ledger = copy.deepcopy(base)
            mutate(ledger)
            self.assertTrue(
                any(fragment in e for e in check_traceability.validate(ledger, fixture.root)),
                fragment,
            )
        errors = check_traceability.evidence_errors({}, fixture.root, 'test')
        self.assertIn('test: missing integer exit_code', errors)
        path = fixture.root / 'ledger.json'
        path.write_text(json.dumps(base))
        for args in (
            [path, '--check-ready', 'fix'],
            [path, '--check-ready', 'unknown'],
            [path, '--check-ready', 'fix', '--write-summaries'],
        ):
            self.assertEqual(invoke(check_traceability, args)[0], 2)
        plan = fixture.root / 'plan.md'
        plan.write_text('missing table')
        self.assertEqual(invoke(check_traceability, [path, '--plan', plan])[0], 1)
        plan.write_text('| P00 | old |\n')
        csv = fixture.root / 'tasks.csv'
        args = [path, '--csv', csv, '--plan', plan]
        self.assertEqual(invoke(check_traceability, [*args, '--write-summaries'])[0], 0)
        # This synthetic ledger uses non-Pxx IDs, so recreate an action row for drift checking.
        plan.write_text('| P00 | old |\n')
        self.assertEqual(invoke(check_traceability, args)[0], 1)

    def test_executable_entry_points_expose_help_without_side_effects(self):
        for name in (
            'check_coverage',
            'check_requirements',
            'check_traceability',
            'inventory_numeric_decisions',
            'generate_api_reference',
            'benchmark_baseline',
            'publish_benchmark_report',
            'publish_competitor_snapshot',
            'verify_distribution',
            'build_chemistry_model',
            'add_ph_reagents',
        ):
            if name == 'add_ph_reagents':
                continue  # This maintenance script has no parser.
            with (
                self.subTest(name=name),
                patch.object(sys, 'argv', [name, '--help']),
                contextlib.redirect_stdout(io.StringIO()) as out,
                self.assertRaises(SystemExit) as caught,
            ):
                runpy.run_module('tools.' + name, run_name='__main__')
            self.assertEqual(caught.exception.code, 0)
            self.assertIn('usage:', out.getvalue())
