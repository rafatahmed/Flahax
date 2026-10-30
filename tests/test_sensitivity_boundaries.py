# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Sensitivity refusal witnesses; injected states are not chemistry certificates."""

from dataclasses import replace
from fractions import Fraction
import unittest
from unittest.mock import patch
from flahax import DeliveryError
from flahax import joint_sensitivity as sensitivity
from flahax.joint_workflow import joint_candidate
from tests import test_joint_problem_contract as contract
from tests.catalogue_history import historical_catalogue


class SensitivityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.problem = contract.JointContractTests().problem()
        self.state = self.problem.evaluate({}, 0)

    def assert_refused(self, state, message):
        with self.assertRaisesRegex(DeliveryError, message) as caught:
            sensitivity.equilibrium_charge_gradient(self.problem, state)
        self.assertEqual(caught.exception.code, 'unresolved_sensitivity')

    def test_invalid_activity_and_ambiguous_water_floor(self):
        for changes, message in [
            ({'ionic_strength': 0}, 'activity'),
            ({'water_activity': 0}, 'activity'),
            ({'water_activity': 0.9}, 'floor'),
        ]:
            self.assert_refused(
                self.state | {'equilibrium': replace(self.state['equilibrium'], **changes)},
                message,
            )

    def test_singular_absent_component_power_and_overflow_are_refused(self):
        bases = {
            b
            for source in (*self.problem.fertilizers, self.problem.reagent)
            for b in source.components
        }
        absent = next(b for b in bases if b not in self.state['equilibrium'].totals)
        for power, beta, message in [
            (-1, 0, 'singular boundary'),
            (0.5, 0, 'singular boundary'),
            (1, 1000, 'nonfinite boundary'),
        ]:
            record = dict(name='synthetic', powers={absent: power}, beta=beta, charge=1)
            with patch.object(sensitivity, 'chemistry', return_value={'aqueous': [record]}):
                self.assert_refused(self.state, message)

    def test_corrupt_adjoint_cannot_escape_as_finite_sensitivity(self):
        # Fault injection at the linear-solver boundary, not a physical equilibrium.
        for value in (Fraction(10**1000), float('inf')):
            with patch.object(
                sensitivity,
                '_exact_linear',
                side_effect=lambda matrix, rhs: [[value] for row in matrix],
            ):
                self.assert_refused(self.state, 'nonfinite charge')

    def test_inexact_linear_inputs_cannot_claim_exact_residual(self):
        with self.assertRaisesRegex(DeliveryError, 'linear residual'):
            sensitivity._exact_linear([[0.3]], [[0.7]])


class JointInputBoundaryTests(unittest.TestCase):
    def test_missing_chemistry_and_nonmapping_config_are_rejected_before_search(self):
        args = [None] * 13
        for components, config, code in [
            (None, None, 'missing_chemistry'),
            ({}, [], 'invalid_type'),
        ]:
            args[12] = components
            with self.assertRaises(DeliveryError) as caught:
                joint_candidate(*args, config=config)
            self.assertEqual(caught.exception.code, code)


class JointAcceptanceBoundaryTests(unittest.TestCase):
    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_missing_optional_start_uses_recipe_seed(self):
        self.enterContext(historical_catalogue())
        from tests import test_joint_workflow as fixtures

        stage = fixtures.JointWorkflowTests().positive_case(config_change={'starting_points': {}})
        self.assertIsNotNone(stage.value.selected)
        self.assertAlmostEqual(stage.value.selected.target.ph, 5.8, delta=0.001)

    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_nutrient_failure_cannot_be_promoted_by_a_clear_chemical_judgement(self):
        self.enterContext(historical_catalogue())
        from tests import test_joint_workflow as fixtures
        from flahax import ph_adjustment

        original = ph_adjustment._blend_recipe

        def missed(*args, **kwargs):
            return original(*args, **kwargs) | {'feasible': False}

        with patch.object(ph_adjustment, '_blend_recipe', missed):
            with patch.object(ph_adjustment, '_judge', return_value=('accepted', None, None, {})):
                stage = fixtures.JointWorkflowTests().positive_case()
        self.assertTrue(stage.value.candidates)
        self.assertEqual(stage.value.candidates[0].status, 'requires_review')
        self.assertEqual(
            stage.value.candidates[0].message, 'joint candidate misses nutrient targets'
        )
