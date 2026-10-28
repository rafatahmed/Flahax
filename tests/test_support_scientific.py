# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Remaining scientific helper boundaries, without changing model data or tolerances."""

import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import fit_phosphate_conductivity as fitting
from tools import verify_joint_sensitivity as sensitivity
from tools import qualify_joint_fit as qualification
from tests import test_joint_problem_contract as contract
from tests.test_joint_fit import controls

ROOT = Path(__file__).resolve().parents[1]


class SupportScientificTests(unittest.TestCase):
    def test_phosphate_fit_cli_and_temporary_write(self):
        block, rows = fitting.fit()
        self.assertEqual(block['fit']['points'], len(rows))
        with (
            tempfile.TemporaryDirectory() as folder,
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            destination = Path(folder) / 'coefficients.json'
            destination.write_text('{"preserved": true}')
            fitting.write(block, destination)
            self.assertTrue(json.loads(destination.read_text())['preserved'])
            self.assertEqual(json.loads(destination.read_text())['supplementary'], block)
            for args in ([], ['--residuals'], ['--write']):
                with (
                    patch.object(sys, 'argv', ['fit', *args]),
                    patch.object(fitting, 'fit', return_value=(block, rows)),
                    patch.object(
                        fitting,
                        'write',
                        side_effect=lambda value: fitting_write(value, destination),
                    ),
                ):
                    fitting.main()
            self.assertIn('kappa_obs', out.getvalue())
        with patch.object(fitting, 'GAP_LIMIT_PERCENT', 0):
            block, _ = fitting.fit()
        self.assertTrue(
            any(
                'note' in value[ion]
                for value in block['cross_checks'].values()
                for ion in fitting.FITTED
            )
        )
        with (
            patch.object(sys, 'argv', ['fit', '--help']),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            runpy.run_module('tools.fit_phosphate_conductivity', run_name='__main__')

    def test_verification_module_commands(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            runpy.run_module('tools.verify_conductivity', run_name='__main__')
        report = json.loads(out.getvalue())
        self.assertEqual(report['method'], '50-digit Decimal QR')
        self.assertTrue(report['withheld_kcl'])
        with (
            patch.object(sys, 'argv', ['qualify', '--help']),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            runpy.run_module('tools.qualify_chemistry_model', run_name='__main__')

    def test_independent_elimination_and_nonfinite_derivative_refusal(self):
        D = sensitivity.D
        self.assertEqual(
            sensitivity._decimal_solve([[D(0), D(1)], [D(1), D(0)]], [[D(2)], [D(3)]], 80),
            [[D(3)], [D(2)]],
        )
        with self.assertRaisesRegex(ValueError, 'singular'):
            sensitivity._decimal_solve([[D(0)]], [[D(1)]], 80)
        problem = contract.JointContractTests().problem()
        state = problem.evaluate({}, 0)
        with (
            patch.object(sensitivity.math, 'isfinite', return_value=False),
            self.assertRaisesRegex(ValueError, 'nonfinite'),
        ):
            sensitivity.independent_charge_gradient(problem, state, 1e-10)
        actual = sensitivity.independent_charge_gradient(problem, state, 1e-10)
        self.assertEqual(len(actual), 2)
        settings = controls(
            problem,
            sensitivity_method='equilibrium',
            stationarity_tolerance=1e-6,
            active_bound_tolerance=1e-8,
            objective_gap_tolerance=1e-12,
        )
        result = qualification.qualify_starts(problem, [({}, 0)], settings)['starts'][0]
        self.assertTrue(result['independentStationarityVerified'])
        with patch.object(
            sensitivity, 'independent_charge_gradient', side_effect=ValueError('injected')
        ):
            self.assertFalse(qualification.verify_stationarity(problem, result, settings))

    def test_precision_disagreement_is_not_a_verified_derivative(self):
        problem = contract.JointContractTests().problem()
        state = problem.evaluate({'salt': 0.3}, 0.05)
        original = sensitivity._decimal_solve

        def drift(matrix, rhs, precision):
            result = original(matrix, rhs, precision)
            return [[v * (2 if precision == 160 else 1) for v in row] for row in result]

        with (
            patch.object(sensitivity, '_decimal_solve', side_effect=drift),
            self.assertRaisesRegex(ValueError, 'precision unresolved'),
        ):
            sensitivity.independent_charge_gradient(problem, state, 1e-10)


fitting_write = fitting.write
