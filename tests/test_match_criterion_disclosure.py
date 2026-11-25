# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Generated reports state the numeric criterion for "target met" (contract Q24, #299).

The constants are unchanged. The summary carries them, the explanation names them, and the
report prints them; "configured tolerances" alone told the reader nothing.
"""

import unittest

from flahax import VolumeLitres, load_library, plan_fertilizer_workflow, summarize_batch
from flahax.grower_report import render_report, status_explanations
from flahax.requirement_fit import RELATIVE_TOLERANCE, ZERO_TARGET_TOLERANCE_MG_PER_L

LIBRARY = load_library()
SALTS = LIBRARY['salts']
TOMATO = {f['name']: f['targets'] for f in LIBRARY['formulas']}['Tomato (Howard Resh)']
FLOW = plan_fertilizer_workflow(SALTS, TOMATO, {}, 5.8, final_volume=VolumeLitres(1000))
SUMMARY = summarize_batch(FLOW, SALTS, title='T', water_label='RO')


class MatchCriterionTests(unittest.TestCase):
    def test_the_summary_carries_the_criterion_it_applied(self):
        criterion = SUMMARY['formulation']['match_criterion']
        self.assertEqual(criterion['relative'], RELATIVE_TOLERANCE)
        self.assertEqual(criterion['zero_target_mg_per_l'], ZERO_TARGET_TOLERANCE_MG_PER_L)
        self.assertEqual(criterion['relative'], 1e-5)
        self.assertEqual(criterion['zero_target_mg_per_l'], 1e-6)

    def test_the_explanation_states_the_numbers_whether_or_not_targets_are_met(self):
        for met in (True, False):
            with self.subTest(targets_met=met):
                summary = dict(SUMMARY, formulation=dict(SUMMARY['formulation'], targets_met=met))
                text = status_explanations(summary)['formulation']
                self.assertIn('1e-05', text)
                self.assertIn('1e-06 mg/L', text)

    def test_the_report_prints_the_criterion(self):
        visible = render_report(SUMMARY).split('<pre id="flahax-result-data">')[0]
        self.assertIn('within 1e-05 of the target', visible)
        self.assertIn('1e-06 mg/L for a declared zero', visible)

    def test_the_wording_no_longer_leaves_the_tolerance_unnamed(self):
        text = status_explanations(SUMMARY)['formulation']
        self.assertNotIn('configured tolerances', text)


if __name__ == '__main__':
    unittest.main()
