# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Targets are validated by one function, and no entry point keeps an older rule.

A total-N target (``N``) once worked in ``recommend`` but was rejected by the workflow, the
batch command and the pH solver, because each validated targets with its own call and a flag
the caller had to remember. These tests close that class of bug: one validator for targets, a
guard that fails when a call site bypasses it, and the same targets through every entry point.
"""

import ast
import json
from pathlib import Path
import tempfile
import unittest

from flahax import (
    InputError,
    VolumeLitres,
    gap_for,
    load_library,
    plan_fertilizer_workflow,
    recommend,
    rescore_with_reagent,
    solve_weights,
)
from flahax.batch_request import BatchOptions, run_batch
from flahax.composition import validate_profile, validate_targets
from flahax.joint_problem import JointProblem, JointSource

SRC = Path(__file__).resolve().parents[1] / 'src' / 'flahax'
SALTS = load_library()['salts']
OLD_RULE = ('uses N', 'split total N', 'total-N figure')
VALID_TOTAL_N = {
    'total alone': {'N': 150.0, 'Ca': 100.0},
    'forms that agree': {'N': 150.0, 'N_NO3': 120.0, 'N_NH4': 30.0, 'Ca': 100.0},
    'some forms': {'N': 150.0, 'N_NH4': 20.0, 'Ca': 100.0},
}


class OneValidatorTests(unittest.TestCase):
    def test_the_profile_validator_has_no_flag_to_forget(self):
        import inspect

        self.assertNotIn('total_n', inspect.signature(validate_profile).parameters)

    def test_water_maxima_and_assays_never_accept_total_n(self):
        with self.assertRaises(InputError) as raised:
            validate_profile({'N': 5.0}, 'water')
        self.assertIn('target only', str(raised.exception))

    def test_targets_accept_total_n_and_reject_what_every_profile_rejects(self):
        self.assertEqual(validate_targets({'N': 5.0, 'Ca': 1.0}, 'targets'), {'N': 5.0, 'Ca': 1.0})
        for bad in ({'N': -1.0}, {'N': float('nan')}, {'Zz': 1.0}, {'Ca': -1.0}):
            with self.subTest(bad=bad), self.assertRaises(InputError):
                validate_targets(bad, 'targets')
        with self.assertRaises(InputError):
            validate_targets([('N', 5.0)], 'targets')

    def test_no_call_site_validates_a_targets_map_with_the_profile_validator(self):
        offenders = []
        for path in sorted(SRC.glob('*.py')):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            allowed = {
                id(node)
                for function in ast.walk(tree)
                if isinstance(function, ast.FunctionDef) and function.name == 'validate_targets'
                for node in ast.walk(function)
            }
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and id(node) not in allowed
                    and getattr(node.func, 'id', None) == 'validate_profile'
                    and any(
                        'target' in ast.unparse(argument).lower()
                        for argument in [*node.args, *[k.value for k in node.keywords]]
                    )
                ):
                    offenders.append(f'{path.name}:{node.lineno}')
        self.assertEqual(offenders, [], 'validate targets with validate_targets')


class EveryEntryPointTests(unittest.TestCase):
    def check(self, label, call):
        for name, targets in VALID_TOTAL_N.items():
            with self.subTest(entry=label, targets=name):
                try:
                    call(dict(targets))
                except Exception as error:  # a legitimate refusal must not be the old rule
                    self.assertFalse(
                        any(phrase in str(error) for phrase in OLD_RULE),
                        f'{label} still applies the old total-N rule: {error}',
                    )

    def test_the_python_functions(self):
        self.check('recommend', lambda t: recommend(SALTS, t, {}))
        self.check('solve_weights', lambda t: solve_weights(SALTS, t, {}))
        self.check('gap_for', lambda t: gap_for(t, {}))
        self.check(
            'workflow',
            lambda t: plan_fertilizer_workflow(SALTS, t, {}, 5.8, final_volume=VolumeLitres(1000)),
        )
        self.check('rescore_with_reagent', lambda t: rescore_with_reagent({'Ca': 100.0}, t, {}))

    def test_the_equilibrium_delivery_planner(self):
        from flahax import plan_equilibrium_delivery
        from tests.test_equilibrium_delivery import arguments

        self.check(
            'plan_equilibrium_delivery',
            lambda t: plan_equilibrium_delivery(**(arguments() | {'targets': t})),
        )

    def test_the_joint_solver_problem(self):
        source = JointSource('p', {'N_NO3': 0.1, 'Ca': 0.1}, None)
        reagent = JointSource('r', {'K': 0.3}, None)
        self.check(
            'JointProblem',
            lambda t: JointProblem(
                (source,),
                reagent,
                t,
                {},
                final_volume_litres=1000,
                solvent_mass_kg=1000,
                target_ph=5.8,
                maximum_reagent_mass_g=1e6,
            ),
        )

    def test_the_batch_command_and_its_json_boundary(self):
        def batch(targets):
            with tempfile.TemporaryDirectory() as folder:
                target_file = Path(folder, 't.json')
                target_file.write_text(json.dumps(targets))
                water = Path(folder, 'w.json')
                water.write_text(json.dumps({'mg_per_litre': {'HCO3': 0}, 'measured_ph': 6.0}))
                return run_batch(
                    BatchOptions(
                        water=str(water), targets=str(target_file), volume=1000, ratio=100
                    )
                )

        self.check('batch', batch)


if __name__ == '__main__':
    unittest.main()
