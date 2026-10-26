# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent scale, conditioning and termination controls for numerical rules."""

from fractions import Fraction as F
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flahax.aqueous_model import linear, solve
from flahax.calculated_ph import calculate_equilibrium_ph
from flahax.delivery_contracts import DeliveryError
from flahax.engine import nnls
from flahax.composition import InputError
from flahax.root_finding import shrink_bracket
from tools.numerical_verification import acid_bracket, box_least_squares, linear_solution


class RootPrecisionTests(unittest.TestCase):
    def test_explicit_accept_predicate_can_finish_before_width(self):
        lo, hi = shrink_bracket(
            lambda x: x * x - 2, 0, -2, 2, 2, accept=lambda x, gx, lo, hi: True
        )
        self.assertEqual((lo, hi), (1, 1))

    def test_budget_exhaustion_is_not_success(self):
        with self.assertRaisesRegex(DeliveryError, 'step budget'):
            shrink_bracket(lambda x: x * x - 2, 0, -2, 2, 2, width=1e-12, max_steps=1)

    def test_invalid_signs_domains_and_nonfinite_values(self):
        for args, kwargs in [
            ((0, 1, 2, 3), {}),
            ((2, -1, 1, 1), {}),
            ((0, -1, 1, 1), {'width': -1}),
            ((0, -1, 1, 1), {'relative': -1}),
            ((0, -1, 1, 1), {'max_steps': 0}),
            ((0, -1, 1, 1), {'max_steps': True}),
            ((0, -1, 1, math.inf), {}),
            ((0, -1, 1, 1), {'width': math.nan}),
            ((0, -1, 1e308, 1), {'relative': 1e308}),
        ]:
            with self.assertRaises(ValueError):
                shrink_bracket(lambda x: x, *args, **kwargs)
        for value in (math.nan, math.inf):
            with self.assertRaisesRegex(DeliveryError, 'nonfinite'):
                shrink_bracket(lambda x: value, 0, -1, 1, 1)

    def test_unattainable_width_is_explicit(self):
        lo = 1.0
        hi = math.nextafter(lo, math.inf)
        with self.assertRaisesRegex(DeliveryError, 'resolution'):
            shrink_bracket(lambda x: 1, lo, -1, hi, 1)

    def test_endpoint_zero_and_final_step_acceptance(self):
        self.assertEqual(shrink_bracket(lambda x: x, -1, -1, 0, 0), (0, 0))
        lo, hi = shrink_bracket(lambda x: x * x - 2, 0, -2, 2, 2, width=1, max_steps=1)
        self.assertEqual(hi - lo, 1)

    def test_overflow_resistant_interpolation_and_negative_interval(self):
        self.assertEqual(shrink_bracket(lambda x: x, -1e308, -1e308, 1e308, 1e308), (0, 0))
        lo, hi = shrink_bracket(lambda x: x * x - 2, -2, 2, -1, -1, relative=1e-12)
        self.assertLessEqual(hi - lo, 1e-12 * abs(hi))
        self.assertLessEqual(abs((lo + hi) / 2 + math.sqrt(2)), 1e-12)

    def test_ideal_acid_root_against_exact_sign_oracle(self):
        for total, ka in [('0', '1e-5'), ('1e-12', '1e-5'), ('.01', '1e-5')]:
            c, k, kw = float(total), float(ka), 1e-14

            def charge(h):
                return h - kw / h - k * c / (k + h)

            lo, hi = shrink_bracket(charge, 1e-10, charge(1e-10), 1, charge(1), relative=1e-12)
            exact_lo, exact_hi = acid_bracket(total, ka, digits=80)
            # Endpoint width plus eight ulps covers evaluation rounding in this
            # controlled polynomial family; no production threshold is changed.
            error = abs(F.from_float((lo + hi) / 2) - F(exact_hi))
            budget = F.from_float(hi - lo + 8 * math.ulp(float(exact_hi)))
            self.assertLessEqual(error, budget)
            self.assertLessEqual(F(exact_hi) - F(exact_lo), F(1, 10**80))


class LinearPrecisionTests(unittest.TestCase):
    def test_unrepresentable_nnls_products_do_not_report_zero_optimum(self):
        for scale in (1e-200, 1e200):
            with self.assertRaisesRegex(InputError, 'floating-point range'):
                nnls([[scale]], [scale])
        with self.assertRaisesRegex(InputError, 'right-hand-side products'):
            nnls([[1e150]], [1e200])
        self.assertEqual(nnls([[0]], [1]), [0])

    def test_scaled_systems_against_exact_rational_solution(self):
        for scale in (1e-150, 1e-30, 1, 1e150):
            for rows in ([[1, 0], [0, 2]], [[0, 2], [1, 1]], [[1, 1], [1, 1.000001]]):
                a = [[v * scale for v in row] for row in rows]
                b = [math.fsum(row) for row in a]
                exact = linear_solution(
                    [[F.from_float(v) for v in row] for row in a], [F.from_float(v) for v in b]
                )
                result = linear(a, b)
                for actual, expected in zip(result, exact):
                    self.assertLessEqual(abs(actual - float(expected)), 1e-9)
                for row, value in zip(a, b):
                    residual = abs(math.fsum(v * x for v, x in zip(row, result)) - value)
                    magnitude = math.fsum(abs(v * x) for v, x in zip(row, result)) + abs(value)
                    self.assertLessEqual(residual, 8 * math.ulp(1.0) * magnitude)

    def test_singular_nonfinite_and_overflow_fail(self):
        for a, b in [
            ([[0]], [1]),
            ([[1, 1], [1, 1]], [1, 2]),
            ([[math.inf]], [1]),
            ([[1]], [math.inf]),
            ([[1e-300]], [1e300]),
        ]:
            with self.assertRaises(DeliveryError):
                linear(a, b)
        self.assertEqual(linear([], []), [])

    def test_nnls_scaled_trace_zero_and_near_dependent(self):
        for scale in (1e-150, 1e-30, 1, 1e150):
            for a, b in [
                ([[1, 0], [0, 1]], [0, 1e-12]),
                ([[1, 1], [1, 0], [0, 1]], [3, 0, 0]),
                ([[1, 1], [1, 1.0001]], [2, 2.0001]),
                ([[1, 1]], [1]),
                ([[1, 0], [0, 1]], [0, 0]),
            ]:
                reference = box_least_squares(a, b, [0, 0], [3, 3])
                diagnostics = {}
                x = nnls(
                    [[v * scale for v in row] for row in a],
                    [v * scale for v in b],
                    diagnostics=diagnostics,
                )
                objective = sum(
                    (
                        sum(F.from_float(v) * F.from_float(w) for v, w in zip(row, x))
                        - F.from_float(float(y))
                    )
                    ** 2
                    for row, y in zip(a, b)
                )
                self.assertLessEqual(abs(float(objective - reference['objective'])), 1e-14)
                self.assertTrue(diagnostics['optimality_passed'], diagnostics)
                self.assertTrue(all(v >= 0 for v in x))
                self.assertIsNone(diagnostics['condition_estimate'])

    def test_rank_exclusion_report_does_not_invent_condition_estimate(self):
        with (
            patch('flahax.engine._gram_lstsq', return_value=None),
            patch('flahax.engine._lstsq', side_effect=ValueError('rank deficient')),
        ):
            diagnostics = {}
            x = nnls([[1]], [1], diagnostics=diagnostics)
        self.assertEqual(x, [0])
        self.assertEqual(diagnostics['rejected_columns'], [0])
        self.assertFalse(diagnostics['optimality_passed'])


class ChemistryTerminationTests(unittest.TestCase):
    def test_discontinuous_charge_cannot_pass_the_iteration_limit(self):
        def discontinuous(totals, ph, **kwargs):
            return SimpleNamespace(ph=ph, charge_balance=1 if ph < 7.1 else -1)

        with patch('flahax.calculated_ph.solve', side_effect=discontinuous):
            with self.assertRaisesRegex(DeliveryError, 'did not close charge'):
                calculate_equilibrium_ph(
                    {}, complete_analysis=True, carbon_boundary='closed', phases=[]
                )

    def test_small_charge_alone_does_not_certify_ph(self):
        seen = []

        def at(totals, ph, **kwargs):
            seen.append(ph)
            return SimpleNamespace(ph=ph, charge_balance=1e-200 * (7.1 - ph))

        with patch('flahax.calculated_ph.solve', side_effect=at):
            result = calculate_equilibrium_ph(
                {}, complete_analysis=True, carbon_boundary='closed', phases=[]
            )
        self.assertLessEqual(abs(result.ph - 7.1), 1e-7)
        self.assertGreater(len(seen), 2)
        self.assertLess(len(seen), 80)

    def test_exact_scan_root_and_unbracketed(self):
        for target in (7, 7.5):
            with patch(
                'flahax.calculated_ph.solve',
                side_effect=lambda totals, ph, **kw: SimpleNamespace(
                    ph=ph, charge_balance=target - ph
                ),
            ):
                result = calculate_equilibrium_ph(
                    {}, complete_analysis=True, carbon_boundary='closed', phases=[]
                )
                self.assertEqual(result.ph, target)
        with patch(
            'flahax.calculated_ph.solve', return_value=SimpleNamespace(ph=7, charge_balance=1)
        ):
            with self.assertRaisesRegex(DeliveryError, 'no charge-balanced'):
                calculate_equilibrium_ph(
                    {}, complete_analysis=True, carbon_boundary='closed', phases=[]
                )

    def test_aqueous_diagnostics_record_existing_residual_limits(self):
        for totals in ({}, {'Na+': 1e-12, 'Cl-': 1e-12}, {'Na+': 0.01, 'Cl-': 0.01}):
            for strength in (None, 0.01):
                result = solve(totals, 7, ionic_strength=strength)
                d = result.numerical_diagnostics
                self.assertLess(d['mass_action_log_residual'], 2e-10)
                self.assertLess(d['maximum_relative_balance'], 10 ** (2e-10) - 1)
                self.assertLess(d['water_activity_update'], 1e-12)
                self.assertEqual(d['fixed_ionic_strength'], strength is not None)
                if strength is None:
                    self.assertLess(d['ionic_strength_update'], 1e-12)
