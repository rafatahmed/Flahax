# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tomato examples: the statements their report and batch sheets make must hold."""

import re
import unittest

from examples import tomato_advanced, tomato_simple
from examples.common import serializable
from examples.tomato_report import build
from flahax import load_library
from flahax.tank_grouping import _class_conflict, product_classes
from tests.catalogue_history import historical_catalogue

with historical_catalogue():
    PRODUCTS = {p['name']: p for p in load_library()['salts']}


def compatible(tank):
    classes = [product_classes(PRODUCTS[p['name']]) for p in tank['products']]
    return all(
        _class_conflict(a, b) is None for i, a in enumerate(classes) for b in classes[i + 1 :]
    )


class SimpleTomatoTests(unittest.TestCase):
    # Owner catalogue: re-enable in PR 4 (G5)
    # Owner catalogue: re-enable in PR 3 (G25)
    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(historical_catalogue())
        cls.r = serializable(tomato_simple.run())

    def test_recipe_meets_every_target_and_scales_to_the_batch(self):
        self.assertTrue(self.r['feasible'])
        for row in self.r['nutrients']:
            self.assertLessEqual(abs(row['deltaPct']), 1.0, row['symbol'])
        for item in self.r['recipe']:
            self.assertAlmostEqual(
                item['grams_in_batch'], item['grams_per_litre'] * self.r['batch_litres'], places=6
            )
            self.assertTrue(item['identity'])

    def test_balance_and_ec_are_reported(self):
        self.assertLess(abs(self.r['ion_balance']['imbalancePercent']), 1.0)
        self.assertEqual(self.r['ec']['status'], 'not_supported')
        self.assertIsNone(self.r['ec']['ec25_ms_cm'])
        self.assertIsNone(self.r['ec']['range_ms_cm'])


class AdvancedTomatoTests(unittest.TestCase):
    # Owner catalogue: re-enable in PR 4 (G5)
    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(historical_catalogue())
        cls.r = serializable(tomato_advanced.run())

    def test_blend_is_the_largest_share_within_the_sodium_and_chloride_limits(self):
        limits, blends = self.r['limits_mg_l'], {b['well_percent']: b for b in self.r['blends']}
        chosen = blends[self.r['blend_percent']]
        self.assertLessEqual(chosen['Na'], limits['Na'])
        self.assertLessEqual(chosen['Cl'], limits['Cl'])
        self.assertGreater(blends[25]['Cl'], limits['Cl'])
        # Decided on the laboratory analysis (#84): 8% passes, 9% fails on its measured chloride
        # (115.2 mg/L) although the charge-balanced model (104.3 mg/L) would pass it.
        self.assertEqual(self.r['blend_percent'], 8)
        self.assertAlmostEqual(chosen['Na'], 54.4, places=1)
        self.assertAlmostEqual(chosen['Cl'], 102.4, places=1)
        self.assertGreater(blends[9]['Cl'], limits['Cl'])
        self.assertLess(blends[9]['Cl_model'], limits['Cl'])
        one_more = tomato_advanced.water_mg_l(
            {k: v * 0.09 for k, v in _balanced().analytical_totals.items()}
        )
        self.assertGreater(one_more['Cl'], limits['Cl'])
        self.assertAlmostEqual(
            self.r['chloride_boundary_percent'], 100 * limits['Cl'] / 1280.4, places=9
        )

    def test_phosphoric_acid_is_withdrawn_because_it_overacidifies(self):
        check = self.r['phosphoric_check']
        self.assertGreater(check['phosphoric_g_per_litre'], 0)
        self.assertLess(check['mixed_ph'], self.r['target_ph'])
        self.assertNotIn(
            tomato_advanced.PHOSPHORIC, [s['name'] for s in self.r['recipe']['salts']]
        )
        self.assertGreater(self.r['chemistry']['mixed_ph'], self.r['target_ph'])

    def test_acids_are_evaluated_and_the_nitric_dose_closes_the_nitrate_gap(self):
        acid = self.r['acid']
        self.assertEqual(
            {c['product'] for c in acid['candidates']}, {'HNO3-example', 'H3PO4-example'}
        )
        self.assertIsNone(acid['selected'])  # phase-blocked nitric; phosphoric misses P
        self.assertEqual(
            {c['product']: c['status'] for c in acid['candidates']}['HNO3-example'],
            'rejected',
        )
        nitric = next(c for c in acid['candidates'] if c['product'] == 'HNO3-example')
        self.assertIn('Hydroxylapatite', nitric['message'])
        self.assertIsNone(nitric['volume_litres'])
        self.assertTrue(acid['supersaturated_after_acid'])
        self.assertGreater(acid['nitric_ml_per_batch'], 0)
        miss = (
            abs(acid['nitrate_after_mg_l'] - acid['nitrate_target_mg_l'])
            / acid['nitrate_target_mg_l']
        )
        self.assertLess(miss, 0.01)
        self.assertLess(abs(self.r['ec']['acidified']['ph'] - self.r['target_ph']), 1e-6)

    def test_tanks_follow_the_cited_table_and_stages_are_separate_batches(self):
        for tank in self.r['tanks']['tanks'].values():
            self.assertTrue(compatible(tank))
        self.assertEqual(len(self.r['stages']), 3)
        self.assertTrue(self.r['stages'][0]['feasible'])


class TomatoReportTests(unittest.TestCase):
    # Owner catalogue: re-enable in PR 4 (G5)
    def test_report_and_sheets_are_complete_and_offline(self):
        self.enterContext(historical_catalogue())
        files = build()
        self.assertEqual(
            set(files),
            {'tomato-report.html', 'batch-sheet-simple.html', 'batch-sheet-advanced.html'},
        )
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
        # Micronutrients and chelates have a tank: A, with calcium (FlahaX rule, #79).
        self.assertNotIn('Not in table', sheet)
        self.assertIn('<td>A</td><td>Mn EDTA</td>', sheet)


def _balanced():
    from flahax import balance_water_analysis

    well = {
        i: mg / tomato_advanced.GRAMS_PER_MOL[i] / 1000
        for i, mg in tomato_advanced.WELL_MG_L.items()
    }
    return balance_water_analysis(well, measured_ph=tomato_advanced.WELL_PH)


if __name__ == '__main__':
    unittest.main()
