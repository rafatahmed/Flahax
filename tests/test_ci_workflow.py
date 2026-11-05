# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The Test workflow keeps its required check names and its two tiers (docs/adr/0002)."""

import importlib.util
import json
from pathlib import Path
import re
import unittest

WORKFLOWS = Path(__file__).resolve().parent.parent / '.github' / 'workflows'
WORKFLOW = WORKFLOWS / 'test.yml'
PUBLISH = WORKFLOWS / 'publish.yml'
REQUIRED_CHECKS = {'test (3.11)', 'test (3.12)', 'test (3.13)', 'phreeqc-live', 'coverage-gate'}


def scope_matrices(jobs):
    """The light and full matrices, read from the literal JSON the scope job writes."""
    script = next(s['run'] for s in jobs['scope']['steps'] if s.get('id') == 'scope')
    light = json.loads(re.search(r"light='(.*)'", script).group(1))
    full = json.loads(re.search(r"all='(.*)'", script).group(1))
    return light, full


@unittest.skipUnless(importlib.util.find_spec('yaml'), 'PyYAML unavailable')
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        import yaml

        self.jobs = yaml.safe_load(WORKFLOW.read_text(encoding='utf-8'))['jobs']

    def check_names(self, matrix):
        return {f'test ({row["python-version"]})' for row in matrix['include']}

    def test_the_light_tier_reports_every_required_test_check_on_linux_only(self):
        light, _ = scope_matrices(self.jobs)
        self.assertEqual({r['os'] for r in light['include']}, {'ubuntu-latest'})
        self.assertEqual(self.check_names(light), {'test (3.11)', 'test (3.12)', 'test (3.13)'})
        self.assertLessEqual(
            REQUIRED_CHECKS - {'phreeqc-live', 'coverage-gate'}, self.check_names(light)
        )

    def test_the_full_tier_adds_python_314_windows_and_macos(self):
        _, full = scope_matrices(self.jobs)
        pairs = {(r['os'], r['python-version']) for r in full['include']}
        self.assertTrue(
            {('ubuntu-latest', '3.14'), ('windows-latest', '3.13'), ('macos-latest', '3.13')}
            <= pairs
        )

    def test_every_required_job_still_exists(self):
        self.assertIn('phreeqc-live', self.jobs)
        self.assertEqual(self.jobs['coverage-gate']['name'], 'coverage-gate')

    def test_coverage_and_codecov_run_only_in_the_full_tier(self):
        coverage = [
            s for s in self.jobs['test']['steps'] if 'native coverage' in s.get('name', '')
        ]
        self.assertEqual([s['if'] for s in coverage], ["env.COVERAGE_RUN == 'true'"])
        steps = self.jobs['coverage-gate']['steps']
        # Every step after the prerequisites runs in the full tier only, directly or because
        # it follows the aggregation step, which is itself skipped in the light tier.
        guarded = [
            s
            for s in steps[1:]
            if "needs.scope.outputs.full == 'true'" in s.get('if', '')
            or "steps.aggregate.outcome == 'success'" in s.get('if', '')
        ]
        self.assertEqual(len(guarded), len(steps) - 1)
        self.assertNotIn('if', steps[0])  # the prerequisites are required in both tiers

    def test_a_release_cannot_publish_without_the_full_gate(self):
        import yaml

        publish = yaml.safe_load(PUBLISH.read_text(encoding='utf-8'))['jobs']
        gate = publish['full-gate']
        self.assertEqual(gate['uses'], './.github/workflows/test.yml')
        self.assertIn('full-gate', publish['build']['needs'])
        script = next(s['run'] for s in self.jobs['scope']['steps'] if s.get('id') == 'scope')
        self.assertIn('"$EVENT" = release', script)

    def test_documentation_only_changes_skip_the_live_reference_replay(self):
        steps = self.jobs['phreeqc-live']['steps']
        for step in steps:
            self.assertIn("needs.scope.outputs.code == 'true'", step['if'])

    def test_a_pull_request_is_replaced_by_its_next_push(self):
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", text)


if __name__ == '__main__':
    unittest.main()
