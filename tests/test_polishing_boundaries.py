# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Synthetic proposal refusal witnesses, separate from chemistry qualification."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch
from flahax import joint_solver as solver
from flahax.joint_polishing import block_polish_direction


class WholeMixBoundaryTests(unittest.TestCase):
    def test_exchange_stays_on_charge_surface_and_binding_nutrient_cap(self):
        from flahax.joint_active_set import whole_mix_direction

        # Minimize (a-1)^2 + (b-3)^2 with a+b <= 1, a,b >= 0.
        # At the cap a unit exchange favors b all the way to (0,1).
        point = [0.5, 0.5, 0.5]
        matrix = [[1, 0, 0], [0, 1, 0], [1, 1, -1]]
        limits = [([-1, 0, 0], 0), ([0, -1, 0], 0), ([0, 0, -1], 0), ([1, 1, 0], 1)]
        direction, _ = whole_mix_direction(point, [-0.5, -2.5, 0], matrix, limits, 20)
        for actual, expected in zip(direction, [-0.5, 0.5, 0.0]):
            self.assertAlmostEqual(actual, expected)

    def test_declared_zero_keeps_its_only_source_out_of_the_step(self):
        from flahax.joint_active_set import whole_mix_direction

        point = [0.0, 0.5, 0.5]
        matrix = [[1, 1, 0], [0, 1, -1]]
        limits = [([-1, 0, 0], 0), ([0, -1, 0], 0), ([0, 0, -1], 0), ([1, 0, 0], 0)]
        direction, _ = whole_mix_direction(point, [-1.0, 0.0], matrix, limits, 20)
        self.assertEqual(direction[0], 0.0)
        self.assertAlmostEqual(direction[1], 1.0)
        self.assertAlmostEqual(direction[2], 1.0)


class WholeMixRefusalTests(unittest.TestCase):
    """Synthetic trial-model boundaries. These are numerical checks, not chemistry fixtures."""

    def trial(self, **changes):
        from flahax.joint_active_set import whole_mix_trial

        def value(u, **kw):
            residual = u[0] - 2
            charge = u[1] - 1 + (u[0] - 1) ** 2
            return ({'chargeResidual': charge}, [residual, charge], 0, residual**2)

        matrix = [[1.0, 0.0], [0.0, 1.0]]
        args = dict(
            point=[1.0, 1.0],
            current=value([1.0, 1.0]),
            matrix=matrix,
            constraints=[([-1.0, 0.0], 0.0), ([0.0, -1.0], 0.0)],
            radius=2.0,
            budget=3,
            charge_tolerance=1e-12,
            evaluate=value,
            active_tolerance=1e-8,
            matrix_at=lambda state: matrix,
            improves_stationarity=lambda u, v: False,
            charge_scale=1.0,
        )
        return whole_mix_trial(**(args | changes))

    def test_no_proposal_when_variables_fixed_charge_flat_or_budget_spent(self):
        from flahax.joint_active_set import whole_mix_direction

        point, residual = [1.0, 1.0], [-1.0, 0.0]
        mat = [[1.0, 0.0], [0.0, 1.0]]
        self.assertIsNone(whole_mix_direction(point, residual, mat, [([1.0, 1.0], 0.0)], 4))
        self.assertIsNone(whole_mix_direction(point, residual, [mat[0], [0.0, 0.0]], [], 4))
        self.assertIsNone(whole_mix_direction(point, residual, mat, [], 0))

    def test_refinement_refuses_an_empty_face_or_unusable_charge_tangent(self):
        self.assertIsNone(self.trial(refine=True, point=[0.0, 0.0]))
        box = [([-1.0, 0.0], 0.0), ([0.0, -1.0], 0.0), ([1.0, 0.0], 1.0), ([0.0, 1.0], 1.0)]
        self.assertIsNone(self.trial(refine=True, constraints=box))
        self.assertIsNone(self.trial(refine=True, matrix=[[1.0, 0.0], [0.0, 0.0]]))
        self.assertIsNone(
            self.trial(
                refine=True,
                point=[5e-324, 0.0],
                active_tolerance=0.0,
                matrix=[[1.0, 0.0], [1.0, 0.0]],
            )
        )

    def test_a_failed_curvature_probe_or_unusable_trial_has_no_result(self):
        self.assertIsNone(self.trial(refine=True, evaluate=lambda u, **kw: None))

        def failed_probe(u, **kwargs):
            raise ValueError('out of model domain')

        self.assertIsNone(self.trial(refine=True, evaluate=failed_probe))
        self.assertIsNone(self.trial(evaluate=lambda u, **kw: None))

    def test_zero_step_and_sub_roundoff_moves_do_not_claim_progress(self):
        self.assertIsNone(self.trial(current=({'chargeResidual': 0}, [0.0, 0.0], 0.0, 0.0)))
        self.assertIsNone(self.trial(radius=1e-20))

    def test_charge_correction_obeys_pivot_trust_and_backtrack_limits(self):
        def outside_charge(u, **kwargs):
            return ({'chargeResidual': 10.0}, [-1.0, 10.0], 0.0, 1.0)

        self.assertIsNone(self.trial(matrix=[[0.0, 1.0], [1.0, 0.0]], evaluate=outside_charge))
        self.assertIsNone(self.trial(evaluate=outside_charge))
        self.assertIsNone(self.trial(evaluate=outside_charge, radius=0.1))

        # A useful correction on the last allowed iteration still misses charge.
        def halves(u, **kwargs):
            charge = 0.5 * (u[1] - 1) + 0.1
            return ({'chargeResidual': charge}, [-1.0, charge], 0.0, 1.0)

        self.assertIsNone(self.trial(evaluate=halves, budget=1))


class PolishingBoundaryTests(unittest.TestCase):
    def arguments(self, n=3):
        source = SimpleNamespace(components={})
        problem = SimpleNamespace(fertilizers=[source] * (n - 1), reagent=source)
        value = ({'chargeResidual': 0, 'equilibrium': SimpleNamespace(totals={})}, [1, 0])
        return dict(
            problem=problem,
            point=[1.0] * n,
            value=value,
            matrix=[[1.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            scales=[1.0] * n,
            constraints=[],
            charge_scale=1,
            charge_tolerance=1e-10,
            sensitivity_tolerance=0.1,
            radius=1,
            budget=2,
            evaluate=lambda point: value,
        )

    def test_scalar_proposal_requires_active_pivot_and_useful_coordinate(self):
        args = self.arguments()
        self.assertIsNone(solver._polish_direction(**(args | {'point': [0, 0, 0]})))
        self.assertIsNone(solver._polish_direction(**(args | {'point': [0, 0, 1]})))
        self.assertIsNone(solver._polish_direction(**(args | {'evaluate': lambda p: None})))

    def test_scalar_probe_refuses_nonclosing_or_zero_curvature_response(self):
        args = self.arguments()
        bad = ({'chargeResidual': 1}, [1, 1])
        for budget in (0, 2):
            self.assertIsNone(
                solver._polish_direction(**(args | {'evaluate': lambda p: bad, 'budget': budget}))
            )
        with patch.object(solver, '_implicit_matrix', return_value=args['matrix']):
            self.assertIsNone(solver._polish_direction(**args))
        with patch.object(solver, '_implicit_matrix', return_value=[[1, 1, 0], [0, 0, 0]]):
            self.assertIsNone(solver._polish_direction(**args))

    def test_scalar_active_constraint_can_reverse_the_probe(self):
        args = self.arguments()
        visited = []
        args['constraints'] = [([1, 0, 0], 1)]
        args['evaluate'] = lambda point: visited.append(point) or None
        self.assertIsNone(solver._polish_direction(**args))
        self.assertLess(visited[0][0], 1)

    def test_block_requires_candidate_nonzero_and_positive_correlation(self):
        args = self.arguments()
        self.assertIsNone(block_polish_direction(**args, candidate=None))
        for matrix in (
            [[0, 1, 0], [0, 0, 1]],
            [[1, 0, 0], [0, 0, 1]],
            [[1, -1, 0], [0, 0, 1]],
        ):
            self.assertIsNone(
                block_polish_direction(**(args | {'matrix': matrix}), candidate=([], 0, 0))
            )

    def test_block_refuses_failed_nonclosing_or_zero_curvature_probe(self):
        args = self.arguments()
        self.assertIsNone(
            block_polish_direction(**(args | {'evaluate': lambda p: None}), candidate=([], 0, 0))
        )
        bad = ({'chargeResidual': 1}, [1, 1])
        for budget in (0, 2):
            self.assertIsNone(
                block_polish_direction(
                    **(args | {'evaluate': lambda p: bad, 'budget': budget}), candidate=([], 0, 0)
                )
            )
        with patch.object(solver, '_implicit_matrix', return_value=args['matrix']):
            self.assertIsNone(block_polish_direction(**args, candidate=([], 0, 0)))
        with patch.object(solver, '_implicit_matrix', return_value=[[1, 1, 0], [0, 0, 0]]):
            self.assertIsNone(block_polish_direction(**args, candidate=([], 0, 0)))

    def test_block_active_constraint_can_reverse_the_probe(self):
        args = self.arguments()
        visited = []
        args['constraints'] = [([1, 0, 0], 1)]
        args['evaluate'] = lambda point: visited.append(point) or None
        self.assertIsNone(block_polish_direction(**args, candidate=([], 0, 0)))
        self.assertLess(visited[0][0], 1)


class JointFailureCertificateTests(unittest.TestCase):
    def test_cold_recheck_cannot_keep_warm_success_when_correction_fails(self):
        from flahax import JointProblem, JointSource, DeliveryError
        from tests.test_joint_fit import problem, controls

        p = problem(targets={'K': 0}, reagent=JointSource('r', {}, {}))
        original = JointProblem.evaluate
        for derivative in ('error', [0, 0], [0, 1], [0, -1], [0, -100]):
            calls = []

            def stale(self, doses, reagent, **kwargs):
                result = original(self, doses, reagent, **kwargs)
                result['chargeResidual'] = 0 if not calls else 1
                calls.append((dict(doses), reagent))
                return result

            def gradient(*args):
                if derivative == 'error':
                    raise DeliveryError('unresolved_sensitivity', 'injected derivative failure')
                return derivative

            with patch.object(JointProblem, 'evaluate', stale):
                with patch('flahax.joint_sensitivity.equilibrium_charge_gradient', gradient):
                    result = solver.solve_joint_problem(
                        p,
                        {},
                        0,
                        **controls(
                            p, sensitivity_method='equilibrium', max_backtracks=2, trust_radius=0.1
                        ),
                    )
            self.assertEqual(result['status'], 'search_incomplete')
            self.assertFalse(result['accepted'])
            self.assertEqual(result['evaluation']['chargeResidual'], 1)

    def test_failed_boundary_sensitivity_never_certifies_a_snapped_dose(self):
        from flahax import DeliveryError
        from tests import test_joint_problem_contract as contract
        from tests.test_joint_fit import controls

        p = contract.JointContractTests().problem()
        for active in (None, 1e-8):
            changes = dict(sensitivity_method='equilibrium', max_iterations=2)
            if active is not None:
                changes.update(active_bound_tolerance=active, stationarity_tolerance=1e-6)
            with patch(
                'flahax.joint_sensitivity.equilibrium_charge_gradient',
                side_effect=DeliveryError('unresolved_sensitivity', 'injected'),
            ):
                result = solver.solve_joint_problem(
                    p, {'salt': 0.3}, 1e-12, **controls(p, **changes)
                )
            self.assertEqual(result['status'], 'search_incomplete')
            self.assertFalse(result['accepted'])
            self.assertEqual(result['reason'], 'sensitivity_failed')


class ExactChargeStepBoundaryTests(unittest.TestCase):
    def test_dual_search_reaches_an_exact_representable_charge(self):
        diagnostics = {}
        point, penalty = solver._charge_constrained_step(
            [[1.0], [1.0]],
            [2.0, 1.0],
            1e-12,
            80,
            lower=[0.0],
            upper=[10.0],
            diagnostics=diagnostics,
        )
        self.assertAlmostEqual(point[0], 1, places=12)
        self.assertGreater(penalty, abs(diagnostics['chargeMultiplier']))
        self.assertAlmostEqual(abs(diagnostics['chargeMultiplier']), 2, places=10)


class PolishingOverflowBoundaryTests(unittest.TestCase):
    def test_finite_probe_data_cannot_emit_a_nonfinite_block_direction(self):
        args = PolishingBoundaryTests().arguments()
        probe = ({'chargeResidual': 0}, [1e155, 0])
        args['evaluate'] = lambda point: probe
        with patch.object(solver, '_implicit_matrix', return_value=args['matrix']):
            self.assertIsNone(block_polish_direction(**args, candidate=([], 0, 0)))


class RecomputedCertificateBoundaryTests(unittest.TestCase):
    def test_failed_sensitivity_of_snapped_endpoint_is_not_a_recovery(self):
        from flahax import JointProblem, JointSource, DeliveryError
        from tests.test_joint_fit import problem, controls

        p = problem(targets={'K': 200}, reagent=JointSource('r', {}, {}))
        original = JointProblem.evaluate

        def neutral(self, doses, reagent, **kwargs):
            result = original(self, doses, reagent, **kwargs)
            result['chargeResidual'] = 0
            return result

        with patch.object(JointProblem, 'evaluate', neutral):
            with patch(
                'flahax.joint_sensitivity.equilibrium_charge_gradient',
                side_effect=DeliveryError('unresolved_sensitivity', 'injected'),
            ):
                result = solver.solve_joint_problem(
                    p,
                    {'k': 1},
                    1e-12,
                    **controls(
                        p,
                        sensitivity_method='equilibrium',
                        stationarity_tolerance=1e-6,
                        active_bound_tolerance=1e-8,
                    ),
                )
        self.assertEqual(result['reason'], 'sensitivity_failed')
        self.assertFalse(result['accepted'])
        self.assertNotEqual(result['reagentDose'], 0)

    def test_final_derivative_failure_discards_a_prior_stationarity_certificate(self):
        from flahax import JointProblem, JointSource, DeliveryError
        from tests.test_joint_fit import problem, controls

        p = problem(targets={'K': 200}, reagent=JointSource('r', {}, {}))
        original = JointProblem.evaluate

        def neutral(self, doses, reagent, **kwargs):
            result = original(self, doses, reagent, **kwargs)
            result['chargeResidual'] = 0
            return result

        with patch.object(JointProblem, 'evaluate', neutral):
            with patch(
                'flahax.joint_sensitivity.equilibrium_charge_gradient',
                side_effect=[[0, 0], DeliveryError('unresolved_sensitivity', 'final derivative')],
            ):
                with patch.object(solver, '_stationarity', return_value={'passed': True}):
                    result = solver.solve_joint_problem(
                        p,
                        {'k': 1},
                        0,
                        **controls(
                            p,
                            sensitivity_method='equilibrium',
                            stationarity_tolerance=1e-6,
                            active_bound_tolerance=1e-8,
                        ),
                    )
        self.assertEqual(result['status'], 'search_incomplete')
        self.assertFalse(result['accepted'])
        self.assertIn('final derivative', result['diagnostics']['lastError'])


class OptionalPolishingFailureTests(unittest.TestCase):
    def curved_case(self, start=(0.8, 0.7, 1.13), fail_below=None, backtracks=20):
        from flahax import JointProblem, JointSource
        from tests.test_joint_fit import problem, controls

        p = problem(
            [JointSource('a', {'K': 0.125}, {}), JointSource('b', {'K': 0.125}, {})],
            reagent=JointSource('r', {'N_NO3': 0.125}, {}),
            targets={'K': 250, 'N_NO3': 125},
            maximum_reagent_mass_g=4,
        )
        original = JointProblem.evaluate

        def curved(self, doses, reagent, **kwargs):
            state = original(self, doses, reagent, **kwargs)
            a, b = doses.get('a', 0), doses.get('b', 0)
            if fail_below is not None and 0 < a < fail_below:
                from flahax import DeliveryError

                raise DeliveryError('nonconvergent', 'injected trial domain boundary')
            state['chargeResidual'] = reagent - a * a - b * b
            state['witnessDoses'] = a, b
            return state

        def derivative(problem, state):
            a, b = state['witnessDoses']
            return [-2 * a, -2 * b, 1]

        settings = controls(
            p,
            sensitivity_method='equilibrium',
            curvature_block=True,
            stationarity_tolerance=1e-6,
            active_bound_tolerance=1e-8,
            max_iterations=20,
            max_backtracks=backtracks,
        )
        with patch.object(JointProblem, 'evaluate', curved):
            with patch('flahax.joint_sensitivity.equilibrium_charge_gradient', derivative):
                return solver.solve_joint_problem(
                    p, {'a': start[0], 'b': start[1]}, start[2], **settings
                )

    def test_optional_coordinate_or_block_failure_preserves_explicit_status(self):
        from flahax import DeliveryError

        cases = [
            (
                'flahax.joint_solver._polish_direction',
                DeliveryError('numerical_failure', 'probe failure'),
            ),
            ('flahax.joint_solver._polish_direction', None),
            ('flahax.joint_polishing.block_polish_direction', ZeroDivisionError('probe failure')),
        ]
        for target, failure in cases:
            with self.subTest(target=target, failure=failure):
                options = {'side_effect': failure} if failure else {'return_value': None}
                with patch(target, **options) as optional:
                    result = self.curved_case()
                self.assertGreater(optional.call_count, 0)
                self.assertFalse(result['accepted'])
                self.assertFalse(result['globalOptimalityProven'])
                self.assertIn(result['status'], ('search_incomplete', 'stationary_point'))
                if result['status'] == 'stationary_point':
                    self.assertLessEqual(abs(result['evaluation']['chargeResidual']), 1e-10)


class ChargeRestorationFailureTests(unittest.TestCase):
    def test_flat_response_rejects_restoration_despite_nonzero_reported_derivative(self):
        from flahax import JointProblem
        from tests.test_joint_fit import problem, controls

        p = problem()
        original = JointProblem.evaluate

        def flat(self, doses, reagent, **kwargs):
            state = original(self, doses, reagent, **kwargs)
            state['chargeResidual'] = 1
            return state

        with patch.object(JointProblem, 'evaluate', flat):
            with patch(
                'flahax.joint_sensitivity.equilibrium_charge_gradient', return_value=[0, 1]
            ):
                result = solver.solve_joint_problem(
                    p,
                    {'k': 1},
                    0.2,
                    **controls(
                        p, sensitivity_method='equilibrium', max_backtracks=2, max_iterations=2
                    ),
                )
        self.assertEqual(result['status'], 'search_incomplete')
        self.assertFalse(result['accepted'])
        self.assertEqual(result['evaluation']['chargeResidual'], 1)


class ColdCorrectionBudgetTests(unittest.TestCase):
    def test_improving_cold_corrections_do_not_hide_budget_exhaustion(self):
        from flahax import JointProblem, JointSource
        from tests.test_joint_fit import problem, controls

        p = problem(targets={'K': 0}, reagent=JointSource('r', {}, {}))
        original = JointProblem.evaluate
        calls = []

        def response(self, doses, reagent, **kwargs):
            state = original(self, doses, reagent, **kwargs)
            state['chargeResidual'] = reagent - 0.2 if calls else 0
            calls.append(reagent)
            return state

        with patch.object(JointProblem, 'evaluate', response):
            with patch(
                'flahax.joint_sensitivity.equilibrium_charge_gradient', return_value=[0, 2]
            ):
                result = solver.solve_joint_problem(
                    p, {}, 0, **controls(p, sensitivity_method='equilibrium', max_backtracks=2)
                )
        self.assertEqual(result['status'], 'search_incomplete')
        self.assertEqual(result['diagnostics']['finalColdCorrections'], 2)
        self.assertAlmostEqual(result['evaluation']['chargeResidual'], -0.05)
        self.assertFalse(result['accepted'])


class TrialDomainBoundaryTests(unittest.TestCase):
    def test_failed_probe_and_zero_derivative_coordinate_preserve_qualification(self):
        fixture = OptionalPolishingFailureTests()
        failed = fixture.curved_case(fail_below=0.79)
        self.assertGreater(failed['diagnostics']['rejectedTrials'], 0)
        self.assertFalse(failed['accepted'])
        zero = fixture.curved_case(start=(0.8, 0, 0.64))
        self.assertFalse(zero['accepted'])
        self.assertTrue(all(v >= 0 for v in zero['fertilizerDoses'].values()))
        if zero['status'] == 'stationary_point':
            self.assertLessEqual(abs(zero['evaluation']['chargeResidual']), 1e-10)


class UnusableTrialBoundaryTests(unittest.TestCase):
    def test_failed_nonlinear_trial_is_not_used_for_charge_correction(self):
        from flahax import JointProblem, DeliveryError
        from tests.test_joint_fit import problem, controls

        p = problem()
        original = JointProblem.evaluate

        def domain(self, doses, reagent, **kwargs):
            if reagent > 0 or any(doses.values()):
                raise DeliveryError('nonconvergent', 'synthetic trial domain failure')
            state = original(self, doses, reagent, **kwargs)
            state['chargeResidual'] = 0
            return state

        with patch.object(JointProblem, 'evaluate', domain):
            with patch(
                'flahax.joint_sensitivity.equilibrium_charge_gradient', return_value=[0, 0]
            ):
                result = solver.solve_joint_problem(
                    p,
                    {},
                    0,
                    **controls(
                        p, sensitivity_method='equilibrium', max_backtracks=2, max_iterations=2
                    ),
                )
        self.assertEqual(result['status'], 'search_incomplete')
        self.assertGreater(result['diagnostics']['rejectedTrials'], 0)
        self.assertEqual(result['diagnostics']['trialChargeCorrections'], 0)
        self.assertFalse(result['accepted'])


class ShortCorrectionBudgetTests(unittest.TestCase):
    def test_last_budgeted_correction_is_evaluated_before_qualification(self):
        result = OptionalPolishingFailureTests().curved_case(backtracks=1)
        self.assertGreater(result['diagnostics']['trialChargeCorrections'], 0)
        self.assertFalse(result['accepted'])
        if result['status'] == 'stationary_point':
            self.assertLessEqual(abs(result['evaluation']['chargeResidual']), 1e-10)
