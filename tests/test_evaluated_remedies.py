# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent scoped remedy witnesses and honest unresolved
outcomes.
"""

import copy
import json
from fractions import Fraction
from types import SimpleNamespace as Record
import unittest
from unittest.mock import patch

from flahax import (
    plan_fertilizer_workflow,
    load_library,
    VolumeLitres,
    InjectionRatio,
    TemperatureCelsius,
    StockTank,
)
from flahax.delivery_contracts import DeliveryError
from flahax import evaluated_remedies
from flahax.evaluated_remedies import (
    _candidate_score,
    _joint_start_retry,
    available_product_search,
)
from flahax.batch_summary import summarize_batch
from flahax.report_html import render_report
from tests.test_joint_workflow import configuration
from tests.test_ph_adjustment import ACIDS, RO
from tests.test_stock_planning import record
from tests.test_stock_assignments import synthetic_model


def product(name, **elements):
    return dict(id=name, name=name, elements=elements)


def catalogue(products, **extra):
    return dict(
        id='bundle', kind='catalogue', available=True, changes={'products': products}, **extra
    )


class EvaluatedRemediesTests(unittest.TestCase):
    def run_plan(self, options=(), **kw):
        args = dict(
            salts=[product('K', K=10)],
            targets={'K': 100, 'Ca': 100, 'Mg': 50},
            water={},
            target_ph=5.5,
            final_volume=VolumeLitres(10),
            remedy_options=options,
        )
        return plan_fertilizer_workflow(**(args | kw))

    def test_available_product_search_combines_products_only_if_targets_miss(self):
        option = available_product_search([product('Ca', Ca=10), product('Mg', Mg=10)])
        result = self.run_plan([option])
        self.assertEqual(result.remedies['evaluations'], 1)
        candidate = json.loads(result.remedies['options'][0]['snapshot'])
        fit = candidate['workflow']['recommendation']
        self.assertTrue(fit['feasible'])
        self.assertEqual(set(fit['saltIds']), {'K', 'Ca', 'Mg'})
        self.assertFalse(result.recommendation['feasible'])

        matched = self.run_plan([option], targets={'K': 100})
        self.assertTrue(matched.recommendation['feasible'])
        self.assertEqual(matched.remedies['evaluations'], 0)
        self.assertEqual(matched.remedies['options'], [])

    def test_each_scenario_runs_through_the_planner_that_is_passed_in(self):
        requests = []
        real = evaluated_remedies.evaluate_remedies

        def spy_plan(**request):
            requests.append(request)
            return plan_fertilizer_workflow(**request)

        def with_spy(*args, plan, **kwargs):
            self.assertIs(plan, plan_fertilizer_workflow)  # the workflow passes itself
            return real(*args, plan=spy_plan, **kwargs)

        option = available_product_search([product('Ca', Ca=10), product('Mg', Mg=10)])
        with patch('flahax.fertilizer_workflow.evaluate_remedies', with_spy):
            result = self.run_plan([option])
        self.assertEqual(result.remedies['evaluations'], 1)
        self.assertEqual(len(requests), 1)
        self.assertEqual({s['id'] for s in requests[0]['salts']}, {'K', 'Ca', 'Mg'})

    def test_multi_product_bundle_is_evaluated_without_adoption(self):
        option = catalogue([product('Ca', Ca=10), product('Mg', Mg=10)])
        before = copy.deepcopy(option)
        w = self.run_plan([option])
        r = w.remedies['options'][0]
        self.assertEqual(r['status'], 'evaluated_candidate')
        self.assertFalse(w.recommendation['feasible'])
        candidate = json.loads(r['snapshot'])['workflow']['recommendation']
        self.assertTrue(candidate['feasible'])
        oracle = {'K': Fraction(1), 'Ca': Fraction(1), 'Mg': Fraction(1, 2)}
        for salt in candidate['salts']:
            self.assertAlmostEqual(salt['gramsPerLitre'], float(oracle[salt['id']]), places=12)
        self.assertTrue({'nutrient:Ca', 'nutrient:Mg'} <= set(r['resolved_requirements']))
        self.assertTrue(r['remaining_requirements'])
        self.assertEqual(option, before)
        self.assertEqual(w.remedies['evaluations'], 1)
        self.assertEqual(w.canonical_result.to_dict()['workflow']['remedies'], w.remedies)

    def test_expanded_miss_ranks_source_retries_and_preserves_budget_and_ceiling(self):
        option = available_product_search(
            [product('A-contaminated', Ca=10, Na=5), product('Z-clean', Ca=10)]
        )
        result = self.run_plan(
            [option], maximum_concentrations={'Na': 0}, max_remedy_evaluations=2
        )
        remedies = result.remedies
        self.assertEqual(remedies['evaluations'], 2)
        self.assertEqual(remedies['status'], 'search_incomplete')
        tried = remedies['options'][1]
        self.assertEqual(tried['source_product_id'], 'Z-clean')
        candidate = json.loads(tried['snapshot'])
        self.assertEqual(candidate['inputs']['maximum_concentrations'], {'Na': 0})
        self.assertEqual(set(candidate['workflow']['recommendation']['saltIds']), {'K', 'Z-clean'})
        self.assertEqual(remedies['options'][2]['status'], 'not_evaluated')

    def test_invalid_expanded_pool_cannot_hide_a_verified_source(self):
        option = available_product_search([product('invalid', Ca=-1), product('valid', Ca=10)])

        def evaluate(**request):
            if any(record['id'] == 'invalid' for record in request['salts']):
                raise DeliveryError('invalid_assay', 'Synthetic workflow failure')
            return plan_fertilizer_workflow(**request)

        with patch('flahax.fertilizer_workflow.plan_fertilizer_workflow', side_effect=evaluate):
            result = self.run_plan([option], targets={'K': 100, 'Ca': 100})
        remedies = result.remedies
        expanded, valid, invalid = remedies['options']
        self.assertEqual(expanded['status'], 'evaluation_failed')
        self.assertEqual(valid['source_product_id'], 'valid')
        self.assertEqual(invalid['status'], 'evaluation_failed')
        self.assertEqual(remedies['best_verified_candidate_id'], valid['id'])
        self.assertEqual(remedies['status'], 'search_incomplete')

    def test_joint_start_from_original_mix_uses_the_same_budget_and_limits(self):
        nitrate = next(p for p in load_library()['salts'] if p['formula'] == 'KNO3')
        extra = dict(nitrate, id='extra-nitrate', name='Potassium Nitrate (extra)')
        acid = ACIDS[0]
        config = configuration([nitrate], acid, loss_tolerance=2.0)
        config['additional_product_steps'] = {extra['id']: 1e-4}
        args = dict(
            salts=[nitrate],
            targets={'K': 100, 'Ca': 100},
            water={'Na': 0.002 * 22.989769 * 1000},
            target_ph=5.8,
            final_volume=VolumeLitres(1000),
            maximum_concentrations={'Na': 50, 'N_NO3': 200},
            equilibrium=RO | dict(water_totals={'Na+': 0.002, 'CO3-2': 0.002}, water_mass_kg=1000),
            ph_adjustment=dict(products=[acid], maximum_reagent_volume_litres=5, joint=config),
        )
        option = available_product_search([extra])
        limited = self.run_plan([option], **args, max_remedy_evaluations=1)
        self.assertEqual(limited.remedies['evaluations'], 1)
        self.assertEqual(limited.remedies['options'][1]['status'], 'not_evaluated')

        result = self.run_plan([option], **args, max_remedy_evaluations=2)
        self.assertEqual(result.remedies['evaluations'], 2)
        expanded, retried = result.remedies['options']
        self.assertIn('snapshot', expanded)
        self.assertEqual(retried['joint_start_reagent_id'], acid['id'])
        original = result.stages['ph_adjustment'].value.selected.joint_result
        repeat = json.loads(retried['snapshot'])['inputs']
        point = repeat['ph_adjustment']['joint']['starting_points'][acid['id']]
        self.assertGreater(point['reagent_dose'], 0)
        self.assertEqual(point['reagent_dose'], original['reagentDose'])
        self.assertEqual(point['fertilizer_doses'], original['fertilizerDoses'])
        self.assertEqual(repeat['maximum_concentrations'], args['maximum_concentrations'])
        self.assertNotIn('starting_points', config)

    def test_joint_start_requires_a_distinct_qualified_seed(self):
        recipe = dict(rows=[], salts=[], feasible=False)
        result = dict(status='numerical_candidate', fertilizerDoses={'K': 1}, reagentDose=0.1)
        chosen = Record(
            joint_result=result, product_id='acid', direction='acid', recommendation=recipe
        )
        ph = Record(status='requires_review', value=Record(selected=chosen))
        baseline = Record(stages={'ph_adjustment': ph}, recommendation=recipe)
        expanded_ph = Record(direction='acid', unadjusted_recommendation=recipe)
        expanded = Record(
            stages={'ph_adjustment': Record(value=expanded_ph)}, recommendation=recipe
        )
        joint = {}
        adjust = dict(joint=joint, correct_mixed_ph=True)
        request = dict(ph_adjustment=adjust, maximum_concentrations=None)
        option = dict(id='pool')
        retry, _ = _joint_start_retry(
            option, request, baseline, expanded, {'pool:joint-start:acid'}
        )
        self.assertEqual(retry['id'], 'pool:joint-start:acid:retry')
        joint['starting_points'] = {'acid': dict(fertilizer_doses={'K': 1}, reagent_dose=0.1)}
        self.assertIsNone(_joint_start_retry(option, request, baseline, expanded, set()))
        joint.clear()
        expanded_ph.direction = 'base'
        self.assertIsNone(_joint_start_retry(option, request, baseline, expanded, set()))
        expanded_ph.direction = 'acid'
        joint['sequential_fallbacks'] = {'acid': 'sample'}
        self.assertIsNone(_joint_start_retry(option, request, baseline, expanded, set()))
        joint.clear()
        expanded.stages['ph_adjustment'].value = None
        self.assertIsNone(_joint_start_retry(option, request, baseline, expanded, set()))
        expanded.stages['ph_adjustment'].value = expanded_ph
        for changes in (
            {'fertilizerDoses': []},
            {'reagentDose': float('nan')},
            {'status': 'rejected'},
        ):
            with self.subTest(changes=changes):
                chosen.joint_result = result | changes
                self.assertIsNone(_joint_start_retry(option, request, baseline, expanded, set()))
        chosen.joint_result = result
        recipe['requirementConflicts'] = ['Ca']
        self.assertIsNone(_joint_start_retry(option, request, baseline, expanded, set()))
        recipe.pop('requirementConflicts')
        ph.value.selected = None
        self.assertIsNone(_joint_start_retry(option, request, baseline, expanded, set()))

    def test_blocked_rounded_preparation_is_not_ranked(self):
        recipe = dict(rows=[], salts=[], feasible=True)
        stages = {'volumetric_stocks': Record(status='blocked')}
        request = dict(ph_adjustment=None, maximum_concentrations=None, volumetric_stocks={})
        self.assertIsNone(
            _candidate_score(Record(stages=stages, recommendation=recipe), request, ())
        )

    def test_tolerance_and_declared_preferences_rank_verified_options_even_after_failure(self):
        def bundle(id_, *products):
            return catalogue(list(products)) | {'id': id_}

        options = [
            bundle('a-more-sodium', product('mixed', Ca=10, Na=5)),
            bundle('z-no-sodium', product('clean', Ca=10)),
            bundle('miss', product('other', Mg=10)),
            dict(
                id='failed',
                kind='treatment',
                evidence={'source': 'synthetic', 'revision': '1'},
                changes={'water': {'Ca': -1}, 'equilibrium': {}},
            ),
            available_product_search([product('other', Mg=10)], preferences=('incidental_mg_l',)),
        ]
        for declared in (options, options[::-1]):
            result = self.run_plan(
                declared, targets={'K': 100, 'Ca': 100}, maximum_concentrations={'Na': 100}
            )
            self.assertEqual(
                result.remedies['ranked_candidate_ids'][:2], ['z-no-sodium', 'a-more-sodium']
            )
            self.assertEqual(
                result.remedies['verified_candidate_ids'], ['z-no-sodium', 'a-more-sodium']
            )
            self.assertIn(
                'z-no-sodium', {r['id'] for r in result.remedies['options'] if 'snapshot' in r}
            )

    def test_unavailable_missing_and_budget_are_not_success(self):
        option = catalogue([product('Ca', Ca=10)])
        option['available'] = False
        w = self.run_plan([option])
        self.assertEqual(w.remedies['options'][0]['status'], 'potential_remedy')
        self.assertEqual(w.remedies['evaluations'], 0)
        self.assertEqual(w.remedies['status'], 'search_incomplete')
        w = self.run_plan([catalogue([product('Ca', Ca=10)])], max_remedy_evaluations=0)
        self.assertEqual(w.remedies['options'][0]['status'], 'not_evaluated')
        self.assertEqual(w.remedies['status'], 'search_incomplete')

    def test_budget_counts_only_attempts_and_retains_individual_outcomes(self):
        pending = catalogue([product('Ca', Ca=10)])
        pending.update(id='pending', available=False)
        first = catalogue([product('Ca', Ca=10)])
        last = catalogue([product('Mg', Mg=10)])
        last['id'] = 'last'
        w = self.run_plan([pending, first, last], max_remedy_evaluations=1)
        self.assertEqual(w.remedies['evaluations'], 1)
        self.assertEqual(
            [r['status'] for r in w.remedies['options']],
            ['potential_remedy', 'evaluated_candidate', 'not_evaluated'],
        )
        self.assertEqual(w.remedies['status'], 'search_incomplete')
        self.assertNotIn('snapshot', w.remedies['options'][-1])

    def test_impossibility_scope_and_limits_are_preserved(self):
        w = self.run_plan(
            [catalogue([product('Ca', Ca=10, Na=5)])], maximum_concentrations={'Na': 0}
        )
        r = w.remedies['options'][0]
        self.assertNotIn('nutrient:Ca', r['resolved_requirements'])
        candidate = json.loads(r['snapshot'])
        self.assertEqual(candidate['inputs']['maximum_concentrations'], {'Na': 0})
        self.assertTrue(
            any(x['status'] == 'proven_infeasible' for x in r['remaining_requirements'])
        )
        w = self.run_plan([catalogue([product('Ca', Ca=10)])], maximum_concentrations={'Ca': 1})
        self.assertTrue(
            any('conflicting target' in r['next_action'] for r in w.remedies['requirements'])
        )

    def test_treatment_needs_evidence_and_rechecks_supplied_analysis(self):
        option = dict(id='treated', kind='treatment', changes={'water': {}, 'equilibrium': {}})
        self.assertEqual(
            self.run_plan([option]).remedies['options'][0]['status'], 'potential_remedy'
        )
        option['evidence'] = dict(source='synthetic analysis', revision='1')
        w = self.run_plan([option], water={'Ca': 200})
        r = w.remedies['options'][0]
        self.assertNotEqual(r['status'], 'potential_remedy')
        self.assertEqual(json.loads(r['snapshot'])['inputs']['water'], {})
        self.assertTrue(any(x['id'] == 'stage:chemistry' for x in r['remaining_requirements']))
        self.assertEqual(w.water, {'Ca': 200})

    def test_equipment_is_rerun_and_model_qualification_is_separate(self):
        stocks = dict(
            injection_ratio=InjectionRatio(100),
            tanks=[StockTank('A', VolumeLitres(0.01))],
            temperature=TemperatureCelsius(20),
            compatibility_rules=[],
            solubility_limits=[
                record(
                    'limit',
                    productId='K',
                    maxGramsPerLitre=200,
                    temperatureMinC=10,
                    temperatureMaxC=30,
                )
            ],
        )
        option = dict(
            id='larger',
            kind='equipment',
            changes={'stocks': dict(stocks, tanks=[StockTank('A', VolumeLitres(1))])},
        )
        w = self.run_plan([option], targets={'K': 10}, stocks=stocks)
        r = w.remedies['options'][0]
        self.assertIn('stage:stocks', {x['id'] for x in r['remaining_requirements']})
        option['changes']['stocks']['mixture_model'] = synthetic_model
        w = self.run_plan([option], targets={'K': 10}, stocks=stocks)
        self.assertIn('stage:stocks', w.remedies['options'][0]['resolved_requirements'])

    def test_invalid_options_and_failed_scenarios(self):
        for options, extra in (
            (None, {}),
            ([{}], {}),
            ([dict(id='x', kind='unknown')], {}),
            ([catalogue([]), catalogue([])], {}),
            ([catalogue([], preferences=[{}])], {}),
            ([catalogue([], preferences=['product_count', 'product_count'])], {}),
            (
                [
                    catalogue([], preferences=['product_count']),
                    available_product_search([product('Ca', Ca=10)]),
                ],
                {},
            ),
            ((), {'max_remedy_evaluations': True}),
            ([dict(id='x', kind='catalogue', changes={'targets': {'K': 0}})], {}),
            ([catalogue([product('K', K=20)])], {}),
            ([catalogue([product('Ca', Ca=10), product('Ca', Ca=10)])], {}),
        ):
            with self.subTest(options=options), self.assertRaises(DeliveryError):
                self.run_plan(options, **extra)
        for option in (
            catalogue([]),
            dict(id='x', kind='equipment'),
            dict(id='x', kind='equipment', changes={}),
            dict(id='x', kind='treatment', evidence={'source': 's', 'revision': '1'}, changes={}),
        ):
            self.assertEqual(
                self.run_plan([option]).remedies['options'][0]['status'], 'potential_remedy'
            )
        failed = dict(
            id='bad-water',
            kind='treatment',
            evidence={'source': 's', 'revision': '1'},
            changes={'water': {'Ca': -1}, 'equilibrium': {}},
        )
        self.assertEqual(
            self.run_plan([failed]).remedies['options'][0]['status'], 'evaluation_failed'
        )

    def test_water_limit_and_declared_treatment_witness(self):
        w = self.run_plan(water={'Na': 10}, maximum_concentrations={'Na': 1})
        self.assertIn('limit:Na', {r['id'] for r in w.remedies['requirements']})
        option = dict(
            id='analysis',
            kind='treatment',
            evidence={'source': 'synthetic', 'revision': '1'},
            changes={'water': {'Ca': 100, 'Mg': 50}, 'equilibrium': {}},
        )
        w = self.run_plan([option], water={'Ca': 200, 'Mg': 50})
        r = w.remedies['options'][0]
        self.assertIn('nutrient:Ca', r['resolved_requirements'])
        candidate = json.loads(r['snapshot'])
        self.assertEqual(candidate['inputs']['targets'], {'K': 100, 'Ca': 100, 'Mg': 50})
        self.assertTrue(candidate['workflow']['recommendation']['feasible'])
        self.assertTrue(r['remaining_requirements'])
        with self.assertRaises(DeliveryError):
            self.run_plan([catalogue([{'id': 'bad'}])])

    def test_json_equipment_options_and_missing_inputs(self):
        from flahax.planning_cli import execute

        base = dict(
            salts=[product('K', K=10)],
            targets={'K': 10},
            water={},
            target_ph=5.5,
            final_volume_litres=10,
        )
        stocks = dict(
            final_litres_per_stock_litre=100,
            temperature_c=20,
            tanks=[{'id': 'A', 'capacity_litres': 1}],
            compatibility_rules=[],
            solubility_limits=[
                record(
                    'limit',
                    productId='K',
                    maxGramsPerLitre=200,
                    temperatureMinC=10,
                    temperatureMaxC=30,
                )
            ],
        )
        for config in (stocks, {}):
            option = dict(id='tank', kind='equipment', changes={'stocks': config})
            w = execute('workflow', base | {'remedy_options': [option]})
            self.assertEqual(w.remedies['evaluations'], 1)
            self.assertIn(
                'stage:stocks',
                {r['id'] for r in w.remedies['options'][0]['remaining_requirements']},
            )
        with self.assertRaises(DeliveryError):
            execute('workflow', base | {'stocks': dict(stocks, tanks=[{}])})

    def test_public_report_and_json_workflow(self):
        from flahax.planning_cli import execute

        payload = dict(
            salts=[product('K', K=10)],
            targets={'K': 100, 'Ca': 100},
            water={},
            target_ph=5.5,
            final_volume_litres=10,
            remedy_options=[catalogue([product('Ca', Ca=10)])],
        )
        w = execute('workflow', payload)
        s = summarize_batch(w, payload['salts'], title='Remedies', water_label='Zero')
        self.assertIn('Remedies and next actions', render_report(s))
        self.assertEqual(s['remedies'], w.remedies)
        self.assertFalse(s['formulation']['feasible'])
        self.assertTrue(all(r['next_action'] for r in w.remedies['requirements']))
