# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Evidence gates reject bypasses and preserve the distinction between red and fixed."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

from tools.check_traceability import render_csv, render_rows, validate


class TraceabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'raw.log').write_text('retained evidence\n', encoding='utf-8')
        self.record = {
            'path': 'raw.log',
            'sha256': hashlib.sha256((self.root / 'raw.log').read_bytes()).hexdigest(),
            'command': 'python -m unittest test_control',
            'source_revision': 'base',
            'environment': 'test interpreter',
            'exit_code': 0,
        }
        self.ledger = {
            'schema_version': 2,
            'policy': {
                'required_assignee': 'maintainer',
                'issue_gate': 'tracking',
                'acceptance_task': 'accept',
                'reproduction_task': 'reproduce',
            },
            'required_controls': ['zero'],
            'controls': [{'id': 'zero', 'fix_task': 'fix', 'status': 'planned'}],
            'summary_fields': ['id', 'depends_on', 'status'],
            'tasks': [
                self.task('tracking', 'foundation', ''),
                self.task('reproduce', 'reproduction', 'tracking'),
                self.task('fix', 'fix', 'tracking,reproduce'),
                self.task('accept', 'acceptance', 'fix'),
                self.task('experiment', 'physical', 'accept'),
            ],
        }

    def task(self, name, kind, deps):
        return {
            'id': name,
            'kind': kind,
            'depends_on': deps,
            'status': 'planned',
            'test_outcome': 'not_run',
            'findings': 'zero',
            'action': 'verify',
            'exit_evidence': 'retained',
        }

    def complete(self, name):
        task = next(t for t in self.ledger['tasks'] if t['id'] == name)
        task.update(
            status='complete',
            test_outcome='passed',
            completion={
                'documentation': 'contract.md',
                'review': 'recorded scope',
                'implementation_revision': 'base',
                'evidence': copy.deepcopy(self.record),
            },
        )
        return task

    def reproduced(self):
        self.complete('tracking')
        self.complete('reproduce')['test_outcome'] = 'reproduction_verified'
        control = self.ledger['controls'][0]
        control.update(
            input_sha256=self.record['sha256'],
            input_path='raw.log',
            test_id='tests.test_control.test_zero',
            status='reproduced',
            oracle={**self.record, 'independent_method': 'rational arithmetic'},
            baseline={
                **self.record,
                'exit_code': 1,
                'failure_kind': 'assertion',
                'input_sha256': self.record['sha256'],
                'test_id': 'tests.test_control.test_zero',
            },
        )
        return control

    def fixed(self):
        control = self.reproduced()
        task = self.complete('fix')
        task['issue'] = {
            'url': 'https://github.com/maintainer/example/issues/1',
            'assignee': 'maintainer',
            'labels': ['bug'],
            'state': 'OPEN',
            'verified_at': '2026-10-25',
            'evidence': self.record,
        }
        control.update(
            status='resolved',
            fix={
                **self.record,
                'oracle_sha256': self.record['sha256'],
                'input_sha256': self.record['sha256'],
                'test_id': 'tests.test_control.test_zero',
            },
        )

    def assert_error(self, fragment):
        self.assertTrue(
            any(fragment in e for e in validate(self.ledger, self.root)),
            validate(self.ledger, self.root),
        )

    def test_planned_and_reproduced_states_are_valid_but_not_fixed(self):
        self.assertEqual(validate(self.ledger, self.root), [])
        self.reproduced()
        self.assertEqual(validate(self.ledger, self.root), [])
        self.assertEqual(self.ledger['tasks'][2]['status'], 'planned')

    def test_issue_gate_cannot_be_removed_from_fix_or_acceptance(self):
        self.ledger['tasks'][2]['depends_on'] = ''
        self.assert_error('fix: issue gate missing')
        self.assert_error('accept: issue gate missing')

    def test_fix_cannot_start_while_tracking_incomplete(self):
        self.ledger['tasks'][2]['status'] = 'implementing'
        self.assert_error('prerequisite tracking incomplete')
        self.assert_error('issue URL missing')

    def test_reproduction_cannot_be_called_passing_fix(self):
        self.reproduced()
        self.ledger['tasks'][1]['test_outcome'] = 'passed'
        self.assert_error('requires verified controls')

    def test_reproduction_rejects_missing_oracle_setup_error_and_changed_inputs(self):
        control = self.reproduced()
        for role, field, value, error in (
            ('oracle', 'independent_method', '', 'oracle not validated'),
            ('baseline', 'failure_kind', 'import_error', 'assertion failure'),
            ('baseline', 'exit_code', 0, 'assertion failure'),
            ('baseline', 'input_sha256', 'b' * 64, 'input identity mismatch'),
        ):
            with self.subTest(field=field):
                saved = control[role][field]
                control[role][field] = value
                self.assert_error(error)
                control[role][field] = saved

    def test_missing_and_tampered_evidence_fail(self):
        self.reproduced()
        (self.root / 'raw.log').write_text('changed', encoding='utf-8')
        self.assert_error('hash mismatch')
        (self.root / 'raw.log').unlink()
        self.assert_error('file missing')

    def test_fix_requires_same_input_passing_evidence_and_revision(self):
        self.fixed()
        self.assertEqual(validate(self.ledger, self.root), [])
        result = self.ledger['controls'][0]['fix']
        result['input_sha256'] = 'b' * 64
        self.assert_error('unchanged control')
        result['source_revision'] = 'other'
        self.assert_error('revision mismatch')

    def test_resolved_label_without_completed_fix_is_rejected(self):
        self.reproduced()['status'] = 'resolved'
        self.assert_error('cannot resolve')

    def test_final_acceptance_requires_every_math_task_not_physical(self):
        self.fixed()
        self.complete('accept')
        self.assertEqual(validate(self.ledger, self.root), [])
        self.ledger['tasks'].append(self.task('unlinked', 'foundation', ''))
        self.assert_error('mathematical task unlinked incomplete')

    def test_final_acceptance_rejects_unresolved_controls(self):
        self.fixed()
        self.complete('accept')
        self.ledger['controls'][0]['status'] = 'reproduced'
        self.assert_error('unresolved regression')

    def test_graph_and_schema_failures(self):
        for change, fragment in (
            (lambda d: d.update(schema_version=99), 'schema'),
            (lambda d: d['tasks'].append(d['tasks'][0]), 'unique'),
            (lambda d: d['tasks'][0].update(depends_on='accept'), 'cycle'),
            (lambda d: d['tasks'][0].update(depends_on='absent'), 'unknown dependency'),
            (lambda d: d['tasks'][0].update(depends_on='experiment'), 'physical work'),
            (lambda d: d['controls'].clear(), 'inventory mismatch'),
        ):
            original = copy.deepcopy(self.ledger)
            change(self.ledger)
            self.assert_error(fragment)
            self.ledger = original

    def test_summaries_derive_dependencies_from_ledger(self):
        self.assertIn('fix,"tracking,reproduce",planned', render_csv(self.ledger))
        self.assertIn('| fix | tracking,reproduce |', render_rows(self.ledger))

    def test_cli_refuses_early_start_and_detects_summary_drift(self):
        ledger_path = self.root / 'ledger.json'
        ledger_path.write_text(json.dumps(self.ledger), encoding='utf-8')
        tool = Path(__file__).resolve().parents[1] / 'tools' / 'check_traceability.py'
        command = [sys.executable, str(tool), str(ledger_path)]
        blocked = subprocess.run(
            command + ['--check-ready', 'fix'], capture_output=True, text=True, check=False
        )
        self.assertEqual(blocked.returncode, 1)
        self.assertIn('prerequisite tracking incomplete', blocked.stdout)
        csv_path = self.root / 'tasks.csv'
        written = subprocess.run(
            command + ['--csv', str(csv_path), '--write-summaries'],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(written.returncode, 0, written.stdout + written.stderr)
        csv_path.write_text('stale', encoding='utf-8')
        stale = subprocess.run(
            command + ['--csv', str(csv_path)], capture_output=True, text=True, check=False
        )
        self.assertEqual(stale.returncode, 1)
        self.assertIn('summary drift', stale.stdout)
        self.assertEqual(csv_path.read_text(), 'stale')

    def test_changed_oracle_or_assertion_cannot_close_fix(self):
        self.fixed()
        result = self.ledger['controls'][0]['fix']
        result['oracle_sha256'] = 'b' * 64
        result['test_id'] = 'different.assertion'
        self.assert_error('oracle identity mismatch')
        self.assert_error('assertion identity mismatch')

    def test_malformed_ledger_fails_closed(self):
        for malformed in (None, [], {'tasks': [None]}, {'tasks': [{'id': 'x'}]}):
            self.assertTrue(validate(malformed, self.root))


if __name__ == '__main__':
    unittest.main()
