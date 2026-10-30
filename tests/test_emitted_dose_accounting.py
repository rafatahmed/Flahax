# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent dose accounting, without changing targets or reference inputs."""

from fractions import Fraction
import json
import math
import unittest

from flahax import (
    DeliveryError,
    InputError,
    MassGrams,
    rescore_weighed_recipe,
    VolumeLitres,
    final_solution_recipe,
    load_library,
    recommend,
    solve_weights,
)
from flahax.composition import assay_conflict
from flahax.engine import forward


class EmittedDoseTests(unittest.TestCase):
    def test_trace_and_rounding_boundaries(self):
        product = dict(id='mo', name='mo', elements={'Mo': 10})
        for dose in (1e-10, 1e-7, 1e-6, math.nextafter(1e-6, math.inf), 0.123456789):
            for solver in (recommend, solve_weights):
                result = solver([product], {'Mo': dose * 100}, {})
                result = json.loads(json.dumps(result))
                self.assertEqual(len(result['salts']), 1)
                emitted = result['salts'][0]['gramsPerLitre']
                self.assertEqual(emitted, result['grams'][0])
                expected = float(Fraction(str(emitted)) * 100)
                actual = next(r['final'] for r in result['rows'] if r['symbol'] == 'Mo')
                self.assertAlmostEqual(actual / expected, 1, places=14)
                self.assertEqual(result['totalGramsPerLitre'], emitted)
                for volume in (0.001, 1, 1000, 1e6):
                    batch = final_solution_recipe(result, VolumeLitres(volume))
                    self.assertEqual(batch.salts[0].mass.value, emitted * volume)

    def test_all_shipped_formulas_reconstruct_from_published_quantities(self):
        library = load_library()
        products = [p for p in library['salts'] if assay_conflict(p) is None]
        by_id = {p['id']: p for p in products}
        self.assertEqual(len(library['formulas']), 13)
        for formula in library['formulas']:
            with self.subTest(formula=formula['name']):
                result = recommend(products, formula['targets'], formula['water'])
                emitted = json.loads(json.dumps(result['salts']))
                reconstructed = forward(
                    [by_id[p['id']] for p in emitted],
                    [p['gramsPerLitre'] for p in emitted],
                    formula['water'],
                )
                for row in result['rows']:
                    self.assertEqual(row['final'], reconstructed.get(row['symbol'], 0))
                self.assertEqual(
                    result['totalGramsPerLitre'], sum(p['gramsPerLitre'] for p in emitted)
                )


class WeighedRecipeTests(unittest.TestCase):
    products = [
        dict(id='k', name='K material', elements={'K': 10}),
        dict(id='ca', name='Ca material', elements={'Ca': 10}),
    ]

    def test_actual_weights_replace_planned_accuracy(self):
        for volume in (0.001, 1, 1000):
            result = rescore_weighed_recipe(
                self.products,
                {'k': MassGrams(0.99 * volume), 'ca': MassGrams(0)},
                VolumeLitres(volume),
                {'K': 100, 'Ca': 0},
                {'K': 1},
            )
            self.assertTrue(result['feasible'])
            self.assertEqual(result['salts'][0]['gramsPerLitre'], 0.99)
            self.assertEqual(len(result['salts']), 1)
            self.assertEqual(next(r['final'] for r in result['rows'] if r['symbol'] == 'K'), 100)
        omitted = rescore_weighed_recipe(self.products, {}, VolumeLitres(1), {'K': 100})
        self.assertFalse(omitted['feasible'])
        self.assertEqual(omitted['salts'], [])

    def test_hard_limits_zero_and_target_conflicts_reassessed(self):
        for targets, water, maxima in (
            ({'K': 100}, {}, {'K': 99}),
            ({'K': 0}, {}, {}),
            ({'Ca': 0}, {'K': 2}, {'K': 1}),
            ({'K': 100}, {}, {'K': 99.9}),
        ):
            result = rescore_weighed_recipe(
                self.products,
                {'k': MassGrams(1)},
                VolumeLitres(1),
                targets,
                water,
                maximum_concentrations=maxima,
            )
            self.assertFalse(result['feasible'])
        result = rescore_weighed_recipe(self.products, {}, VolumeLitres(1), {'K': 0})
        self.assertTrue(result['feasible'])

    def test_invalid_weighing_inputs(self):
        cases = [
            dict(targets=None),
            dict(water=[]),
            dict(maximum_concentrations=[]),
            dict(final_volume=1),
            dict(products=()),
            dict(masses=[]),
            dict(products=[None]),
            dict(products=[{'id': 1}]),
            dict(products=[dict(id='', elements={'K': 10})]),
            dict(products=self.products * 2),
            dict(products=[dict(id='bad', elements={'K': -1})]),
            dict(masses={'unknown': MassGrams(1)}),
            dict(masses={'k': 1}),
            dict(masses={'k': MassGrams(1e308)}, final_volume=VolumeLitres(1e-308)),
        ]
        for override in cases:
            args = (
                dict(
                    products=self.products,
                    masses={},
                    final_volume=VolumeLitres(1),
                    targets={'K': 1},
                )
                | override
            )
            with self.subTest(override=override), self.assertRaises(DeliveryError):
                rescore_weighed_recipe(**args)
        for override in (
            dict(targets={}),
            dict(targets={'K': -1}),
            dict(water={'K': -1}),
            dict(maximum_concentrations={'K': -1}),
        ):
            args = (
                dict(
                    products=self.products,
                    masses={},
                    final_volume=VolumeLitres(1),
                    targets={'K': 1},
                )
                | override
            )
            with self.assertRaises(InputError):
                rescore_weighed_recipe(**args)
