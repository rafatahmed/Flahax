# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""User-declared acceptable deviation ranges (contract Q24, Q26, Q28, Q30, finding C2).

A range is a setting the user gives: a symmetric percentage for positive targets and
per-nutrient shortage/excess overrides in percent or mg/L. None is set by default. Assess
classifies a result against the ranges; Require constrains the search by them. A range
never relaxes an explicit zero target or a hard maximum, and a miss widens nothing.
"""

import unittest

from flahax import DeliveryError, InputError, VolumeLitres, load_library, recommend
from flahax.deviation_ranges import classify, effective_ranges, normalize_ranges

TARGETS = {'K': 100.0, 'Ca': 50.0, 'N_NO3': 80.0, 'Mg': 0.0}


class EffectiveRangeTests(unittest.TestCase):
    def test_no_setting_means_no_range(self):
        self.assertEqual(effective_ranges(None, TARGETS), [])

    def test_a_symmetric_percentage_applies_to_every_positive_target(self):
        ranges = {r['symbol']: r for r in effective_ranges(dict(percent=5), TARGETS)}
        self.assertEqual(sorted(ranges), ['Ca', 'K', 'N_NO3'])
        self.assertAlmostEqual(ranges['K']['low'], 95.0)
        self.assertAlmostEqual(ranges['K']['high'], 105.0)
        self.assertEqual(ranges['K']['shortage'], {'percent': 5.0})
        self.assertNotIn('Mg', ranges)  # an explicit zero is a hard zero, never a range

    def test_an_override_changes_one_side_in_percent_or_concentration(self):
        spec = dict(
            percent=5,
            overrides={'K': dict(shortage_percent=2), 'Ca': dict(excess_mg_per_l=4.0)},
        )
        ranges = {r['symbol']: r for r in effective_ranges(spec, TARGETS)}
        self.assertAlmostEqual(ranges['K']['low'], 98.0)
        self.assertAlmostEqual(
            ranges['K']['high'], 105.0
        )  # the other side keeps the symmetric value
        self.assertAlmostEqual(ranges['Ca']['low'], 47.5)
        self.assertAlmostEqual(ranges['Ca']['high'], 54.0)
        self.assertEqual(ranges['Ca']['excess'], {'mg_per_l': 4.0})

    def test_a_side_nobody_set_is_open(self):
        (only,) = effective_ranges(dict(overrides={'K': dict(shortage_percent=3)}), TARGETS)
        self.assertEqual(only['symbol'], 'K')
        self.assertAlmostEqual(only['low'], 97.0)
        self.assertIsNone(only['high'])

    def test_a_shortage_larger_than_the_target_floors_at_zero(self):
        (only,) = effective_ranges(dict(overrides={'K': dict(shortage_mg_per_l=500)}), TARGETS)
        self.assertEqual(only['low'], 0.0)

    def test_invalid_settings_are_refused(self):
        bad = [
            dict(percent=-1),
            dict(percent=float('nan')),
            dict(percent=True),
            dict(mode='maybe'),
            dict(overrides={'K': dict(shortage_percent=1, shortage_mg_per_l=1)}),
            dict(overrides={'K': dict(shortage_pct=1)}),
            dict(overrides={'K': dict(shortage_percent=-1)}),
            dict(overrides={'Mg': dict(shortage_percent=1)}),  # explicit zero target
            dict(overrides={'Zn': dict(shortage_percent=1)}),  # no target at all
            dict(unknown_field=1),
            'five percent',
        ]
        for spec in bad:
            with self.subTest(spec=spec):
                with self.assertRaises(DeliveryError):
                    effective_ranges(spec, TARGETS)

    def test_overrides_must_be_mappings(self):
        for spec in (dict(overrides='K'), dict(overrides={'K': 5})):
            with self.subTest(spec=spec):
                with self.assertRaises(DeliveryError) as raised:
                    effective_ranges(spec, TARGETS)
                self.assertEqual(raised.exception.code, 'invalid_type')

    def test_the_mode_defaults_to_assess(self):
        self.assertEqual(normalize_ranges(dict(percent=5))['mode'], 'assess')
        self.assertEqual(normalize_ranges(dict(percent=5, mode='require'))['mode'], 'require')
        self.assertIsNone(normalize_ranges(None))


class ClassifyTests(unittest.TestCase):
    def test_each_nutrient_is_inside_below_or_above_with_its_distance(self):
        ranges = effective_ranges(dict(percent=5), TARGETS)
        rows = classify(ranges, {'K': 99.0, 'Ca': 47.0, 'N_NO3': 85.0})
        by = {r['symbol']: r for r in rows}
        self.assertEqual(by['K']['position'], 'inside')
        self.assertEqual(by['Ca']['position'], 'below')
        self.assertAlmostEqual(by['Ca']['outsideBy'], 0.5)
        self.assertEqual(by['N_NO3']['position'], 'above')
        self.assertAlmostEqual(by['N_NO3']['outsideBy'], 1.0)

    def test_a_bound_within_the_numerical_criterion_counts_as_inside(self):
        (row,) = classify(effective_ranges(dict(percent=5), {'K': 100.0}), {'K': 95.0 - 1e-6})
        self.assertEqual(row['position'], 'inside')

    def test_an_absent_final_is_below_a_positive_floor(self):
        (row,) = classify(effective_ranges(dict(percent=5), {'K': 100.0}), {})
        self.assertEqual(row['position'], 'below')


class RecommendRangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        library = load_library()
        cls.salts = library['salts']
        cls.targets = {f['name']: f['targets'] for f in library['formulas']}[
            'Lettuce 2 (Howard Resh)'
        ]
        cls.plain = recommend(cls.salts, cls.targets, {})

    @staticmethod
    def final(result, symbol):
        return next(r['final'] for r in result['rows'] if r['symbol'] == symbol)

    def test_without_ranges_nothing_changes(self):
        self.assertIsNone(self.plain['deviationRanges'])
        again = recommend(self.salts, self.targets, {}, deviation_ranges=None)
        self.assertEqual(again['rows'], self.plain['rows'])

    def test_assess_classifies_and_leaves_the_recipe_alone(self):
        result = recommend(
            self.salts, self.targets, {}, deviation_ranges=dict(percent=1, mode='assess')
        )
        self.assertEqual(result['rows'], self.plain['rows'])
        assessment = result['deviationRanges']
        self.assertEqual(assessment['mode'], 'assess')
        by = {r['symbol']: r for r in assessment['assessment']}
        self.assertEqual(by['N_NO3']['position'], 'below')  # 161.1 against 165 -2.4 %
        self.assertEqual(by['N_NH4']['position'], 'inside')
        self.assertFalse(assessment['allInside'])
        self.assertEqual(
            {r['symbol'] for r in assessment['effective']},
            {s for s, t in self.targets.items() if t > 0},
        )

    def test_require_pulls_a_short_nutrient_inside_its_floor(self):
        spec = dict(overrides={'N_NO3': dict(shortage_percent=1.0)}, mode='require')
        result = recommend(self.salts, self.targets, {}, deviation_ranges=spec)
        floor = self.targets['N_NO3'] * 0.99
        self.assertGreaterEqual(self.final(result, 'N_NO3'), floor * (1 - 1e-5))
        self.assertGreater(self.final(result, 'N_NO3'), self.final(self.plain, 'N_NO3'))
        self.assertEqual(result['deviationRanges']['requirement']['status'], 'met')

    def test_require_holds_an_excess_at_its_ceiling(self):
        spec = dict(overrides={'N_NH4': dict(excess_percent=0.0)}, mode='require')
        result = recommend(self.salts, self.targets, {}, deviation_ranges=spec)
        self.assertLessEqual(self.final(result, 'N_NH4'), self.targets['N_NH4'] * (1 + 1e-5))
        self.assertGreater(self.final(self.plain, 'N_NH4'), self.targets['N_NH4'])  # it was above

    def test_an_unreachable_requirement_keeps_the_candidate_and_widens_nothing(self):
        spec = dict(
            percent=0.0, mode='require'
        )  # every target exactly: the charge imbalance forbids it
        result = recommend(self.salts, self.targets, {}, deviation_ranges=spec)
        requirement = result['deviationRanges']['requirement']
        self.assertEqual(requirement['status'], 'search_incomplete')
        self.assertTrue(requirement['unmet'])
        self.assertFalse(result['feasible'])
        self.assertTrue(result['salts'])  # the candidate is retained
        self.assertIn('not a proof', requirement['scope'])
        for row in result['deviationRanges']['effective']:
            self.assertEqual(row['low'], self.targets[row['symbol']])  # nothing widened

    def test_a_hard_maximum_still_wins_over_a_range(self):
        spec = dict(percent=50.0, mode='require')
        result = recommend(
            self.salts,
            self.targets,
            {},
            maximum_concentrations={'K': 300.0},
            deviation_ranges=spec,
        )
        self.assertLessEqual(self.final(result, 'K'), 300.0 * (1 + 1e-5))

    def test_an_explicit_zero_target_is_not_relaxed_by_a_percentage(self):
        targets = dict(self.targets, Na=0.0)
        result = recommend(self.salts, targets, {}, deviation_ranges=dict(percent=50.0))
        self.assertNotIn('Na', {r['symbol'] for r in result['deviationRanges']['effective']})
        self.assertLessEqual(self.final(result, 'Na'), 1e-6)

    def test_invalid_settings_are_refused_before_fitting(self):
        with self.assertRaises(InputError):
            recommend(self.salts, self.targets, {}, deviation_ranges=dict(percent=-5))


class WorkflowRangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_ph_interval import PRODUCTS, plan

        cls.products, cls.plan = PRODUCTS, staticmethod(plan)

    def summary(self, spec):
        from flahax import summarize_batch

        flow = self.plan(5.8, deviation_ranges=spec)
        return flow, summarize_batch(flow, self.products, title='T', water_label='RO')

    def test_without_ranges_the_summary_has_none_and_the_report_no_table(self):
        from flahax.grower_report import render_report

        _, summary = self.summary(None)
        self.assertIsNone(summary['deviation_ranges'])
        self.assertNotIn('Acceptable deviation ranges', render_report(summary))

    def test_the_final_recipe_is_classified_and_the_settings_are_saved_with_the_inputs(self):
        spec = dict(percent=1.0, mode='assess')
        _, summary = self.summary(spec)
        ranges = summary['deviation_ranges']
        self.assertEqual(ranges['mode'], 'assess')
        self.assertEqual({r['symbol'] for r in ranges['assessment']}, {'K', 'N_NO3', 'P'})
        self.assertEqual(summary['supplied_inputs']['deviation_ranges'], spec)

    def test_the_report_prints_each_effective_range_and_where_the_delivery_sits(self):
        from flahax.grower_report import render_report

        _, summary = self.summary(dict(percent=1.0, mode='assess'))
        visible = render_report(summary).split('<pre id="flahax-result-data">')[0]
        self.assertIn('Acceptable deviation ranges', visible)
        self.assertIn('Assessed only', visible)
        for symbol in ('K', 'N_NO3', 'P'):
            self.assertIn(f'<td>{symbol}</td>', visible)

    def test_a_required_range_that_is_not_met_asks_for_review_and_names_it(self):
        _, summary = self.summary(dict(percent=0.0, mode='require'))
        self.assertEqual(summary['deviation_ranges']['requirement']['status'], 'search_incomplete')
        self.assertIn(summary['status'], ('requires_review', 'blocked'))
        self.assertTrue(
            any('required deviation range is not met' in w for w in summary['warnings'])
        )
        self.assertTrue(any('No range was widened' in w for w in summary['warnings']))

    def test_an_invalid_setting_is_refused_before_any_fitting(self):
        with self.assertRaises(DeliveryError):
            self.plan(5.8, deviation_ranges=dict(percent=-1))

    def test_a_missed_required_range_never_lifts_a_blocked_status(self):
        from flahax import plan_fertilizer_workflow, summarize_batch
        from tests.test_ph_interval import EQUILIBRIUM, PRODUCTS, REAGENTS

        flow = plan_fertilizer_workflow(
            PRODUCTS,
            {'K': 150, 'N_NO3': 40, 'P': 25},
            {'Na': 100.0},  # the water alone is above the declared maximum: blocked
            5.8,
            final_volume=VolumeLitres(1000),
            equilibrium=EQUILIBRIUM,
            ph_adjustment=dict(
                products=REAGENTS, maximum_reagent_volume_litres=5, correct_mixed_ph=True
            ),
            maximum_concentrations={'Na': 5.0},
            deviation_ranges=dict(percent=0.0, mode='require'),
        )
        summary = summarize_batch(flow, PRODUCTS, title='T', water_label='RO')
        self.assertEqual(summary['status'], 'blocked')
        self.assertEqual(summary['deviation_ranges']['requirement']['status'], 'search_incomplete')
        self.assertTrue(
            any('required deviation range is not met' in w for w in summary['warnings'])
        )


class RangeInterfaceTests(unittest.TestCase):
    def test_the_json_workflow_accepts_ranges(self):
        from flahax.planning_cli import execute
        from tests.test_ph_interval import PRODUCTS

        payload = dict(
            salts=PRODUCTS,
            targets={'K': 150, 'N_NO3': 40, 'P': 25},
            water={},
            target_ph=5.8,
            final_volume_litres=1000,
            deviation_ranges=dict(percent=2.0),
        )
        self.assertEqual(execute('workflow', payload).deviation_ranges, dict(percent=2.0))

    def test_a_range_option_is_read_as_percent_or_mg_per_l_per_side(self):
        from flahax.batch_cli import parse_range

        self.assertEqual(
            parse_range('K=2%:5%'), ('K', dict(shortage_percent=2.0, excess_percent=5.0))
        )
        self.assertEqual(parse_range('Ca=:4mg'), ('Ca', dict(excess_mg_per_l=4.0)))
        for bad in ('K', 'K=2%', '=2%:3%', 'K=2:3%', 'K=a%:3%'):
            with self.subTest(bad=bad):
                with self.assertRaises(DeliveryError):
                    parse_range(bad)

    def test_the_batch_command_takes_the_range_options(self):
        import json
        import tempfile
        from pathlib import Path

        from flahax.batch_cli import main

        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'batch'
            main(
                [
                    '--formula',
                    'Tomato (Howard Resh)',
                    '--water',
                    'ro',
                    '--range-percent',
                    '5',
                    '--range',
                    'K=2%:',
                    '--output',
                    str(out),
                ]
            )
            summary = json.loads((out / 'summary.json').read_text())
        ranges = {r['symbol']: r for r in summary['deviation_ranges']['effective']}
        self.assertEqual(ranges['K']['shortage'], {'percent': 2.0})
        self.assertEqual(ranges['K']['excess'], {'percent': 5.0})
        self.assertEqual(summary['deviation_ranges']['mode'], 'assess')


if __name__ == '__main__':
    unittest.main()
