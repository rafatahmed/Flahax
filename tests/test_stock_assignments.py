# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent graph-coloring witnesses and synthetic mixture-domain controls."""

from itertools import combinations, product
import unittest
from flahax import DeliveryError, InjectionRatio, StockTank, TemperatureCelsius, VolumeLitres
from flahax.stock_planning import plan_stocks
from flahax.tank_grouping import group_tanks
from tests.test_stock_planning import recipe, limits, record


def synthetic_model(tank, temperature):
    """A synthetic interface witness, never physical mixture evidence."""
    return dict(
        status='compatible',
        model_id='synthetic-only',
        source='test oracle',
        revision='1',
        review_id='synthetic-review',
        reviewed=True,
        product_ids=[s.salt_id for s in tank.salts],
        basis='g_per_l_stock_solution',
        temperature_min_c=10,
        temperature_max_c=30,
        ionic_strength=0.02,
        ionic_strength_max=0.1,
        total_concentration_max_g_per_l=100,
        mass_balance_verified=True,
        evaluated_concentrations_g_per_l={s.salt_id: s.concentration.value for s in tank.salts},
    )


def plan(model=None, **kw):
    return plan_stocks(
        recipe(),
        InjectionRatio(100),
        [StockTank('A', VolumeLitres(2)), StockTank('B', VolumeLitres(2))],
        [],
        limits(),
        TemperatureCelsius(20),
        mixture_model=model,
        **kw,
    )


class AssignmentTests(unittest.TestCase):
    def test_all_four_vertex_graphs_match_independent_minimum(self):
        pairs = list(combinations(range(4), 2))
        products = [dict(id=str(i), name=str(i), elements={}) for i in range(4)]
        rows = [dict(id=str(i), name=str(i), gramsPerLitre=1) for i in range(4)]
        for mask in range(64):
            edges = [e for bit, e in enumerate(pairs) if mask & (1 << bit)]
            rules = [
                record(
                    f'r{i}',
                    productIds=[str(a), str(b)],
                    constraint='separate',
                    reason='synthetic graph edge',
                    temperatureMinC=0,
                    temperatureMaxC=40,
                )
                for i, (a, b) in enumerate(edges)
            ]
            minimum = next(
                k
                for k in range(1, 5)
                if any(
                    all(colors[a] != colors[b] for a, b in edges)
                    for colors in product(range(k), repeat=4)
                )
            )
            found = group_tanks(rows, products, rules=rules)
            self.assertEqual(len(found.tanks), minimum, mask)
            self.assertFalse(found.waived)
            for a, b in edges:
                self.assertNotEqual(found.tank_of(str(a)), found.tank_of(str(b)))
            if minimum > 1:
                with self.assertRaises(DeliveryError):
                    group_tanks(rows, products, rules=rules, max_tanks=minimum - 1)
        self.assertEqual(group_tanks([], []).tanks, ())

    def test_budget_and_input_failures_are_distinct(self):
        products = [dict(id='a', name='A', elements={})]
        rows = [dict(id='a', name='A', gramsPerLitre=1)]
        for kw in ({'max_tanks': 0}, {'max_tanks': True}, {'max_search_nodes': 0}):
            with self.assertRaises(DeliveryError):
                group_tanks(rows, products, **kw)
        with self.assertRaises(DeliveryError) as caught:
            group_tanks(rows, products, max_search_nodes=1)
        self.assertEqual(caught.exception.code, 'stock_search_limit')
        with self.assertRaises(DeliveryError):
            group_tanks(rows * 2, products)
        with self.assertRaises(DeliveryError):
            group_tanks(rows, [])
        for dose in (-1, float('nan'), True):
            with self.assertRaises(DeliveryError):
                group_tanks([dict(rows[0], gramsPerLitre=dose)], products)
        self.assertEqual(group_tanks([dict(rows[0], gramsPerLitre=0)], products).tanks, ())

    def test_no_equipment_or_small_dose_waiver(self):
        products = [
            dict(id='ca', name='calcium', elements={'Ca': 1}),
            dict(id='mg', name='magnesium sulfate', elements={'Mg': 1, 'S': 1}),
            dict(id='p', name='phosphate', elements={'P': 1}),
            dict(id='zn', name='micro sulfate', elements={'Zn': 1, 'S': 1}),
        ]
        rows = [dict(id=p['id'], name=p['name'], gramsPerLitre=0.00001) for p in products]
        result = group_tanks(rows, products)
        self.assertEqual(len(result.tanks), 3)
        self.assertNotEqual(result.tank_of('calcium'), result.tank_of('micro sulfate'))
        with self.assertRaises(DeliveryError):
            group_tanks(rows, products, max_tanks=2)


class MixtureTests(unittest.TestCase):
    def test_missing_model_never_approves(self):
        found = plan()
        self.assertEqual(found.status, 'requires_review')
        self.assertFalse(found.mixture_approved)
        self.assertEqual(found.mixture_assessments[0]['status'], 'not_supported')

    def test_qualified_alternative_preserves_exact_mass(self):
        def common_ion_witness(tank, temperature):
            # Synthetic pair rejection tests the interface, not a physical constant.
            result = synthetic_model(tank, temperature)
            if len(tank.salts) > 1:
                result['status'] = 'incompatible'
                result['reason'] = 'synthetic common-ion witness'
            return result

        found = plan(common_ion_witness)
        self.assertTrue(found.mixture_approved)
        self.assertEqual(len(found.tanks), 2)
        self.assertGreater(found.assignments_evaluated, 1)
        masses = {
            s.salt_id: s.concentration.value * t.stock_volume.value
            for t in found.tanks
            for s in t.salts
        }
        self.assertEqual(masses, {'calcium-nitrate': 50, 'phosphate': 25})
        self.assertEqual(plan(synthetic_model).status, 'qualified')

    def test_domains_and_review_cannot_be_invented(self):
        cases = [
            ('reviewed', False),
            ('review_id', ''),
            ('source', None),
            ('product_ids', ['other-grade']),
            ('basis', 'g_per_l_water'),
            ('evaluated_concentrations_g_per_l', {}),
            ('temperature_min_c', 21),
            ('temperature_max_c', 19),
            ('ionic_strength', 0.2),
            ('ionic_strength', -1),
            ('total_concentration_max_g_per_l', 10),
            ('mass_balance_verified', False),
        ]
        for key, value in cases:

            def model(t, temp):
                return dict(synthetic_model(t, temp), **{key: value})

            with self.subTest(key=key):
                self.assertFalse(plan(model).mixture_approved)
        for raw in (None, {}, {'status': 'unknown'}):
            with self.assertRaises(DeliveryError):
                plan(lambda t, temp: raw)
        for value in (float('nan'), True, '0.02'):
            with self.assertRaises(DeliveryError):
                plan(lambda t, temp: dict(synthetic_model(t, temp), ionic_strength=value))
        with self.assertRaises(DeliveryError):
            plan(3)
        with self.assertRaises(DeliveryError):
            plan(max_assignments=0)

    def test_exhaustion_and_known_incompatibility_are_distinct(self):
        def reject(t, temp):
            return {'status': 'incompatible'}

        with self.assertRaises(DeliveryError) as caught:
            plan(reject)
        self.assertEqual(caught.exception.code, 'no_stock_assignment')
        with self.assertRaises(DeliveryError) as caught:
            plan(reject, max_assignments=1)
        self.assertEqual(caught.exception.code, 'stock_search_limit')
        found = plan(lambda t, temp: {'status': 'not_supported'}, max_assignments=1)
        self.assertFalse(found.search_complete)
        self.assertFalse(found.mixture_approved)


class AssignmentBoundaryTests(unittest.TestCase):
    def test_public_types_and_empty_recipe(self):
        from flahax import final_solution_recipe

        good_tank = StockTank('A', VolumeLitres(2))
        for name, capacity in [('', VolumeLitres(2)), ('A', 2)]:
            with self.assertRaises(DeliveryError):
                StockTank(name, capacity)
        args = [recipe(), InjectionRatio(100), [good_tank], [], limits(), TemperatureCelsius(20)]
        for index, value in [
            (0, None),
            (1, 100),
            (5, 20),
            (2, None),
            (2, []),
            (2, [1]),
            (2, [good_tank, good_tank]),
        ]:
            changed = args.copy()
            changed[index] = value
            with self.assertRaises(DeliveryError):
                plan_stocks(*changed)
        empty = final_solution_recipe({'feasible': True, 'salts': []}, VolumeLitres(100))
        args[0] = empty
        self.assertEqual(plan_stocks(*args).tanks, ())
        args[0] = recipe()
        args[4] = limits() + [dict(limits()[0], id='higher', maxGramsPerLitre=200)]
        self.assertIn('calcium-limit', plan_stocks(*args).solubility_limit_ids)

    def test_acid_reagent_and_default_separation_evidence(self):
        from flahax.engine import PH_REAGENT
        from flahax.tank_grouping import default_compatibility_rules

        products = [
            dict(id='ca', name='calcium', elements={'Ca': 1}),
            dict(id='p', name='phosphate', elements={'P': 1}),
            dict(id='m', name='micro', elements={'Fe': 1}),
            dict(id='h', name='acid', elements={}, formula='HNO3'),
            dict(id='r', name='reagent', elements={}, role=PH_REAGENT),
        ]
        rows = [dict(id=p['id'], name=p['name'], gramsPerLitre=1) for p in products]
        found = group_tanks(rows, products)
        self.assertEqual(found.reagent_channel, ('reagent',))
        self.assertNotEqual(found.tank_of('acid'), found.tank_of('calcium'))
        self.assertNotEqual(found.tank_of('acid'), found.tank_of('micro'))
        self.assertEqual(sum(sum(t.stock_grams_per_litre(100).values()) for t in found.tanks), 400)
        rules = default_compatibility_rules(products)
        self.assertTrue(any(set(r['productIds']) == {'m', 'p'} for r in rules))
        self.assertTrue(all('r' not in r['productIds'] for r in rules))
