# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent small optimization witnesses and safeguarded failure boundaries."""

import unittest
from unittest.mock import patch
from flahax import JointSource, JointProblem, DeliveryError
from flahax.joint_solver import solve_joint_problem


def problem(salts=None, **changes):
    args = dict(
        fertilizers=tuple(salts or [JointSource('k', {'K': 0.1}, {})]),
        reagent=JointSource('r', {'N_NO3': 0.1}, {}),
        targets={'K': 100, 'N_NO3': 20},
        water={},
        water_components={},
        final_volume_litres=1,
        solvent_mass_kg=1,
        target_ph=7,
        reference_charge_mol_per_kg=0,
        maximum_reagent_mass_g=1,
    )
    return JointProblem(**(args | changes))


def controls(p, **changes):
    return (
        dict(
            dose_steps={s.product_id: 0.1 for s in (*p.fertilizers, p.reagent)},
            charge_scale=1,
            charge_tolerance=1e-10,
            loss_tolerance=1e-16,
            sensitivity_tolerance=0.01,
            trust_radius=10,
            max_iterations=80,
            max_backtracks=20,
        )
        | changes
    )


class JointFitTests(unittest.TestCase):
    def test_exact_independent_joint_optimum(self):
        p = problem()
        evaluate = JointProblem.evaluate

        def linear(self, doses, reagent):
            result = evaluate(self, doses, reagent)
            result['chargeResidual'] = reagent - 0.2 * doses.get('k', 0)
            return result

        with patch.object(JointProblem, 'evaluate', linear):
            result = solve_joint_problem(p, {}, 0, **controls(p))
        self.assertEqual(result['status'], 'numerical_candidate')
        self.assertAlmostEqual(result['fertilizerDoses']['k'], 1, places=8)
        self.assertAlmostEqual(result['reagentDose'], 0.2, places=8)
        self.assertFalse(result['accepted'])
        self.assertLessEqual(result['evaluation']['loss'], 1e-16)

    def test_active_cap_and_rank_dependent_products(self):
        p = problem(
            [JointSource('a', {'K': 0.1, 'Na': 0.1}, {}), JointSource('b', {'K': 0.1}, {})],
            targets={'K': 100},
            reagent=JointSource('r', {}, {}),
            maximum_reagent_mass_g=0,
            maximum_concentrations={'Na': 50},
        )
        evaluate = JointProblem.evaluate

        def linear(self, doses, reagent):
            result = evaluate(self, doses, reagent)
            result['chargeResidual'] = 0
            return result

        with patch.object(JointProblem, 'evaluate', linear):
            result = solve_joint_problem(p, {}, 0, **controls(p))
        self.assertEqual(result['status'], 'numerical_candidate')
        self.assertLessEqual(result['fertilizerDoses']['a'], 0.5)
        self.assertAlmostEqual(sum(result['fertilizerDoses'].values()), 1, places=8)
        self.assertEqual(result['reagentDose'], 0)
        self.assertEqual(result['evaluation']['violations'], [])

    def test_exhaustion_and_missing_chemistry_never_converge(self):
        p = problem(water_components=None)
        r = solve_joint_problem(p, {}, 0, **controls(p))
        self.assertEqual(r['status'], 'search_incomplete')
        self.assertEqual(r['reason'], 'initial_evaluation_failed')
        p = problem()
        r = solve_joint_problem(p, {}, 0, **controls(p, max_iterations=1, trust_radius=0.01))
        self.assertEqual(r['status'], 'search_incomplete')
        self.assertFalse(r['accepted'])

    def test_bad_nonlinear_trials_and_unstable_sensitivity_are_rejected(self):
        p = problem(targets={'K': 0}, maximum_reagent_mass_g=1, reagent=JointSource('r', {}, {}))
        evaluate = JointProblem.evaluate

        def nonlinear(self, doses, reagent):
            if reagent > 0.5:
                raise DeliveryError('nonconvergent', 'deliberately bad trial')
            result = evaluate(self, doses, reagent)
            result['chargeResidual'] = reagent * reagent - 0.09
            return result

        with patch.object(JointProblem, 'evaluate', nonlinear):
            r = solve_joint_problem(
                p,
                {},
                0,
                **controls(
                    p,
                    dose_steps={"k": 0.1, "r": 0.8},
                    trust_radius=10,
                    charge_tolerance=1e-8,
                    sensitivity_tolerance=1e-8,
                    max_iterations=120,
                ),
            )
        self.assertEqual(r['status'], 'numerical_candidate')
        self.assertAlmostEqual(r['reagentDose'], 0.3, places=6)
        self.assertGreater(r['diagnostics']['sensitivityFailures'], 0)
        self.assertGreater(r['diagnostics']['rejectedTrials'], 0)
        self.assertEqual(r['fertilizerDoses']['k'], 0)

    def test_rank_failure_falls_back_and_zero_dose_is_valid(self):
        p = problem(targets={'K': 10, 'N_NO3': 0}, maximum_reagent_mass_g=0)
        evaluate = JointProblem.evaluate

        def linear(self, doses, reagent):
            r = evaluate(self, doses, reagent)
            r['chargeResidual'] = 0
            return r

        with (
            patch.object(JointProblem, 'evaluate', linear),
            patch('flahax.joint_solver.nnls', side_effect=ValueError('rank failure')),
        ):
            r = solve_joint_problem(p, {}, 0, **controls(p))
        self.assertEqual(r['status'], 'numerical_candidate')
        self.assertEqual(r['reagentDose'], 0)
        self.assertGreater(r['diagnostics']['linearFailures'], 0)
        self.assertEqual(r['evaluation']['concentrations']['K'], 10)

    def test_final_recomputation_cannot_inherit_success(self):
        p = problem(targets={'K': 0, 'N_NO3': 0})
        evaluate = JointProblem.evaluate
        calls = 0

        def stateful(self, doses, reagent):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise DeliveryError('nonconvergent', 'final check fails')
            r = evaluate(self, doses, reagent)
            r['chargeResidual'] = 0
            return r

        with patch.object(JointProblem, 'evaluate', stateful):
            r = solve_joint_problem(p, {}, 0, **controls(p))
        self.assertEqual(r['status'], 'search_incomplete')
        self.assertIsNone(r['evaluation'])
        self.assertFalse(r['accepted'])

    def test_real_nitric_reference(self):
        import json
        from pathlib import Path
        from flahax import make_joint_problem

        data = json.loads(
            (
                Path(__file__).parent / 'fixtures/phreeqc/acid_selection/HNO3/expected.json'
            ).read_text()
        )
        reagent = dict(
            id='r',
            chemicalFormula='HNO3',
            massFraction=0.5,
            densityKgPerL=1.2,
            source='pinned test',
            revision='1',
            recordedAt='2026-10-26',
        )
        p = make_joint_problem(
            [],
            reagent,
            {'Na': 45.979538},
            {'Na': 45.979538, 'Cl': 70.906},
            reagent_solvent_fraction=0.5,
            water_components=data['totals'],
            final_volume_litres=100,
            solvent_mass_kg=100,
            target_ph=data['target_ph'],
            reference_charge_mol_per_kg=0,
            maximum_reagent_mass_g=10,
        )
        r = solve_joint_problem(
            p,
            {},
            0,
            **controls(
                p,
                dose_steps={'r': 1e-5},
                charge_scale=1e-6,
                charge_tolerance=2e-12,
                trust_radius=10,
            ),
        )
        self.assertEqual(r['status'], 'numerical_candidate')
        actual_molal = r['reagentDose'] * 0.5 / 63.01284
        tolerance = data['tolerances']
        self.assertAlmostEqual(
            actual_molal,
            data['acid_molal'],
            delta=tolerance['dose_absolute'] + tolerance['dose_relative'] * data['acid_molal'],
        )
        self.assertLessEqual(abs(r['evaluation']['chargeResidual']), 2e-12)

    def test_invalid_controls_and_initial_constraints(self):
        p = problem(maximum_concentrations={'Na': 0}, water={'Na': 1})
        r = solve_joint_problem(p, {}, 0, **controls(p))
        self.assertEqual(r['reason'], 'initial_evaluation_failed')
        for change in (
            {'dose_steps': {}},
            {'charge_scale': 0},
            {'charge_tolerance': -1},
            {'loss_tolerance': -1},
            {'sensitivity_tolerance': float('nan')},
            {'trust_radius': True},
            {'max_iterations': 0},
            {'max_backtracks': 1.5},
        ):
            with self.subTest(change=change), self.assertRaises(DeliveryError):
                solve_joint_problem(problem(), {}, 0, **controls(problem(), **change))
        with self.assertRaises(DeliveryError):
            solve_joint_problem(None, {}, 0, **controls(problem()))

    def test_product_switch_on_active_shared_cap_recomputes_state(self):
        p = problem(
            [JointSource('a', {'K': 0.1, 'N_NO3': 0.1}, {}), JointSource('b', {'K': 0.1}, {})],
            targets={'N_NO3': 100},
            maximum_concentrations={'K': 100},
            reagent=JointSource('r', {}, {}),
            maximum_reagent_mass_g=0,
        )
        evaluate = JointProblem.evaluate
        visited = []

        def linear(self, doses, reagent):
            visited.append(dict(doses))
            r = evaluate(self, doses, reagent)
            r['chargeResidual'] = 0
            return r

        with patch.object(JointProblem, 'evaluate', linear):
            r = solve_joint_problem(p, {'b': 1}, 0, **controls(p))
        self.assertEqual(r['status'], 'numerical_candidate')
        self.assertAlmostEqual(r['fertilizerDoses']['a'], 1)
        self.assertAlmostEqual(r['fertilizerDoses']['b'], 0)
        self.assertEqual(visited[-1], r['fertilizerDoses'])
        self.assertEqual(r['evaluation']['violations'], [])

    def test_flat_response_and_nonfinite_merit_remain_incomplete(self):
        p = problem(targets={'K': 0}, reagent=JointSource('r', {}, {}))
        evaluate = JointProblem.evaluate
        for charge in (1, float('inf')):

            def flat(self, doses, reagent):
                r = evaluate(self, doses, reagent)
                r['chargeResidual'] = charge
                return r

            with patch.object(JointProblem, 'evaluate', flat):
                r = solve_joint_problem(p, {}, 0, **controls(p, max_iterations=2))
            self.assertEqual(r['status'], 'search_incomplete')
            self.assertFalse(r['globalOptimalityProven'])

    def test_volume_cap_and_unrepresentable_constraint(self):
        p = problem(
            reagent=JointSource('r', {}, {}, density_kg_per_litre=1),
            maximum_reagent_volume_litres=0.0001,
        )
        r = solve_joint_problem(p, {}, 0.2, **controls(p))
        self.assertEqual(r['reason'], 'initial_evaluation_failed')
        with self.assertRaises(DeliveryError):
            solve_joint_problem(
                problem(maximum_concentrations={"K": 100}),
                {},
                0,
                **controls(problem(), dose_steps={"k": 1e308, "r": 0.1}),
            )

    def test_finite_but_inconsistent_derivatives_are_discarded(self):
        p = problem(targets={'K': 0}, reagent=JointSource('r', {}, {}))
        evaluate = JointProblem.evaluate

        def curved(self, doses, reagent):
            r = evaluate(self, doses, reagent)
            r['chargeResidual'] = reagent**2 - 0.09
            return r

        with patch.object(JointProblem, 'evaluate', curved):
            r = solve_joint_problem(
                p,
                {},
                0,
                **controls(
                    p, sensitivity_tolerance=1e-8, charge_tolerance=1e-8, max_iterations=120
                ),
            )
        self.assertEqual(r['status'], 'numerical_candidate')
        self.assertAlmostEqual(r['reagentDose'], 0.3, places=6)
        # k is fixed to zero, but the finite nonlinear reagent column must also
        # fail the h versus h/2 check rather than being treated as reliable.
        self.assertGreater(r['diagnostics']['sensitivityFailures'], r['diagnostics']['iterations'])
