# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent scoped remedy witnesses and honest unresolved outcomes."""

import copy
import json
from fractions import Fraction
import unittest

from flahax import (
    plan_fertilizer_workflow,
    VolumeLitres,
    InjectionRatio,
    TemperatureCelsius,
    StockTank,
)
from flahax.delivery_contracts import DeliveryError
from flahax.grower_report import summarize_batch, render_report
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
