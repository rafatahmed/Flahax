# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The grower journey end to end: ``batch`` plans the recipe and its pH reagent together."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flahax.batch_cli import BatchOptions, main, run_batch
from flahax.engine import load_library

NITRIC_65 = 'HNO3:0.65:1.39:Nitric acid 65%'


def tomato(**changes):
    options = dict(
        water='ro',
        formula='Tomato (Howard Resh)',
        acid=[NITRIC_65],
        tank_litres={'A': 100, 'B': 100, 'acid': 20},
        ratio=100,
    )
    return run_batch(BatchOptions(**(options | changes)))


def check_grower_outputs(case, summary, report, sheet):
    """Check observable output contracts against the reported calculation quantities."""
    from html import unescape
    import math
    import re

    retired = (
        'identity_inconsistent',
        'ionic_strength_outside_phosphate_fit',
        'missing_evidence',
        'assumed_density_floor',
        'No salt combination meets every target',
        'exceeds the maximum imbalance',
    )
    for output in (json.dumps(summary), report, sheet):
        for message in retired:
            case.assertNotIn(message, output)
    case.assertIn(summary['ec']['status'], ('estimated', 'range'))
    low, high = summary['ec']['ec25_range_ms_cm']
    case.assertTrue(math.isfinite(low) and 0 < low <= high and math.isfinite(high))
    case.assertIn('EC', sheet)
    if summary['tanks']['required_tanks'] > 2:
        case.assertIn('needs a third tank', ' '.join(summary['warnings']))
    else:
        case.assertLessEqual(len(summary['tanks']['tanks']), 2)
    case.assertTrue(summary['formulation']['salts'])

    def cells(html):
        return [
            [
                unescape(re.sub('<[^>]+>', '', cell)).strip()
                for cell in re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
            ]
            for row in re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S)
        ]

    nutrient_table = re.search(r'<table><caption>Nutrient fit,.*?</table>', report, re.S)
    case.assertIsNotNone(nutrient_table)
    report_rows = {r[0]: r for r in cells(nutrient_table.group(0)) if len(r) == 4}
    sheet_text = unescape(re.sub('<[^>]+>', ' ', sheet))
    misses = []
    for row in summary['formulation']['rows']:
        if row['target'] is None:
            continue
        symbol, target, actual = row['symbol'], row['target'], row['final']
        case.assertTrue(math.isfinite(actual), symbol)
        delta = actual - target
        tolerance = 1e-5 * target if target > 0 else 1e-6
        if target > 0:
            case.assertAlmostEqual(row['deltaPct'], 100 * delta / target, places=9)
        else:
            case.assertIsNone(row['deltaPct'])
        case.assertIn(symbol, report_rows)
        displayed = report_rows[symbol]
        case.assertAlmostEqual(float(displayed[1].replace(',', '')), target, delta=0.00051)
        case.assertAlmostEqual(float(displayed[2].replace(',', '')), actual, delta=0.00051)
        if abs(delta) > tolerance:
            misses.append(symbol)
            difference = re.search(r'([+-][0-9.eE+-]+) mg/L', displayed[3])
            case.assertIsNotNone(difference, (symbol, displayed))
            shown = float(difference.group(1))
            case.assertAlmostEqual(shown, delta, delta=abs(delta) * 0.00051)
            case.assertIn(difference.group(0), sheet_text)
    case.assertEqual(summary['formulation']['targets_met'], not misses)
    if misses:
        case.assertEqual(summary['status'], 'requires_review')
        case.assertIn('Review required', sheet)


class ReagentQualificationTests(unittest.TestCase):
    def test_only_declared_solvent_and_mass_caps_enter_the_joint_configuration(self):
        from flahax.batch_cli import joint_configuration, acid_record
        from flahax.ph_adjustment import catalogue_ph_reagents
        from flahax.delivery_contracts import DeliveryError

        unqualified = acid_record('HNO3:0.6:1.37')
        declared = acid_record('HNO3:0.65:1.39:aqueous:0.35')
        dry = next(r for r in catalogue_ph_reagents() if r['chemicalFormula'] == 'KHCO3')
        config = joint_configuration([], [dry, declared, unqualified], 100, 2, solid_cap=12)
        self.assertNotIn(unqualified['id'], config['reagent_solvent_fractions'])
        self.assertEqual(config['reagent_solvent_fractions'][declared['id']], 0.35)
        self.assertEqual(config['maximum_reagent_mass_g'][dry['id']], 12)
        self.assertNotIn(dry['id'], config['sequential_fallbacks'])
        for solvent in ('abc', 'nan', '-0.1', '0.9'):
            with self.assertRaises(DeliveryError):
                acid_record('HNO3:0.60:1.37:acid:' + solvent)
        for cap in (-1, True, float('nan')):
            with self.assertRaises(DeliveryError):
                joint_configuration([], [dry], 100, 2, solid_cap=cap)

    def test_undeclared_physical_form_cannot_bypass_a_liquid_volume_cap(self):
        from flahax.batch_cli import joint_configuration

        reagent = dict(id='unknown', chemicalFormula='KHCO3', massFraction=0.95)
        config = joint_configuration([], [reagent], 100, 2)
        self.assertNotIn('unknown', config['sequential_fallbacks'])
        self.assertNotIn('unknown', config['maximum_reagent_mass_g'])

    def test_sequential_solid_still_honours_a_declared_mass_cap(self):
        from flahax import catalogue_ph_reagents, plan_fertilizer_workflow, VolumeLitres
        from flahax.batch_cli import joint_configuration
        from tests.test_joint_workflow import RO

        pool = [next(p for p in load_library()['salts'] if p['name'] == 'Potassium Nitrate')]
        solid = next(p for p in catalogue_ph_reagents() if p['chemicalFormula'] == 'KHCO3')
        solid = dict(solid, solventMassFraction=None)
        for cap in (1, 100):
            joint = joint_configuration(pool, [solid], 1000, 5, cap)
            stage = plan_fertilizer_workflow(
                pool,
                {'K': 100},
                {},
                8,
                final_volume=VolumeLitres(1000),
                equilibrium=RO,
                ph_adjustment=dict(
                    products=[solid],
                    joint=joint,
                    correct_mixed_ph=True,
                    maximum_reagent_volume_litres=5,
                ),
            ).stages['ph_adjustment']
            if cap == 1:
                self.assertIsNone(stage.value.selected)
                self.assertEqual(stage.value.candidates[0].error_code, 'dose_limit_exceeded')
            else:
                self.assertEqual(stage.value.selected.joint_result['status'], 'sequential')
                self.assertTrue(1 < stage.value.selected.reagent_mass_g < cap)

    def test_joint_dry_candidate_obeys_its_mass_cap_without_a_density(self):
        from flahax import catalogue_ph_reagents, plan_fertilizer_workflow, VolumeLitres
        from flahax.batch_cli import joint_configuration
        from tests.test_joint_workflow import RO

        pool = [next(p for p in load_library()['salts'] if p['name'] == 'Potassium Nitrate')]
        solid = next(p for p in catalogue_ph_reagents() if p['chemicalFormula'] == 'KHCO3')
        for cap in (1000, 0):
            joint = joint_configuration(pool, [solid], 1000, 5, cap)
            adjustment = dict(
                products=[solid],
                joint=joint,
                correct_mixed_ph=True,
                maximum_reagent_volume_litres=5,
            )
            stage = plan_fertilizer_workflow(
                pool,
                {'K': 100},
                {},
                8,
                final_volume=VolumeLitres(1000),
                equilibrium=RO,
                ph_adjustment=adjustment,
            ).stages['ph_adjustment']
            if cap == 0:
                self.assertIsNone(stage.value.selected)
            else:
                candidate = stage.value.selected
                self.assertEqual(candidate.joint_result['reason'], 'residual_criteria_met')
                self.assertTrue(0 < candidate.reagent_mass_g <= cap)
                self.assertIsNone(candidate.reagent_volume_litres)
                self.assertAlmostEqual(candidate.target.ph, 8, places=4)

    def test_known_density_does_not_change_the_display_unit_of_a_dry_product(self):
        from flahax import (
            catalogue_ph_reagents,
            plan_fertilizer_workflow,
            summarize_batch,
            VolumeLitres,
        )
        from flahax.batch_cli import joint_configuration
        from tests.test_joint_workflow import RO

        pool = [next(p for p in load_library()['salts'] if p['name'] == 'Potassium Nitrate')]
        solid = next(p for p in catalogue_ph_reagents() if p['chemicalFormula'] == 'KHCO3')
        # Synthetic density to distinguish a computable volume from the unit used to weigh a solid.
        solid = dict(solid, densityKgPerL=1.2)
        config = joint_configuration(pool, [solid], 1000, 5, 100)
        flow = plan_fertilizer_workflow(
            pool,
            {'K': 100},
            {},
            8,
            final_volume=VolumeLitres(1000),
            equilibrium=RO,
            ph_adjustment=dict(
                products=[solid],
                joint=config,
                correct_mixed_ph=True,
                maximum_reagent_volume_litres=5,
            ),
        )
        summary = summarize_batch(flow, pool, title='Mass-unit fixture', water_label='RO')
        selected = summary['ph']['selected']
        self.assertGreater(selected['mass_g_per_batch'], 0)
        self.assertIsNone(selected['volume_ml_per_batch'])

    def test_measured_water_reference_reaches_the_target_in_an_explicit_joint_fit(self):
        from tests.catalogue_history import historical_catalogue
        from tests.test_grower_sheet import WELL

        with historical_catalogue(), tempfile.TemporaryDirectory() as folder:
            well = Path(folder) / 'well.json'
            well.write_text(json.dumps(WELL), encoding='utf-8')
            summary = tomato(
                water=str(well),
                water_share=8,
                acid=['HNO3:0.60:1.37:aqueous:0.40'],
                limit=[('Na', 68.97), ('Cl', 106.35), ('N_NH4', 14)],
            )
        chosen = summary['ph']['selected']
        self.assertIsNotNone(chosen, summary['ph']['message'])
        self.assertIn(
            chosen['joint']['status'],
            ('numerical_candidate', 'stationary_point', 'bounded_best_fit'),
        )
        self.assertAlmostEqual(chosen['joint']['finalPh'], 5.8, places=4)
        self.assertEqual(summary['status'], 'requires_review')

    def test_dry_reagent_uses_mass_on_a_real_batch_when_no_joint_candidate_verifies(self):
        summary = tomato(formula='Lettuce 2 (Howard Resh)', ph=6.5)
        chosen = summary['ph']['selected']
        self.assertIsNotNone(chosen, summary['ph']['message'])
        self.assertEqual(chosen['joint']['status'], 'sequential')
        self.assertIsNone(chosen['volume_ml_per_batch'])
        self.assertGreater(chosen['mass_g_per_batch'], 0)
        self.assertIn('mass cap', chosen['joint']['reason'])
        self.assertAlmostEqual(summary['chemistry']['final_ph'], 6.5, places=4)


class DirectionTests(unittest.TestCase):
    def test_missing_base_is_reported_without_trying_the_offered_acid(self):
        with (
            patch('flahax.batch_cli.catalogue_ph_reagents', return_value=[]),
            patch('flahax.joint_workflow.solve_joint_problem') as solver,
        ):
            ph = tomato()['ph']
        solver.assert_not_called()
        self.assertIsNone(ph['selected'])
        self.assertIn('none was offered: add a base', ph['message'])

    def test_only_reagents_in_the_needed_direction_enter_the_joint_solver(self):
        from flahax.delivery_contracts import DeliveryError

        def record(problem, *args, **kwargs):
            calls.append(problem.reagent.product_id)
            raise DeliveryError('joint_search_incomplete', 'direction probe')

        for target, direction in ((5.8, 'base'), (4.5, 'acid'), (4.8927367, 'none')):
            with self.subTest(target=target):
                calls = []
                with patch('flahax.joint_workflow.solve_joint_problem', side_effect=record):
                    ph = tomato(ph=target, acid=[NITRIC_65 + ':0.35'])['ph']
                self.assertEqual(ph['direction'], direction)
                expected = {
                    c['product_id'] for c in ph['candidates'] if c['direction'] == direction
                }
                self.assertTrue(set(calls) <= expected, calls)
                if direction == 'base':
                    self.assertIn('cmz1kohsol45q8z9phup00001', calls)
                    self.assertIn('HNO3-0.65-1.39', {c['product_id'] for c in ph['skipped']})
                elif direction == 'acid':
                    self.assertIn('HNO3-0.65-1.39', calls)
                self.assertEqual(bool(calls), direction != 'none')


class JointFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = tomato()

    def test_every_evaluated_reagent_carries_its_joint_fit_record(self):
        candidates = self.summary['ph']['candidates']
        self.assertTrue(candidates)
        for candidate in candidates:
            self.assertIn('joint', candidate, candidate['product'])
            self.assertTrue(candidate['joint']['status'], candidate['product'])

    def test_tomato_converges_with_verified_ph_charge_and_reported_misses(self):
        from flahax.grower_report import render_report, render_batch_sheet
        from flahax.requirement_fit import PH_TOLERANCE

        ph = self.summary['ph']
        self.assertEqual(ph['selected']['formula'], 'KOH')
        result = ph['selected']['joint']
        self.assertEqual(result['reason'], 'first_order_stationarity')
        self.assertLessEqual(result['stationarityResidual'], 1e-6)
        self.assertLessEqual(abs(result['finalPh'] - ph['target_ph']), PH_TOLERANCE)
        self.assertLessEqual(abs(result['chargeResidual']), result['chargeTolerance'])
        formulation = self.summary['formulation']
        self.assertEqual(self.summary['statuses']['numerical'], 'stationary_point')
        self.assertFalse(formulation['targets_met'])
        self.assertEqual(self.summary['status'], 'requires_review')
        phosphorus = next(row for row in formulation['rows'] if row['symbol'] == 'P')
        self.assertEqual(phosphorus['target'], 50)
        self.assertAlmostEqual(phosphorus['final'], 50.125, places=2)
        for render in (render_report, render_batch_sheet):
            self.assertIn('Nutrient targets met: no', render(self.summary))

    def test_the_selected_reagent_fit_never_claims_acceptance_or_global_optimality(self):
        joint = self.summary['ph']['selected']['joint']
        self.assertIs(joint['accepted'], False)
        self.assertIs(joint['globalOptimalityProven'], False)
        self.assertIn('chargeResidual', joint)


class ReportReviewTests(unittest.TestCase):
    def test_signed_difference_handles_a_tiny_shortfall_and_a_zero_target(self):
        from flahax.grower_report import _miss_difference

        self.assertEqual(_miss_difference(3, 2.99996445), '-0.00003555 mg/L (-0.001185%)')
        self.assertEqual(
            _miss_difference(0, 0.000002),
            '+0.000002 mg/L; relative difference undefined (zero target)',
        )

    def test_saved_summary_respects_declared_limits_and_ammonium_allowance(self):
        from flahax.grower_report import _review_reason

        summary = dict(
            formulation=dict(
                rows=[
                    dict(symbol='K', target=100, final=100),
                    dict(symbol='Cl', target=None, final=1),
                    dict(symbol='Na', target=None, final=1),
                    dict(symbol='N_NH4', target=None, final=1),
                ],
                ammonium_allowance={'mgPerL': 8},
            ),
            limits=[dict(symbol='Cl', balancingChangesDecision=False)],
            ph={'unadjusted_ph': 5.8},
            stages={},
            solubility=[],
            tanks={'mixture_approved': False},
        )
        self.assertEqual(
            _review_reason(summary),
            'All nutrient targets met. Sodium has no declared maximum. '
            'Mixed-stock solubility is unverified.',
        )

    def test_old_report_with_a_changed_water_limit_names_the_qualification(self):
        from flahax.grower_report import _review_reason, number

        summary = dict(
            formulation=dict(rows=[dict(symbol='N_NH4', target=None, final=1)]),
            limits=[
                dict(symbol='Cl', balancingChangesDecision=True, note='Check the water analysis.')
            ],
            ph=None,
            stages={
                'chemistry': {'status': 'requires_review', 'message': 'Water basis needs review.'}
            },
            solubility=[],
            tanks={'mixture_approved': True},
        )
        reason = _review_reason(summary)
        self.assertIn('Ammonium nitrogen has no declared maximum.', reason)
        self.assertIn('Water basis needs review.', reason)
        self.assertIn('Check the water analysis.', reason)
        self.assertNotIn('Mixed-stock', reason)
        self.assertEqual(number('unavailable'), 'unavailable')

    def test_on_target_cli_and_mix_sheet_do_not_prepare_a_reagent(self):
        from flahax.grower_sheet import render_mix_sheet

        with (
            tempfile.TemporaryDirectory() as temp,
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            folder = Path(temp) / 'report'
            code = main(
                [
                    '--water',
                    'ro',
                    '--formula',
                    'Tomato (Howard Resh)',
                    '--ph',
                    '4.8927367',
                    '--acid',
                    NITRIC_65,
                    '--output',
                    str(folder),
                ]
            )
            summary = json.loads((folder / 'summary.json').read_text())
        self.assertEqual(code, 0)
        self.assertIn('no reagent needed', out.getvalue())
        html = render_mix_sheet(summary, 2)
        self.assertNotIn('after acid', html)
        self.assertIn('No pH reagent is needed.', html)
        self.assertNotIn('Acid container: add', html)

    def test_status_reasons_and_tiny_signed_miss(self):
        from flahax.grower_report import render_batch_sheet, render_report
        from flahax.grower_sheet import render_mix_sheet

        cases = [
            (
                'Tomato Stage.3 - to plant maturity (Howard Resh)',
                'Calcium is 120',
                'below target',
                '+0.00003555 mg/L',
            ),
            (
                'Melons (Douglas Peckenpaugh)',
                'All nutrient targets met.',
                'Sodium has no declared maximum',
                None,
            ),
            ('Pepper (Howard Resh)', 'Sulfur is 139.5', 'below target', '-139.5 mg/L'),
        ]
        for name, lead, detail, delta in cases:
            with self.subTest(name=name):
                summary = tomato(formula=name)
                for render in (
                    render_report,
                    render_batch_sheet,
                    lambda s: render_mix_sheet(s, 2),
                ):
                    html = render(summary)
                    status = (
                        html.split('requires review</strong>', 1)[-1]
                        if render == render_report
                        else html.split('Review required.</b>', 1)[-1]
                    )
                    near = status[:650]
                    self.assertIn(lead, near)
                    self.assertIn(detail, near)
                    self.assertIn('Mixed-stock solubility is unverified', near)
                    if name.startswith('Pepper'):
                        self.assertIn('Iron EDDHA', near)
                    if delta:
                        self.assertIn(delta, html.split('Full calculation evidence')[0])


class CatalogueFitTests(unittest.TestCase):
    def check_formula(self, formula):
        from flahax.requirement_fit import PH_TOLERANCE, met

        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            out = Path(temp) / 'batch'
            code = main(
                [
                    '--formula',
                    formula,
                    '--water',
                    'ro',
                    '--volume',
                    '10000',
                    '--ratio',
                    '100',
                    '--ph',
                    '5.8',
                    '--acid',
                    NITRIC_65,
                    '--output',
                    str(out),
                ]
            )
            self.assertEqual(code, 0, formula)
            summary = json.loads((out / 'summary.json').read_text())
            check_grower_outputs(
                self,
                summary,
                (out / 'report.html').read_text(encoding='utf-8'),
                (out / 'batch-sheet.html').read_text(encoding='utf-8'),
            )
        # 10,000 L at 1:100 corresponds to 100 L of each stock tank.
        self.assertEqual(summary['tanks']['injection_ratio'], 100)
        self.assertEqual(summary['tanks']['temperature_c'], 25)
        self.assertEqual(summary['batch_litres'], 10000)
        ph = summary['ph']
        self.assertIsNotNone(ph['selected'], (formula, ph['message']))
        joint = ph['selected']['joint']
        self.assertIn(joint['reason'], ('residual_criteria_met', 'first_order_stationarity'))
        self.assertLessEqual(abs(joint['chargeResidual']), joint['chargeTolerance'])
        self.assertLessEqual(abs(joint['finalPh'] - ph['target_ph']), PH_TOLERANCE)
        self.assertLessEqual(joint['iterations'], 60)
        self.assertGreater(joint['evaluations'], 0)
        self.assertLess(joint['evaluations'], 10000, formula)
        if joint['reason'] == 'first_order_stationarity':
            self.assertLessEqual(joint['stationarityResidual'], 1e-6)
        rows = summary['formulation']['rows']
        if formula == 'Strawberry Drip Irrigation (schundler.com)':
            ammonium = next(r for r in rows if r['symbol'] == 'N_NH4')
            self.assertLessEqual(ammonium['final'], 8.0)
        targets_met = all(met(r['target'], r['final']) for r in rows if r['target'] is not None)
        self.assertEqual(summary['formulation']['targets_met'], targets_met)
        if not targets_met:
            self.assertEqual(summary['status'], 'requires_review')

    def test_all_catalogue_formulas(self):
        self.assertEqual(len(load_library()['formulas']), 13)
        for formula in load_library()['formulas']:
            with self.subTest(formula=formula['name']):
                self.check_formula(formula['name'])


class RemedyTests(unittest.TestCase):
    def test_confirmed_product_id_reruns_only_that_alternative(self):
        salts = load_library()['salts']
        kept = next(p for p in salts if p['name'] == 'Potassium Nitrate')
        extra = next(p for p in salts if p['name'] == 'Potassium Sulfate')
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(temp)
            products = root / 'products.json'
            targets = root / 'targets.json'
            products.write_text(json.dumps([kept]), encoding='utf-8')
            targets.write_text(json.dumps({'K': 100, 'S': 30}), encoding='utf-8')
            out = root / 'batch'
            main(
                [
                    '--water',
                    'ro',
                    '--products',
                    str(products),
                    '--targets',
                    str(targets),
                    '--output',
                    str(out),
                    '--confirmed-product',
                    extra['id'],
                    '--acid',
                    'HNO3:0.60:1.37:aqueous:0.40',
                ]
            )
            result = json.loads((out / 'summary.json').read_text())
        self.assertNotIn(extra['id'], [s['id'] for s in result['formulation']['salts']])
        remedies = result['remedies']
        self.assertEqual(remedies['evaluations'], 1)
        evaluated = [o for o in remedies['options'] if o['status'] != 'potential_remedy']
        self.assertEqual(len(evaluated), 1)
        option = evaluated[0]
        self.assertEqual(option['id'], 'catalogue:Potassium Sulfate')
        self.assertIn(option['status'], ('evaluated_candidate', 'evaluated_no_resolution'))
        self.assertTrue(option['calculation_id'])
        snapshot = json.loads(option['snapshot'])
        self.assertIn(extra['id'], [salt['id'] for salt in snapshot['inputs']['salts']])
        ph = snapshot['workflow']['stages']['ph_adjustment']['value']
        chosen = next(c for c in ph['candidates'] if c['product_id'] == ph['selected_product_id'])
        self.assertEqual(chosen['joint_result']['status'], 'numerical_candidate')

    def test_saved_session_preserves_confirmations_and_rejects_malformed_options(self):
        from flahax.mix_store import Store, bind_session
        from flahax.mix_cli import options_for
        from flahax.delivery_contracts import DeliveryError
        from tests.test_mix_cli import GOOD_SESSION

        salt = next(s for s in load_library()['salts'] if s['name'] == 'Potassium Sulfate')
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            session = GOOD_SESSION | {
                'confirmed_products': [salt['id']],
                'max_solid_reagent_grams': 30,
            }
            replay = options_for(store, bind_session(store, session))
            self.assertEqual(replay.confirmed_products, [salt['id']])
            self.assertEqual(replay.max_solid_reagent_grams, 30)
            for change in ({'confirmed_products': 'bad'}, {'max_solid_reagent_grams': -1}):
                with self.assertRaises(DeliveryError):
                    options_for(store, GOOD_SESSION | change)
        for ids in ('not a list', ['missing'], [salt['id'], salt['id']]):
            from flahax.batch_cli import left_out_products

            with self.assertRaises(DeliveryError):
                left_out_products(load_library(), [], ids)

    def test_a_restricted_product_list_lists_the_catalogue_products_left_out(self):
        library = load_library()
        kept = [s for s in library['salts'] if s['name'] != 'Potassium Sulfate']
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'products.json'
            path.write_text(json.dumps(kept), encoding='utf-8')
            summary = tomato(products=str(path))
        options = {o['id']: o for o in summary['remedies']['options']}
        self.assertIn('catalogue:Potassium Sulfate', options)
        self.assertEqual(options['catalogue:Potassium Sulfate']['status'], 'potential_remedy')
        self.assertIn('availability', options['catalogue:Potassium Sulfate']['next_action'])

    def test_the_whole_catalogue_leaves_nothing_to_offer(self):
        self.assertEqual(tomato()['remedies']['options'], [])


class CurrentEdtaAcceptanceTests(unittest.TestCase):
    def test_packaged_lettuce_edta_batch_reports_phase_and_stock_qualifications(self):
        edta = {'Iron EDTA', 'Mn EDTA', 'Zn EDTA', 'Copper EDTA'}
        products = [
            product
            for product in load_library()['salts']
            if product.get('role') != 'ph_reagent'
            and (
                not {'Fe', 'Mn', 'Zn', 'Cu'} & set(product['elements']) or product['name'] in edta
            )
        ]
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(temp)
            available = root / 'products.json'
            available.write_text(json.dumps(products), encoding='utf-8')
            out = root / 'batch'
            code = main(
                [
                    '--formula',
                    'Lettuce 2 (Howard Resh)',
                    '--water',
                    'ro',
                    '--volume',
                    '10000',
                    '--ratio',
                    '100',
                    '--ph',
                    '5.8',
                    '--products',
                    str(available),
                    '--output',
                    str(out),
                ]
            )
            self.assertEqual(code, 0)
            summary = json.loads((out / 'summary.json').read_text())
            check_grower_outputs(
                self,
                summary,
                (out / 'report.html').read_text(encoding='utf-8'),
                (out / 'batch-sheet.html').read_text(encoding='utf-8'),
            )
        self.assertIn('MnHPO4', [r['phase'] for r in summary['chemistry']['information']])
        self.assertNotIn('MnHPO4', [r['phase'] for r in summary['chemistry']['risk']])
        manganese = [r for r in summary['solubility'] if r['product'] == 'Mn EDTA']
        self.assertTrue(manganese)
        for row in manganese:
            self.assertEqual(row['status'], 'ok')
        self.assertFalse(summary['tanks']['mixture_approved'])
        self.assertEqual(summary['status'], 'requires_review')


class SavedCucumberAcceptanceTests(unittest.TestCase):
    def test_original_saved_inputs_replay_through_mix(self):
        from flahax.mix_cli import main as mix
        from flahax.mix_store import Store, migrate_session

        fixtures = Path(__file__).parent / 'fixtures' / 'grower'
        original = json.loads((fixtures / 'cucumber-session.json').read_text())
        certificate = json.loads((fixtures / 'hno3-65.json').read_text())
        frozen = json.dumps(original, sort_keys=True)
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp) / 'home')
            store.save('acids', 'hno3-65', certificate)
            # Replay the saved grower view, then request full output for the same inputs.
            for depth in (original['depth'], 3):
                with self.subTest(depth=depth):
                    migrated = migrate_session(store, original | {'depth': depth})
                    store.save('sessions', 'cucumber', migrated)
                    out = Path(temp) / f'output-{depth}'
                    code = mix(
                        ['sessions/cucumber', '--plain', '--output', str(out)],
                        store=store,
                        ask=lambda prompt: self.fail('Saved-session replay asked: ' + prompt),
                        say=lambda *args: None,
                    )
                    self.assertEqual(code, 0)
                    summary = json.loads((out / 'summary.json').read_text())
                    sheet = (out / 'batch-sheet.html').read_text(encoding='utf-8')
                    self.assertIn('Cucumber (Howard Resh)', sheet)
                    self.assertIn('Review required', sheet)
                    self.assertIn(summary['ph']['selected']['product'], sheet)
                    self.assertEqual(summary['title'], 'Cucumber (Howard Resh)')
                    # The 100 L reagent tank limits the shared 1:100 irrigation run.
                    self.assertEqual(summary['batch_litres'], 10000)
                    self.assertEqual(summary['ph']['target_ph'], 5.9)
                    self.assertAlmostEqual(summary['chemistry']['final_ph'], 5.9, delta=1e-4)
                    joint = summary['ph']['selected']['joint']
                    self.assertIn(
                        joint['reason'], ('residual_criteria_met', 'first_order_stationarity')
                    )
                    self.assertLessEqual(abs(joint['chargeResidual']), joint['chargeTolerance'])
                    self.assertEqual(migrated['spec'], original['spec'])
                    self.assertEqual(migrated['acids'], ['hno3-65'])
                    if depth == 3:
                        report = (out / 'report.html').read_text(encoding='utf-8')
                        check_grower_outputs(self, summary, report, sheet)
        self.assertEqual(json.dumps(original, sort_keys=True), frozen)


class ConsoleTests(unittest.TestCase):
    def test_a_solid_reagent_prints_its_mass_not_a_missing_volume(self):
        out = io.StringIO()
        # Exercise the console with a selected solid independently of catalogue ranking.
        summary = dict(
            title='solid test',
            status='requires_review',
            tanks={'tanks': []},
            batch_litres=1000,
            ph={
                'direction': 'base',
                'selected': {
                    'product': 'Potassium Bicarbonate',
                    'volume_ml_per_batch': None,
                    'mass_g_per_batch': 12.5,
                },
            },
        )
        with (
            tempfile.TemporaryDirectory() as folder,
            contextlib.redirect_stdout(out),
            patch('flahax.batch_cli.build', return_value=({}, summary)),
        ):
            code = main(
                [
                    '--water',
                    'ro',
                    '--formula',
                    'Tomato (Howard Resh)',
                    '--acid',
                    NITRIC_65,
                    '--output',
                    str(Path(folder) / 'sheet'),
                ]
            )
        text = out.getvalue()
        self.assertEqual(code, 0, text)
        self.assertNotIn('Not available', text)
        self.assertRegex(text, r'pH: [\d.,]+ ?g Potassium Bicarbonate per 1000 L')


if __name__ == '__main__':
    unittest.main()
