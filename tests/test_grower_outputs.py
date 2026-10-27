# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Grower outputs shipped in the package: tank grouping, report, batch sheet and CLI (#79)."""

import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from flahax import (
    InjectionRatio,
    StockTank,
    TemperatureCelsius,
    VolumeLitres,
    catalogue_ph_reagents,
    default_compatibility_rules,
    final_solution_recipe,
    group_tanks,
    load_library,
    plan_fertilizer_workflow,
    plan_stocks,
    recommend,
    render_batch_sheet,
    render_report,
    summarize_batch,
)
from flahax.batch_cli import main as batch
from flahax.nutrient_acceptance import assess_incidental, assessed_limits
from flahax.ph_adjustment import _judge
from flahax.delivery_contracts import DeliveryError
from flahax.tank_grouping import (
    ANALOGUE,
    CLASS_RULES,
    MICRO_PHOSPHATE,
    WAIVED_RULES,
    _class_conflict,
    product_classes,
)

LIBRARY = load_library()
PRODUCTS = LIBRARY['salts']
BY_NAME = {p['name']: p for p in PRODUCTS}
FORMULAS = {f['name']: f['targets'] for f in LIBRARY['formulas']}
ACIDS = [
    dict(
        id=f'{f}-example',
        name=f'{f} example',
        source='EXAMPLE GRADE',
        revision='1',
        recordedAt='2026-10-22T00:00:00Z',
        chemicalFormula=f,
        massFraction=m,
        densityKgPerL=d,
    )
    for f, m, d in (('HNO3', 0.60, 1.37), ('H3PO4', 0.75, 1.58))
]
RO = dict(
    water_totals={},
    water_mass_kg=1000,
    water_analysis_id='RO',
    complete_analysis=True,
    carbon_boundary='closed',
    temperature_c=25,
    phases=[],
)
# Yara p. 65: the twelve "No" pairs.
PAGE_65_NO = {
    frozenset(pair)
    for pair in (
        ('CALCINIT', 'KRISTA-SOP'),
        ('CALCINIT', 'KRISTA-MKP'),
        ('CALCINIT', 'KRISTA-MAP'),
        ('CALCINIT', 'Phos. acid'),
        ('CALCINIT', 'AS'),
        ('CALCINIT', 'KRISTA-MgS'),
        ('KRISTA-MAG', 'KRISTA-MKP'),
        ('KRISTA-MAG', 'KRISTA-MAP'),
        ('KRISTA-MAG', 'Phos. acid'),
        ('KRISTA-MgS', 'KRISTA-MKP'),
        ('KRISTA-MgS', 'KRISTA-MAP'),
        ('KRISTA-MgS', 'Phos. acid'),
    )
}


def rows(*pairs):
    return [dict(id=BY_NAME[n]['id'], name=n, gramsPerLitre=g) for n, g in pairs]


def workflow(formula, products=ACIDS):
    return plan_fertilizer_workflow(
        PRODUCTS,
        FORMULAS[formula],
        {},
        5.8,
        final_volume=VolumeLitres(1000),
        equilibrium=RO,
        ph_adjustment=dict(
            products=products + catalogue_ph_reagents(), maximum_reagent_volume_litres=5
        ),
    )


class TankGroupingTests(unittest.TestCase):
    def test_composition_rules_reproduce_the_page_65_table(self):
        names = list(ANALOGUE)
        found = {
            frozenset({ANALOGUE[a], ANALOGUE[b]})
            for i, a in enumerate(names)
            for b in names[i + 1 :]
            if _class_conflict(
                product_classes(BY_NAME[a]),
                product_classes(BY_NAME[b]),
                CLASS_RULES + WAIVED_RULES,
            )
        }
        self.assertEqual(found, PAGE_65_NO)
        self.assertEqual(WAIVED_RULES, ())

    def test_micronutrients_join_calcium_in_tank_a_which_takes_no_acid(self):
        grouping = group_tanks(
            rows(
                ('Calcium Nitrate (ag grade)', 0.9),
                ('Magnesium Sulfate (Heptahydrate)', 0.5),
                ('Potassium Monobasic Phosphate', 0.1),
                ('Phosphoric Acid (75%)', 0.05),
                ('Zinc Sulfate (Monohydrate)', 0.001),
                ('Iron EDTA', 0.02),
            ),
            PRODUCTS,
        )
        tanks = {t.name: t for t in grouping.tanks}
        self.assertEqual(
            [p.name for p in tanks['A'].products],
            ['Calcium Nitrate (ag grade)', 'Iron EDTA'],
        )
        self.assertFalse(tanks['A'].acid_allowed)
        self.assertTrue(any('never acidify' in n.lower() for n in tanks['A'].notes))
        # Equipment cannot waive the magnesium/phosphate separation.
        self.assertEqual([t.name for t in grouping.tanks], ['A', 'B', 'C'])
        self.assertNotEqual(
            grouping.tank_of('Magnesium Sulfate (Heptahydrate)'),
            grouping.tank_of('Potassium Monobasic Phosphate'),
        )
        self.assertEqual(
            grouping.tank_of('Phosphoric Acid (75%)'),
            grouping.tank_of('Potassium Monobasic Phosphate'),
        )

    def test_tomato_reports_required_equipment_without_waivers(self):
        recipe = workflow('Tomato (Howard Resh)').recommendation
        grouping = group_tanks(recipe['salts'], PRODUCTS)
        self.assertEqual(len(grouping.tanks), 3)
        self.assertFalse(grouping.waived)
        self.assertNotEqual(
            grouping.tank_of('Magnesium Sulfate (Heptahydrate)'),
            grouping.tank_of('Potassium Monobasic Phosphate'),
        )
        with self.assertRaises(DeliveryError):
            group_tanks(recipe['salts'], PRODUCTS, max_tanks=2)

    def test_calcium_separations_still_hold(self):
        grouping = group_tanks(
            rows(
                ('Calcium Nitrate (ag grade)', 0.9),
                ('Magnesium Sulfate (Heptahydrate)', 0.5),
                ('Potassium Sulfate', 0.4),
                ('Potassium Monobasic Phosphate', 0.1),
                ('Potassium Dibasic Phosphate', 0.1),
            ),
            PRODUCTS,
        )
        calcium = grouping.tank_of('Calcium Nitrate (ag grade)')
        for tank in grouping.tanks:
            if tank.name == calcium:
                for p in tank.products:
                    classes = product_classes(BY_NAME[p.name])
                    self.assertFalse(
                        classes & {'sulfate', 'phosphate'} and 'calcium' not in classes, p.name
                    )

    def test_more_than_two_tanks_is_refused(self):
        rule = dict(
            schemaVersion='0.1',
            id='test-1',
            source='test',
            revision='1',
            recordedAt='2026-10-22T00:00:00Z',
            productIds=[
                BY_NAME['Potassium Sulfate']['id'],
                BY_NAME['Magnesium Sulfate (Heptahydrate)']['id'],
            ],
            constraint='separate',
            reason='test separation',
            temperatureMinC=0,
            temperatureMaxC=40,
        )
        with self.assertRaises(DeliveryError) as caught:
            group_tanks(
                rows(
                    ('Calcium Nitrate (ag grade)', 0.9),
                    ('Potassium Sulfate', 0.4),
                    ('Magnesium Sulfate (Heptahydrate)', 0.5),
                    ('Potassium Monobasic Phosphate', 0.1),
                ),
                PRODUCTS,
                rules=[rule],
                max_tanks=2,
            )
        self.assertEqual(caught.exception.code, 'too_many_tanks')
        self.assertIn('Magnesium Sulfate (Heptahydrate)', str(caught.exception))

    def test_without_calcium_micronutrients_still_keep_away_from_phosphate(self):
        grouping = group_tanks(
            rows(
                ('Potassium Nitrate', 0.5),
                ('Potassium Monobasic Phosphate', 0.2),
                ('Mn EDTA', 0.002),
                ('Iron EDTA', 0.02),
            ),
            PRODUCTS,
        )
        self.assertEqual(grouping.tank_of('Mn EDTA'), 'A')
        self.assertEqual(grouping.tank_of('Potassium Monobasic Phosphate'), 'B')
        self.assertIn(MICRO_PHOSPHATE, [why for *_, why in grouping.separations])

    def test_reagents_get_their_own_channel_and_user_rules_apply(self):
        rule = dict(
            schemaVersion='0.1',
            id='grower-1',
            source='my supplier',
            revision='1',
            recordedAt='2026-10-22T00:00:00Z',
            productIds=[BY_NAME['Iron EDTA']['id'], BY_NAME['Calcium Nitrate (ag grade)']['id']],
            constraint='separate',
            reason='supplier advice',
            temperatureMinC=0,
            temperatureMaxC=40,
        )
        grouping = group_tanks(
            rows(
                ('Calcium Nitrate (ag grade)', 0.9),
                ('Iron EDTA', 0.02),
                ('Potassium Hydroxide (45% solution)', 0.01),
            ),
            PRODUCTS,
            rules=[rule],
        )
        self.assertEqual(grouping.reagent_channel, ('Potassium Hydroxide (45% solution)',))
        self.assertNotEqual(grouping.tank_of('Iron EDTA'), 'A')

    def test_default_rules_feed_the_stock_planner(self):
        fit = recommend(
            PRODUCTS,
            {'Ca': 150, 'N_NO3': 150, 'P': 40, 'K': 200, 'S': 50},
            max_ammonium_fraction=0.10,
        )
        recipe = final_solution_recipe(fit, VolumeLitres(1000))
        used = [BY_NAME[s.name] for s in recipe.salts]
        rules = default_compatibility_rules(used)
        limits = [
            dict(
                schemaVersion='0.1',
                id=f'{p["id"]}-limit',
                source='test',
                revision='1',
                recordedAt='2026-10-22T00:00:00Z',
                productId=p['id'],
                maxGramsPerLitre=500,
                temperatureMinC=10,
                temperatureMaxC=30,
            )
            for p in used
        ]
        plan = plan_stocks(
            recipe,
            InjectionRatio(100),
            [StockTank(t, VolumeLitres(20)) for t in 'ABC'],
            rules,
            limits,
            TemperatureCelsius(20),
        )
        for tank in plan.tanks:
            members = [BY_NAME[s.name] for s in tank.salts]
            for i, a in enumerate(members):
                for b in members[i + 1 :]:
                    self.assertIsNone(_class_conflict(product_classes(a), product_classes(b)))


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tomato = summarize_batch(
            workflow('Tomato (Howard Resh)'), PRODUCTS, title='Tomato', water_label='RO'
        )
        cls.chilli = summarize_batch(
            workflow('Chilli (maximumyield)'), PRODUCTS, title='Chilli', water_label='RO'
        )

    def test_phase_block_keeps_unadjusted_recipe_and_quantity_outputs(self):
        s = self.tomato
        self.assertEqual(s['status'], 'blocked')
        self.assertIsNone(s['ph']['selected'])
        self.assertTrue(s['chemistry']['phase_assessment']['blocks'])
        self.assertFalse(s['chemistry']['phase_assessment']['mixing_approved'])
        weighed = {x['name'] for x in s['formulation']['salts']}
        in_tanks = {p['name'] for t in s['tanks']['tanks'] for p in t['products']}
        self.assertEqual(weighed, in_tanks)
        self.assertEqual([t['name'] for t in s['tanks']['tanks']], ['A', 'B', 'C'])
        self.assertFalse(s['tanks']['waived'])
        self.assertFalse(s['tanks']['mixture_approved'])
        self.assertIn('needs 3 tanks', render_report(s))
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
        with mock.patch.object(
            grower_report,
            'unreviewed_reason',
            side_effect=lambda r: 'x 1 mg/L' if r is first else None,
        ):
            wf = copy.copy(base)
            wf.stages = dict(base.stages, formulation=copy.copy(stage))
            wf.stages['formulation'].status, wf.stages['formulation'].message = (
                'requires_review',
                'x 1 mg/L',
            )
            s = summarize_batch(wf, PRODUCTS, title='T', water_label='RO')
        self.assertEqual(
            (s['stages']['formulation']['status'], s['stages']['formulation']['message']),
            ('calculated', None),
        )
        self.assertFalse([w for w in s['warnings'] if w.startswith('formulation:')])
        # first fit clean, weighed recipe has incidentals: review raised, overall status follows
        with mock.patch.object(
            grower_report,
            'unreviewed_reason',
            side_effect=lambda r: None if r is first else 'y 2 mg/L',
        ):
            wf = copy.copy(base)
            wf.stages = dict(base.stages, formulation=copy.copy(stage))
            wf.stages['formulation'].status, wf.stages['formulation'].message = 'calculated', None
            s = summarize_batch(wf, PRODUCTS, title='T', water_label='RO')
        self.assertEqual(
            (s['stages']['formulation']['status'], s['stages']['formulation']['message']),
            ('requires_review', 'y 2 mg/L'),
        )
        self.assertIn('formulation: y 2 mg/L', s['warnings'])
        self.assertEqual(s['status'], 'blocked')  # phase block survives incidental review
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
        self.assertEqual(s['chemistry']['state_basis'], 'unadjusted_recipe')
        rejected = s['chemistry']['rejected_candidate_diagnostics']
        self.assertEqual(rejected['state_basis'], 'rejected_candidate_not_weighed')
        self.assertIn('CaHPO4', [p for p, _ in rejected['phase_assessment']['blocking']])

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
        self.assertIn('never acidify', render_batch_sheet(self.tomato).lower())


class IncidentalAssessmentTests(unittest.TestCase):
    """One assessment of untargeted nutrients: recommend's ammonium allowance, with each source
    named (#92)."""

    TOMATO = 'Tomato (Howard Resh)'
    NITRIC = dict(products=[ACIDS[0]], maximum_reagent_volume_litres=5)

    @staticmethod
    def row(recommendation, symbol='N_NH4'):
        return next(r for r in recommendation['incidentalContributions'] if r['symbol'] == symbol)

    def test_first_fit_and_refit_rate_ammonium_alike(self):
        flow = plan_fertilizer_workflow(
            PRODUCTS,
            FORMULAS[self.TOMATO],
            {},
            5.8,
            final_volume=VolumeLitres(1000),
            equilibrium=RO,
            ph_adjustment=self.NITRIC,
        )
        first, refit = (
            self.row(flow.recommendation),
            self.row(
                next(
                    c.recommendation
                    for c in flow.stages['ph_adjustment'].value.candidates
                    if c.target is not None
                )
            ),
        )
        self.assertEqual(first['assessment'], 'requires_review')
        self.assertEqual(first['maximumPpm'], refit['maximumPpm'])
        self.assertIsNone(first['maximumPpm'])
        self.assertEqual(refit['assessment'], 'requires_review')
        self.assertEqual(
            [
                r['symbol']
                for r in flow.recommendation['incidentalContributions']
                if r['assessment'] == 'requires_review'
            ],
            ['N_NH4', 'Na'],
        )  # neither maximum was declared
        summary = summarize_batch(flow, PRODUCTS, title='Tomato', water_label='RO')
        self.assertIn('N_NH4', summary['stages']['formulation'].get('message') or '')

    def test_each_incidental_names_the_products_that_supply_it(self):
        flow = plan_fertilizer_workflow(
            PRODUCTS,
            FORMULAS[self.TOMATO],
            {},
            5.8,
            final_volume=VolumeLitres(1000),
            equilibrium=RO,
            ph_adjustment=self.NITRIC,
        )
        selected = {s['name'] for s in flow.recommendation['salts']}
        sources = {
            p['name']
            for p in PRODUCTS
            if p['name'] in selected and p['elements'].get('N_NH4', 0) > 0
        }
        self.assertTrue(sources)
        self.assertEqual(set(self.row(flow.recommendation)['source']), sources)
        summary = summarize_batch(flow, PRODUCTS, title='Tomato', water_label='RO')
        rows = {r['symbol']: r for r in summary['formulation']['rows']}
        self.assertIn('Calcium Nitrate (ag grade)', rows['N_NH4']['source'])
        self.assertNotIn('source', rows['Ca'])

    def test_explicit_ammonium_maximum_is_preserved_through_ph_candidates(self):
        limits = {'Na': 50, 'N_NH4': 14}
        flow = plan_fertilizer_workflow(
            PRODUCTS,
            FORMULAS[self.TOMATO],
            {},
            5.8,
            final_volume=VolumeLitres(1000),
            equilibrium=RO,
            ph_adjustment=self.NITRIC,
            maximum_concentrations=limits,
        )
        stage = flow.stages['ph_adjustment']
        self.assertIsNone(stage.value.selected)
        self.assertEqual(stage.status, 'blocked')
        chosen = next(c for c in stage.value.candidates if c.target is not None)
        self.assertEqual(self.row(chosen.recommendation)['assessment'], 'within_limit')
        for candidate in stage.value.candidates:
            self.assertNotIn('N_NH4', candidate.message or '')
        self.assertNotIn('N_NH4', stage.message or '')
        seen = []

        def spy(rows, maxima=None):
            seen.append(assess_incidental(rows, maxima))
            return seen[-1]

        with mock.patch('flahax.ph_adjustment.assess_incidental', spy):
            status, _, message, _ = _judge(chosen.recommendation, chosen.target, limits)
        self.assertNotIn(
            'N_NH4',
            [
                r['symbol']
                for r in seen[0]['incidentalContributions']
                if r['assessment'] == 'requires_review'
            ],
        )
        self.assertNotIn('N_NH4', message or '')
        reviewed = assess_incidental(
            chosen.recommendation['rows'], assessed_limits(limits, chosen.recommendation)
        )
        self.assertNotIn(
            'N_NH4',
            [
                r['symbol']
                for r in reviewed['incidentalContributions']
                if r['assessment'] == 'requires_review'
            ],
        )
        self.assertEqual(status, chosen.status)

    def test_declared_ammonium_maximum_wins_over_the_allowance(self):
        flow = plan_fertilizer_workflow(
            PRODUCTS, FORMULAS[self.TOMATO], {}, 5.8, maximum_concentrations={'N_NH4': 5}
        )
        row = self.row(flow.recommendation)
        self.assertEqual(row['maximumPpm'], 5)
        self.assertLessEqual(row['ppm'], 5 + 1e-9)
        self.assertIsNone(flow.recommendation['ammoniumLimit'])

    def test_recipes_do_not_depend_on_how_the_workflow_assesses(self):
        direct = recommend(PRODUCTS, FORMULAS[self.TOMATO], {})
        flow = plan_fertilizer_workflow(PRODUCTS, FORMULAS[self.TOMATO], {}, 5.8)
        self.assertEqual(flow.recommendation['salts'], direct['salts'])


class BatchCommandTests(unittest.TestCase):
    def run_batch(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = batch(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_writes_report_sheet_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'sheet'
            code, out, _ = self.run_batch(
                '--crop',
                'tomato (howard',
                '--water',
                'ro',
                '--acid',
                'HNO3:0.60:1.37',
                '--output',
                str(target),
            )
            self.assertEqual(code, 3)  # reports are written, but phase applicability blocks
            self.assertEqual(
                sorted(p.name for p in target.iterdir()),
                ['batch-sheet.html', 'report.html', 'summary.json'],
            )
            summary = json.loads((target / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['title'], 'Tomato (Howard Resh)')
            self.assertIn('Tank A', out)
            self.assertNotIn('Tank C', out)
            with self.assertRaises(SystemExit):  # never overwrites
                self.run_batch(
                    '--crop', 'tomato (howard', '--water', 'ro', '--output', str(target)
                )

    def test_review_reason_quotes_the_weighed_recipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'sheet'
            self.run_batch(
                '--crop',
                'tomato (howard',
                '--water',
                'ro',
                '--ph',
                '5.8',
                '--volume',
                '1000',
                '--limit',
                'N_NH4=14',
                '--acid',
                'HNO3:0.60:1.37:Nitric acid 60%',
                '--output',
                str(target),
            )
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
        code, _, err = self.run_batch(
            '--crop', 'tomato', '--water', 'ro', '--output', 'unused-dir'
        )
        self.assertEqual(code, 1)
        self.assertIn('Tomato Stage.1', err)

    def test_measured_water_is_closed_and_used_consistently(self):
        with tempfile.TemporaryDirectory() as tmp:
            water = Path(tmp) / 'well.json'
            # Shomar et al. (2024) station 104, as in examples/tomato_advanced.py.
            water.write_text(
                json.dumps(
                    dict(
                        id='station-104',
                        measured_ph=7.8,
                        mg_per_litre=dict(
                            Ca=244,
                            Mg=100.8,
                            K=44.2,
                            Na=680,
                            Cl=1280.4,
                            S=241.43,
                            N_NO3=3.474,
                            HCO3=196.9,
                        ),
                    )
                ),
                encoding='utf-8',
            )
            code, _, err = self.run_batch(
                '--formula',
                'Lettuce General (Howard Resh)',
                '--water',
                str(water),
                '--acid',
                'HNO3:0.60:1.37',
                '--output',
                str(Path(tmp) / 'out'),
            )
            self.assertIn(code, (0, 3), err)
            summary = json.loads((Path(tmp) / 'out/summary.json').read_text(encoding='utf-8'))
            self.assertEqual(summary['stages']['chemistry']['status'], 'requires_review')
            self.assertEqual(summary['water']['reconciliation'], 'assumed')
            self.assertEqual(summary['water']['analysis_mg_per_litre']['Cl'], 1280.4)
            self.assertAlmostEqual(summary['chemistry']['water_ph'], 7.8, places=6)
