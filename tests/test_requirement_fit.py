# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""A requirement is met only within the numerical tolerance (G25): 1e-5 relative, 1e-6 mg/L
for a declared zero, 1e-4 pH. A missed target is a reported deviation, not a block."""

import unittest

from flahax import (
    VolumeLitres,
    final_solution_recipe,
    load_library,
    plan_fertilizer_workflow,
    recommend,
)
from flahax.requirement_fit import (
    PH_TOLERANCE,
    RELATIVE_TOLERANCE,
    ZERO_TARGET_TOLERANCE_MG_PER_L,
    met,
)

LIBRARY = load_library()  # the packaged catalogue (Flaha Agri Tech Analysis Ver 0.0)
SALTS = LIBRARY['salts']
FORMULAS = {f['name']: f['targets'] for f in LIBRARY['formulas']}
LETTUCE = FORMULAS['Lettuce 2 (Howard Resh)']


def row(result, symbol):
    return next(r for r in result['rows'] if r['symbol'] == symbol)


class ToleranceTests(unittest.TestCase):
    def test_the_validated_values(self):
        self.assertEqual(
            (RELATIVE_TOLERANCE, ZERO_TARGET_TOLERANCE_MG_PER_L, PH_TOLERANCE),
            (1e-5, 1e-6, 1e-4),
        )

    def test_met_is_relative_for_positive_targets(self):
        self.assertTrue(met(100, 100.0009))
        self.assertFalse(met(100, 100.0011))
        self.assertTrue(met(100, 99.9991))
        self.assertFalse(met(100, 99.9989))

    def test_met_is_absolute_for_declared_zeros(self):
        self.assertTrue(met(0, 9e-7))
        self.assertFalse(met(0, 2e-6))


class Lettuce2DeviationTests(unittest.TestCase):
    """Lettuce 2 (Howard Resh), packaged catalogue, empty water: P finishes 0.32 % short.

    The former 1 % band counted that as met; under the numerical tolerance it is a deviation,
    listed in unmetTargets and in the formulation stage. Mo, 0.0056 % short with Micro Combi
    Mix 1 (inside the former band), is short under the tolerance, so the only held-back Mo
    source, sodium molybdate, is admitted and meets it.
    """

    @classmethod
    def setUpClass(cls):
        cls.result = recommend(SALTS, LETTUCE, {})
        cls.flow = plan_fertilizer_workflow(
            SALTS, LETTUCE, {}, 5.8, final_volume=VolumeLitres(100)
        )

    def test_phosphorus_is_not_met(self):
        p = row(self.result, 'P')
        self.assertEqual(p['target'], 50)
        self.assertAlmostEqual(p['final'], 49.8384, places=4)
        self.assertAlmostEqual(p['deltaPct'], -0.3232, places=4)
        self.assertFalse(met(p['target'], p['final']))
        self.assertFalse(self.result['feasible'])

    def test_the_phosphorus_deviation_is_listed(self):
        listed = {u['symbol']: u for u in self.result['unmetTargets']}
        self.assertIn('P', listed)
        self.assertEqual(listed['P']['deltaPct'], row(self.result, 'P')['deltaPct'])
        message = self.flow.stages['formulation'].message
        self.assertIn('targets missed: ', message)
        self.assertIn('P -0.323 %', message)

    def test_molybdenum_short_by_less_than_one_percent_recovers_its_source(self):
        self.assertIn(
            'Sodium Molybdate (Dihydrate) is included because Mo stayed short of its target '
            'without it. It also carries Na.',
            self.result['warnings'],
        )
        names = [item['name'] for item in self.result['salts']]
        self.assertIn('Sodium Molybdate (Dihydrate)', names)
        self.assertNotIn('Micro Combi Mix 1', names)
        self.assertTrue(met(0.05, row(self.result, 'Mo')['final']))

    def test_only_unmet_targets_are_listed(self):
        expected = [
            r['symbol']
            for r in self.result['rows']
            if r['target'] and not met(r['target'], r['final'])
        ]
        self.assertEqual(
            expected, ['N_NO3', 'N_NH4', 'P', 'K', 'Ca', 'Mg', 'S', 'Fe']
        )  # Zn and Cu are within 1e-5; B, Mn and Mo are exact
        self.assertEqual([u['symbol'] for u in self.result['unmetTargets']], expected)


class WorkflowDeviationTests(unittest.TestCase):
    def test_deviations_without_a_broken_maximum_require_review(self):
        flow = plan_fertilizer_workflow(SALTS, LETTUCE, {}, 5.8, final_volume=VolumeLitres(100))
        stage = flow.stages['formulation']
        self.assertEqual(flow.recommendation['limitViolations'], [])
        self.assertEqual(stage.status, 'requires_review')
        self.assertIsNone(stage.error_code)
        self.assertEqual(
            stage.message,
            'targets missed: N_NO3 -2.35 %, N_NH4 +0.218 %, P -0.323 %, K +1.07 %, '
            'Ca +1.9 %, Mg +0.74 %, S -1.41 %, Fe +0.0286 %; '
            'incidental nutrients with no declared maximum: Na 0.442 mg/L; check them, '
            'or declare maximum concentrations',
        )
        batch = flow.stages['batch']
        self.assertEqual(batch.status, 'calculated')
        self.assertTrue(batch.value.feasible)

    def test_a_broken_maximum_still_blocks(self):
        # Water sodium 30 mg/L above a declared 20 mg/L maximum: no recipe can remove it.
        flow = plan_fertilizer_workflow(
            SALTS,
            LETTUCE,
            {'Na': 30},
            5.8,
            final_volume=VolumeLitres(100),
            maximum_concentrations={'Na': 20},
        )
        stage = flow.stages['formulation']
        self.assertEqual(stage.status, 'blocked')
        self.assertEqual(stage.error_code, 'infeasible_recipe')
        self.assertTrue(stage.message.startswith('Na would be '), stage.message)
        self.assertFalse(flow.stages['batch'].value.feasible)

    def test_a_batch_recipe_is_planned_unless_a_maximum_is_broken(self):
        salts = [{'id': 'k', 'name': 'K', 'gramsPerLitre': 0.5}]
        missed = dict(feasible=False, salts=salts, limitViolations=[])
        broken = dict(missed, limitViolations=[{'symbol': 'Na', 'ppm': 30, 'maximumPpm': 20}])
        self.assertTrue(final_solution_recipe(missed, VolumeLitres(10)).feasible)
        self.assertFalse(final_solution_recipe(broken, VolumeLitres(10)).feasible)
        # Without a limitViolations list the flag is kept as given.
        bare = dict(feasible=False, salts=salts)
        self.assertFalse(final_solution_recipe(bare, VolumeLitres(10)).feasible)


if __name__ == '__main__':
    unittest.main()
