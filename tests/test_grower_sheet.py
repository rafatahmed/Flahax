# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.grower_sheet."""

import json
from pathlib import Path
import tempfile
import unittest

from flahax.batch_cli import BatchOptions, run_batch
from flahax.grower_report import render_report
from flahax.grower_sheet import agronomist_rows, render_mix_sheet
from tests.test_growers_page import WELL

NITRIC = ['HNO3:0.60:1.37:Nitric acid 60%']
TANKS = {'A': 20, 'B': 20, 'acid': 20}


def tomato_ro():
    return run_batch(
        BatchOptions(water='ro', formula='Tomato (Howard Resh)', acid=NITRIC, tank_litres=TANKS)
    )


class SheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ro = tomato_ro()
        cls.tmp = tempfile.TemporaryDirectory()
        well = Path(cls.tmp.name) / 'well.json'
        well.write_text(json.dumps(WELL), encoding='utf-8')
        cls.well = run_batch(
            BatchOptions(
                water=str(well),
                formula='Tomato (Howard Resh)',
                water_share=8,
                acid=NITRIC,
                limit=[('Na', 68.97), ('Cl', 106.35)],
                volume=1000,
            )
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_sheet_weighs_for_prepared_volume(self):
        a = next(t for t in self.ro['tanks']['tanks'] if t['name'] == 'A')
        calcium = next(p for p in a['products'] if p['name'] == 'Calcium Nitrate (ag grade)')
        self.assertAlmostEqual(calcium['gramsPerBatch'], 1860.7, delta=0.05)
        sheet = render_mix_sheet(self.ro, 1)
        self.assertIn('prepare <b>20 L</b> in your 20 L tank', sheet)
        self.assertIn('1,860.7 g', sheet)
        self.assertIn('Never add acid to tank A.', sheet)

    def test_acid_card_container_volume(self):
        sheet = render_mix_sheet(self.ro, 1)
        self.assertIn('46.8 mL per 1,000 L of irrigation, on its own injector', sheet)
        self.assertIn('add <b>93.7 mL</b> to water and make up to <b>20 L</b>', sheet)
        self.assertIn('Add acid to water, never water to acid.', sheet)

    def test_agronomist_table_station_104(self):
        rows = {r['nutrient']: r for r in agronomist_rows(self.well)}
        ca = rows['Ca']
        self.assertEqual(ca['target'], 180)
        self.assertAlmostEqual(ca['water'], 19.52, places=2)
        self.assertAlmostEqual(ca['required'], 160.48, places=2)
        self.assertAlmostEqual(ca['final'], 178.27, places=2)
        self.assertAlmostEqual(ca['diff_mg_l'], -1.73, places=2)
        self.assertAlmostEqual(ca['diff_pct'], -0.96, places=2)
        self.assertAlmostEqual(ca['achieved'], ca['final'] - ca['water'], places=12)
        self.assertIsNone(rows['Na']['target'])
        self.assertAlmostEqual(rows['Na']['final'], 55.08, places=2)
        listed = [r['target'] is None for r in agronomist_rows(self.well)]
        self.assertEqual(listed, sorted(listed))  # formula nutrients first, then the others

    def test_depth_one_has_no_nutrient_table(self):
        self.assertNotIn('Nutrients, mg/L', render_mix_sheet(self.ro, 1))
        two = render_mix_sheet(self.ro, 2)
        self.assertIn('Nutrients, mg/L', two)
        self.assertIn(
            'Calcium Nitrate (ag grade), not in formula', two
        )  # untargeted ammonium names its source
        self.assertIn('after fertilizers', two)

    def test_depth_three_names_the_waived_rule(self):
        self.assertIn('owner decision 2026-10-22', render_report(self.ro))

    def test_blocked_sheet_offers_nothing_to_weigh(self):
        blocked = dict(self.ro, status='blocked')
        sheet = render_mix_sheet(blocked, 1)
        self.assertIn('Do not mix.', sheet)
        self.assertNotIn('class="tick"', sheet)
        self.assertNotIn('Acid container', sheet)


if __name__ == '__main__':
    unittest.main()
