# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Calibrated conductivity boundary checks for runtime coverage closure (#186)."""

from copy import deepcopy
from dataclasses import replace
import unittest
from flahax import DeliveryError, VolumeLitres, GramsPerLitre, ec_recipe_key, plan_ec_delivery
from examples.ec_and_injection import inputs


class CalibratedConductivityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.stocks, self.profiles, _ = inputs()
        self.args = dict(
            profiles=self.profiles, water_source_id='synthetic-water', water_ec_ms_cm=0.5
        )

    def rejected(self, code, stocks=None, **changes):
        with self.assertRaises(DeliveryError) as caught:
            plan_ec_delivery(self.stocks if stocks is None else stocks, **(self.args | changes))
        self.assertEqual(caught.exception.code, code)

    def test_request_and_recipe_identity_guards(self):
        self.rejected('invalid_type', stocks=[])
        self.rejected('missing_field', water_source_id=' ')
        for profiles in ({}, [None], [{}], self.profiles * 2):
            self.rejected('invalid_ec_profile', profiles=profiles)
        self.rejected('unknown_channel', profiles=[self.profiles[0] | dict(channel='tank:unused')])
        self.rejected('missing_field', pump_calibrations={})
        self.rejected('missing_field', available_volumes={})
        for stock, channel, kwargs, code in [
            ([], 'irrigation', {}, 'invalid_type'),
            (self.stocks, 'tank:unused', {}, 'unknown_channel'),
            (self.stocks, 'irrigation', {'reagent_doses_g_per_l': {' ': 1}}, 'invalid_type'),
            (
                replace(
                    self.stocks,
                    recipe=replace(self.stocks.recipe, salts=self.stocks.recipe.salts * 2),
                ),
                'irrigation',
                {},
                'inconsistent_recipe',
            ),
        ]:
            with self.assertRaises(DeliveryError) as caught:
                ec_recipe_key(stock, channel, **kwargs)
            self.assertEqual(caught.exception.code, code)

    def test_corrupt_stock_assignments_are_not_used_for_ec_or_injection(self):
        a, b = self.stocks.tanks
        self.rejected('inconsistent_recipe', stocks=replace(self.stocks, tanks=(a, a)))
        self.rejected(
            'inconsistent_recipe',
            stocks=replace(self.stocks, tanks=(a, replace(b, salts=a.salts))),
        )
        unknown = replace(a, salts=(replace(a.salts[0], salt_id='unknown'),))
        broken = replace(self.stocks, tanks=(unknown, b))
        with self.assertRaises(DeliveryError) as caught:
            ec_recipe_key(broken, 'tank:' + a.tank.tank_id)
        self.assertEqual(caught.exception.code, 'inconsistent_recipe')
        changed = replace(a, salts=(replace(a.salts[0], concentration=GramsPerLitre(1e-9)),))
        self.rejected('inconsistent_recipe', stocks=replace(self.stocks, tanks=(changed, b)))
        self.rejected(
            'dry_tank_risk',
            stocks=replace(self.stocks, tanks=(replace(a, stock_volume=VolumeLitres(1e-9)), b)),
        )

    def test_malformed_measured_evidence_blocks_prediction(self):
        for change in [
            dict(recordedAt='2026-09-28T00:00:00'),
            dict(points=[]),
            dict(points=[None]),
            dict(extra=object()),
        ]:
            profiles = deepcopy(self.profiles)
            profiles[0].update(change)
            plan = plan_ec_delivery(self.stocks, **(self.args | dict(profiles=profiles)))
            prediction = plan.predictions['irrigation']
            self.assertEqual(prediction.status, 'blocked')
            self.assertEqual(prediction.error_code, 'invalid_ec_profile')
            self.assertIsNone(prediction.ec_ms_cm)

    def test_nonfinite_interpolation_coordinate_does_not_produce_a_prediction(self):
        from flahax.conductivity import _bracket

        with self.assertRaises(DeliveryError) as caught:
            _bracket([0, 1], float('nan'))
        self.assertEqual(caught.exception.code, 'invalid_ec_profile')


class IrrigationConductivityBoundaryTests(unittest.TestCase):
    def test_invalid_request_values_and_inner_solver_failures_are_not_ec_estimates(self):
        from unittest.mock import patch
        from flahax import irrigation_ec as ec

        args = dict(
            totals_molal={'Na+': 0.001, 'Cl-': 0.001},
            solution_id='test',
            ph_mode='supplied',
            ph=7,
            phase_policy='dissolved',
        )
        for change, code in [
            (dict(phases='Calcite'), 'invalid_phase_policy'),
            (dict(temperature_c=True), 'invalid_value'),
            (dict(assay_charge_residual_eq_per_kgw=float('nan')), 'invalid_value'),
        ]:
            with self.assertRaises(DeliveryError) as caught:
                ec.calculate_ec_from_totals(**(args | change))
            self.assertEqual(caught.exception.code, code)
        with patch.object(
            ec, 'solve', side_effect=DeliveryError('nonconvergent', 'injected failed solve')
        ):
            with self.assertRaises(DeliveryError) as caught:
                ec.calculate_ec_from_totals(**args)
        self.assertEqual(caught.exception.code, 'nonconvergent')

    def test_water_and_reagent_provenance_is_required(self):
        from flahax import irrigation_ec as ec
        from flahax.measured_water import balance_water_analysis

        with self.assertRaises(DeliveryError) as caught:
            ec.DeclaredPureWater('test', 'unknown')
        self.assertEqual(caught.exception.code, 'invalid_value')
        args = dict(
            recipe_id='test',
            water=ec.DeclaredPureWater('test', 'RO'),
            ph_mode='supplied',
            ph=7,
            phase_policy='dissolved',
        )
        balanced = balance_water_analysis({'Na+': 0.001, 'Cl-': 0.001, 'CO3-2': 0}, measured_ph=7)
        cases = [
            ([], {}, 'invalid_value'),
            ({}, dict(water=balanced), 'incomplete_water_analysis'),
            ({}, dict(reagent_id='acid'), 'missing_field'),
            ({}, dict(reagent_additions_molal={'NO3-': 0.001}), 'missing_field'),
            ({}, dict(reagent_id='acid', reagent_additions_molal={'unknown': 1}), 'invalid_value'),
        ]
        for doses, changes, code in cases:
            with self.assertRaises(DeliveryError) as caught:
                ec.calculate_irrigation_ec(doses, **(args | changes))
            self.assertEqual(caught.exception.code, code)

    def test_unknown_declared_charge_is_not_silently_zero(self):
        from unittest.mock import patch
        from flahax import irrigation_ec as ec
        from flahax.catalogue_chemistry import ProductChemistry

        profile = ProductChemistry('Synthetic', 'salt', ('Na+',), 'synthetic')
        for totals in ({'PO4-3': 1}, {'unknown': 1}):
            with patch.object(
                ec, 'catalogue_dose_contributions', return_value=[('Synthetic', profile, totals)]
            ):
                with self.assertRaises(DeliveryError) as caught:
                    ec.assay_charge_residual({'Synthetic': 1})
            self.assertEqual(caught.exception.code, 'unsupported_product_chemistry')

    def test_plan_temperature_is_not_extrapolated(self):
        from flahax import plan_equilibrium_delivery
        from flahax.irrigation_ec import calculate_irrigation_ec_from_plan
        from tests.test_equilibrium_delivery import arguments

        plan = plan_equilibrium_delivery(**arguments())
        changed = replace(plan, audit=plan.audit | dict(temperatureC=20))
        result = calculate_irrigation_ec_from_plan(changed)
        self.assertEqual(result.status, 'not_supported')
        self.assertIsNone(result.ec25_ms_cm)
        self.assertEqual(result.reason, 'temperature_outside_reference')
