# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""A total-N target reaches the workflow, not only ``recommend`` (D2, contract Q11-Q13)."""

import json
import math
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

from flahax import InputError, VolumeLitres, load_library, plan_fertilizer_workflow
from flahax.batch_request import BatchOptions, run_batch
from flahax.joint_problem import JointProblem, JointSource
from flahax.nitrogen import total_nitrogen

SALTS = load_library()['salts']


def plan(targets):
    return plan_fertilizer_workflow(SALTS, targets, {}, 5.8, final_volume=VolumeLitres(1000))


class TotalNitrogenWorkflowTests(unittest.TestCase):
    def test_total_nitrogen_alone_is_planned_without_a_form_split(self):
        rows = {r['symbol']: r for r in plan({'N': 150.0, 'Ca': 100.0}).recommendation['rows']}
        self.assertEqual(rows['N']['target'], 150.0)
        self.assertAlmostEqual(rows['N']['final'], 150.0, places=6)

    def test_total_with_all_forms_that_agree_is_planned(self):
        flow = plan({'N': 150.0, 'N_NO3': 120.0, 'N_NH4': 30.0, 'Ca': 100.0})
        total = flow.recommendation['totalN']
        self.assertFalse(total['fitted'])  # the forms determine it, so it is checked, not fitted
        self.assertAlmostEqual(total['final'], 150.0, places=6)

    def test_total_with_some_forms_is_planned_and_discloses_the_overlap(self):
        flow = plan({'N': 150.0, 'N_NH4': 20.0, 'Ca': 100.0})
        self.assertTrue(flow.recommendation['totalN']['overlapForms'])

    def test_a_contradictory_total_is_still_rejected_before_fitting(self):
        with self.assertRaises(InputError):
            plan({'N': 200.0, 'N_NO3': 120.0, 'N_NH4': 30.0, 'Ca': 100.0})


class JointTotalNitrogenTests(unittest.TestCase):
    def test_a_source_and_water_total_n_is_the_sum_of_the_forms(self):
        source = JointSource('p', {'N_NO3': 0.1, 'N_NH4': 0.02, 'Ca': 0.1}, None)
        self.assertAlmostEqual(source.fraction('N'), 0.12)
        self.assertEqual(source.fraction('Ca'), 0.1)
        self.assertEqual(source.fraction('Mg'), 0)

    def test_total_n_is_added_exactly_as_the_engine_adds_it(self):
        # Three forms whose left-to-right float sum differs from the exactly rounded sum on
        # Python 3.11 (0.6000000000000001 against 0.6; 6.200000000000001 against 6.2). The
        # joint solver and the engine must use one total, on every supported Python.
        source = JointSource('uan', {'N_NO3': 0.1, 'N_NH4': 0.2, 'N_UREA': 0.3}, None)
        self.assertEqual(source.fraction('N'), math.fsum([0.1, 0.2, 0.3]))
        self.assertEqual(source.fraction('N'), total_nitrogen(source.nutrients))
        water = {'N_NO3': 4.4, 'N_NH4': 0.7, 'N_UREA': 1.1}
        problem = SimpleNamespace(water=water)
        self.assertEqual(JointProblem.water_at(problem, 'N'), math.fsum([4.4, 0.7, 1.1]))
        self.assertEqual(JointProblem.water_at(problem, 'N'), total_nitrogen(water))

    def test_water_total_n_is_the_sum_of_its_forms(self):
        problem = SimpleNamespace(water={'N_NO3': 4.0, 'N_NH4': 1.0, 'Ca': 9.0})
        self.assertEqual(JointProblem.water_at(problem, 'N'), 5.0)
        self.assertEqual(JointProblem.water_at(problem, 'Ca'), 9.0)
        self.assertEqual(JointProblem.water_at(problem, 'Mg'), 0)

    def test_the_batch_command_plans_a_total_n_only_target_with_a_reagent_in_play(self):
        with tempfile.TemporaryDirectory() as folder:
            targets = Path(folder, 'targets.json')
            targets.write_text(json.dumps({'N': 150, 'Ca': 100}))
            water = Path(folder, 'water.json')
            water.write_text(
                json.dumps({'mg_per_litre': {'HCO3': 60, 'N_NO3': 4}, 'measured_ph': 7.5})
            )
            result = run_batch(
                BatchOptions(water=str(water), targets=str(targets), volume=1000, ratio=100)
            )
        total = result['formulation']['total_n']
        self.assertAlmostEqual(total['final'], 150.0, places=4)
        self.assertEqual(total['overlapForms'], [])


if __name__ == '__main__':
    unittest.main()
