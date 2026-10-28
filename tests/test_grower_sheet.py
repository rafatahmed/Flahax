# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.grower_sheet."""

import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest

from flahax.batch_cli import BatchOptions, run_batch
from flahax.grower_report import dose_number, grams, render_batch_sheet, render_report
from flahax.canonical_result import seal_summary
from flahax.mix_results import _nutrient_rows
from flahax.grower_sheet import agronomist_rows, render_mix_sheet
from tests.test_growers_page import WELL

NITRIC = ['HNO3:0.60:1.37:Nitric acid 60%']
TANKS = {'A': 20, 'B': 20, 'acid': 20}


def tomato_ro():
    return run_batch(
        BatchOptions(
            water='ro',
            formula='Tomato (Howard Resh)',
            acid=NITRIC,
            tank_litres=TANKS,
            limit=[('N_NH4', 14)],
        )
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
                limit=[('Na', 68.97), ('Cl', 106.35), ('N_NH4', 14)],
                volume=1000,
            )
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_sheet_weighs_for_prepared_volume(self):
        a = next(t for t in self.ro['tanks']['tanks'] if t['name'] == 'A')
        calcium = next(p for p in a['products'] if p['name'] == 'Calcium Nitrate (ag grade)')
        recipe = next(p for p in self.ro['formulation']['salts'] if p['name'] == calcium['name'])
        self.assertAlmostEqual(
            calcium['gramsPerBatch'],
            recipe['gramsPerLitre'] * self.ro['batch_litres'],
            places=10,
        )
        sheet = render_mix_sheet(self.ro, 1)
        self.assertEqual(self.ro['status'], 'blocked')
        self.assertIn('not to be prepared', sheet)
        self.assertIn(grams(calcium['gramsPerBatch']), sheet)
        self.assertIn('Never add acid to tank A.', sheet)

    def test_blocked_reagent_is_not_a_preparation_instruction(self):
        sheet = render_mix_sheet(self.ro, 1)
        self.assertNotIn('Acid container:', sheet)
        self.assertNotIn('on its own injector.</p>', sheet)
        self.assertIn('Do not mix.', sheet)

    def test_agronomist_table_station_104(self):
        rows = {r['nutrient']: r for r in agronomist_rows(self.well)}
        ca = rows['Ca']
        self.assertEqual(ca['target'], 180)
        self.assertAlmostEqual(ca['water'], 19.52, places=2)
        self.assertAlmostEqual(ca['required'], 160.48, places=2)
        reported = next(r for r in self.well['formulation']['rows'] if r['symbol'] == 'Ca')
        self.assertEqual(ca['final'], reported['final'])
        self.assertEqual(ca['diff_mg_l'], reported['final'] - 180)
        self.assertEqual(ca['diff_pct'], 100 * (reported['final'] - 180) / 180)
        self.assertAlmostEqual(ca['achieved'], ca['final'] - ca['water'], places=12)
        self.assertIsNone(rows['Na']['target'])
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

    def test_report_preserves_condition_qualified_rules(self):
        report = render_report(self.ro)
        self.assertNotIn('owner decision 2026-10-22', report)
        self.assertFalse(self.ro['tanks']['waived'])
        self.assertIn('Pairs kept apart', report)

    def test_blocked_sheet_offers_nothing_to_weigh(self):
        blocked = dict(self.ro, status='blocked')
        sheet = render_mix_sheet(blocked, 1)
        self.assertIn('Do not mix.', sheet)
        self.assertNotIn('class="tick"', sheet)
        self.assertNotIn('Acid container', sheet)

    def test_zero_target_and_undefined_percentage_in_all_views(self):
        for final in (0, 1):
            summary = copy.deepcopy(self.ro)
            summary.pop('export_identity', None)
            summary.pop('calculation_identity', None)
            row = next(r for r in summary['formulation']['rows'] if r['symbol'] == 'K')
            row.update(target=0, final=final, deltaPct=None)
            summary['formulation']['unmet'] = [dict(row, reason='hard_zero')] if final else []
            summary = seal_summary(summary)
            actual = next(r for r in agronomist_rows(summary) if r['nutrient'] == 'K')
            self.assertEqual(actual['target'], 0)
            self.assertEqual(actual['diff_mg_l'], final)
            self.assertIsNone(actual['diff_pct'])
            self.assertIn('undefined (zero target)', render_report(summary))
            self.assertIn('undefined (zero target)', render_mix_sheet(summary, 2))
            self.assertIn('undefined (zero target)', str(_nutrient_rows(summary)))

    def test_offline_evidence_roundtrips_with_escaped_text_and_partial_ec(self):
        summary = copy.deepcopy(self.ro)
        summary.pop('export_identity', None)
        summary.pop('calculation_identity', None)
        summary['title'] = '</pre><script>alert("x")</script>'
        summary['ec'].update(
            status='partial',
            known_species_subtotal_ms_cm=0.123456789012345,
            ec25_ms_cm=None,
            ec25_range_ms_cm=None,
        )
        summary = seal_summary(summary)
        for render in (
            render_report,
            render_batch_sheet,
            lambda s: render_mix_sheet(s, 1),
            lambda s: render_mix_sheet(s, 2),
            lambda s: render_mix_sheet(s, 3),
        ):
            page = render(summary)
            parsed = EvidenceParser()
            parsed.feed(page)
            self.assertEqual(json.loads(''.join(parsed.payload)), json.loads(json.dumps(summary)))
            self.assertFalse(parsed.active)
            self.assertIn('not a total EC estimate, bound or midpoint', page)
            self.assertIn('EC uncertainty interval: not quantified', page)
            self.assertIn('physical validation is not established', page)
            self.assertNotIn('Direct batch: dissolve', page)
            self.assertNotIn('class="tick"', page)

    def test_blocked_selected_reagent_remains_diagnostic(self):
        summary = copy.deepcopy(self.ro)
        summary.pop('export_identity', None)
        summary.pop('calculation_identity', None)
        summary['ph']['selected'] = dict(
            direction='acid',
            product='Synthetic reagent',
            formula='HNO3',
            volume_ml_per_batch=0.001,
            mass_g_per_batch=0.002,
        )
        from flahax.grower_report import _reagent_line

        self.assertIn('diagnostic only', _reagent_line(summary))
        self.assertNotIn('Add ', _reagent_line(summary))

    def test_positive_doses_do_not_disappear(self):
        for value in (1e-15, 0.00001, 0.01, 1, 1000):
            self.assertGreater(float(dose_number(value, 1).replace(',', '')), 0)


class QualificationTests(unittest.TestCase):
    def test_missing_and_zero_doses_remain_distinct(self):
        self.assertEqual(dose_number(None), 'Not available')
        self.assertEqual(dose_number(0), '0')
        self.assertEqual(dose_number(-1), '-1')

    def test_ec_applicability_states_and_real_range_only(self):
        from flahax.grower_report import qualification_lines

        self.assertIn('not evaluated', ' '.join(qualification_lines({'ec': None})))
        estimated = dict(
            status='estimated',
            ec25_ms_cm=0,
            ec25_range_ms_cm=[0, 0.2],
            uncertainty_components={'model': {'status': 'not_validated'}},
        )
        lines = ' '.join(qualification_lines({'ec': estimated}))
        self.assertIn('calculated estimate: 0 mS/cm', lines)
        self.assertIn('Reported EC range: [0, 0.2]', lines)
        self.assertIn('not_validated', lines)
        for status in ('partial', 'not_supported'):
            estimated['status'] = status
            lines = ' '.join(qualification_lines({'ec': estimated}))
            self.assertNotIn('calculated estimate', lines)

    def test_independent_nutrient_arithmetic_and_incidental_distinction(self):
        # Independent fixture: 2 mg/L water + 3 fertilizer + 4 reagent = 9 final.
        summary = {
            'water': {'analysis_mg_per_litre': {'K': 2}},
            'formulation': {
                'rows': [
                    {'symbol': 'K', 'target': 10, 'final': 2 + 3 + 4},
                    {'symbol': 'Na', 'target': None, 'final': 1},
                    {'symbol': 'Cl', 'target': None, 'final': 0},
                    {'symbol': 'P', 'target': 0, 'final': 0},
                ]
            },
        }
        rows = {r['nutrient']: r for r in agronomist_rows(summary)}
        self.assertEqual(rows['K']['required'], 8)
        self.assertEqual(rows['K']['achieved'], 7)
        self.assertEqual(rows['K']['diff_mg_l'], -1)
        self.assertEqual(rows['K']['diff_pct'], -10)
        self.assertIsNone(rows['Na']['target'])
        self.assertNotIn('Cl', rows)
        self.assertEqual(rows['P']['target'], 0)


class EvidenceParser(HTMLParser):
    """Read the inert evidence element and reject active dependencies."""

    def __init__(self):
        super().__init__()
        self.inside = False
        self.payload = []
        self.active = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'pre' and attrs.get('id') == 'flahax-result-data':
            self.inside = True
        if tag in {'script', 'iframe', 'object'} or any(
            k in {'src', 'href'} or k.startswith('on') for k in attrs
        ):
            self.active.append((tag, attrs))

    def handle_endtag(self, tag):
        if tag == 'pre':
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.payload.append(data)


if __name__ == '__main__':
    unittest.main()
