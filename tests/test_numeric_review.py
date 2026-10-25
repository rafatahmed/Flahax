# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Reject incomplete reviews and unqualified adoption, including stale inputs."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.check_numeric_review import validate
from tools.inventory_numeric_decisions import inventory

ROOT = Path(__file__).resolve().parents[1]


class NumericReviewTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / 'src/flahax/model.py'
        self.source.parent.mkdir(parents=True)
        self.source.write_text('LIMIT = 0.1\ndef check(x):\n    return x <= LIMIT\n')
        self.register = dict(
            schema_version=1,
            audit_complete=True,
            owner_tasks=['qualify'],
            groups={
                'domain': dict(
                    categories=['scientific', 'numerical'],
                    disposition='retain_unqualified',
                    adopted=False,
                    rationale='Domain boundary is inherited, not newly justified.',
                    units='mol/kg water',
                    conditions='Pinned model, 25 C; broader domain not established.',
                    source_status='Source applicability awaits review.',
                    reviewer='test',
                    owner_tasks=['qualify'],
                )
            },
            entries=[
                dict(id=row['id'], source_sha256=row['source_sha256'], group='domain')
                for row in inventory(self.root)
            ],
        )

    def errors(self, register=None, **kwargs):
        return validate(register or self.register, self.root, self.root, **kwargs)

    def test_complete_audit_does_not_pass_qualification_gate(self):
        self.assertEqual(self.errors(), [])
        self.assertTrue(self.errors(require_qualified=True))

    def test_unqualified_adoption_and_structural_disguise_are_rejected(self):
        self.register['groups']['domain']['adopted'] = True
        self.assertTrue(self.errors())
        self.register['groups']['domain']['disposition'] = 'structural'
        self.assertTrue(self.errors())

    def test_missing_duplicate_and_changed_inventory_are_rejected(self):
        for rows in (self.register['entries'][:-1], self.register['entries'] * 2):
            candidate = copy.deepcopy(self.register)
            candidate['entries'] = rows
            self.assertTrue(self.errors(candidate))
        self.source.write_text('LIMIT = 0.2\ndef check(x):\n    return x <= LIMIT\n')
        self.assertTrue(self.errors())

    def test_units_conditions_sources_and_owner_cannot_be_omitted(self):
        for field in ('units', 'conditions', 'source_status', 'reviewer', 'owner_tasks'):
            candidate = copy.deepcopy(self.register)
            del candidate['groups']['domain'][field]
            with self.subTest(field=field):
                self.assertTrue(self.errors(candidate))
        self.register['groups']['domain']['owner_tasks'] = ['unknown']
        self.assertTrue(self.errors())

    def test_qualified_claim_needs_independent_evidence_and_applicability(self):
        group = self.register['groups']['domain']
        group['disposition'] = 'qualified'
        self.assertTrue(self.errors())
        proof = self.root / 'proof.json'
        proof.write_text('{"passed": true}')
        group['qualification'] = dict(
            path=proof.name,
            sha256=hashlib.sha256(proof.read_bytes()).hexdigest(),
            independent_method='Independent bounded reference comparison',
            applicability='Only this explicit fixture domain',
            reviewer='test',
            exit_code=0,
        )
        self.assertEqual(self.errors(require_qualified=True), [])
        proof.write_text('{"passed": false}')
        self.assertTrue(self.errors())

    def test_cli_checks_the_same_boundary(self):
        path = self.root / 'register.json'
        path.write_text(json.dumps(self.register))
        command = [
            sys.executable,
            str(ROOT / 'tools/check_numeric_review.py'),
            str(path),
            '--root',
            str(self.root),
        ]
        good = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(good.returncode, 0, good.stderr)
        strict = subprocess.run(
            command + ['--require-qualified'], capture_output=True, text=True, check=False
        )
        self.assertEqual(strict.returncode, 1, strict.stderr)


if __name__ == '__main__':
    unittest.main()
