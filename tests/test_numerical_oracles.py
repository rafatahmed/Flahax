# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Adversarial qualification of references, not new runtime tolerances."""

import ast
import copy
from decimal import Decimal, localcontext
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import unittest

from tools import numerical_verification as oracle


class ExactOracleTests(unittest.TestCase):
    def test_hand_solved_faces_and_kkt_certificates(self):
        cases = [
            ([[1, 0], [0, 1]], ['1/3', '2/3'], [1, 1], (F(1, 3), F(2, 3)), 0),
            ([[1, 0], [0, 1]], [-1, 2], [1, 1], (0, 1), 2),
            ([[1, 1], [1, 0], [0, 1]], [3, 0, 0], [3, 3], (1, 1), 3),
            ([[1, 1]], [1], [1, 1], (0, 1), 0),
            ([[0, 0]], [1], [1, 1], (0, 0), 1),
            ([[1]], [2], [0], (0,), 4),
        ]
        for a, b, hi, expected, objective in cases:
            result = oracle.box_least_squares(a, b, [0] * len(hi), hi)
            self.assertEqual(result['x'], expected)
            self.assertEqual(result['objective'], objective)
            for x, gradient, upper in zip(result['x'], result['gradient'], hi):
                if upper == 0:
                    continue
                if x == 0:
                    self.assertGreaterEqual(gradient, 0)
                elif x == upper:
                    self.assertLessEqual(gradient, 0)
                else:
                    self.assertEqual(gradient, 0)

    def test_negative_bounds_and_rational_elimination(self):
        self.assertEqual(oracle.box_least_squares([[1]], [-2], [-3], [-1])['x'], (-2,))
        self.assertEqual(
            oracle.linear_solution([[F(0), F(2)], [F(1), F(1)]], [F(4), F(3)]), (1, 2)
        )
        self.assertIsNone(oracle.linear_solution([[F(0)]], [F(1)]))

    def test_invalid_box_domains(self):
        for a, b, lo, hi in [
            ([], [], [], []),
            ([[1]], [1], [0], []),
            ([], [], [0], [1]),
            ([[1]], [], [0], [1]),
            ([[1, 2]], [1], [0], [1]),
            ([[1]], [1], [2], [1]),
            ([[1] * 7], [1], [0] * 7, [1] * 7),
        ]:
            with self.assertRaises(ValueError):
                oracle.box_least_squares(a, b, lo, hi)

    def test_wrong_feasible_and_infeasible_results_are_distinguishable(self):
        optimum = oracle.box_least_squares([[1, 1], [1, 0], [0, 1]], [3, 0, 0], [0, 0], [3, 3])
        for wrong in [(0, 0), (F(3, 2), F(3, 2)), (3, 3)]:
            objective = (sum(wrong) - 3) ** 2 + sum(x * x for x in wrong)
            self.assertFalse(
                oracle.error_account(objective, optimum['objective'], absolute=0, relative=0)[
                    'passed'
                ]
            )
        self.assertFalse(
            oracle.error_account(-1, optimum['x'][0], absolute=0, relative=0)['passed']
        )

    def test_acid_exact_root_and_precision_nesting(self):
        # H=1/10, Ka=1/10, Kw=1/1000 => C=18/100 by charge balance.
        lo, hi = oracle.acid_bracket('.18', '.1', '.001', digits=80)
        self.assertLessEqual(lo, Decimal('.1'))
        self.assertEqual(hi, Decimal('.1'))
        previous = None
        for digits in (16, 40, 80, 160, 200):
            lo, hi = oracle.acid_bracket('.01', '1e-5', digits=digits)
            low, h = F(lo), F(hi)
            c, k, kw = F('0.01'), F('1e-5'), F('1e-14')

            # Independent polynomial form (positive denominator cleared).
            def polynomial(x):
                return x**3 + k * x * x - (k * c + kw) * x - k * kw

            self.assertLessEqual(polynomial(low), 0)
            self.assertGreaterEqual(polynomial(h), 0)
            self.assertLessEqual(h - low, F(1, 10**digits))
            if previous:
                self.assertGreaterEqual(low, previous[0])
                self.assertLessEqual(h, previous[1])
            previous = low, h
        with localcontext() as context:
            context.prec = 220
            wrong = hi * 2
        self.assertFalse(oracle.error_account(wrong, hi, absolute='1e-80', relative=0)['passed'])

    def test_water_only_and_small_root(self):
        lo, hi = oracle.acid_bracket(0, '1e-5', digits=40)
        self.assertLessEqual(lo, Decimal('1e-7'))
        self.assertEqual(hi, Decimal('1e-7'))
        lo, hi = oracle.acid_bracket(0, 1, '1e-100', digits=16)
        self.assertEqual(lo, 0)
        self.assertEqual(hi, Decimal('1e-16'))

    def test_invalid_acid_domains(self):
        for c, k, water in [(-1, 1, 1), (1, 0, 1), (1, 1, 0)]:
            with self.assertRaises(ValueError):
                oracle.acid_bracket(c, k, water)
        for digits in (True, 16.5, 15, 201):
            with self.assertRaises(ValueError):
                oracle.acid_bracket(1, 1, digits=digits)

    def test_error_budgets_boundaries_and_nonfinite(self):
        self.assertTrue(oracle.error_account('1.11', 1, absolute='.01', relative='.1')['passed'])
        self.assertFalse(
            oracle.error_account('1.11000000000000001', 1, absolute='.01', relative='.1')['passed']
        )
        report = oracle.error_account('1e-30', 0, absolute='1e-30', relative=0)
        self.assertIsNone(report['relative_error'])
        self.assertTrue(report['passed'])
        self.assertTrue(oracle.error_account('-1.1', -1, absolute=0, relative='.1')['passed'])
        for absolute, relative in [(-1, 0), (0, -1)]:
            with self.assertRaises(ValueError):
                oracle.error_account(1, 1, absolute=absolute, relative=relative)
        for bad in ('NaN', 'Infinity', '-Infinity'):
            with self.assertRaises(ValueError):
                oracle.error_account(bad, 0, absolute=0, relative=0)

    def test_oracle_has_no_production_or_reference_generator_imports(self):
        tree = ast.parse(Path(oracle.__file__).read_text())
        modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertEqual(set(modules), {'decimal', 'fractions', 'itertools'})
        self.assertFalse(any(isinstance(node, ast.Import) for node in ast.walk(tree)))


class ReferenceOracleTests(unittest.TestCase):
    def record(self):
        return dict(
            conditions=dict(
                temperature_c=25,
                units='mol/kg water',
                totals={'Na': 1},
                ph=6,
                carbon_boundary='closed',
                redox='fixed analytical',
                phases=[],
                charge_balance='matched final inventory',
            ),
            values={'Na': 1},
            method='declared method',
            sha256={'base': 'a' * 64},
        )

    def test_shared_data_and_disjoint_data_both_limit_claims(self):
        for digest in ('a' * 64, 'b' * 64):
            actual, expected = self.record(), self.record()
            actual['sha256']['base'] = digest
            result = oracle.compare_reference(
                actual, expected, {'Na': dict(absolute=0, relative=0)}
            )
            self.assertTrue(result['passed'])
            self.assertEqual(result['shared_sha256'], ['a' * 64] if digest[0] == 'a' else [])
            self.assertEqual(result['parameter_independence'], 'not established')
            self.assertFalse(result['physical_validation'])

    def test_missing_mismatched_conditions_provenance_and_quantities(self):
        expected = self.record()
        for key in oracle.CONDITIONS:
            actual = copy.deepcopy(expected)
            del actual['conditions'][key]
            with self.assertRaises(ValueError):
                oracle.compare_reference(actual, expected, {})
            actual = copy.deepcopy(expected)
            actual['conditions'][key] = 'different'
            with self.assertRaises(ValueError):
                oracle.compare_reference(actual, expected, {})
        for change in (
            {'method': ''},
            {'sha256': {}},
            {'sha256': {'a': 'x'}},
            {'sha256': {'a': 'g' * 64}},
            {'values': {}},
            {'values': {'K': 1}},
        ):
            with self.assertRaises(ValueError):
                oracle.compare_reference(
                    expected | change, expected, {'Na': dict(absolute=0, relative=0)}
                )
        with self.assertRaises(ValueError):
            oracle.compare_reference(expected, expected, {})
        with self.assertRaises(ValueError):
            oracle.compare_reference(expected | {'values': {}}, expected | {'values': {}}, {})

    def test_pinned_matched_phreeqc_capture_and_deliberate_wrong_output(self):
        from flahax.aqueous_model import solve

        root = Path(__file__).parent / 'fixtures/phreeqc/products/fe_edta'
        data = json.loads((root / 'expected.json').read_text())
        for name, digest in data['hashes'].items():
            self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), digest)
        # Compare final sodium-balanced inventory, not the initial Na charge input.
        row = data['selected_rows'][-1]
        result = solve(data['runtime_totals'], row['pH'], phases=(), temperature_c=25)
        record = self.record()
        record['conditions'].update(totals=data['runtime_totals'], ph=row['pH'])
        record['sha256'] = dict(
            data['reference']['extensions'], base=data['reference']['base_sha256']
        )
        expected = copy.deepcopy(record)
        expected['method'] = data['reference']['software'] + '; pinned input/database'
        expected['sha256']['executable'] = data['reference']['executable_sha256']
        expected['sha256']['input'] = data['hashes']['fe_edta.pqi']
        expected['values'] = {k: v for k, v in row.items() if k.startswith('m_')}
        actual = copy.deepcopy(record)
        actual['method'] = 'FlahaX selected model; Davies; approximate water activity'
        model = Path(__file__).parents[1] / 'src/flahax/data/chemistry_25c.json'
        actual['sha256']['model'] = hashlib.sha256(model.read_bytes()).hexdigest()
        actual['values'] = {k: result.species[k[2:]] for k in expected['values']}
        tolerance = data['tolerances']
        budgets = {
            k: dict(
                absolute=tolerance['runtime_molality_absolute'],
                relative=tolerance['runtime_molality_relative'],
            )
            for k in expected['values']
        }
        comparison = oracle.compare_reference(actual, expected, budgets)
        self.assertTrue(comparison['passed'], comparison)
        self.assertTrue(comparison['shared_sha256'])
        actual['values']['m_Na+'] *= 2
        comparison = oracle.compare_reference(actual, expected, budgets)
        self.assertFalse(comparison['passed'])
        self.assertFalse(comparison['errors']['m_Na+']['passed'])
