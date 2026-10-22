"""Grower outputs shipped in the package: tank grouping, report, batch sheet and CLI (#79)."""
import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

from flahax import (InjectionRatio, StockTank, TemperatureCelsius, VolumeLitres, catalogue_ph_reagents,
                    default_compatibility_rules, final_solution_recipe, group_tanks, load_library,
                    plan_fertilizer_workflow, plan_stocks, recommend, render_batch_sheet, render_report,
                    summarize_batch)
from flahax.batch_cli import main as batch
from flahax.tank_grouping import ANALOGUE, MICRO_PHOSPHATE, _class_conflict, product_classes

LIBRARY = load_library()
PRODUCTS = LIBRARY['salts']
BY_NAME = {p['name']: p for p in PRODUCTS}
FORMULAS = {f['name']: f['targets'] for f in LIBRARY['formulas']}
ACIDS = [dict(id=f'{f}-example', name=f'{f} example', source='EXAMPLE GRADE', revision='1',
              recordedAt='2026-10-22T00:00:00Z', chemicalFormula=f, massFraction=m, densityKgPerL=d)
         for f, m, d in (('HNO3', .60, 1.37), ('H3PO4', .75, 1.58))]
RO = dict(water_totals={}, water_mass_kg=1000, water_analysis_id='RO', complete_analysis=True,
          carbon_boundary='closed', temperature_c=25, phases=[])
# Yara p. 65: the twelve "No" pairs.
PAGE_65_NO = {frozenset(pair) for pair in (
    ('CALCINIT', 'KRISTA-SOP'), ('CALCINIT', 'KRISTA-MKP'), ('CALCINIT', 'KRISTA-MAP'), ('CALCINIT', 'Phos. acid'),
    ('CALCINIT', 'AS'), ('CALCINIT', 'KRISTA-MgS'), ('KRISTA-MAG', 'KRISTA-MKP'), ('KRISTA-MAG', 'KRISTA-MAP'),
    ('KRISTA-MAG', 'Phos. acid'), ('KRISTA-MgS', 'KRISTA-MKP'), ('KRISTA-MgS', 'KRISTA-MAP'),
    ('KRISTA-MgS', 'Phos. acid'))}


def rows(*pairs):
    return [dict(id=BY_NAME[n]['id'], name=n, gramsPerLitre=g) for n, g in pairs]


def workflow(formula, products=ACIDS):
    return plan_fertilizer_workflow(PRODUCTS, FORMULAS[formula], {}, 5.8, final_volume=VolumeLitres(1000),
                                    equilibrium=RO, ph_adjustment=dict(products=products + catalogue_ph_reagents(),
                                                                       maximum_reagent_volume_litres=5))


class TankGroupingTests(unittest.TestCase):
    def test_composition_rules_reproduce_the_page_65_table(self):
        names = list(ANALOGUE)
        found = {frozenset({ANALOGUE[a], ANALOGUE[b]}) for i, a in enumerate(names) for b in names[i + 1:]
                 if _class_conflict(product_classes(BY_NAME[a]), product_classes(BY_NAME[b]))}
        self.assertEqual(found, PAGE_65_NO)

    def test_micronutrients_join_calcium_in_tank_a_which_takes_no_acid(self):
        grouping = group_tanks(rows(('Calcium Nitrate (ag grade)', .9), ('Magnesium Sulfate (Heptahydrate)', .5),
                                    ('Potassium Monobasic Phosphate', .1), ('Phosphoric Acid (75%)', .05),
                                    ('Zinc Sulfate (Monohydrate)', .001), ('Iron EDTA', .02)), PRODUCTS)
        tanks = {t.name: t for t in grouping.tanks}
        self.assertEqual([p.name for p in tanks['A'].products],
                         ['Calcium Nitrate (ag grade)', 'Zinc Sulfate (Monohydrate)', 'Iron EDTA'])
        self.assertFalse(tanks['A'].acid_allowed)
        self.assertTrue(any('never acidify' in n for n in tanks['A'].notes))
        # Magnesium sulfate and the phosphates cannot share (p. 65), so three tanks.
        self.assertEqual(len(grouping.tanks), 3)
        self.assertNotEqual(grouping.tank_of('Magnesium Sulfate (Heptahydrate)'),
                            grouping.tank_of('Potassium Monobasic Phosphate'))
        self.assertEqual(grouping.tank_of('Phosphoric Acid (75%)'), grouping.tank_of('Potassium Monobasic Phosphate'))

    def test_without_calcium_micronutrients_still_keep_away_from_phosphate(self):
        grouping = group_tanks(rows(('Potassium Nitrate', .5), ('Potassium Monobasic Phosphate', .2),
                                    ('Mn EDTA', .002), ('Iron EDTA', .02)), PRODUCTS)
        self.assertEqual(grouping.tank_of('Mn EDTA'), 'A')
        self.assertEqual(grouping.tank_of('Potassium Monobasic Phosphate'), 'B')
        self.assertIn(MICRO_PHOSPHATE, [why for *_, why in grouping.separations])

    def test_reagents_get_their_own_channel_and_user_rules_apply(self):
        rule = dict(schemaVersion='0.1', id='grower-1', source='my supplier', revision='1',
                    recordedAt='2026-10-22T00:00:00Z', productIds=[BY_NAME['Iron EDTA']['id'],
                                                                   BY_NAME['Calcium Nitrate (ag grade)']['id']],
                    constraint='separate', reason='supplier advice', temperatureMinC=0, temperatureMaxC=40)
        grouping = group_tanks(rows(('Calcium Nitrate (ag grade)', .9), ('Iron EDTA', .02),
                                    ('Potassium Hydroxide (45% solution)', .01)), PRODUCTS, rules=[rule])
        self.assertEqual(grouping.reagent_channel, ('Potassium Hydroxide (45% solution)',))
        self.assertNotEqual(grouping.tank_of('Iron EDTA'), 'A')

    def test_default_rules_feed_the_stock_planner(self):
        fit = recommend(PRODUCTS, {'Ca': 150, 'N_NO3': 150, 'P': 40, 'K': 200, 'S': 50})
        recipe = final_solution_recipe(fit, VolumeLitres(1000))
        used = [BY_NAME[s.name] for s in recipe.salts]
        rules = default_compatibility_rules(used)
        limits = [dict(schemaVersion='0.1', id=f'{p["id"]}-limit', source='test', revision='1',
                       recordedAt='2026-10-22T00:00:00Z', productId=p['id'], maxGramsPerLitre=500,
                       temperatureMinC=10, temperatureMaxC=30) for p in used]
        plan = plan_stocks(recipe, InjectionRatio(100), [StockTank(t, VolumeLitres(20)) for t in 'ABC'],
                           rules, limits, TemperatureCelsius(20))
        for tank in plan.tanks:
            members = [BY_NAME[s.name] for s in tank.salts]
            for i, a in enumerate(members):
                for b in members[i + 1:]:
                    self.assertIsNone(_class_conflict(product_classes(a), product_classes(b)))


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tomato = summarize_batch(workflow('Tomato (Howard Resh)'), PRODUCTS, title='Tomato', water_label='RO')
        cls.chilli = summarize_batch(workflow('Chilli (maximumyield)'), PRODUCTS, title='Chilli', water_label='RO')

    def test_selected_reagent_recipe_is_the_one_to_weigh(self):
        s = self.tomato
        self.assertEqual(s['status'], 'requires_review')
        chosen = s['ph']['selected']
        self.assertGreater(chosen['volume_ml_per_batch'], 0)
        self.assertAlmostEqual(s['chemistry']['final_ph'], 5.8, places=6)
        weighed = {x['name'] for x in s['formulation']['salts']}
        in_tanks = {p['name'] for t in s['tanks']['tanks'] for p in t['products']}
        self.assertEqual(weighed, in_tanks)
        self.assertTrue(s['chemistry']['review'])
        json.dumps(s, allow_nan=False)

    def test_review_is_judged_on_the_weighed_recipe_both_ways(self):
        import copy
        from unittest import mock
        from flahax import grower_report
        base = workflow('Tomato (Howard Resh)')
        first = base.recommendation
        stage = base.stages['formulation']
        # first fit had incidentals, weighed recipe has none: review drops
        with mock.patch.object(grower_report, 'unreviewed_reason', side_effect=lambda r: 'x 1 mg/L' if r is first else None):
            wf = copy.copy(base)
            wf.stages = dict(base.stages, formulation=copy.copy(stage))
            wf.stages['formulation'].status, wf.stages['formulation'].message = 'requires_review', 'x 1 mg/L'
            s = summarize_batch(wf, PRODUCTS, title='T', water_label='RO')
        self.assertEqual((s['stages']['formulation']['status'], s['stages']['formulation']['message']), ('calculated', None))
        self.assertFalse([w for w in s['warnings'] if w.startswith('formulation:')])
        # first fit clean, weighed recipe has incidentals: review raised, overall status follows
        with mock.patch.object(grower_report, 'unreviewed_reason', side_effect=lambda r: None if r is first else 'y 2 mg/L'):
            wf = copy.copy(base)
            wf.stages = dict(base.stages, formulation=copy.copy(stage))
            wf.stages['formulation'].status, wf.stages['formulation'].message = 'calculated', None
            s = summarize_batch(wf, PRODUCTS, title='T', water_label='RO')
        self.assertEqual((s['stages']['formulation']['status'], s['stages']['formulation']['message']),
                         ('requires_review', 'y 2 mg/L'))
        self.assertIn('formulation: y 2 mg/L', s['warnings'])
        self.assertEqual(s['status'], 'requires_review')
        # a block is never downgraded
        with mock.patch.object(grower_report, 'unreviewed_reason', return_value='z 3 mg/L'):
            wf = copy.copy(base)
            wf.stages = dict(base.stages, formulation=copy.copy(stage))
            wf.stages['formulation'].status, wf.stages['formulation'].message = 'blocked', 'nope'
            s = summarize_batch(wf, PRODUCTS, title='T', water_label='RO')
        self.assertEqual(s['stages']['formulation']['status'], 'blocked')

    def test_blocked_plan_shows_the_reason_and_the_acid_free_recipe(self):
        s = self.chilli
        self.assertEqual(s['status'], 'blocked')
        self.assertIsNone(s['ph']['selected'])
        self.assertNotIn('Phosphoric Acid (75%)', [x['name'] for x in s['formulation']['salts']])
        self.assertIn('CaHPO4', [b['phase'] for b in s['chemistry']['blocking']])

    def test_html_is_complete_and_offline(self):
        for s in (self.tomato, self.chilli):
            for html in (render_report(s), render_batch_sheet(s)):
                self.assertTrue(html.startswith('<!doctype html>'))
                self.assertNotIn('<script', html)
                self.assertIsNone(re.search(r'(src|href)="https?:|url\(https?:|@import', html))
                self.assertNotIn('>None<', html)
                for salt in s['formulation']['salts']:
                    self.assertIn(salt['name'], html)
        self.assertIn('<svg', render_report(self.tomato))
        self.assertIn('never acidify', render_batch_sheet(self.tomato))


class BatchCommandTests(unittest.TestCase):
    def run_batch(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = batch(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_writes_report_sheet_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'sheet'
            code, out, _ = self.run_batch('--crop', 'tomato (howard', '--water', 'ro', '--acid', 'HNO3:0.60:1.37',
                                          '--output', str(target))
            self.assertEqual(code, 0)
            self.assertEqual(sorted(p.name for p in target.iterdir()), ['batch-sheet.html', 'report.html', 'summary.json'])
            summary = json.loads((target / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['title'], 'Tomato (Howard Resh)')
            self.assertIn('Tank A', out)
            with self.assertRaises(SystemExit):     # never overwrites
                self.run_batch('--crop', 'tomato (howard', '--water', 'ro', '--output', str(target))

    def test_review_reason_quotes_the_weighed_recipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'sheet'
            self.run_batch('--crop', 'tomato (howard', '--water', 'ro', '--ph', '5.8', '--volume', '1000',
                           '--acid', 'HNO3:0.60:1.37:Nitric acid 60%', '--output', str(target))
            summary = json.loads((target / 'summary.json').read_text(encoding='utf-8'))
        message = summary['stages']['formulation']['message']
        final = {r['symbol']: r['final'] for r in summary['formulation']['rows']}
        for text in (message, *(w for w in summary['warnings'] if w.startswith('formulation:'))):
            quoted = re.findall(r'(\w+) ([\d.]+) mg/L', text)
            self.assertTrue(quoted, text)
            self.assertNotIn('10.4', text)
            for symbol, value in quoted:
                self.assertEqual(float(value), float(f'{final[symbol]:.3g}'), f'{symbol}: {text}')

    def test_ambiguous_crop_lists_the_choices(self):
        code, _, err = self.run_batch('--crop', 'tomato', '--water', 'ro', '--output', 'unused-dir')
        self.assertEqual(code, 1)
        self.assertIn('Tomato Stage.1', err)

    def test_measured_water_is_closed_and_used_consistently(self):
        with tempfile.TemporaryDirectory() as tmp:
            water = Path(tmp) / 'well.json'
            # Shomar et al. (2024) station 104, as in examples/tomato_advanced.py.
            water.write_text(json.dumps(dict(id='station-104', measured_ph=7.8, mg_per_litre=dict(
                Ca=244, Mg=100.8, K=44.2, Na=680, Cl=1280.4, S=241.43, N_NO3=3.474, HCO3=196.9))), encoding='utf-8')
            code, _, err = self.run_batch('--formula', 'Lettuce General (Howard Resh)', '--water', str(water),
                                          '--acid', 'HNO3:0.60:1.37', '--output', str(Path(tmp) / 'out'))
            self.assertIn(code, (0, 3), err)
            summary = json.loads((Path(tmp) / 'out/summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['stages']['chemistry']['status'], 'requires_review')
            self.assertEqual(summary['water']['reconciliation'], 'assumed')
            self.assertEqual(summary['water']['analysis_mg_per_litre']['Cl'], 1280.4)
            self.assertAlmostEqual(summary['chemistry']['water_ph'], 7.8, places=6)
