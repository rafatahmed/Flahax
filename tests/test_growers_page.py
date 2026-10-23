# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The growers page's worked example (#80) must match what flahax batch produces."""

import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

from flahax.batch_cli import main as batch

PAGE = Path(__file__).resolve().parents[1] / 'docs/site/growers.md'
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
        code = batch(['--formula', 'Tomato (Howard Resh)', *argv, '--output', str(out)])
    return code, json.loads((out / 'summary.json').read_text(encoding='utf-8'))


class GrowersPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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

    def test_the_sheet_table_matches_a_fresh_run(self):
        code, summary = self.eight
        self.assertEqual((code, summary['status']), (0, 'requires_review'))
        produced = {
            (t['name'], p['name']): (
                round(p['gramsPerBatch'], 1),
                round(p['stockGramsPerLitre'], 2),
            )
            for t in summary['tanks']['tanks']
            for p in t['products']
        }
        rows = re.findall(r'^\| ([A-C]) \| ([^|]+?) \| ([\d.]+) \| ([\d.]+) \|$', self.page, re.M)
        documented = {
            (tank, name): (float(grams), float(stock)) for tank, name, grams, stock in rows
        }
        self.assertEqual(documented, produced)

    def test_the_quoted_numbers_match(self):
        _, s = self.eight
        self.assertFalse(s['formulation']['unmet'])
        self.assertEqual(round(s['ph']['selected']['volume_ml_per_batch'], 1), 1.5)
        self.assertEqual(round(s['chemistry']['mixed_ph'], 2), 5.84)
        limits = {row['symbol']: round(row['analyticalPpm'], 1) for row in s['limits']}
        self.assertEqual(limits, {'Cl': 102.4, 'Na': 55.1})
        self.assertEqual(round(s['ec']['ec25_ms_cm'], 1), 2.6)
        nh4 = next(r['final'] for r in s['formulation']['rows'] if r['symbol'] == 'N_NH4')
        self.assertEqual(round(nh4, 1), 9.2)
        for text in (
            '1.5 mL',
            '5.84',
            'Cl is 102.4 mg/L and Na 55.1 mg/L',
            '9.2 mg/L NH4-N',
            '2.6 mS/cm',
        ):
            self.assertIn(text, self.page)

    def test_nine_percent_is_blocked_and_ro_needs_acid(self):
        code, nine = self.nine
        self.assertEqual((code, nine['status']), (3, 'blocked'))
        self.assertEqual(
            round(next(r['analyticalPpm'] for r in nine['limits'] if r['symbol'] == 'Cl'), 1),
            115.2,
        )
        self.assertIn('115.2 mg/L chloride', self.page)
        _, ro = self.ro
        self.assertEqual(round(ro['ph']['selected']['volume_ml_per_batch']), 47)
        self.assertIn('47 mL of nitric', self.page)
        code, bare = self.ro_no_acid
        self.assertEqual(
            (code, bare['status'], round(bare['ph']['unadjusted_ph'], 1)), (3, 'blocked', 6.9)
        )
