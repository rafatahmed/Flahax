# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Status contract: one vocabulary; parents cannot outrank blocked children."""

import unittest

from flahax import VolumeLitres, load_library, plan_fertilizer_workflow, summarize_batch
from flahax.batch_cli import run_batch
from flahax.canonical_result import STATUS_VOCABULARY, result_statuses
from flahax.fertilizer_workflow import apply_status_rollup, WorkflowStage
from tests.test_core_cucumber_witness import witness_inputs


LIBRARY = load_library()
SALTS = LIBRARY['salts']


class StatusVocabularyTests(unittest.TestCase):
    def test_vocabulary_is_the_locked_contract_set(self):
        self.assertEqual(
            STATUS_VOCABULARY,
            frozenset(
                {
                    'ready',
                    'requires_review',
                    'blocked',
                    'not_supported',
                    'needs_input',
                    'not_validated',
                }
            ),
        )


class StatusRollupTests(unittest.TestCase):
    def test_batch_cannot_stay_calculated_when_formulation_is_blocked(self):
        stages = {
            'formulation': WorkflowStage('blocked', error_code='infeasible_recipe'),
            'batch': WorkflowStage('calculated', value={'final_volume': 1}),
        }
        apply_status_rollup(stages)
        self.assertEqual(stages['batch'].status, 'blocked')
        self.assertIsNotNone(stages['batch'].value)

    def test_chemistry_cannot_outrank_blocked_batch(self):
        stages = {
            'formulation': WorkflowStage('blocked'),
            'batch': WorkflowStage('blocked', value=object()),
            'chemistry': WorkflowStage('calculated', value={'mixed': object()}),
        }
        apply_status_rollup(stages)
        self.assertEqual(stages['chemistry'].status, 'blocked')
        self.assertIsNotNone(stages['chemistry'].value)

    def test_calculated_batch_survives_when_formulation_is_ok(self):
        stages = {
            'formulation': WorkflowStage('calculated'),
            'batch': WorkflowStage('calculated', value=object()),
        }
        apply_status_rollup(stages)
        self.assertEqual(stages['batch'].status, 'calculated')


class CucumberStatusHonestyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = run_batch(witness_inputs())

    def test_batch_does_not_outrank_blocked_formulation(self):
        stages = {
            name: stage.get('status') if isinstance(stage, dict) else stage
            for name, stage in self.summary['stages'].items()
        }
        self.assertEqual(stages['formulation'], 'blocked')
        self.assertNotIn(stages['batch'], ('calculated', 'ready'))
        self.assertEqual(stages['batch'], 'blocked')

    def test_exported_statuses_use_contract_vocabulary(self):
        for name, status in self.summary['statuses'].items():
            with self.subTest(status=name):
                self.assertIn(status, STATUS_VOCABULARY)

    def test_formulation_status_is_blocked_not_legacy_infeasible(self):
        self.assertEqual(self.summary['statuses']['formulation'], 'blocked')
        self.assertEqual(self.summary['statuses']['overall'], 'blocked')
        self.assertNotEqual(self.summary['status'], 'ready')

    def test_summary_still_emits_diagnostic_chemistry_when_batch_blocked(self):
        self.assertIsNotNone(self.summary.get('chemistry'))
        self.assertEqual(self.summary['ec']['status'], 'not_supported')


class GrowerOverallRollupTests(unittest.TestCase):
    def test_overall_stays_blocked_when_formulation_blocked_even_if_ph_calculated(self):
        pool = [p for p in SALTS if p['formula'] == 'KNO3']
        flow = plan_fertilizer_workflow(
            pool,
            {'K': 10, 'N_NO3': 10 * 14.0067 / 39.0983},
            {},
            6.5,
            final_volume=VolumeLitres(100),
        )
        flow.canonical_result = None
        flow.stages['formulation'].status = 'blocked'
        flow.stages['formulation'].message = 'synthetic block'

        class _Plan:
            selected = None
            unadjusted_state = None
            unadjusted_recommendation = None
            unadjusted_ph = 6.8
            target_ph = 6.5
            candidates = ()
            direction = 'acid'

        flow.stages['ph_adjustment'] = WorkflowStage('calculated', value=_Plan())
        summary = summarize_batch(flow, pool, title='Rollup', water_label='RO')
        self.assertEqual(summary['status'], 'blocked')
        self.assertEqual(result_statuses(summary)['formulation'], 'blocked')


if __name__ == '__main__':
    unittest.main()
