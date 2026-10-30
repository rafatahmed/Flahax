# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent equation derivatives and phase-boundary rejection witnesses."""

from dataclasses import replace
from fractions import Fraction as F
import unittest

from flahax import DeliveryError, JointSource
from flahax.joint_sensitivity import _exact_linear, equilibrium_charge_gradient
from flahax.joint_solver import solve_joint_problem
from tests.test_joint_fit import controls
from tests import test_joint_problem_contract as contract
from tools.verify_joint_sensitivity import independent_charge_gradient
from tests.catalogue_history import historical_catalogue


class JointSensitivityTests(unittest.TestCase):
    def test_exact_elimination_preserves_tiny_pivot(self):
        tiny = F(1, 10**80)
        matrix = [[F(1), F(1)], [F(1), F(1) + tiny]]
        self.assertEqual(_exact_linear(matrix, [[F(3)], [F(3) + 2 * tiny]]), [[1], [2]])
        with self.assertRaises(DeliveryError):
            _exact_linear([[F(0)]], [[F(1)]])

    def test_adjoint_preserves_charge_in_an_ill_conditioned_system(self):
        tiny = F(1, 10**80)
        matrix = [[F(1), F(1)], [F(1), F(1) + tiny]]
        rhs = [[F(1), F(2)], [F(1), F(3)]]
        forward = _exact_linear(matrix, rhs)
        adjoint = _exact_linear([list(row) for row in zip(*matrix)], [[F(1)], [F(1)]])
        for j, expected in enumerate((1, 2)):
            self.assertEqual(sum(row[j] for row in forward), expected)
            self.assertEqual(sum(z[0] * row[j] for z, row in zip(adjoint, rhs)), expected)

    def test_independent_derivatives_present_and_absent_components(self):
        p = contract.JointContractTests().problem()
        for doses, reagent in [({}, 0), ({'salt': 0.3}, 0.05)]:
            with self.subTest(doses=doses):
                state = p.evaluate(doses, reagent)
                actual = equilibrium_charge_gradient(p, state)
                oracle = independent_charge_gradient(p, state, 1e-10)
                for a, b in zip(actual, oracle):
                    self.assertAlmostEqual(a, b, delta=1e-12)
                # Independent forward perturbation of the full nonlinear solve.
                for j in range(2):
                    shifted = dict(doses)
                    q = reagent
                    step = 1e-8
                    if j == 0:
                        shifted['salt'] = shifted.get('salt', 0) + step
                    else:
                        q += step
                    finite = (
                        p.evaluate(shifted, q)['chargeResidual'] - state['chargeResidual']
                    ) / step
                    self.assertAlmostEqual(actual[j], finite, delta=2e-9)

    def test_volume_mass_scaling_and_cold_restart(self):
        p = contract.JointContractTests().problem()
        state = p.evaluate({'salt': 0.3}, 0.05)
        scaled = replace(p, final_volume_litres=100, solvent_mass_kg=80, maximum_reagent_mass_g=20)
        other = scaled.evaluate({'salt': 0.3}, 0.05)
        self.assertEqual(
            equilibrium_charge_gradient(p, state), equilibrium_charge_gradient(scaled, other)
        )
        warm = p.evaluate({'salt': 0.31}, 0.05, equilibrium_start=state['equilibrium'])
        cold = p.evaluate({'salt': 0.31}, 0.05)
        self.assertAlmostEqual(warm['chargeResidual'], cold['chargeResidual'], delta=1e-12)

    def test_phase_and_missing_state_are_not_sensitivity_proofs(self):
        p = contract.JointContractTests().problem()
        state = p.evaluate({'salt': 0.3}, 0.05)
        for candidate, value in [(p, {}), (replace(p, phases=('Calcite',)), state)]:
            with self.assertRaises(DeliveryError):
                equilibrium_charge_gradient(candidate, value)
        with self.assertRaises(ValueError):
            independent_charge_gradient(replace(p, phases=('Calcite',)), state, 0.01)
        with self.assertRaises(DeliveryError):
            solve_joint_problem(p, {}, 0, **controls(p, sensitivity_method='unknown'))

    def test_real_chemistry_stationarity_independently_verified(self):
        from copy import deepcopy
        from tools.qualify_joint_fit import qualify_starts, verify_stationarity

        p = contract.JointContractTests().problem()
        settings = controls(
            p,
            sensitivity_method='equilibrium',
            stationarity_tolerance=1e-6,
            active_bound_tolerance=1e-8,
            objective_gap_tolerance=1e-12,
        )
        result = qualify_starts(p, [({}, 0), ({'salt': 0.3}, 0.05)], settings)
        self.assertEqual(result['status'], 'numerical_checks_passed')
        self.assertFalse(result['accepted'])
        for row in result['starts']:
            self.assertEqual(row['solverStatus'], 'stationary_point')
            self.assertTrue(row['independentStationarityVerified'])
            tampered = deepcopy(row)
            tampered['stationarity']['chargeMultiplier'] *= 2
            self.assertFalse(verify_stationarity(p, tampered, settings))
            tampered = deepcopy(row)
            tampered['stationarity']['sensitivityMethod'] = 'finite_difference'
            self.assertFalse(verify_stationarity(p, tampered, settings))

    def test_clipped_trace_reagent_recovers_only_a_verified_boundary(self):
        p = contract.JointContractTests().problem(
            fertilizers=(JointSource('salt', {'K': 0.125}, {'K+': 0.003}),),
            reagent=JointSource('acid', {}, {'Citrate-3': 0.01}),
            targets={'K': 100},
            water={},
            water_components={'Zn+2': 0.001},
            maximum_concentrations={'K': 125},
        )
        state = p.evaluate({'salt': 1}, 1e-164)
        with self.assertRaisesRegex(DeliveryError, 'clipping'):
            equilibrium_charge_gradient(p, state)
        p = replace(p, reference_charge_mol_per_kg=state['chargeResidual'])
        settings = controls(
            p,
            dose_steps={'salt': 0.125, 'acid': 0.125},
            sensitivity_method='equilibrium',
            stationarity_tolerance=1e-6,
            active_bound_tolerance=1e-8,
        )
        result = solve_joint_problem(p, {'salt': 1}, 1e-164, **settings)
        self.assertEqual(result['status'], 'stationary_point')
        self.assertEqual(result['reagentDose'], 0)
        self.assertTrue(result['diagnostics']['history'][0]['boundaryRecovery'])
        self.assertLessEqual(
            abs(result['evaluation']['chargeResidual']), settings['charge_tolerance']
        )
        self.assertFalse(result['accepted'])

    def test_correlated_sources_match_independent_cubic_optimum(self):
        from decimal import Decimal as D, localcontext
        from unittest.mock import patch
        from flahax import JointProblem
        from tests.test_joint_fit import problem

        p = problem(
            [JointSource('a', {'K': 0.125}, {}), JointSource('b', {'K': 0.125}, {})],
            reagent=JointSource('r', {'N_NO3': 0.125}, {}),
            targets={'K': 250, 'N_NO3': 125},
            maximum_reagent_mass_g=4,
        )
        original = JointProblem.evaluate

        def curved(self, doses, reagent, **kwargs):
            value = original(self, doses, reagent, **kwargs)
            a, b = doses.get('a', 0), doses.get('b', 0)
            value['chargeResidual'] = reagent - a * a - b * b
            value['witnessDoses'] = a, b
            return value

        def derivative(problem, state):
            a, b = state['witnessDoses']
            return [-2 * a, -2 * b, 1]

        settings = controls(
            p,
            sensitivity_method='equilibrium',
            curvature_block=True,
            stationarity_tolerance=1e-6,
            active_bound_tolerance=1e-8,
        )
        with (
            patch.object(JointProblem, 'evaluate', curved),
            patch('flahax.joint_sensitivity.equilibrium_charge_gradient', derivative),
        ):
            result = solve_joint_problem(p, {'a': 0.8, 'b': 0.7}, 1.13, **settings)
        self.assertEqual(result['status'], 'stationary_point')
        # Eliminating r=a^2+b^2 gives a symmetric interior minimum. Its t=a=b
        # solves 8*t^3-3*t-1=0; bisection is independent of the solver's derivatives.
        with localcontext() as context:
            context.prec = 60
            low, high = D('.7'), D('.8')
            for _ in range(180):
                middle = (low + high) / 2
                if 8 * middle**3 - 3 * middle - 1 > 0:
                    high = middle
                else:
                    low = middle
            expected = float((low + high) / 2)
        for value in result['fertilizerDoses'].values():
            self.assertAlmostEqual(value, expected, delta=2e-6)
        self.assertAlmostEqual(result['reagentDose'], 2 * expected**2, delta=2e-6)
        with self.assertRaises(DeliveryError):
            solve_joint_problem(p, {}, 0, **controls(p, curvature_block='yes'))
        with self.assertRaises(DeliveryError):
            solve_joint_problem(p, {}, 0, **controls(p, curvature_block=True))

    # Owner catalogue: re-enable in PR 3 (G24)
    def test_cold_charge_correction_rechecks_actual_melon_candidate(self):
        self.enterContext(historical_catalogue())
        from flahax import load_library, make_joint_problem, balance_water_analysis
        from flahax.ph_adjustment import nutrient_salts
        from flahax.measured_water import nutrient_mg_per_litre
        from tests.test_measured_water import STATION_104
        from tools.qualify_joint_fit import verify_stationarity

        library = load_library()
        targets = next(
            f['targets']
            for f in library['formulas']
            if f['name'] == 'Melons (Douglas Peckenpaugh)'
        )
        balanced = balance_water_analysis(STATION_104, measured_ph=7.8)
        p = make_joint_problem(
            nutrient_salts(library['salts']),
            dict(
                id='reagent',
                chemicalFormula='KOH',
                massFraction=0.5,
                densityKgPerL=1.2,
                source='synthetic regression grade',
                revision='1',
                recordedAt='2026-10-27',
            ),
            targets,
            nutrient_mg_per_litre({k: v * 0.2 for k, v in STATION_104.items()}, 1000, 1000),
            reagent_solvent_fraction=0.5,
            water_components={k: v * 0.2 for k, v in balanced.totals.items()},
            final_volume_litres=1000,
            solvent_mass_kg=1000,
            target_ph=5.8,
            reference_charge_mol_per_kg=0,
            maximum_reagent_mass_g=6000,
            maximum_reagent_volume_litres=5,
        )
        # Retained failing search point, not an oracle for optimal quantities.
        doses = {
            'cmbpfudkn00naq8z9kd4qsr60': 0.48176024259035294,
            'cmuh6f7s80005127gbyr2ip91': 0.4035994690084655,
            'cmbpfudmb00omq8z9a5nu1i5b': 0.004004352779466222,
            'cmbpfudif00lkq8z99slfmci3': 0.7850738599401509,
            'cmbpfudls00o7q8z929uh7kwl': 0.00027506667084065725,
            'cmbpfudm400ohq8z9h4pbl5iz': 0.034148245922976675,
            'cmbpfudmm00ouq8z91yim9eru': 0.45487885771189207,
            'cmbpfudhl00kyq8z9j8u2rr14': 0.3020313556591289,
            'cmbpfudhw00l6q8z9wj92mk5s': 0.01512760979282954,
            'cmy5qdto0d3yl7lo8vww3taj6': 0.6463954164825587,
            'cmbpfudlf00nxq8z9wx4ryy2b': 0.0001261017597093709,
            'cmbpfudly00ocq8z9zrrcr9zt': 0.0006862061201358166,
        }
        steps = {s.product_id: 1e-4 for s in (*p.fertilizers, p.reagent)}
        settings = controls(
            p,
            dose_steps=steps | {'cmuh6f7s20002127gu7u773mx': 0.01},
            charge_scale=0.001,
            charge_tolerance=2e-12,
            trust_radius=10000,
            max_iterations=20,
            sensitivity_method='equilibrium',
            curvature_block=True,
            objective_gap_tolerance=1e-12,
            stationarity_tolerance=1e-6,
            active_bound_tolerance=1e-8,
        )
        self.assertGreater(abs(p.evaluate(doses, 0)['chargeResidual']), 2e-12)
        result = solve_joint_problem(p, doses, 0, **settings)
        self.assertEqual(result['status'], 'stationary_point', result['reason'])
        self.assertGreater(result['diagnostics']['finalColdCorrections'], 0)
        fresh = p.evaluate(result['fertilizerDoses'], result['reagentDose'])
        self.assertEqual(fresh['rows'], result['evaluation']['rows'])
        self.assertLessEqual(abs(fresh['chargeResidual']), 2e-12)
        self.assertTrue(verify_stationarity(p, result, settings))
        check = solve_joint_problem(
            p,
            result['fertilizerDoses'],
            result['reagentDose'],
            **(settings | dict(dose_steps=steps, max_iterations=1, curvature_block=False)),
        )
        self.assertEqual(check['status'], 'stationary_point')
        self.assertFalse(result['accepted'])

    def test_fresh_stationarity_cannot_reuse_a_stale_certificate(self):
        from unittest.mock import patch
        import flahax.joint_solver as solver

        p = contract.JointContractTests().problem()
        settings = controls(
            p,
            sensitivity_method='equilibrium',
            stationarity_tolerance=1e-6,
            active_bound_tolerance=1e-8,
        )
        valid = solve_joint_problem(p, {}, 0, **settings)
        self.assertEqual(valid['status'], 'stationary_point')
        actual = solver._implicit_matrix
        calls = 0

        def changed(problem, value, scales, charge_scale):
            nonlocal calls
            calls += 1
            matrix = actual(problem, value, scales, charge_scale)
            if calls > 1:
                matrix[-1] = [0.0] * len(scales)
            return matrix

        with patch.object(solver, '_implicit_matrix', changed):
            checked = solve_joint_problem(
                p, valid['fertilizerDoses'], valid['reagentDose'], **settings
            )
        self.assertGreaterEqual(calls, 2)
        self.assertEqual(checked['status'], 'search_incomplete')
        self.assertIsNone(checked['stationarity'])

    def test_bound_reagent_restores_charge_through_fertilizer(self):
        from unittest.mock import patch
        from flahax import JointProblem
        from tests.test_joint_fit import problem

        p = problem(
            [JointSource('a', {'K': 0.1}, {})],
            reagent=JointSource('r', {}, {}),
            targets={'K': 100},
        )
        original = JointProblem.evaluate

        def charge(self, doses, reagent, **kwargs):
            value = original(self, doses, reagent, **kwargs)
            value['chargeResidual'] = 1 - doses.get('a', 0) + reagent
            return value

        settings = controls(
            p,
            sensitivity_method='equilibrium',
            stationarity_tolerance=1e-6,
            active_bound_tolerance=1e-8,
        )
        with (
            patch.object(JointProblem, 'evaluate', charge),
            patch('flahax.joint_sensitivity.equilibrium_charge_gradient', return_value=[-1, 1]),
        ):
            result = solve_joint_problem(p, {}, 0, **settings)
            limited = solve_joint_problem(
                replace(p, maximum_concentrations={'K': 50}),
                {},
                0,
                **(settings | dict(max_iterations=2)),
            )
        self.assertEqual(limited['status'], 'search_incomplete')
        self.assertLessEqual(limited['fertilizerDoses'].get('a', 0), 0.5)
        self.assertGreater(
            abs(1 - limited['fertilizerDoses'].get('a', 0) + limited['reagentDose']),
            settings['charge_tolerance'],
        )
        # Charge equality requires a=1+r. Nonnegativity and the squared
        # nutrient residual independently give the unique optimum a=1, r=0.
        self.assertEqual(result['status'], 'numerical_candidate')
        self.assertAlmostEqual(result['fertilizerDoses']['a'], 1)
        self.assertEqual(result['reagentDose'], 0)
        self.assertTrue(
            any(h.get('fertilizerRestoration') for h in result['diagnostics']['history'])
        )
        self.assertFalse(result['accepted'])

    def test_tiny_bound_reagent_is_not_a_free_charge_pivot(self):
        from unittest.mock import patch
        from flahax import JointProblem
        from tests.test_joint_fit import problem
        import math

        p = problem(
            [JointSource('a', {'K': 0.125}, {}), JointSource('b', {'K': 0.125}, {})],
            reagent=JointSource('r', {'N_NO3': 0.125}, {}),
            targets={'K': 250, 'N_NO3': 125},
            water={'N_NO3': 250},
        )
        original = JointProblem.evaluate

        def curved(self, doses, reagent, **kwargs):
            value = original(self, doses, reagent, **kwargs)
            a, b = doses.get('a', 0), doses.get('b', 0)
            value['chargeResidual'] = reagent + a * a + b * b - 1
            value['witnessDoses'] = a, b
            return value

        def derivative(problem, state):
            a, b = state['witnessDoses']
            return [2 * a, 2 * b, 1]

        settings = controls(
            p,
            sensitivity_method='equilibrium',
            curvature_block=True,
            stationarity_tolerance=1e-6,
            active_bound_tolerance=1e-8,
        )
        with (
            patch.object(JointProblem, 'evaluate', curved),
            patch('flahax.joint_sensitivity.equilibrium_charge_gradient', derivative),
        ):
            result = solve_joint_problem(p, {'a': 0.8, 'b': 0.6}, 1e-160, **settings)
        self.assertEqual(result['status'], 'stationary_point')
        # Cauchy-Schwarz: a+b <= sqrt(2*(1-r)); both objective terms worsen
        # for r>0. Thus r=0 and a=b=1/sqrt(2) give the independent optimum.
        for dose in result['fertilizerDoses'].values():
            self.assertAlmostEqual(dose, 1 / math.sqrt(2), delta=2e-6)
        self.assertLessEqual(result['reagentDose'], 1e-12)
        self.assertFalse(result['accepted'])

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_full_catalogue_chelate_derivatives(self):
        self.enterContext(historical_catalogue())
        from flahax import load_library, make_joint_problem, recommend
        from flahax.ph_adjustment import nutrient_salts

        library = load_library()
        pool = nutrient_salts(library['salts'])
        targets = next(
            f['targets'] for f in library['formulas'] if f['name'] == 'Lettuce 2 (Howard Resh)'
        )
        p = make_joint_problem(
            pool,
            dict(
                id='r',
                chemicalFormula='HNO3',
                massFraction=0.5,
                densityKgPerL=1.2,
                source='synthetic test grade',
                revision='1',
                recordedAt='2026-10-26',
            ),
            targets,
            {},
            reagent_solvent_fraction=0.5,
            water_components={},
            final_volume_litres=1000,
            solvent_mass_kg=1000,
            target_ph=5.8,
            reference_charge_mol_per_kg=0,
            maximum_reagent_mass_g=6000,
            maximum_reagent_volume_litres=5,
        )
        recipe = recommend(pool, targets, {})
        doses = {s['id']: s['gramsPerLitre'] for s in recipe['salts']}
        state = p.evaluate(doses, 0.01)
        actual = equilibrium_charge_gradient(p, state)
        independent = independent_charge_gradient(p, state, 1e-10)
        for source, a, b in zip((*p.fertilizers, p.reagent), actual, independent):
            with self.subTest(source=source.product_id):
                self.assertAlmostEqual(a, b, delta=max(abs(a), abs(b)) * 1e-10)

    def test_neutral_source_at_active_water_floor_has_zero_derivative(self):
        p = contract.JointContractTests().problem(
            fertilizers=(JointSource('urea', {}, {'Ure': 1}),),
            targets={'K': 0},
            final_volume_litres=1,
            solvent_mass_kg=1,
        )
        state = p.evaluate({'urea': 10}, 0.05)
        self.assertEqual(state['equilibrium'].water_activity, 0.9)
        self.assertEqual(equilibrium_charge_gradient(p, state)[0], 0)
        self.assertEqual(independent_charge_gradient(p, state, 1e-10)[0], 0)
        self.assertEqual(
            p.evaluate({'urea': 10.001}, 0.05)['chargeResidual'], state['chargeResidual']
        )


if __name__ == '__main__':
    unittest.main()
