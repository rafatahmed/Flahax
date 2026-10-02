"""Manufacturer transcription, screening boundaries and site-input contracts."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from flahax import (DeliveryError, estimate_manufacturer_ec, size_injection_requirements,
                    plan_fertilizer_workflow, load_library)
from flahax.planning_cli import interactive, execute


class SitePlanningTests(unittest.TestCase):
    def test_brochure_anchor_transcription(self):
        anchors = {'Ultrasol K Plus': 1.3, 'Ultrasol SOP': 1.5, 'Ultrasol MKP': .7,
                   'Ultrasol MAP': .9, 'Ultrasol Calcium': 1.2, 'Ultrasol Magsul': 1.2,
                   'Ultrasol Magnit': .9}
        for product, ec in anchors.items():
            result = estimate_manufacturer_ec({product: 1}, water_ec_ms_cm=0)
            self.assertEqual(result['ec_ms_cm'], ec)
            self.assertEqual(result['status'], 'screening_estimate')
            self.assertIsNone(result['uncertainty_ms_cm'])

    def test_pre_acid_mixture_math_and_tds(self):
        result = estimate_manufacturer_ec({'Ultrasol K Plus': .5, 'Ultrasol Calcium': .25,
                                         'Ultrasol MKP': .1}, water_tds_ppm=250, tds_factor=.5)
        self.assertAlmostEqual(result['ec_ms_cm'], 1.52)
        self.assertEqual(result['water_ec_ms_cm'], .5)

    def test_no_silent_aliases_missing_trace_or_extrapolation(self):
        cases = [({'Potassium Nitrate': .1}, {}, 'missing_product_ec_evidence'),
                 ({'Ultrasol K Plus': .1, 'Mn EDTA': .001}, {}, 'missing_product_ec_evidence'),
                 ({'Ultrasol K Plus': 10}, {}, 'loading_outside_screening_policy'),
                 ({'Ultrasol K Plus': .1}, {'channel': 'tank:A'}, 'concentrated_stock_model_unavailable'),
                 ({'Ultrasol K Plus': .1}, {'acid_added': True}, 'acid_reaction_model_unavailable'),
                 ({'Ultrasol K Plus': .1}, {'temperature_c': 20}, 'temperature_outside_reference')]
        for doses, kwargs, code in cases:
            result = estimate_manufacturer_ec(doses, water_ec_ms_cm=.5, **kwargs)
            self.assertIsNone(result['ec_ms_cm'])
            self.assertEqual(result['error_code'], code)

    def test_invalid_ec_inputs(self):
        for kwargs in ({'water_tds_ppm': 250}, {'water_ec_ms_cm': True},
                       {'water_ec_ms_cm': .5, 'acid_added': 'false'},
                       {'water_ec_ms_cm': .5, 'temperature_c': True},
                       {'water_ec_ms_cm': .5, 'channel': 'tank:'}):
            with self.assertRaises(DeliveryError):
                estimate_manufacturer_ec({'Ultrasol K Plus': .5}, **kwargs)
        for amount in (-1, float('nan'), float('inf'), True):
            with self.assertRaises(DeliveryError):
                estimate_manufacturer_ec({'Ultrasol K Plus': amount}, water_ec_ms_cm=.5)

    def sizing(self, **kwargs):
        args = dict(duration_hours=2, equipment_type='dosing_pump', final_volume_litres=10000,
                    channels={n: dict(final_litres_per_stock_litre=100, available_stock_litres=100)
                              for n in ('A', 'B')})
        args.update(kwargs)
        return size_injection_requirements(**args)

    def test_flow_volume_and_ratio_conservation(self):
        for kind in ('dosing_pump', 'venturi', 'dosatron'):
            result = self.sizing(equipment_type=kind)
            self.assertEqual(result['final_flow_litres_per_hour'], 5000)
            self.assertEqual(result['carrier_water_litres'], 9800)
            self.assertIsNone(result['selected_model'])
            self.assertEqual(result['status'], 'sized')
            for channel in result['channels'].values():
                self.assertEqual(channel['required_flow_litres_per_hour'], 50)
                self.assertEqual(channel['required_stock_litres'], 100)
                self.assertAlmostEqual(channel['stock_percent_of_common_carrier'], 100 / 98)

    def test_area_and_inventory(self):
        result = self.sizing(final_volume_litres=None, active_area_m2=2000, gross_depth_mm=5)
        self.assertEqual(result['final_volume_litres'], 10000)
        self.assertEqual(self.sizing(channels={'A': dict(final_litres_per_stock_litre=100,
                                                       available_stock_litres=99)})['status'], 'insufficient_stock')
        for kwargs in ({'active_area_m2': 100}, {'duration_hours': 0}, {'duration_hours': True},
                       {'final_volume_litres': None, 'active_area_m2': 100},
                       {'equipment_type': 'made-up'}, {'channels': {}},
                       {'channels': {'A': dict(final_litres_per_stock_litre=1, available_stock_litres=1)}}):
            with self.assertRaises(DeliveryError):
                self.sizing(**kwargs)

    def test_workflow_requires_explicit_water(self):
        with self.assertRaises(DeliveryError):
            execute('workflow', dict(salts=[{}], targets={'K':10}, target_ph=6.5, final_volume_litres=100))

    def test_standard_acid_boundary(self):
        salt = next(s for s in load_library()['salts'] if s['name'] == 'Potassium Nitrate')
        result = plan_fertilizer_workflow([salt], {'K':10}, {}, 6.5,
            acids=dict(products=[{'chemicalFormula':'H2SO4'}], maximum_nutrient_error_percent=1,
                       maximum_reagent_volume_litres=1))
        self.assertEqual(result.stages['acid_selection'].error_code, 'unsupported_standard_acid')

    def test_interactive_prompts_do_not_supply_water_defaults(self):
        answers = iter(['{"Ultrasol K Plus":0.5}', 'ec', '0.5', '25', 'irrigation', 'false'])
        with patch('builtins.input', side_effect=lambda: next(answers)), patch('sys.stderr', new=io.StringIO()):
            payload = interactive('ec')
        self.assertEqual(execute('ec', payload)['ec_ms_cm'], 1.15)
        with patch('builtins.input', return_value=''), patch('sys.stderr', new=io.StringIO()):
            with self.assertRaises(DeliveryError):
                interactive('ec')

    def test_cli_machine_readable_and_malformed_inputs(self):
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
        args = [sys.executable, '-m', 'flahax', 'ec']
        result = subprocess.run(args, input=json.dumps(dict(doses_g_per_litre={'Ultrasol K Plus': .5},
                                                           water_ec_ms_cm=.5)), text=True, capture_output=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['ec_ms_cm'], 1.15)
        for value in ('[]', '{bad', '{"unexpected":1}'):
            result = subprocess.run(args, input=value, text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
