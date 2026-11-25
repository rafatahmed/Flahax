# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Workflow stage statuses are one documented set, enforced where a stage is made (#300)."""

import ast
from pathlib import Path
import unittest

from flahax import VolumeLitres, load_library, plan_fertilizer_workflow, summarize_batch
from flahax.delivery_contracts import DeliveryError
from flahax.fertilizer_workflow import STAGE_STATUSES, WorkflowStage

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {'calculated', 'requires_review', 'needs_input', 'blocked', 'not_calculated'}
LIBRARY = load_library()
SALTS = LIBRARY['salts']
TOMATO = {f['name']: f['targets'] for f in LIBRARY['formulas']}['Tomato (Howard Resh)']


def literal_values(node):
    """The string literals a status expression can take; None for anything else."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.IfExp):
        left, right = literal_values(node.body), literal_values(node.orelse)
        return None if left is None or right is None else left | right
    return None


class StatusVocabularyTests(unittest.TestCase):
    def test_the_vocabulary_is_the_five_documented_values(self):
        self.assertEqual(set(STAGE_STATUSES), EXPECTED)

    def test_the_developer_guide_names_every_value(self):
        text = (ROOT / 'docs/site/developer/water-to-delivery.md').read_text(encoding='utf-8')
        sentence = text.split('Each `WorkflowStage` exposes', 1)[1].split('A calculated stage', 1)[
            0
        ]
        for status in EXPECTED:
            with self.subTest(status=status):
                self.assertIn(f'`{status}`', sentence)

    def test_a_stage_with_another_status_is_refused(self):
        for status in ('done', 'Calculated', '', None):
            with self.subTest(status=status):
                with self.assertRaises(DeliveryError) as raised:
                    WorkflowStage(status)
                self.assertEqual(raised.exception.code, 'invalid_value')

    def test_every_stage_status_written_in_the_workflow_is_in_the_vocabulary(self):
        tree = ast.parse((ROOT / 'src/flahax/fertilizer_workflow.py').read_text(encoding='utf-8'))
        found = set()
        for node in ast.walk(tree):
            expressions = []
            if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'WorkflowStage':
                expressions = node.args[:1] + [k.value for k in node.keywords if k.arg == 'status']
            elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Attribute) and t.attr == 'status' for t in node.targets
            ):
                expressions = [node.value]
            for expression in expressions:
                values = literal_values(expression)
                if values is not None:
                    found |= values
        self.assertTrue(found)
        self.assertLessEqual(found, EXPECTED)

    def test_a_blocked_stage_is_never_outranked_by_the_batch(self):
        flow = plan_fertilizer_workflow(
            SALTS,
            TOMATO,
            {'Na': 100.0},  # the water alone is above the declared maximum
            5.8,
            final_volume=VolumeLitres(1000),
            maximum_concentrations={'Na': 5},
        )
        self.assertEqual(flow.stages['formulation'].status, 'blocked')
        summary = summarize_batch(flow, SALTS, title='T', water_label='RO')
        self.assertEqual(summary['status'], 'blocked')
        for name, stage in summary['stages'].items():
            self.assertIn(stage['status'], EXPECTED, name)


if __name__ == '__main__':
    unittest.main()
