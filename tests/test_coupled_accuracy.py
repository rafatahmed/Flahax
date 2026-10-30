# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent mass and real-chemistry controls for coupled recipe switching."""

from fractions import Fraction
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from flahax.delivery_contracts import DeliveryError

from flahax import recommend
from flahax.ph_adjustment import _blend_recipe, _couple
from flahax.requirement_fit import met
from tests.test_ph_adjustment import coupled, amended_ph
from tests.catalogue_history import historical_catalogue


class RecipeBlendTests(unittest.TestCase):
    def setUp(self):
        self.pool = [
            dict(id='k', name='K source', elements={'K': 10}),
            dict(id='ca', name='Ca source', elements={'Ca': 10}),
        ]
        self.targets = {'K': 100, 'Ca': 100}
        self.ends = [recommend([p], self.targets) for p in self.pool]

    def test_convex_mass_balance_and_diagnostics_are_rebuilt(self):
        result = _blend_recipe(self.pool, self.targets, {'K': 10}, self.ends, 0.25, {})
        expected = {'K': Fraction(10) + Fraction(3, 4) * 100, 'Ca': Fraction(1, 4) * 100}
        rows = {r['symbol']: r for r in result['rows']}
        for symbol, value in expected.items():
            self.assertEqual(rows[symbol]['final'], float(value))
        self.assertAlmostEqual(
            result['recipeIonBalance']['cationsMeqPerL'], 85 / 39.0983 + 2 * 25 / 40.078
        )
        self.assertNotEqual(result['recipeIonBalance'], self.ends[0]['recipeIonBalance'])
        self.assertEqual(result['chargeAssessment']['assayOnlyProducts'], ['k', 'ca'])
        self.assertEqual(result['grams'], [0.75, 0.25])
        self.assertEqual(result['loss'], float(Fraction(15, 100) ** 2 + Fraction(75, 100) ** 2))
        for miss in result['unmetTargets']:
            self.assertEqual(miss['final'], rows[miss['symbol']]['final'])
            self.assertEqual(miss['deltaPct'], rows[miss['symbol']]['deltaPct'])
        self.assertEqual([i['gramsPerLitre'] for i in result['materialInventory']], [0.75, 0.25])

    def test_zero_and_maximum_are_checked_against_actual_blend(self):
        for targets, maxima in [({'K': 0, 'Ca': 100}, {}), (self.targets, {'Ca': 20})]:
            result = _blend_recipe(self.pool, targets, {}, self.ends, 0.25, maxima)
            self.assertFalse(result['feasible'])
            self.assertTrue(result['limitViolations'])

    def test_supply_conflicts_are_recomputed_not_copied(self):
        result = _blend_recipe(self.pool, self.targets, {'Ca': 120}, self.ends, 0, {'Ca': 110})
        self.assertEqual(
            result['requirementConflicts'],
            [dict(symbol='Ca', reason='water_above_maximum', waterPpm=120, maximumPpm=110)],
        )
        result = _blend_recipe(self.pool, self.targets, {}, [result] * 2, 0, {})
        self.assertEqual(result['requirementConflicts'], [])

    def test_endpoints_preserve_product_identity_without_zero_rows(self):
        for weight, identity in ((0, 'k'), (1, 'ca')):
            result = _blend_recipe(self.pool, self.targets, {}, self.ends, weight, {})
            self.assertEqual([s['id'] for s in result['salts']], [identity])
            self.assertEqual(result['salts'][0]['gramsPerLitre'], 1)


class CoupledFailureTests(unittest.TestCase):
    def test_unbracketed_blend_and_dose_disagreement_fail_closed(self):
        # Controlled solver failures exercise rejection, not chemical predictions.
        pool = [dict(id=k, name=k, elements={'N_NO3': 10}) for k in ('a', 'b')]
        targets = {'N_NO3': 100}
        endpoints = [recommend([p], targets) for p in pool]

        def fit(_pool, _targets, supply, **_kwargs):
            return endpoints[int(supply.get('N_NO3', 0) > 1000)]

        def mix(recipe):
            amount_a = sum(s['gramsPerLitre'] for s in recipe['salts'] if s['id'] == 'a')
            return SimpleNamespace(
                totals={'a': amount_a}, ph=7 if amount_a else 5, charge_balance=0
            )

        def demand(_totals, ph, *_args, **_kwargs):
            if ph < 5.8:
                raise DeliveryError('wrong_reagent_direction', 'injected direction crossing')
            return 2, SimpleNamespace(charge_balance=0)

        for bracketed, message in ((False, 'does not bracket'), (True, 'dose disagree')):

            def chemistry(totals, *_args, **_kwargs):
                return SimpleNamespace(charge_balance=2 * totals['a'] - 1 if bracketed else 1)

            with (
                patch('flahax.ph_adjustment.recommend', side_effect=fit),
                patch('flahax.ph_adjustment.reagent_dose', side_effect=demand),
                patch('flahax.ph_adjustment.solve', side_effect=chemistry),
            ):
                with self.assertRaisesRegex(DeliveryError, message) as caught:
                    _couple(
                        pool,
                        targets,
                        {},
                        5.8,
                        dict(id='acid', chemicalFormula='HNO3'),
                        1,
                        1,
                        63,
                        {'N_NO3': 1},
                        mix,
                        1,
                        1,
                        10,
                        (),
                        {},
                    )
                self.assertEqual(caught.exception.code, 'nonconvergent')


class CoupledAccuracyTests(unittest.TestCase):
    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_direction_crossing_returns_a_real_phosphoric_plan(self):
        self.enterContext(historical_catalogue())
        flow = coupled('Tomato (Howard Resh)', maxima={'N_NH4': 14})
        candidate = next(
            c for c in flow.stages['ph_adjustment'].value.candidates if c.formula == 'H3PO4'
        )
        self.assertIsNotNone(candidate.target)
        self.assertGreater(candidate.dose_molal, 0)
        self.assertTrue(candidate.recommendation['feasible'])
        self.assertEqual(candidate.recommendation['limitViolations'], [])
        self.assertAlmostEqual(amended_ph(candidate), 5.8, places=4)
        for row in candidate.recommendation['rows']:
            if row['target']:
                self.assertTrue(met(row['target'], row['final']), row['symbol'])

    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_initial_direction_and_numerical_failures_are_not_used_as_bounds(self):
        self.enterContext(historical_catalogue())
        for code in ('wrong_reagent_direction', 'nonconvergent'):
            with patch(
                'flahax.ph_adjustment.reagent_dose',
                side_effect=DeliveryError(code, 'injected failure'),
            ):
                flow = coupled('Tomato (Howard Resh)', maxima={'N_NH4': 14})
            candidates = flow.stages['ph_adjustment'].value.candidates
            for candidate in candidates:
                if candidate.direction == 'acid':
                    self.assertEqual(candidate.status, 'rejected')
                    self.assertEqual(candidate.error_code, code)
                    self.assertIsNone(candidate.target)

    # Catalogue v0.0: re-enable in PR 4 (G5)
    def test_only_acid_is_not_applicable_when_accuracy_fit_needs_base(self):
        self.enterContext(historical_catalogue())
        flow = coupled('Tomato Stage.2 - first cluster (Howard Resh)')
        plan = flow.stages['ph_adjustment'].value
        self.assertLess(plan.unadjusted_ph, 5.8)
        for candidate in plan.candidates:
            if candidate.direction == 'acid':
                self.assertEqual(candidate.status, 'not_applicable')
                self.assertEqual(candidate.error_code, 'wrong_reagent_direction')
                self.assertIsNone(candidate.target)


if __name__ == '__main__':
    unittest.main()
