# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Each nitrogen form is its own target; total N is their reported sum (D1, G23, G24)."""

import math
import unittest

from flahax import VolumeLitres, load_library, plan_fertilizer_workflow, recommend, summarize_batch
from flahax.composition import nitrogen_rows
from flahax.engine import AMMONIUM_CAP_MG_PER_L, AMMONIUM_FRACTION

LIBRARY = load_library()  # the packaged catalogue (Flaha Agri Tech Analysis Ver 0.0)
SALTS = LIBRARY['salts']
FORMULAS = {f['name']: f['targets'] for f in LIBRARY['formulas']}
CALCIUM_NITRATE = 'Calcium Nitrate (ag grade)'
BASIS = 'Dutch soilless practice (De Kreij, Voogt et al.)'
# Literal tolerances until Task 3.2 introduces met() (ledger ruling, PR 3).
RELATIVE = 1e-5
ZERO_MG_PER_L = 1e-6


def row(result, symbol):
    return next((r for r in result['rows'] if r['symbol'] == symbol), None)


class NitrogenRowsTests(unittest.TestCase):
    def test_each_declared_form_is_a_row_and_zero_ammonium_is_none(self):
        self.assertEqual(
            nitrogen_rows({'N_NO3': 140, 'N_NH4': 0, 'K': 350}), {'N_NO3': 140, 'N_UREA': 0}
        )
        self.assertEqual(nitrogen_rows({'N_NO3': 140}), {'N_NO3': 140, 'N_UREA': 0})
        self.assertEqual(
            nitrogen_rows({'N_NO3': 190, 'N_NH4': 18}), {'N_NO3': 190, 'N_NH4': 18, 'N_UREA': 0}
        )
        self.assertEqual(nitrogen_rows({'N_NO3': 100, 'N_UREA': 20}), {'N_NO3': 100, 'N_UREA': 20})

    def test_constants_are_the_dutch_soilless_rule(self):
        self.assertEqual(AMMONIUM_FRACTION, 0.10)
        self.assertEqual(AMMONIUM_CAP_MG_PER_L, 1.5 * 14.0067)


class CucumberAllowanceTests(unittest.TestCase):
    """Cucumber (Howard Resh): N_NO3 140, N_NH4 0 (G23, G24)."""

    @classmethod
    def setUpClass(cls):
        cls.targets = FORMULAS['Cucumber (Howard Resh)']
        cls.result = recommend(SALTS, cls.targets, {})

    def test_formula_values(self):
        self.assertEqual((self.targets['N_NO3'], self.targets['N_NH4']), (140, 0))

    def test_calcium_nitrate_is_eligible_and_selected(self):
        self.assertNotIn(CALCIUM_NITRATE, [item['name'] for item in self.result['excluded']])
        self.assertIn(CALCIUM_NITRATE, [item['name'] for item in self.result['salts']])

    def test_incidental_ammonium_is_within_the_allowance(self):
        limit = self.result['ammoniumLimit']
        self.assertEqual(limit['mgPerL'], min(0.10 * 140, 1.5 * 14.0067))
        self.assertEqual(limit['mgPerL'], 14.0)
        self.assertEqual(limit['fractionOfTotalN'], 0.10)
        self.assertEqual(limit['absoluteCapMgPerL'], 1.5 * 14.0067)
        ammonium = row(self.result, 'N_NH4')
        self.assertGreater(ammonium['final'], 0)
        self.assertLessEqual(ammonium['final'], 14.0)
        self.assertEqual(self.result['limitViolations'], [])

    def test_the_allowance_is_shown_with_its_basis(self):
        self.assertEqual(self.result['ammoniumLimit']['basis'], BASIS)
        incidental = next(
            r for r in self.result['incidentalContributions'] if r['symbol'] == 'N_NH4'
        )
        self.assertEqual(incidental['maximumPpm'], 14.0)
        self.assertEqual(incidental['assessment'], 'within_limit')
        self.assertIn(CALCIUM_NITRATE, incidental['source'])

    def test_grower_summary_shows_the_allowance_and_total_n(self):
        flow = plan_fertilizer_workflow(
            SALTS, self.targets, {}, 5.8, final_volume=VolumeLitres(100)
        )
        summary = summarize_batch(flow, SALTS, title='Cucumber', water_label='RO')
        allowance = summary['formulation']['ammonium_allowance']
        self.assertEqual(allowance['mgPerL'], 14.0)
        self.assertEqual(allowance['basis'], BASIS)
        total = summary['formulation']['total_n']
        self.assertEqual(total['target'], 140)
        self.assertFalse(total['fitted'])

    def test_no_zero_ammonium_row_exists(self):
        ammonium = row(self.result, 'N_NH4')
        self.assertIsNone(ammonium['target'])
        self.assertIsNone(ammonium['deltaPct'])
        self.assertEqual(
            [r['target'] for r in self.result['rows'] if r['symbol'] == 'N_NH4'], [None]
        )
        self.assertNotIn('N_NH4', [m['symbol'] for m in self.result['unmetTargets']])
        self.assertNotIn(
            'prohibited_by_zero_requirement', [m['reason'] for m in self.result['unmetTargets']]
        )


class PepperAmmoniumRowTests(unittest.TestCase):
    def test_explicit_ammonium_requirement_row(self):
        targets = FORMULAS['Pepper (Howard Resh)']
        self.assertEqual(targets['N_NH4'], 18)
        result = recommend(SALTS, targets, {})
        self.assertEqual(row(result, 'N_NH4')['target'], 18)
        self.assertIsNotNone(row(result, 'N_NH4')['deltaPct'])
        self.assertIsNone(result['ammoniumLimit'])


class AmmoniumDeviationTests(unittest.TestCase):
    """Review Focus 5: calcium nitrate's ammonium above a positive NH4-N target is a deviation."""

    def test_ammonium_above_its_target_is_a_deviation_not_a_ban(self):
        calcium = next(s for s in SALTS if s['name'] == CALCIUM_NITRATE)
        rate = {k: v * 10.0 for k, v in calcium['elements'].items()}  # mg/L per g/L
        # Ca and NO3 targets at the dose where calcium nitrate's NH4-N is 15a; with three equal
        # relative-error rows the least-squares dose then gives NH4-N 15a(2 + a)/(2 + a^2) = 16.
        a = (30 - math.sqrt(772)) / 2
        dose = 15 * a / rate['N_NH4']
        targets = {'Ca': rate['Ca'] * dose, 'N_NO3': rate['N_NO3'] * dose, 'N_NH4': 15}
        result = recommend([calcium], targets, {})
        self.assertEqual([item['name'] for item in result['salts']], [CALCIUM_NITRATE])
        ammonium = row(result, 'N_NH4')
        self.assertAlmostEqual(ammonium['final'], 16, delta=16 * RELATIVE)
        self.assertAlmostEqual(ammonium['deltaPct'], 100 / 15, delta=RELATIVE * 100)
        self.assertEqual(round(ammonium['deltaPct'], 1), 6.7)
        self.assertEqual(result['excluded'], [])
        self.assertEqual(result['limitViolations'], [])
        self.assertIsNone(result['ammoniumLimit'])


class Lettuce2Tests(unittest.TestCase):
    """Lettuce 2 (Howard Resh), packaged catalogue, empty water: each form has its own row.

    The formula is 4 % charge-imbalanced, so the least-squares fit cannot meet every target;
    the deviations below are those the fit reports.
    """

    @classmethod
    def setUpClass(cls):
        cls.targets = FORMULAS['Lettuce 2 (Howard Resh)']
        cls.result = recommend(SALTS, cls.targets, {})

    def test_each_nitrogen_form_is_its_own_row_with_its_declared_target(self):
        self.assertEqual((self.targets['N_NO3'], self.targets['N_NH4']), (165, 15))
        self.assertNotIn('N_UREA', self.targets)
        expected = {'N_NO3': (165, -2.4525), 'N_NH4': (15, 0.2272)}
        for symbol, (declared, delta) in expected.items():
            with self.subTest(symbol=symbol):
                r = row(self.result, symbol)
                self.assertEqual(r['target'], declared)
                self.assertAlmostEqual(r['deltaPct'], delta, places=4)
                self.assertAlmostEqual(r['final'], declared * (1 + r['deltaPct'] / 100), places=9)
        self.assertAlmostEqual(row(self.result, 'N_NO3')['final'], 160.9533, places=4)
        self.assertAlmostEqual(row(self.result, 'N_NH4')['final'], 15.0341, places=4)
        urea = row(self.result, 'N_UREA')
        self.assertEqual(urea['target'], 0)
        self.assertLessEqual(abs(urea['final']), ZERO_MG_PER_L)

    def test_no_ph_reagent_is_in_the_recipe(self):
        reagents = {s['id'] for s in SALTS if s.get('role') == 'ph_reagent'}
        self.assertTrue(reagents)
        self.assertFalse(reagents & {item['id'] for item in self.result['salts']})

    def test_reported_total_n_is_the_sum_of_the_forms(self):
        total = self.result['totalN']
        finals = [row(self.result, s)['final'] for s in ('N_NO3', 'N_NH4', 'N_UREA')]
        self.assertEqual(total['target'], 165 + 15 + 0)
        self.assertEqual(total['final'], math.fsum(finals))
        self.assertAlmostEqual(total['final'], 175.9874, places=4)
        self.assertFalse(total['fitted'])
        self.assertNotIn('N', [r['symbol'] for r in self.result['rows']])


if __name__ == '__main__':
    unittest.main()
