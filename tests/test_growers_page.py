# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The worked example in "A batch from files" (#80, was the growers page) matches flahax batch."""

import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

from flahax.batch_cli import main as batch
from tests.catalogue_history import historical_catalogue

PAGE = Path(__file__).resolve().parents[1] / 'docs/site/agronomist/batch-command.md'
WELL = dict(
    id='station-104',
    measured_ph=7.8,
    mg_per_litre=dict(
        Ca=244, Mg=100.8, K=44.2, Na=680, Cl=1280.4, S=241.43, N_NO3=3.474, HCO3=196.9
    ),
)
ACID = 'HNO3:0.60:1.37:Nitric acid 60%'


def run(tmp, *argv):
    out = Path(tmp) / str(abs(hash(argv)))
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        code = batch(
            [
                '--formula',
                'Tomato (Howard Resh)',
                '--limit',
                'N_NH4=14',
                *argv,
                '--output',
                str(out),
            ]
        )
    return code, json.loads((out / 'summary.json').read_text(encoding='utf-8'))


class GrowersPageTests(unittest.TestCase):
    # Owner catalogue: re-enable in PR 3 (G24)
    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(historical_catalogue())
        cls.page = PAGE.read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as tmp:
            water = Path(tmp) / 'well.json'
            water.write_text(json.dumps(WELL), encoding='utf-8')
            limits = ('--acid', ACID, '--limit', 'Na=68.97', '--limit', 'Cl=106.35')
            cls.eight = run(tmp, '--water', str(water), '--water-share', '8', *limits)
            cls.nine = run(tmp, '--water', str(water), '--water-share', '9', *limits)
            cls.ro = run(tmp, '--water', 'ro', '--acid', ACID)
            cls.ro_no_acid = run(tmp, '--water', 'ro')

    def test_the_water_file_on_the_page_is_the_one_tested(self):
        block = re.search(r'```json\n(\{"id": "station-104".*?)```', self.page, re.S).group(1)
        self.assertEqual(json.loads(block), WELL)

    # Owner catalogue: re-enable in PR 3 (G24)
    def test_historical_table_is_not_current_delivery_authorization(self):
        self.enterContext(historical_catalogue())
        code, summary = self.eight
        self.assertEqual((code, summary['status']), (3, 'blocked'))
        self.assertIn('Historical 0.6.0 figures', self.page)
        self.assertIn('not current mixing instructions', self.page)
        # Current equipment keeps the magnesium/phosphate separation.
        self.assertEqual(len(summary['tanks']['tanks']), 3)
        tanks = {p['name']: t['name'] for t in summary['tanks']['tanks'] for p in t['products']}
        self.assertNotEqual(
            tanks['Magnesium Sulfate (Heptahydrate)'], tanks['Potassium Monobasic Phosphate']
        )

    # Owner catalogue: re-enable in PR 3 (G24)
    def test_current_eight_percent_output_preserves_limits_and_blocks_reagent(self):
        self.enterContext(historical_catalogue())
        _, s = self.eight
        self.assertFalse(s['formulation']['unmet'])
        self.assertIsNone(s['ph']['selected'])
        self.assertEqual(s['ph']['status'], 'blocked')
        self.assertTrue(s['ph']['candidates'])
        self.assertTrue(all(c['status'] == 'rejected' for c in s['ph']['candidates']))
        self.assertIn('Hydroxylapatite', s['ph']['candidates'][0]['message'])
        limits = {row['symbol']: row['analyticalPpm'] for row in s['limits']}
        # Product chloride may add to the measured water, up to the explicit cap.
        self.assertGreaterEqual(limits['Cl'], WELL['mg_per_litre']['Cl'] * 0.08)
        self.assertLessEqual(limits['Cl'], 106.35)
        self.assertLessEqual(limits['Na'], 68.97)
        self.assertLessEqual(limits['N_NH4'], 14)
        self.assertEqual(s['ec']['status'], 'not_supported')
        self.assertEqual(s['ec']['reason'], 'ionic_strength_outside_phosphate_fit')
        self.assertIsNone(s['ec']['ec25_ms_cm'])

    # Owner catalogue: re-enable in PR 3 (G24)
    def test_nine_percent_and_ro_cases_remain_blocked(self):
        self.enterContext(historical_catalogue())
        code, nine = self.nine
        self.assertEqual((code, nine['status']), (3, 'blocked'))
        self.assertEqual(
            round(next(r['analyticalPpm'] for r in nine['limits'] if r['symbol'] == 'Cl'), 1),
            115.2,
        )
        self.assertIn('115.2 mg/L chloride', self.page)
        for code, result in (self.ro, self.ro_no_acid):
            self.assertEqual((code, result['status']), (3, 'blocked'))
            self.assertIsNone(result['ph']['selected'])
            self.assertGreater(result['ph']['unadjusted_ph'], result['ph']['target_ph'])
