import copy
from dataclasses import replace
from datetime import datetime, timezone
import unittest

from flahax import DeliveryError, TemperatureCelsius, VolumeLitres, ec_recipe_key, plan_ec_delivery, water_ec25
from examples.ec_and_injection import inputs


class ConductivityTests(unittest.TestCase):
    def setUp(self):
        self.stocks, self.profiles, self.pumps = inputs()
        self.args = dict(profiles=self.profiles, water_source_id='synthetic-water', water_ec_ms_cm=.5)

    def test_water_units_and_meter_scale_are_explicit(self):
        self.assertEqual(water_ec25(ec_ms_cm=.5), .5)
        self.assertEqual(water_ec25(tds_ppm=250, tds_factor=.5), .5)
        self.assertAlmostEqual(water_ec25(tds_ppm=250, tds_factor=.7), 250/700)
        # Numeric robustness only, not a physically meaningful meter scale.
        self.assertAlmostEqual(water_ec25(tds_ppm=1e308, tds_factor=1e308), .001)
        for kwargs in ({}, {'ec_ms_cm':.5, 'tds_ppm':250}, {'tds_ppm':250},
                       {'ec_ms_cm':True}, {'ec_ms_cm':float('nan')}, {'ec_ms_cm':-1},
                       {'tds_ppm':250, 'tds_factor':0}, {'ec_ms_cm':1, 'tds_factor':.5}):
            with self.subTest(kwargs=kwargs), self.assertRaises(DeliveryError):
                water_ec25(**kwargs)

    def test_independent_ec_and_recipe_preserving_injection(self):
        plan = plan_ec_delivery(self.stocks, **self.args)
        self.assertAlmostEqual(plan.predictions['irrigation'].ec_ms_cm, .5+1.4/1.01)
        self.assertAlmostEqual(plan.predictions['tank:A'].ec_ms_cm, 18)
        self.assertAlmostEqual(plan.predictions['tank:B'].ec_ms_cm, 25.5)
        self.assertNotAlmostEqual(plan.predictions['tank:A'].ec_ms_cm,
                                  100*plan.predictions['irrigation'].ec_ms_cm)
        self.assertTrue(all(v['volume_litres'] == 1 for v in plan.injections.values()))
        self.assertTrue(all(v['ml_per_litre_final'] == 10 for v in plan.injections.values()))
        self.assertEqual(len(plan.predictions['tank:A'].profile_sha256), 64)
        self.assertIsNone(plan.predictions['tank:A'].uncertainty_ms_cm)

    def test_interpolation_in_both_axes(self):
        # Independent hand-computed bilinear interpolation: midpoint of 4 corners.
        from flahax.conductivity import _predict
        profile = copy.deepcopy(self.profiles[1])
        result = _predict(profile, .5, 75, profile['recipe_key'], 'tank:A', 'synthetic-water')
        expected = sum(p['ec_ms_cm'] for p in profile['points'] if p['strength'] in (50, 100))/4
        self.assertAlmostEqual(result.ec_ms_cm, expected)

    def test_absent_profiles_do_not_fabricate_ec(self):
        plan = plan_ec_delivery(self.stocks, **(self.args | {'profiles':[]}))
        self.assertTrue(all(p.status == 'needs_input' and p.ec_ms_cm is None for p in plan.predictions.values()))

    def test_water_and_strength_extrapolation_fail(self):
        result = plan_ec_delivery(self.stocks, **(self.args | {'water_ec_ms_cm':1}))
        self.assertTrue(all(p.error_code == 'outside_ec_calibration' for p in result.predictions.values()))
        self.profiles[1]['points'] = [p for p in self.profiles[1]['points'] if p['strength'] <= 50]
        result = plan_ec_delivery(self.stocks, **self.args)
        self.assertEqual(result.predictions['tank:A'].error_code, 'outside_ec_calibration')
        self.assertEqual(result.predictions['irrigation'].status, 'estimated')

    def test_provenance_recipe_source_and_reagents_must_match(self):
        for changes in ({'source':''}, {'recordedAt':'bad'}, {'recipe_key':'changed'},
                        {'water_source_id':'other'}, {'reference_temperature_c':20}):
            profiles = copy.deepcopy(self.profiles)
            profiles[0].update(changes)
            plan = plan_ec_delivery(self.stocks, **(self.args | {'profiles':profiles}))
            self.assertEqual(plan.predictions['irrigation'].status, 'blocked')
        plan = plan_ec_delivery(self.stocks, **self.args, reagent_doses_g_per_l={'acid-lot':.01})
        self.assertEqual(plan.predictions['irrigation'].error_code, 'mismatched_ec_profile')
        self.assertEqual(plan.predictions['tank:A'].status, 'estimated')
        self.assertNotEqual(ec_recipe_key(self.stocks), ec_recipe_key(self.stocks, reagent_doses_g_per_l={'acid':.01}))

    def test_malformed_grids_rejected(self):
        for change in ('duplicate', 'missing', 'nonfinite'):
            profiles = copy.deepcopy(self.profiles)
            points = profiles[0]['points']
            if change == 'duplicate':
                points.append(points[0])
            elif change == 'missing':
                points.pop()
            else:
                points[0]['ec_ms_cm'] = float('inf')
            result = plan_ec_delivery(self.stocks, **(self.args | {'profiles':profiles}))
            self.assertEqual(result.predictions['irrigation'].status, 'blocked')

    def test_temperature_and_inconsistent_stock_rejected(self):
        with self.assertRaises(DeliveryError):
            plan_ec_delivery(replace(self.stocks, temperature=TemperatureCelsius(30)), **self.args)
        with self.assertRaises(DeliveryError):
            plan_ec_delivery(replace(self.stocks, tanks=self.stocks.tanks[:1]), **self.args)

    def test_pump_runtime_inventory_and_channel_guards(self):
        options = dict(pump_calibrations=self.pumps,
                       available_volumes={'A':VolumeLitres(1), 'B':VolumeLitres(1)},
                       as_of=datetime(2026, 9, 28, tzinfo=timezone.utc))
        plan = plan_ec_delivery(self.stocks, **self.args, **options)
        self.assertEqual([p.runtime.value for p in plan.pump_commands], [10, 10])
        self.assertTrue(all(p.requires_operator_verification for p in plan.pump_commands))
        options['available_volumes']['A'] = VolumeLitres(.5)
        with self.assertRaises(DeliveryError) as caught:
            plan_ec_delivery(self.stocks, **self.args, **options)
        self.assertEqual(caught.exception.code, 'dry_tank_risk')
        self.pumps['A']['channelId'] = 'B'
        with self.assertRaises(DeliveryError) as caught:
            plan_ec_delivery(self.stocks, **self.args, **options)
        self.assertEqual(caught.exception.code, 'mismatched_record')
