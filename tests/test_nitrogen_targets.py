# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Each nitrogen form is its own target; total N is their reported sum (D1, G23, G24)."""

from html import escape
import math
import unittest

from flahax import (
    VolumeLitres,
    load_library,
    plan_fertilizer_workflow,
    recommend,
    solve_weights,
    summarize_batch,
)
from flahax.composition import fitted_targets, nitrogen_rows, theoretical_assay
from flahax.engine import AMMONIUM_CAP_MG_PER_L, AMMONIUM_FRACTION
from flahax.grower_report import nitrogen_notes, number, render_batch_sheet, render_report
from flahax.grower_sheet import render_mix_sheet
from flahax.ph_adjustment import _blend_recipe, nutrient_salts
from tests.catalogue_history import historical_catalogue
from tests.test_joint_workflow import configuration
from tests.test_ph_adjustment import ACIDS, RO

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


def nitrogen_sum(rows):
    finals = {r['symbol']: r['final'] for r in rows}
    return math.fsum(finals.get(form, 0.0) for form in ('N_NO3', 'N_NH4', 'N_UREA'))


class TotalNAfterReagentTests(unittest.TestCase):
    """Total N is recomputed from the final rows: water, products and the pH reagent."""

    def test_rebuilt_rows_recompute_total_n(self):
        pool = nutrient_salts(SALTS)
        targets = FORMULAS['Cucumber (Howard Resh)']
        unadjusted = recommend(pool, targets, {})
        blended = _blend_recipe(
            pool, fitted_targets(targets), {'N_NO3': 20}, [unadjusted] * 2, 0.0, None
        )
        self.assertEqual(blended['totalN']['final'], nitrogen_sum(blended['rows']))
        self.assertAlmostEqual(
            blended['totalN']['final'], unadjusted['totalN']['final'] + 20, places=9
        )
        self.assertAlmostEqual(blended['totalN']['final'], 180.8754, places=4)
        self.assertEqual(blended['totalN']['target'], 140)

    def test_summary_total_n_counts_nitric_acid_nitrogen(self):
        # A single theoretical KNO3 product (no catalogue identity) and nitric acid, planned
        # jointly to pH 5.8; the selected recipe is the one the summary weighs.
        kno3 = dict(
            id='kno3-theory',
            name='Potassium nitrate (theoretical)',
            formula='KNO3',
            elements=theoretical_assay('KNO3'),
        )
        pool, product = [kno3], ACIDS[0]
        flow = plan_fertilizer_workflow(
            pool,
            {'K': 100},
            {'Na': 0.002 * 22.989769 * 1000},
            5.8,
            final_volume=VolumeLitres(1000),
            equilibrium=RO | dict(water_totals={'Na+': 0.002, 'CO3-2': 0.002}, water_mass_kg=1000),
            ph_adjustment=dict(
                products=[product],
                maximum_reagent_volume_litres=5,
                joint=configuration(pool, product),
            ),
        )
        selected = flow.stages['ph_adjustment'].value.selected
        self.assertIsNotNone(selected)
        self.assertGreater(selected.nutrient_contribution['N_NO3'], 0)
        summary = summarize_batch(flow, pool, title='KNO3', water_label='RO')
        total = summary['formulation']['total_n']
        self.assertEqual(total['final'], nitrogen_sum(summary['formulation']['rows']))
        self.assertAlmostEqual(total['final'], 57.3591, places=4)
        self.assertAlmostEqual(
            total['final'],
            100 * 14.0067 / 39.0983 + selected.nutrient_contribution['N_NO3'],
            delta=0.01,
        )
        self.assertIsNone(total['target'])


class LegacyBlendAllowanceTests(unittest.TestCase):
    """A rebuilt (blended) recipe is assessed against the same ammonium allowance."""

    def test_blended_recipe_keeps_the_allowance(self):
        pool = nutrient_salts(SALTS)
        targets = FORMULAS['Cucumber (Howard Resh)']
        unadjusted = recommend(pool, targets, {})
        blended = _blend_recipe(
            pool, fitted_targets(targets), {'N_NO3': 20}, [unadjusted] * 2, 0.0, None
        )
        ammonium = next(r for r in blended['incidentalContributions'] if r['symbol'] == 'N_NH4')
        self.assertEqual((ammonium['maximumPpm'], ammonium['assessment']), (14.0, 'within_limit'))
        self.assertEqual(blended['ammoniumLimit']['mgPerL'], 14.0)

    def test_legacy_nitric_candidate_has_no_ammonium_review(self):
        # The frozen pre-packaged catalogue: the packaged KNO3 is blocked by the label/charge
        # gate (G5) before any pH candidate is planned.
        self.enterContext(historical_catalogue())
        library = load_library()
        targets = next(
            f['targets']
            for f in library['formulas']
            if f['name'] == 'Tomato Stage.2 - first cluster (Howard Resh)'
        )
        flow = plan_fertilizer_workflow(
            library['salts'],
            targets,
            {},
            5.8,
            final_volume=VolumeLitres(1000),
            equilibrium=RO,
            ph_adjustment=dict(products=[ACIDS[0]], maximum_reagent_volume_litres=5),
        )
        (candidate,) = flow.stages['ph_adjustment'].value.candidates
        recipe = candidate.recommendation
        ammonium = next(r for r in recipe['incidentalContributions'] if r['symbol'] == 'N_NH4')
        self.assertEqual((ammonium['maximumPpm'], ammonium['assessment']), (13.0, 'within_limit'))
        self.assertLessEqual(ammonium['ppm'], 13.0)
        self.assertEqual(recipe['totalN']['final'], nitrogen_sum(recipe['rows']))
        self.assertNotIn('N_NH4', candidate.message or '')


class SolveWeightsAllowanceTests(unittest.TestCase):
    """solve_weights applies the same allowance as recommend, with the same reporting."""

    def test_same_rule_as_recommend(self):
        calcium = next(s for s in SALTS if s['name'] == CALCIUM_NITRATE)
        nitrate = 84 * 14.4 / 19
        for targets in ({'Ca': 84, 'N_NO3': nitrate}, {'Ca': 84, 'N_NO3': nitrate, 'N_NH4': 0}):
            with self.subTest(targets=targets):
                low = solve_weights([calcium], targets, {})
                high = recommend([calcium], targets, {})
                self.assertEqual(
                    low['ammoniumLimit'],
                    {
                        'mgPerL': 0.1 * nitrate,
                        'fractionOfTotalN': 0.1,
                        'absoluteCapMgPerL': 1.5 * 14.0067,
                        'basis': BASIS,
                    },
                )
                self.assertEqual(low['ammoniumLimit'], high['ammoniumLimit'])
                self.assertEqual(
                    low['incidentalContributions'],
                    [
                        {k: v for k, v in r.items() if k != 'source'}
                        for r in high['incidentalContributions']
                    ],
                )
                self.assertEqual(low['incidentalContributions'][0]['assessment'], 'within_limit')
                self.assertFalse(low['requiresReview'])
                self.assertEqual(low['totalN'], high['totalN'])

    def test_none_and_a_tighter_fraction(self):
        calcium = next(s for s in SALTS if s['name'] == CALCIUM_NITRATE)
        targets = {'Ca': 84, 'N_NO3': 84 * 14.4 / 19}
        none = solve_weights([calcium], targets, max_ammonium_fraction=None)
        self.assertIsNone(none['ammoniumLimit'])
        tight = solve_weights([calcium], targets, max_ammonium_fraction=0.05)
        self.assertEqual(tight['ammoniumLimit']['mgPerL'], 0.05 * targets['N_NO3'])
        self.assertLessEqual(row(tight, 'N_NH4')['final'], 0.05 * targets['N_NO3'])
        self.assertEqual(tight['limitViolations'], [])


class GrowerNitrogenLinesTests(unittest.TestCase):
    """The allowance and total N are printed under the nutrient table of every grower output."""

    ALLOWANCE = (
        'Incidental NH4-N allowed up to 14 mg/L (10 % of total N, cap 21.01 mg/L): '
        'Dutch soilless practice (De Kreij, Voogt et al.)'
    )

    @classmethod
    def setUpClass(cls):
        flow = plan_fertilizer_workflow(
            SALTS, FORMULAS['Cucumber (Howard Resh)'], {}, 5.8, final_volume=VolumeLitres(100)
        )
        cls.summary = summarize_batch(flow, SALTS, title='Cucumber', water_label='RO')
        cls.total = (
            f'Total N: {number(cls.summary["formulation"]["total_n"]["final"], 2)} mg/L '
            '(sum of NO3-N, NH4-N and urea-N; reported, not a target)'
        )

    def test_total_n_line_value(self):
        self.assertEqual(
            self.total,
            'Total N: 160.88 mg/L (sum of NO3-N, NH4-N and urea-N; reported, not a target)',
        )
        self.assertEqual(nitrogen_notes(self.summary), [self.ALLOWANCE, self.total])

    def test_report_batch_sheet_and_mix_sheet_print_both_lines(self):
        for name, page in (
            ('report', render_report(self.summary)),
            ('batch sheet', render_batch_sheet(self.summary)),
            ('mix sheet', render_mix_sheet(self.summary, 2)),
        ):
            with self.subTest(page=name):
                self.assertIn(f'<p class="small">{escape(self.ALLOWANCE)}</p>', page)
                self.assertIn(f'<p class="small">{escape(self.total)}</p>', page)

    def test_lines_only_when_they_apply(self):
        pepper = plan_fertilizer_workflow(
            SALTS, FORMULAS['Pepper (Howard Resh)'], {}, 5.8, final_volume=VolumeLitres(100)
        )
        summary = summarize_batch(pepper, SALTS, title='Pepper', water_label='RO')
        notes = nitrogen_notes(summary)
        self.assertEqual(len(notes), 1)  # an explicit NH4-N target: no allowance
        self.assertTrue(notes[0].startswith('Total N: '))
        self.assertNotIn('Incidental NH4-N allowed', render_report(summary))
        potassium = next(s for s in SALTS if s['name'] == 'Potassium Sulfate')
        bare = plan_fertilizer_workflow(
            [potassium], {'K': 100}, {}, 5.8, final_volume=VolumeLitres(100)
        )
        summary = summarize_batch(bare, [potassium], title='K', water_label='RO')
        self.assertEqual(nitrogen_notes(summary), [])  # no nitrogen declared
        self.assertNotIn('Total N:', render_report(summary))


if __name__ == '__main__':
    unittest.main()
