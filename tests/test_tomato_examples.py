"""Tomato examples: the statements their report and batch sheets make must hold."""
import re
import unittest

from examples import tomato_advanced, tomato_simple
from examples.common import serializable
from examples.tomato_report import build
from examples.tomato_tanks import ANALOGUE, INCOMPATIBLE, group_tanks


def compatible(tank):
    codes = [ANALOGUE[p['name']][0] for p in tank['products']]
    return all(frozenset({a, b}) not in INCOMPATIBLE for i, a in enumerate(codes) for b in codes[i + 1:])


class SimpleTomatoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = serializable(tomato_simple.run())

    def test_recipe_meets_every_target_and_scales_to_the_batch(self):
        self.assertTrue(self.r['feasible'])
        for row in self.r['nutrients']:
            self.assertLessEqual(abs(row['deltaPct']), 1.0, row['symbol'])
        for item in self.r['recipe']:
            self.assertAlmostEqual(item['grams_in_batch'], item['grams_per_litre'] * self.r['batch_litres'], places=6)
            self.assertTrue(item['identity'])

    def test_balance_and_ec_are_reported(self):
        self.assertLess(abs(self.r['ion_balance']['imbalancePercent']), 1.0)
        self.assertEqual(self.r['ec']['status'], 'estimated')
        self.assertGreater(self.r['ec']['ec25_ms_cm'], 1.0)


class AdvancedTomatoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = serializable(tomato_advanced.run())

    def test_blend_is_the_largest_share_within_the_sodium_and_chloride_limits(self):
        limits, blends = self.r['limits_mg_l'], {b['well_percent']: b for b in self.r['blends']}
        chosen = blends[self.r['blend_percent']]
        self.assertLessEqual(chosen['Na'], limits['Na'])
        self.assertLessEqual(chosen['Cl'], limits['Cl'])
        self.assertGreater(blends[25]['Cl'], limits['Cl'])
        one_more = tomato_advanced.water_mg_l({k: v * (self.r['blend_percent'] + 1) / 100 for k, v in
                                               _balanced_totals().items()})
        self.assertTrue(one_more['Na'] > limits['Na'] or one_more['Cl'] > limits['Cl'])

    def test_phosphoric_acid_is_withdrawn_because_it_overacidifies(self):
        check = self.r['phosphoric_check']
        self.assertGreater(check['phosphoric_g_per_litre'], 0)
        self.assertLess(check['mixed_ph'], self.r['target_ph'])
        self.assertNotIn(tomato_advanced.PHOSPHORIC, [s['name'] for s in self.r['recipe']['salts']])
        self.assertGreater(self.r['chemistry']['mixed_ph'], self.r['target_ph'])

    def test_acids_are_evaluated_and_the_nitric_dose_closes_the_nitrate_gap(self):
        acid = self.r['acid']
        self.assertEqual({c['product'] for c in acid['candidates']}, {'HNO3-example', 'H3PO4-example'})
        self.assertIsNone(acid['selected'])   # supersaturated phases block acceptance
        self.assertTrue(acid['supersaturated_after_acid'])
        self.assertGreater(acid['nitric_ml_per_batch'], 0)
        miss = abs(acid['nitrate_after_mg_l'] - acid['nitrate_target_mg_l']) / acid['nitrate_target_mg_l']
        self.assertLess(miss, .01)
        self.assertLess(abs(self.r['ec']['acidified']['ph'] - self.r['target_ph']), 1e-6)

    def test_tanks_follow_the_cited_table_and_stages_are_separate_batches(self):
        for tank in self.r['tanks']['tanks'].values():
            self.assertTrue(compatible(tank))
        self.assertEqual(len(self.r['stages']), 3)
        self.assertTrue(self.r['stages'][0]['feasible'])


class TankGroupingTests(unittest.TestCase):
    def test_magnesium_sulfate_needs_a_third_tank_with_phosphate_and_calcium(self):
        salts = [dict(name=n, gramsPerLitre=g) for n, g in (
            ('Calcium Nitrate (ag grade)', .9), ('Magnesium Sulfate (Heptahydrate)', .5),
            ('Potassium Monobasic Phosphate', .1), ('Potassium Sulfate', .5), ('Iron EDTA', .02))]
        grouped = group_tanks(salts)
        self.assertEqual(len(grouped['tanks']), 3)
        for tank in grouped['tanks'].values():
            self.assertTrue(compatible(tank))
        self.assertEqual(grouped['not_covered'], ['Iron EDTA'])

    def test_every_listed_pair_uses_known_products(self):
        codes = {code for code, _ in ANALOGUE.values()}
        for pair in INCOMPATIBLE:
            self.assertLessEqual(pair, codes)


class TomatoReportTests(unittest.TestCase):
    def test_report_and_sheets_are_complete_and_offline(self):
        files = build()
        self.assertEqual(set(files), {'tomato-report.html', 'batch-sheet-simple.html', 'batch-sheet-advanced.html'})
        for name, html in files.items():
            self.assertTrue(html.startswith('<!doctype html>'), name)
            self.assertNotIn('<script', html)
            # Offline: no external resource (the SVG namespace URI is an identifier, not a fetch).
            self.assertIsNone(re.search(r'(src|href)="https?:|url\(https?:|@import', html), name)
            self.assertNotIn('>None<', html)
            self.assertNotIn('nan', html.lower().replace('nanostructured', ''))
        sheet = files['batch-sheet-advanced.html']
        for salt in serializable(tomato_advanced.run())['recipe']['salts']:
            self.assertIn(salt['name'], sheet)
        self.assertIn('<svg', files['tomato-report.html'])


def _balanced_totals():
    from flahax import balance_water_analysis
    well = {i: mg / tomato_advanced.GRAMS_PER_MOL[i] / 1000 for i, mg in tomato_advanced.WELL_MG_L.items()}
    return balance_water_analysis(well, measured_ph=tomato_advanced.WELL_PH).totals


if __name__ == '__main__':
    unittest.main()
