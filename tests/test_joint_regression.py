# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Joint qualification accounting, failure retention and matched acid references."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch
from flahax import JointSource, make_joint_problem
from tests.test_joint_fit import problem, controls
from tools.qualify_joint_fit import independent_accounting, qualify_starts, relaxed_objective_bound


class JointQualificationTests(unittest.TestCase):
    def test_independent_lower_bound_and_zero_constraints(self):
        p = problem(
            water={'K': 120}, targets={'K': 100, 'N_NO3': 0}, maximum_concentrations={'N_NO3': 0}
        )
        r = independent_accounting(p, {}, 0.1)
        self.assertEqual(r['objectiveLowerBound'], 0.04)
        self.assertEqual(r['loss'], 0.04)
        self.assertEqual(r['lowerBoundGap'], 0)
        self.assertEqual(r['exactNutrientLimitViolations'], ['N_NO3'])
        for value in (-1, float('inf')):
            with self.assertRaises(ValueError):
                independent_accounting(p, {}, value)

    def test_failed_start_cannot_be_hidden_by_success(self):
        from flahax.aqueous_model import solve

        p = problem(
            targets={'K': 0},
            reagent=JointSource('r', {}, {}),
            reference_charge_mol_per_kg=solve({}, 7).charge_balance,
        )
        r = qualify_starts(p, [({}, 0), ({'unknown': 1}, 0)], controls(p))
        self.assertEqual(r['status'], 'qualification_incomplete')
        self.assertEqual(r['starts'][0]['status'], 'verified_numerical_candidate')
        self.assertEqual(r['starts'][1]['status'], 'unqualified')
        self.assertFalse(r['accepted'])
        with self.assertRaises(ValueError):
            qualify_starts(p, [], controls(p))

    def test_false_solver_success_is_not_qualification(self):
        p = problem()
        fake = dict(
            status='numerical_candidate',
            reason='injected',
            fertilizerDoses={},
            reagentDose=0,
            evaluation={'loss': 0, 'chargeResidual': 0, 'violations': []},
            diagnostics={},
        )
        with patch('tools.qualify_joint_fit.solve_joint_problem', return_value=fake):
            r = qualify_starts(p, [({}, 0)], controls(p))
        self.assertEqual(r['status'], 'qualification_incomplete')
        self.assertEqual(r['starts'][0]['independent']['loss'], 2)

    def test_all_pinned_acid_titrations_from_multiple_starts(self):
        paths = sorted(
            (Path(__file__).parent / 'fixtures/phreeqc/acid_selection').glob('*/expected.json')
        )
        self.assertEqual(len(paths), 4)
        for path in paths:
            data = json.loads(path.read_text())
            with self.subTest(formula=data['formula']):
                p = make_joint_problem(
                    [],
                    dict(
                        id='r',
                        chemicalFormula=data['formula'],
                        massFraction=0.5,
                        densityKgPerL=1.2,
                        source='synthetic reference input',
                        revision='1',
                        recordedAt='2026-10-26',
                    ),
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
                settings = controls(
                    p,
                    dose_steps={'r': 1e-5},
                    charge_scale=1e-6,
                    charge_tolerance=2e-12,
                    max_iterations=80,
                )
                r = qualify_starts(p, [({}, 0), ({}, 1e-4)], settings)
                self.assertEqual(r['status'], 'numerical_checks_passed', r)
                from flahax.ph_adjustment import REAGENTS

                mass = REAGENTS[data['formula']][2]
                for row in r['starts']:
                    molal = row['reagentDose'] * 0.5 / mass
                    tol = data['tolerances']
                    self.assertAlmostEqual(
                        molal,
                        data['acid_molal'],
                        delta=tol['dose_absolute'] + tol['dose_relative'] * data['acid_molal'],
                    )
                self.assertFalse(r['globalOptimalityProven'])

    def test_relaxed_bound_has_an_exact_dual_certificate(self):
        # A single product enforces equal K and Ca. Targets 100 and 200
        # minimize (x-1)^2 + (x/2-1)^2 at x=6/5, with exact loss 1/5.
        p = problem(
            [JointSource('equal', {'K': 0.1, 'Ca': 0.1}, {})],
            reagent=JointSource('r', {}, {}),
            targets={'K': 100, 'Ca': 200},
        )
        r = relaxed_objective_bound(p)
        from fractions import Fraction

        exact = Fraction(r['exactLowerBound'])
        self.assertLessEqual(exact, Fraction(1, 5))
        self.assertAlmostEqual(float(exact), 0.2, places=14)
        self.assertTrue(r['dualFeasible'])
        self.assertEqual(relaxed_objective_bound(problem(targets={'K': 0}))['lowerBound'], 0)

    def test_nonzero_best_fit_converges_with_exact_gap_not_target_relaxation(self):
        from flahax.aqueous_model import solve
        from flahax import solve_joint_problem
        from fractions import Fraction

        p = problem(
            [JointSource('equal', {'K': 0.1, 'Ca': 0.1}, {})],
            reagent=JointSource('r', {}, {}),
            targets={'K': 100, 'Ca': 200},
            reference_charge_mol_per_kg=solve({}, 7).charge_balance,
        )
        for start in (0, 0.5, 1.8):
            r = solve_joint_problem(
                p, {'equal': start}, 0, **controls(p, objective_gap_tolerance=1e-12)
            )
            self.assertEqual(r['status'], 'bounded_best_fit', r)
            self.assertAlmostEqual(r['fertilizerDoses']['equal'], 1.2, places=6)
            self.assertAlmostEqual(r['evaluation']['loss'], 0.2, places=12)
            proof = r['objectiveCertificate']
            self.assertLessEqual(Fraction(proof['exactLowerBound']), Fraction(1, 5))
            self.assertLessEqual(Fraction(proof['exactGap']), Fraction(1e-12))
            self.assertFalse(r['accepted'])
            self.assertEqual(dict(p.targets), {'K': 100, 'Ca': 200})

    def test_active_cap_certificate_and_charge_failure(self):
        from flahax.aqueous_model import solve
        from flahax import solve_joint_problem
        from flahax.joint_optimality import objective_certificate
        from fractions import Fraction

        p = problem(
            [JointSource('k', {'K': 0.1, 'Ca': 0.1}, {})],
            targets={'K': 100},
            maximum_concentrations={'Ca': 50},
            reagent=JointSource('r', {}, {}),
            reference_charge_mol_per_kg=solve({}, 7).charge_balance,
        )
        r = solve_joint_problem(p, {}, 0, **controls(p, objective_gap_tolerance=1e-12))
        self.assertEqual(r['status'], 'bounded_best_fit', r)
        self.assertLessEqual(r['evaluation']['concentrations']['K'], 50)
        proof = r['objectiveCertificate']
        self.assertLessEqual(Fraction(proof['exactLowerBound']), Fraction(1, 4))
        self.assertAlmostEqual(proof['lowerBound'], 0.25, places=12)
        self.assertFalse(objective_certificate(p, {'k': 1}, 0)['linearFeasible'])
        p = problem(
            targets={'K': 100}, reagent=JointSource('r', {}, {}), reference_charge_mol_per_kg=1
        )
        r = solve_joint_problem(
            p, {'k': 1}, 0, **controls(p, max_iterations=1, objective_gap_tolerance=1e-12)
        )
        self.assertEqual(r['status'], 'search_incomplete')
        with self.assertRaises(ValueError):
            solve_joint_problem(p, {}, 0, **controls(p, objective_gap_tolerance=-1))

    def test_certificate_corruption_and_failed_proposal_are_rejected(self):
        from copy import deepcopy
        from flahax.joint_optimality import objective_certificate
        from tools.qualify_joint_fit import verify_objective_certificate

        p = problem(
            [JointSource('k', {'K': 0.1, 'Ca': 0.1}, {})],
            targets={'K': 100},
            maximum_concentrations={'Ca': 50},
            reagent=JointSource('r', {}, {}, density_kg_per_litre=1),
            maximum_reagent_volume_litres=0.001,
        )
        # Choose a representably interior dose; the tight cap's exact dual value
        # still gives a useful bound without declaring a rounded violation feasible.
        dose = {'k': 0.4999999999999999}
        proof = objective_certificate(p, dose, 0)
        self.assertTrue(verify_objective_certificate(p, dose, 0, proof))
        for change in (
            {'dualVector': []},
            {'upperMultipliers': []},
            {'exactGap': '-1'},
            {'exactGap': 'not-a-number'},
            {'dualVector': ['-1000']},
        ):
            self.assertFalse(verify_objective_certificate(p, dose, 0, proof | change))
        bad = deepcopy(proof)
        bad['upperMultipliers'][0] = '-1'
        self.assertFalse(verify_objective_certificate(p, dose, 0, bad))
        self.assertFalse(verify_objective_certificate(p, dose, 0, {}))
        with patch('flahax.joint_optimality.nnls', side_effect=ValueError('rank failure')):
            fallback = objective_certificate(p, dose, 0)
        self.assertTrue(verify_objective_certificate(p, dose, 0, fallback))
        self.assertLessEqual(fallback['lowerBound'], 0.25)
        empty = problem(targets={'K': 0}, reagent=JointSource('r', {}, {}))
        zero = objective_certificate(empty, {}, 0)
        self.assertTrue(verify_objective_certificate(empty, {}, 0, zero))
        no_cap = problem(reagent=JointSource('r', {}, {}, density_kg_per_litre=1))
        self.assertTrue(
            verify_objective_certificate(no_cap, {}, 0, objective_certificate(no_cap, {}, 0))
        )

    def test_best_fit_qualification_uses_verified_gap(self):
        from flahax.aqueous_model import solve

        p = problem(
            [JointSource('equal', {'K': 0.1, 'Ca': 0.1}, {})],
            reagent=JointSource('r', {}, {}),
            targets={'K': 100, 'Ca': 200},
            reference_charge_mol_per_kg=solve({}, 7).charge_balance,
        )
        r = qualify_starts(
            p, [({}, 0), ({'equal': 0.5}, 0)], controls(p, objective_gap_tolerance=1e-12)
        )
        self.assertEqual(r['status'], 'numerical_checks_passed', r)
        self.assertTrue(all(s['solverStatus'] == 'bounded_best_fit' for s in r['starts']))
        self.assertFalse(r['accepted'])

    def test_linearized_charge_dual_search_has_independent_solutions(self):
        from flahax.joint_solver import _charge_constrained_step

        # min (x-b)^2 subject to x=1, x>=0: exact solution is one for either b.
        for b in (0, 2, 10):
            diagnostics = {}
            x, penalty = _charge_constrained_step(
                [[1.0], [1.0]], [b, 1], 1e-10, 20, diagnostics=diagnostics
            )
            self.assertAlmostEqual(x[0], 1, places=9)
            self.assertAlmostEqual(diagnostics['chargeMultiplier'], 2 * (b - 1), places=9)
            self.assertGreater(penalty, abs(diagnostics['chargeMultiplier']))
        x, _ = _charge_constrained_step([[1, 0], [0, 1]], [2, 3], 1e-10, 20)
        self.assertEqual(x, [2, 3])
        for matrix, rhs, tol, budget in (
            ([[1], [1]], [0, -1], 1e-10, 2),
            ([[1], [1]], [2, 1], 1e-20, 1),
            ([[1], [1e-320]], [2, 1e-320], 1e-323, 20),
        ):
            with self.assertRaises(ValueError):
                _charge_constrained_step(matrix, rhs, tol, budget)

    def test_nonzero_optimum_with_nonlinear_charge_equality(self):
        from flahax import JointProblem, solve_joint_problem

        p = problem(
            [JointSource('equal', {'K': 0.1, 'Ca': 0.1}, {})],
            reagent=JointSource('r', {}, {}),
            targets={'K': 100, 'Ca': 200},
        )
        original = JointProblem.evaluate

        def curved(self, doses, q):
            result = original(self, doses, q)
            result['chargeResidual'] = q * q - 0.09
            return result

        with patch.object(JointProblem, 'evaluate', curved):
            r = solve_joint_problem(
                p,
                {},
                0.2,
                **controls(
                    p,
                    dose_steps={'equal': 0.001, 'r': 0.001},
                    trust_radius=1000,
                    objective_gap_tolerance=1e-12,
                ),
            )
        self.assertEqual(r['status'], 'bounded_best_fit', r)
        self.assertAlmostEqual(r['reagentDose'], 0.3, places=8)
        self.assertAlmostEqual(r['fertilizerDoses']['equal'], 1.2, places=8)
        self.assertLessEqual(abs(r['evaluation']['chargeResidual']), 1e-10)

    def test_charge_constrained_stationarity_is_not_global_optimality(self):
        from flahax import JointProblem, solve_joint_problem

        p = problem(
            [JointSource('equal', {'K': 0.1, 'Ca': 0.1}, {})],
            reagent=JointSource('r', {}, {}),
            targets={'K': 100, 'Ca': 200},
        )
        original = JointProblem.evaluate

        def equality(self, doses, q):
            r = original(self, doses, q)
            r['chargeResidual'] = doses.get('equal', 0) - 1
            return r

        with patch.object(JointProblem, 'evaluate', equality):
            r = solve_joint_problem(
                p,
                {},
                0,
                **controls(
                    p,
                    objective_gap_tolerance=1e-12,
                    stationarity_tolerance=1e-6,
                    active_bound_tolerance=1e-8,
                ),
            )
        from tools.qualify_joint_fit import verify_stationarity

        settings = controls(
            p,
            objective_gap_tolerance=1e-12,
            stationarity_tolerance=1e-6,
            active_bound_tolerance=1e-8,
        )
        with patch.object(JointProblem, 'evaluate', equality):
            self.assertTrue(verify_stationarity(p, r, settings))
            qualified = qualify_starts(p, [({}, 0)], settings)
            self.assertEqual(qualified['status'], 'numerical_checks_passed', qualified)
            self.assertTrue(qualified['starts'][0]['independentStationarityVerified'])
            from copy import deepcopy

            bad = deepcopy(r)
            bad['stationarity']['chargeMultiplier'] += 10
            self.assertFalse(verify_stationarity(p, bad, settings))
            self.assertFalse(verify_stationarity(p, r | {'stationarity': None}, settings))
        self.assertEqual(r['status'], 'stationary_point', r)
        self.assertAlmostEqual(r['evaluation']['loss'], 0.25, places=9)
        self.assertTrue(r['stationarity']['passed'])
        self.assertFalse(r['globalOptimalityProven'])
        self.assertFalse(r['accepted'])
        for bad in (
            {'stationarity_tolerance': 1e-6},
            {'stationarity_tolerance': 0, 'active_bound_tolerance': 0},
            {'stationarity_tolerance': 1e-6, 'active_bound_tolerance': -1},
        ):
            with self.assertRaises(ValueError):
                solve_joint_problem(p, {}, 0, **controls(p, **bad))

    def test_stationarity_does_not_approve_an_unsettled_or_failed_check(self):
        from flahax import solve_joint_problem
        from flahax.aqueous_model import solve

        p = problem(
            [JointSource('equal', {'K': 0.1, 'Ca': 0.1}, {})],
            reagent=JointSource('r', {}, {}),
            targets={'K': 100, 'Ca': 200},
            reference_charge_mol_per_kg=solve({}, 7).charge_balance,
        )
        settings = controls(p, stationarity_tolerance=1e-6, active_bound_tolerance=1e-8)
        r = solve_joint_problem(p, {'equal': 0.5}, 0, **settings)
        self.assertEqual(r['status'], 'stationary_point', r)
        self.assertAlmostEqual(r['fertilizerDoses']['equal'], 1.2, places=8)
        with patch(
            'flahax.joint_solver._stationarity', side_effect=ValueError('failed KKT solve')
        ):
            r = solve_joint_problem(p, {'equal': 1.2}, 0, **(settings | {'max_iterations': 1}))
        self.assertEqual(r['status'], 'search_incomplete')
        self.assertGreater(r['diagnostics']['linearFailures'], 0)

    def test_adaptive_sensitivities_preserve_nonlinear_charge_closure(self):
        from flahax import JointProblem, solve_joint_problem

        p = problem(
            [JointSource('equal', {'K': 0.1, 'Ca': 0.1}, {})],
            reagent=JointSource('r', {}, {}),
            targets={'K': 100, 'Ca': 200},
        )
        original = JointProblem.evaluate

        def curve(self, doses, q):
            r = original(self, doses, q)
            r['chargeResidual'] = q * q - 0.09
            return r

        with patch.object(JointProblem, 'evaluate', curve):
            r = solve_joint_problem(
                p,
                {},
                0.2,
                **controls(
                    p,
                    dose_steps={'equal': 0.01, 'r': 0.1},
                    trust_radius=1000,
                    sensitivity_tolerance=0.001,
                    objective_gap_tolerance=1e-12,
                ),
            )
        self.assertEqual(r['status'], 'bounded_best_fit', r)
        self.assertAlmostEqual(r['reagentDose'], 0.3, places=8)
        self.assertLess(min(r['diagnostics']['differenceSteps']), 1)

    def test_stationarity_verifier_refuses_changed_constraints_and_derivatives(self):
        from dataclasses import replace
        from copy import deepcopy
        from flahax import JointProblem, solve_joint_problem
        from tools.qualify_joint_fit import verify_stationarity

        p = problem(
            [JointSource('equal', {'K': 0.1, 'Ca': 0.1, 'Na': 0.1}, {})],
            reagent=JointSource('r', {}, {}),
            targets={'K': 100, 'Ca': 200},
        )
        original = JointProblem.evaluate

        def equality(self, doses, q):
            r = original(self, doses, q)
            r['chargeResidual'] = doses.get('equal', 0) - 1
            return r

        settings = controls(p, stationarity_tolerance=1e-6, active_bound_tolerance=1e-8)
        with patch.object(JointProblem, 'evaluate', equality):
            r = solve_joint_problem(p, {'equal': 1}, 0, **settings)
            self.assertTrue(verify_stationarity(p, r, settings))
            bad = deepcopy(r)
            bad['fertilizerDoses']['equal'] = 2
            self.assertFalse(verify_stationarity(p, bad, settings))
            self.assertFalse(
                verify_stationarity(replace(p, maximum_concentrations={'Na': 100}), r, settings)
            )
            self.assertFalse(
                verify_stationarity(replace(p, maximum_reagent_mass_g=0), r, settings)
            )
            backward = deepcopy(r)
            backward['stationarity']['differenceSteps'][-1] = -1
            self.assertTrue(verify_stationarity(p, backward, settings))
            bad = deepcopy(r)
            bad['stationarity']['activeMultipliers'][0]['multiplier'] = -1
            self.assertFalse(verify_stationarity(p, bad, settings))

        def changed(self, doses, q):
            r = equality(self, doses, q)
            r['chargeResidual'] += q * q
            return r

        with patch.object(JointProblem, 'evaluate', changed):
            self.assertFalse(verify_stationarity(p, r, settings))

    def test_bounded_linear_steps_against_independent_box_solutions(self):
        from flahax.joint_linear import bounded_lstsq

        # Independent one-dimensional clipping and a coupled two-variable box.
        self.assertEqual(bounded_lstsq([[1]], [3], [0], [2], 20), [2])
        self.assertEqual(bounded_lstsq([[1]], [-3], [-2], [2], 20), [-2])
        x = bounded_lstsq([[1, 1], [1, -1]], [3, 0], [0, 0], [1, 2], 40)
        self.assertAlmostEqual(x[0], 1, places=12)
        self.assertAlmostEqual(x[1], 1.5, places=12)
        # A weak column is bounded inside the solve, without shrinking the useful x step.
        x = bounded_lstsq([[1, 0], [0, 1e-12]], [1, 1], [0, 0], [2, 2], 40)
        self.assertAlmostEqual(x[0], 1, places=12)
        self.assertEqual(x[1], 2)
        x = bounded_lstsq([[1, 1]], [1], [0, 0], [2, 2], 40)
        self.assertAlmostEqual(sum(x), 1, places=12)
        x = bounded_lstsq([[10, 1], [0, 1]], [1, 2], [0, 0], [0.1, 2], 40)
        self.assertAlmostEqual(x[0], 0, places=12)
        self.assertAlmostEqual(x[1], 1.5, places=12)
        x = bounded_lstsq([[1, 1], [0, 1e-12]], [1, 1], [0, 0], [2, 2], 40)
        self.assertTrue(all(0 <= v <= 2 for v in x))
        self.assertAlmostEqual(sum(x), 1, places=10)
        for args in (
            ([[1]], [1], [2], [1], 10),
            ([[1]], [1], [0], [2], 0),
            ([[float('inf')]], [1], [0], [2], 10),
        ):
            with self.assertRaises(ValueError):
                bounded_lstsq(*args)

    def test_restoration_backtracks_failed_chemistry_and_respects_zero_boundary(self):
        from flahax import JointProblem, solve_joint_problem, DeliveryError

        p = problem(
            [JointSource('equal', {'K': 0.1, 'Ca': 0.1}, {})],
            reagent=JointSource('r', {}, {}),
            targets={'K': 100, 'Ca': 200},
        )
        original = JointProblem.evaluate

        def curved(self, doses, q):
            if q > 0.31:
                raise DeliveryError('nonconvergent', 'injected invalid restoration trial')
            value = original(self, doses, q)
            value['chargeResidual'] = q * q - 0.09
            return value

        with patch.object(JointProblem, 'evaluate', curved):
            r = solve_joint_problem(
                p,
                {},
                0.2,
                **controls(
                    p,
                    dose_steps={'equal': 0.001, 'r': 0.001},
                    trust_radius=1000,
                    objective_gap_tolerance=1e-12,
                ),
            )
        self.assertEqual(r['status'], 'bounded_best_fit', r)
        self.assertGreater(r['diagnostics']['chargeRestorations'], 0)
        self.assertGreater(r['diagnostics']['rejectedTrials'], 0)

        def linear(self, doses, q):
            value = original(self, doses, q)
            value['chargeResidual'] = doses.get('equal', 0) + q - 1
            return value

        with patch.object(JointProblem, 'evaluate', linear):
            r = solve_joint_problem(
                p,
                {'equal': 2},
                0,
                **controls(p, stationarity_tolerance=1e-6, active_bound_tolerance=1e-8),
            )
        self.assertEqual(r['status'], 'stationary_point', r)
        self.assertEqual(r['reagentDose'], 0)
        self.assertAlmostEqual(r['fertilizerDoses']['equal'], 1, places=8)

    def test_bounded_linear_rank_failure_does_not_invent_an_unbounded_step(self):
        from flahax.joint_linear import bounded_lstsq

        with patch('flahax.joint_linear._lstsq', side_effect=ValueError('rank failure')):
            x = bounded_lstsq([[1]], [1], [0], [2], 10)
        self.assertEqual(x, [0])

    def test_invalid_restoration_region_and_unchanged_trial_remain_incomplete(self):
        from flahax import JointProblem, solve_joint_problem, DeliveryError
        from flahax.aqueous_model import solve

        p = problem(
            targets={'K': 100},
            reagent=JointSource('r', {}, {}),
            reference_charge_mol_per_kg=solve({}, 7).charge_balance,
        )
        with patch('flahax.joint_solver._charge_constrained_step', return_value=([0, 0], 1)):
            r = solve_joint_problem(
                p, {}, 0, **controls(p, objective_gap_tolerance=1e-12, max_iterations=1)
            )
        self.assertEqual(r['status'], 'search_incomplete')
        self.assertGreater(r['fertilizerDoses']['k'], 0)
        original = JointProblem.evaluate

        def domain(self, doses, q):
            if q < 0.2:
                raise DeliveryError('nonconvergent', 'injected unavailable restoration domain')
            r = original(self, doses, q)
            r['chargeResidual'] = q - 0.1
            return r

        with patch.object(JointProblem, 'evaluate', domain):
            r = solve_joint_problem(
                p,
                {},
                0.2,
                **controls(p, objective_gap_tolerance=1e-12, max_iterations=1, max_backtracks=3),
            )
        self.assertEqual(r['status'], 'search_incomplete')
        self.assertGreaterEqual(r['diagnostics']['rejectedTrials'], 3)

    def test_curved_charge_equality_corrects_trial_without_relaxing_targets(self):
        from flahax import JointProblem, solve_joint_problem

        p = problem(targets={'K': 100}, reagent=JointSource('r', {}, {}), maximum_reagent_mass_g=2)
        original = JointProblem.evaluate

        def curved(self, doses, q):
            value = original(self, doses, q)
            value['chargeResidual'] = q - doses.get('k', 0) ** 2
            return value

        with patch.object(JointProblem, 'evaluate', curved):
            r = solve_joint_problem(
                p, {'k': 0.5}, 0.25, **controls(p, objective_gap_tolerance=1e-12, max_iterations=4)
            )
        self.assertEqual(r['status'], 'numerical_candidate', r)
        self.assertAlmostEqual(r['fertilizerDoses']['k'], 1, places=8)
        self.assertAlmostEqual(r['reagentDose'], 1, places=8)
        self.assertGreater(r['diagnostics']['trialChargeCorrections'], 0)
        self.assertLessEqual(abs(r['evaluation']['chargeResidual']), 1e-10)

    def test_near_optimum_charge_roundoff_does_not_hide_nutrient_improvement(self):
        from decimal import Decimal, localcontext
        from flahax import JointProblem, solve_joint_problem
        from tools.qualify_joint_fit import verify_stationarity

        # f=(x-1)^2+(q/2-1)^2, q=x^2: df/dx=x^3-2.
        # Bisection in Decimal is independent of the solver and its differences.
        with localcontext() as context:
            context.prec = 60
            lower, upper = Decimal(1), Decimal(2)
            for _ in range(200):
                middle = (lower + upper) / 2
                if middle**3 > 2:
                    upper = middle
                else:
                    lower = middle
            optimum = float((lower + upper) / 2)
        p = problem(targets={'K': 100, 'N_NO3': 200}, maximum_reagent_mass_g=4)
        original = JointProblem.evaluate

        def curved(self, doses, q):
            value = original(self, doses, q)
            value['chargeResidual'] = q - doses.get('k', 0) ** 2
            return value

        settings = controls(
            p,
            dose_steps={'k': 0.001, 'r': 0.001},
            trust_radius=1000,
            charge_tolerance=2e-12,
            sensitivity_tolerance=1e-4,
            stationarity_tolerance=1e-9,
            active_bound_tolerance=1e-8,
            max_iterations=24,
        )
        start = optimum + 1e-8
        with patch.object(JointProblem, 'evaluate', curved):
            result = solve_joint_problem(p, {'k': start}, start**2, **settings)
            self.assertEqual(result['status'], 'stationary_point', result)
            self.assertTrue(verify_stationarity(p, result, settings))
        self.assertLess(abs(result['fertilizerDoses']['k'] - optimum), 1e-9)
        self.assertLessEqual(abs(result['evaluation']['chargeResidual']), 2e-12)
        self.assertFalse(result['accepted'])

    def test_linear_nutrient_gradient_is_independent_of_probe_size(self):
        from fractions import Fraction as F
        from flahax import JointProblem, solve_joint_problem

        p = problem(
            [JointSource('equal', {'K': 0.1, 'Ca': 0.1}, {})],
            targets={'K': 100, 'Ca': 200},
            reagent=JointSource('r', {}, {}),
        )
        original = JointProblem.evaluate

        def constrained(self, doses, q):
            result = original(self, doses, q)
            result['chargeResidual'] = doses.get('equal', 0) - 1
            return result

        for h in (1e-3, 1e-5, 1e-7):
            with patch.object(JointProblem, 'evaluate', constrained):
                result = solve_joint_problem(
                    p,
                    {'equal': 1},
                    0,
                    **controls(
                        p,
                        dose_steps={'equal': h, 'r': 0.001},
                        stationarity_tolerance=1e-6,
                        active_bound_tolerance=1e-8,
                    ),
                )
            self.assertEqual(result['status'], 'stationary_point')
            expected = (
                2
                * F(h)
                * sum((F(1000) * F(0.1) / F(t) - 1) * F(1000) * F(0.1) / F(t) for t in (100, 200))
            )
            self.assertAlmostEqual(
                result['stationarity']['gradient'][0],
                float(expected),
                delta=abs(float(expected)) * 1e-13,
            )
