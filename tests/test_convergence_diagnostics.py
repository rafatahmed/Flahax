# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""A solver that gives up names the stage, the iteration count and the residual (#348, H4).

The message keeps its original wording and gains the facts in brackets, and the same facts are
readable as ``DeliveryError.details``. Successful results are untouched (the exact-digit and
performance-budget tests cover that).
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flahax import aqueous_model as aq
from flahax.calculated_ph import calculate_equilibrium_ph
from flahax.inputs import DeliveryError
from flahax.ph_adjustment import reagent_dose
from flahax.root_finding import shrink_bracket


def budget(limit, replacement=1):
    return lambda *args: range(replacement) if args == (limit,) else range(*args)


class DeliveryErrorDetailsTests(unittest.TestCase):
    def test_details_are_optional_and_keep_the_code(self):
        plain = DeliveryError('out_of_range', 'pH is out of range')
        self.assertEqual(
            (plain.code, plain.details, str(plain)), ('out_of_range', {}, plain.args[0])
        )
        rich = DeliveryError('nonconvergent', 'did not converge', stage='newton', iterations=3)
        self.assertEqual(rich.details, {'stage': 'newton', 'iterations': 3})

    def test_nonconvergent_formats_floats_and_other_values_into_the_message(self):
        error = aq.nonconvergent('gave up', stage='newton', residual=1.5e-3, iterations=7)
        self.assertEqual(error.code, 'nonconvergent')
        self.assertEqual(str(error), 'gave up (stage newton, residual 0.0015, iterations 7)')
        self.assertEqual(str(aq.nonconvergent('gave up')), 'gave up')


class LinearSolveTests(unittest.TestCase):
    def failure(self, matrix, values):
        with self.assertRaises(DeliveryError) as raised:
            aq.linear(matrix, values)
        return raised.exception

    def test_a_zero_row_is_named(self):
        error = self.failure([[1.0, 0.0], [0.0, 0.0]], [1.0, 1.0])
        self.assertEqual(error.details['stage'], 'linear solve')
        self.assertEqual(error.details['zero_or_nonfinite_row'], 1)
        self.assertEqual(error.details['size'], 2)
        self.assertIn('singular or nonfinite equilibrium Jacobian', str(error))

    def test_a_zero_pivot_names_its_column(self):
        error = self.failure([[1.0, 1.0], [1.0, 1.0]], [1.0, 2.0])
        self.assertEqual(error.details['zero_pivot_column'], 1)
        self.assertIn('singular equilibrium Jacobian (stage linear solve', str(error))

    def test_a_nonfinite_solution_is_named(self):
        error = self.failure([[1e-300]], [1e300])
        self.assertEqual(error.details, {'stage': 'linear solve', 'size': 1})
        self.assertIn('nonfinite equilibrium linear solution', str(error))


class NewtonStageTests(unittest.TestCase):
    def test_a_stalled_line_search_reports_iteration_residual_and_pass(self):
        with patch.object(aq, 'linear', side_effect=lambda a, b: [0] * len(b)):
            with patch.object(aq, '_damped_step', return_value=None):
                with self.assertRaises(DeliveryError) as raised:
                    aq._solve({'K+': 0.001}, 7)
        details = raised.exception.details
        self.assertEqual(details['stage'], 'newton line search')
        self.assertEqual(details['iteration'], 1)
        self.assertGreater(details['residual'], 0)
        self.assertEqual((details['phase_step'], details['ionic_strength_pass']), (0, 1))
        self.assertIn(
            'equilibrium line search stalled (stage newton line search', str(raised.exception)
        )
        self.assertIn('residual', str(raised.exception))

    def test_an_exhausted_newton_iteration_reports_its_count_and_residual(self):
        with patch.object(aq, 'range', budget(150), create=True):
            with self.assertRaises(DeliveryError) as raised:
                aq._solve({'K+': 0.001}, 8, phases=('Calcite',))
        details = raised.exception.details
        self.assertEqual((details['stage'], details['iterations']), ('newton', 1))
        self.assertGreater(details['residual'], 0)
        self.assertGreaterEqual(details['newton_evaluations'], 1)
        self.assertIn(
            'aqueous Newton iteration limit (stage newton, iterations 1', str(raised.exception)
        )

    def test_an_exhausted_active_set_names_the_phases(self):
        totals = {'Ca+2': 0.001, 'CO3-2': 0.001}
        with patch.object(aq, 'range', budget(80), create=True):
            with self.assertRaises(DeliveryError) as raised:
                aq._solve(totals, 8, phases=('Calcite',))
        details = raised.exception.details
        self.assertEqual(details['stage'], 'phase active set')
        self.assertEqual(details['phase_steps'], 1)
        self.assertIn('Calcite', details['active_phases'])
        self.assertIn(
            'phase active set iteration limit (stage phase active set', str(raised.exception)
        )

    def test_an_exhausted_ionic_strength_loop_reports_both_gaps(self):
        with patch.object(aq, 'range', budget(100), create=True):
            with self.assertRaises(DeliveryError) as raised:
                aq._solve({'K+': 0.001}, 8, phases=('Calcite',))
        details = raised.exception.details
        self.assertEqual(
            (details['stage'], details['passes']), ('ionic strength and water activity', 1)
        )
        self.assertGreaterEqual(details['ionic_strength_gap'], 0)
        self.assertGreaterEqual(details['water_activity_gap'], 0)
        self.assertIn('ionic strength/water iteration limit (stage', str(raised.exception))


class SolveAttemptsTests(unittest.TestCase):
    def failing(self, label):
        def fail(*args, **kwargs):
            raise aq.nonconvergent('did not converge', stage=label)

        return fail

    def test_the_last_failure_lists_the_earlier_attempts_and_the_pH(self):
        with patch.object(aq, '_solve', side_effect=self.failing('x')):
            with self.assertRaises(DeliveryError) as raised:
                aq.solve({'K+': 0.001}, 7.4)
        details = raised.exception.details
        self.assertEqual(details['pH'], 7.4)
        self.assertEqual(len(details['earlier_attempts']), 1)
        self.assertTrue(details['earlier_attempts'][0].startswith('cold start: did not converge'))

    def test_a_failed_warm_start_is_listed_first(self):
        with patch.object(aq, '_solve', side_effect=self.failing('x')):
            with self.assertRaises(DeliveryError) as raised:
                aq.solve({'K+': 0.001}, 7.4, start=object())
        attempts = raised.exception.details['earlier_attempts']
        self.assertEqual([a.split(':')[0] for a in attempts], ['warm start', 'cold start'])

    def test_other_errors_are_not_changed(self):
        with self.assertRaises(DeliveryError) as raised:
            aq.solve({'K+': 0.001}, 20)
        self.assertEqual(raised.exception.code, 'out_of_range')
        self.assertNotIn('earlier_attempts', raised.exception.details)
        error = DeliveryError('invalid_totals', 'bad')
        with patch.object(aq, '_solve', side_effect=error):
            with self.assertRaises(DeliveryError) as raised:
                aq.solve({'K+': 0.001}, 7)
        self.assertIs(raised.exception, error)
        self.assertEqual(error.details, {})

    def test_a_different_error_from_the_last_attempt_is_left_unchanged(self):
        other = DeliveryError('activity_model_out_of_range', 'ionic strength too high')
        failures = [aq.nonconvergent('cold start failed'), other]
        with patch.object(aq, '_solve', side_effect=failures):
            with self.assertRaises(DeliveryError) as raised:
                aq.solve({'K+': 0.001}, 7)
        self.assertIs(raised.exception, other)
        self.assertEqual(other.details, {})


class RootSearchTests(unittest.TestCase):
    def test_an_exhausted_step_budget_reports_steps_and_bracket(self):
        with self.assertRaises(DeliveryError) as raised:
            shrink_bracket(lambda x: 2.0 - x * x, 0.0, 2.0, 2.0, -2.0, width=1e-12, max_steps=3)
        details = raised.exception.details
        self.assertEqual((details['stage'], details['steps']), ('root search', 3))
        self.assertLess(details['low'], details['high'])
        self.assertAlmostEqual(details['width'], details['high'] - details['low'])
        self.assertGreater(details['width'], details['allowance'])
        self.assertIn(
            'root search exhausted its step budget (steps 3, bracket [', str(raised.exception)
        )


class PhSearchTests(unittest.TestCase):
    def test_a_ph_bisection_that_does_not_close_reports_its_bracket_and_residual(self):
        def discontinuous(totals, ph, **kwargs):
            return SimpleNamespace(ph=ph, charge_balance=1 if ph < 7.1 else -1)

        with patch('flahax.calculated_ph.solve', side_effect=discontinuous):
            with self.assertRaises(DeliveryError) as raised:
                calculate_equilibrium_ph({}, carbon_boundary='closed', phases=[])
        details = raised.exception.details
        self.assertEqual((details['stage'], details['steps']), ('pH bisection', 60))
        self.assertAlmostEqual(details['low'], 7.1, places=6)
        self.assertGreater(details['high'], details['low'])
        self.assertEqual(details['residual'], 1)
        self.assertIn(
            'did not close charge balance (stage pH bisection, steps 60', str(raised.exception)
        )

    def test_an_unbracketed_ph_reports_the_last_ph_and_imbalance(self):
        constant = SimpleNamespace(ph=7, charge_balance=1)
        with patch('flahax.calculated_ph.solve', return_value=constant):
            with self.assertRaises(DeliveryError) as raised:
                calculate_equilibrium_ph({}, carbon_boundary='closed', phases=[])
        self.assertEqual(raised.exception.code, 'ph_not_bracketed')
        details = raised.exception.details
        self.assertEqual(details['stage'], 'pH bracketing')
        self.assertEqual(details['residual'], 1)
        self.assertIn('(stage pH bracketing, last pH', str(raised.exception))

    def test_an_unbracketed_reagent_dose_reports_the_last_dose_and_gap(self):
        def solve_at(totals, ph, **kwargs):
            return SimpleNamespace(ph=ph, charge_balance=1.0 if ph == 6.0 else 0.0)

        with patch('flahax.ph_adjustment.solve', side_effect=solve_at):
            with self.assertRaises(DeliveryError) as raised:
                reagent_dose({'Na+': 0.001}, 7.0, 6.0, 'HNO3')
        details = raised.exception.details
        self.assertEqual((details['stage'], details['steps']), ('dose bracketing', 32))
        self.assertGreater(details['dose'], 1e-6)
        self.assertEqual(details['residual'], 1.0)
        self.assertIn(
            'could not be bracketed (stage dose bracketing, steps 32', str(raised.exception)
        )


if __name__ == '__main__':
    unittest.main()
