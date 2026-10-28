# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Reagent validation and failed demand searches must not imply acceptance."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from flahax import DeliveryError
from flahax import ph_adjustment as ph
from tests.test_ph_adjustment import ACIDS


class ReagentBoundaryTests(unittest.TestCase):
    def test_product_metadata_assay_and_density_are_required(self):
        for value, code in [
            (None, 'invalid_type'),
            ({}, 'missing_field'),
            (ACIDS[0] | {'chemicalFormula': 'HCl'}, 'unsupported_reagent'),
            (ACIDS[0] | {'massFraction': 2}, 'inconsistent_assay'),
            (ACIDS[0] | {'massFraction': True}, 'invalid_value'),
            (ACIDS[0] | {'densityKgPerL': 0}, 'invalid_value'),
        ]:
            with self.subTest(value=value), self.assertRaises(DeliveryError) as caught:
                ph._check_product(value)
            self.assertEqual(caught.exception.code, code)

    def test_coupled_options_reject_invalid_shapes_before_mixing(self):
        args = dict(
            products=ACIDS,
            mix=Mock(),
            water_mass_kg=100,
            final_volume_litres=100,
            maximum_reagent_volume_litres=1,
        )
        for change, code in [
            ({'products': []}, 'missing_field'),
            ({'products': [None]}, 'invalid_value'),
            ({'products': ACIDS * 2}, 'invalid_value'),
            ({'preferred_product_id': 'missing'}, 'unknown_product'),
            ({'phases': 'Calcite'}, 'invalid_type'),
            ({'water_mass_kg': 0}, 'invalid_value'),
        ]:
            with self.subTest(change=change), self.assertRaises(DeliveryError) as caught:
                ph.plan_coupled_ph([], {}, {}, 6, **(args | change))
            self.assertEqual(caught.exception.code, code)
        args['mix'].assert_not_called()

    def test_zero_demand_preserves_original_state_and_unsupported_identity_refuses(self):
        state = SimpleNamespace(charge_balance=0)
        self.assertEqual(ph.reagent_dose({}, 7, 7, 'HNO3', initial=state), (0, state))
        with self.assertRaises(DeliveryError) as caught:
            ph.reagent_dose({}, 7, 6, 'HCl', initial=state)
        self.assertEqual(caught.exception.code, 'unsupported_reagent')

    def test_demand_search_wrong_sign_and_unbracketed_response_refuse(self):
        # Injected response functions isolate bracketing controls, not real chemistry.
        for charge, code in [(-1, 'wrong_reagent_direction'), (1, 'nonconvergent')]:
            with patch.object(ph, 'solve', return_value=SimpleNamespace(charge_balance=charge)):
                with self.assertRaises(DeliveryError) as caught:
                    ph.reagent_dose({}, 7, 6, 'HNO3', initial=SimpleNamespace(charge_balance=0))
            self.assertEqual(caught.exception.code, code)


class ReagentAcceptanceBoundaryTests(unittest.TestCase):
    def test_explicit_overdose_outranks_clear_saturation_and_clear_case_can_pass(self):
        clean = dict(blocks=[], review=[], advisories=[])
        with patch.object(ph, 'assess_saturation', return_value=clean):
            verdict = ph._judge({'rows': []}, None, {}, over_dose=True)
            self.assertEqual(verdict[:2], ('rejected', 'dose_limit_exceeded'))
            verdict = ph._judge({'rows': []}, None, {}, accepted='not_needed')
            self.assertEqual(verdict[:3], ('not_needed', None, None))


class CoupledBracketingBoundaryTests(unittest.TestCase):
    def test_unbounded_demand_feedback_is_not_returned_as_a_recipe(self):
        count = [0]
        mixed = SimpleNamespace(totals={}, ph=7)

        def increasing(*args, **kwargs):
            count[0] += 1
            return 10.0 ** count[0], mixed

        # An intentionally impossible response isolates the bounded search refusal.
        with patch.object(ph, 'recommend', return_value={}):
            with patch.object(ph, 'reagent_dose', increasing):
                with self.assertRaises(DeliveryError) as caught:
                    ph._couple(
                        [],
                        {},
                        {},
                        6,
                        ACIDS[0],
                        0.6,
                        1.37,
                        63,
                        {},
                        lambda recipe: mixed,
                        1,
                        1,
                        1,
                        (),
                        {},
                    )
        self.assertEqual(caught.exception.code, 'nonconvergent')
        self.assertGreater(count[0], 30)


class LegacyBlendBoundaryTests(unittest.TestCase):
    def test_endpoint_without_search_metadata_still_rebuilds_quantities(self):
        from flahax import load_library, recommend

        pool = [p for p in load_library()['salts'] if p['formula'] == 'KNO3']
        endpoint = recommend(pool, {'K': 10}, {})
        endpoint.pop('substitutionSearch', None)
        result = ph._blend_recipe(pool, {'K': 10}, {}, [endpoint, endpoint], 0.5, {})
        self.assertNotIn('substitutionSearch', result)
        self.assertAlmostEqual(next(r['final'] for r in result['rows'] if r['symbol'] == 'K'), 10)
