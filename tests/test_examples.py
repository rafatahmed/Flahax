import json
import unittest

from examples.run_all import SCENARIOS, markdown
from examples.common import serializable
from examples.visual_report import render_html, bars
import xml.etree.ElementTree as ET
import re


class CapabilityExamplesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {name:serializable(run()) for name, run in SCENARIOS.items()}

    def test_pepper_preserves_water_and_incidental_boundary(self):
        workflow = self.results['pepper']['workflow']
        self.assertEqual(workflow['nutrient_gap']['Ca'], 84)
        self.assertEqual(workflow['stages']['chemistry']['status'], 'needs_input')
        self.assertEqual(workflow['stages']['formulation']['status'], 'requires_review')
        self.assertGreater(workflow['recommendation']['incidentalContributions'][0]['ppm'], 0)

    def test_pepper_tank_review_keeps_all_products_and_acid_accounting(self):
        pepper = self.results['pepper']
        review = pepper['stock_allocation_review']
        self.assertEqual(review['status'], 'not_ready_for_mixing')
        rows = {r['product']:r for r in review['rows']}
        recipe = pepper['workflow']['recommendation']['salts']
        self.assertEqual(len(rows), len(recipe))
        for salt in recipe:
            row = rows[salt['name']]
            self.assertAlmostEqual(row['recipe_mass_g'], salt['gramsPerLitre']*1000)
            self.assertIsNone(row['stock_concentration_g_per_litre'])
        self.assertEqual(rows['Calcium Nitrate (ag grade)']['proposed_channel'], 'A')
        self.assertEqual(rows['Mg Nitrate']['proposed_channel'], 'A')
        self.assertEqual(rows['Mn EDTA']['proposed_channel'], 'A')
        self.assertEqual(rows['Potassium Monobasic Phosphate']['proposed_channel'], 'B')
        self.assertEqual(rows['Potassium Sulfate']['proposed_channel'], 'B')
        self.assertEqual(rows['Phosphoric Acid (75%)']['proposed_channel'], 'Acid')
        for name in ('Iron II Sulfate (Hepahydrate)', 'Copper Sulfate (pentahydrate)',
                     'Zinc Sulfate (Monohydrate)', 'Boric Acid', 'Sodium Molybdate (Dihydrate)'):
            self.assertEqual(rows[name]['proposed_channel'], 'Unassigned')
        self.assertIn('Do not add that mass again', review['acid_accounting'])
        self.assertIn('not a requirement stated by the PDF', review['acid_policy'])

    def test_tank_review_does_not_assign_unknown_materials(self):
        from examples.pepper_stock_review import review
        result = review({'salts':[{'id':'x', 'name':'Unknown grade', 'gramsPerLitre':.2}]}, 200)
        self.assertEqual(result['rows'][0]['proposed_channel'], 'Unassigned')
        self.assertEqual(result['rows'][0]['recipe_mass_g'], 40)

    def test_chemistry_covers_catalogue_conservation_and_solids(self):
        result = self.results['chemistry']
        self.assertEqual(len(result['catalogue_conversions_at_001_g_per_kg_water']), 28)
        self.assertGreater(result['mixed']['species']['FeDtp-2'], 0)
        self.assertGreater(result['mixed']['species']['FeEdd-'], 0)
        self.assertTrue(any(v > 0 for v in result['precipitation']['precipitated'].values()))
        for state in (result['mixed'], result['precipitation']):
            self.assertLess(state['ionic_strength'], .1)
            self.assertLess(max(map(abs, state['residuals'].values())), 1e-10)
        self.assertEqual(result['expected_davies_rejection']['error_code'], 'activity_model_out_of_range')

    def test_delivery_is_calculated_not_operator_approved(self):
        result = self.results['delivery']
        self.assertEqual(result['delivery']['state'], 'validated')
        stages = result['workflow']['stages']
        self.assertEqual(len(stages['acid_selection']['value']['candidates']), 2)
        self.assertTrue(result['delivery']['commands'][0]['requires_operator_verification'])
        self.assertEqual(stages['nitric']['value']['target_ph'], 6.5)

    def test_curve_stock_split_and_expected_rejections(self):
        result = self.results['titration_stocks']
        self.assertEqual(len(result['stocks']['tanks']), 2)
        self.assertGreater(result['titration']['reagent_volume_litres'], 0)
        self.assertEqual(result['expected_outside_curve']['error_code'], 'outside_titration_range')
        self.assertTrue(result['expected_insufficient_tanks']['error_code'])

    def test_cli_and_strict_json_report(self):
        self.assertTrue(self.results['cli']['response']['feasible'])
        report = dict(notice='Synthetic only', scenarios=self.results)
        self.assertEqual(json.loads(json.dumps(report, allow_nan=False)), report)
        text = markdown(report)
        self.assertIn('Pepper nutrient balance', text)
        self.assertIn('N_NH4', text)
        self.assertIn('requires_review', text)

    def test_visual_report_charts_tables_and_no_external_resources(self):
        report = dict(notice='Synthetic only <not approved>', scenarios=self.results)
        html = render_html(report)
        self.assertIn('&lt;not approved&gt;', html)
        self.assertNotIn('<script', html)
        self.assertNotIn('https://', html)
        self.assertGreaterEqual(html.count('<table>'), 9)
        charts = re.findall(r'<svg.*?</svg>', html, re.S)
        self.assertEqual(len(charts), 5)
        for chart in charts:
            ET.fromstring(chart)
        self.assertIn('FICTIONAL CALIBRATION DATA', html)
        self.assertIn('requires_review', html)
        self.assertIn('Missing measured EC profiles', html)
        self.assertIn('id="tank-allocation"', html)
        self.assertIn('Not ready for mixing.', html)
        self.assertIn('Acid location in this EC demonstration: none.', html)
        self.assertIn('Do not automatically place these products in B', html)
        self.assertIn('Product actually assigned', html)

    def test_chart_does_not_turn_missing_values_into_zero(self):
        chart = bars('Missing <EC>', ['A', 'B'], [('EC', [None, 0])], 'mS/cm')
        self.assertIn('Missing &lt;EC&gt;', chart)
        self.assertEqual(chart.count('rx="3"'), 1)
        self.assertIn('width="0.0"', chart)
