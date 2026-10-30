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
from flahax.fertilizer_workflow import missed_message, no_reagent_message, signed_percent
from flahax.grower_sheet import missed_target
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


class DeclaredZeroTests(unittest.TestCase):
    """A declared zero is met within 1e-6 mg/L everywhere (G25): urea from the water."""

    def flow(self, targets, urea):
        return plan_fertilizer_workflow(
            SALTS, targets, {'N_UREA': urea}, 5.8, final_volume=VolumeLitres(100)
        )

    def test_half_a_microgram_of_urea_is_met(self):
        cucumber = FORMULAS['Cucumber (Howard Resh)']
        self.assertNotIn('N_UREA', cucumber)
        for targets in (cucumber, dict(cucumber, N_UREA=0)):
            with self.subTest(declared='N_UREA' in targets):
                flow = self.flow(targets, 5e-7)
                result = flow.recommendation
                self.assertEqual(row(result, 'N_UREA')['final'], 5e-7)
                self.assertEqual(result['limitViolations'], [])
                self.assertEqual(result['requirementConflicts'], [])
                self.assertNotIn('N_UREA', [u['symbol'] for u in result['unmetTargets']])
                self.assertNotEqual(flow.stages['formulation'].status, 'blocked')
                self.assertTrue(missed_target({'target': 0, 'final': 5e-7}) is False)

    def test_two_micrograms_of_urea_break_the_declared_zero(self):
        cucumber = FORMULAS['Cucumber (Howard Resh)']
        for targets in (cucumber, dict(cucumber, N_UREA=0)):
            with self.subTest(declared='N_UREA' in targets):
                flow = self.flow(targets, 2e-6)
                result = flow.recommendation
                self.assertEqual(
                    result['limitViolations'],
                    [{'symbol': 'N_UREA', 'ppm': 2e-6, 'maximumPpm': 0.0}],
                )
                self.assertEqual(
                    [(c['symbol'], c['reason']) for c in result['requirementConflicts']],
                    [('N_UREA', 'water_above_maximum')],
                )
                self.assertIn('N_UREA', [u['symbol'] for u in result['unmetTargets']])
                self.assertEqual(flow.stages['formulation'].status, 'blocked')
                self.assertTrue(missed_target({'target': 0, 'final': 2e-6}))

    def test_sheet_marks_only_targets_not_met(self):
        self.assertFalse(missed_target({'target': 50, 'final': 50.0004}))
        self.assertTrue(missed_target({'target': 50, 'final': 50.0006}))
        self.assertFalse(missed_target({'target': None, 'final': 3.0}))


class MissedMessageTests(unittest.TestCase):
    def test_misses_print_three_significant_figures_in_fixed_notation(self):
        rows = [
            {'symbol': 'K', 'target': 10.0, 'final': 150.0, 'deltaPct': 1400.0},
            {'symbol': 'P', 'target': 50.0, 'final': 49.8384, 'deltaPct': -0.3232046},
            {'symbol': 'Zn', 'target': 0.1, 'final': 0.1000051, 'deltaPct': 0.0051234},
            {'symbol': 'B', 'target': 0.5, 'final': 0.5, 'deltaPct': 0.0},
        ]
        self.assertEqual(
            missed_message({'rows': rows}), 'targets missed: K +1400 %, P -0.323 %, Zn +0.00512 %'
        )
        self.assertEqual(signed_percent(-123456.0), '-123000')
        self.assertEqual(signed_percent(0.000012345), '+0.0000123')


class SharedPhToleranceTests(unittest.TestCase):
    def test_every_ph_check_uses_the_numerical_tolerance(self):
        from flahax import joint_workflow, ph_adjustment

        self.assertEqual(PH_TOLERANCE, 1e-4)
        self.assertIs(ph_adjustment.PH_TOLERANCE, PH_TOLERANCE)
        self.assertIs(joint_workflow.PH_TOLERANCE, PH_TOLERANCE)


class NoReagentMessageTests(unittest.TestCase):
    def test_a_feed_already_at_its_target_ph_needs_no_reagent(self):
        # Issue #212: direction 'none' never asks for a base.
        from types import SimpleNamespace

        rejected = SimpleNamespace(
            joint_result=None,
            direction='base',
            status='rejected',
            product_record={'name': 'Potassium Hydroxide (45% solution)'},
            product_id='koh',
            message='precipitation risk at the target pH',
            error_code='precipitation_risk',
        )
        plan = SimpleNamespace(
            direction='none', unadjusted_ph=7.19749, target_ph=7.19754, candidates=[rejected]
        )
        self.assertEqual(
            no_reagent_message(plan),
            'the feed mixes at pH 7.20, within 0.0001 of the target pH 7.20: no pH reagent is '
            'needed; the plan without a reagent is not acceptable: Potassium Hydroxide (45% '
            'solution): precipitation risk at the target pH',
        )
        plan.candidates = []
        self.assertEqual(
            no_reagent_message(plan),
            'the feed mixes at pH 7.20, within 0.0001 of the target pH 7.20: no pH reagent is '
            'needed',
        )


class PhBandTests(unittest.TestCase):
    """Potassium sulfate alone in RO water mixes at pH 6.5447: a target 5e-4 away plans a
    reagent whose dose converges on the target; 5e-5 away is met and plans none (G25)."""

    @classmethod
    def setUpClass(cls):
        from flahax import catalogue_ph_reagents
        from tests.test_ph_adjustment import ACIDS, RO

        cls.pool = [p for p in SALTS if p['name'] == 'Potassium Sulfate']
        cls.targets = {'K': cls.pool[0]['elements']['K']}
        cls.config = dict(
            products=ACIDS + catalogue_ph_reagents(), maximum_reagent_volume_litres=5
        )
        cls.RO = RO
        cls.mixed = cls.plan(cls, 6.0).unadjusted_ph

    def plan(self, target_ph):
        return (
            plan_fertilizer_workflow(
                self.pool,
                self.targets,
                {},
                target_ph,
                final_volume=VolumeLitres(1000),
                equilibrium=self.RO,
                ph_adjustment=self.config,
            )
            .stages['ph_adjustment']
            .value
        )

    def test_the_mixed_ph(self):
        self.assertAlmostEqual(self.mixed, 6.5447, places=4)

    def test_five_ten_thousandths_away_plans_a_converged_reagent(self):
        for offset, direction in ((5e-4, 'base'), (-5e-4, 'acid')):
            with self.subTest(offset=offset):
                target = self.mixed + offset
                plan = self.plan(target)
                self.assertEqual(plan.direction, direction)
                dosed = [c for c in plan.candidates if c.direction == direction]
                self.assertTrue(dosed)
                for candidate in dosed:
                    self.assertGreater(candidate.dose_molal, 0, candidate.formula)
                    self.assertLessEqual(abs(candidate.target.ph - target), PH_TOLERANCE)

    def test_five_hundred_thousandths_away_is_met_and_plans_none(self):
        for offset in (5e-5, -5e-5):
            with self.subTest(offset=offset):
                plan = self.plan(self.mixed + offset)
                self.assertEqual(plan.direction, 'none')
                self.assertEqual(
                    {c.dose_molal for c in plan.candidates if c.status != 'not_applicable'},
                    {0.0},
                )


if __name__ == '__main__':
    unittest.main()
