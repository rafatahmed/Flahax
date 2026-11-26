# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""An acceptable pH interval as a target (contract Q31, finding C5).

``target_ph=(low, high)`` is evaluated against its bounds. No midpoint is invented:
a mix already inside the interval needs no reagent, and a mix outside it is moved to
the nearest bound, the smallest change that qualifies. The point target is unchanged.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from flahax import (
    DeliveryError,
    VolumeLitres,
    catalogue_ph_reagents,
    load_library,
    plan_fertilizer_workflow,
    summarize_batch,
)
from flahax.batch_request import BatchOptions, run_batch
from flahax.batch_cli import main
from flahax.report_html import render_report
from flahax.requirement_fit import PH_TOLERANCE
from tests.test_water_workflow import inputs
from tests.test_water_workflow import products as water_products

PRODUCTS = [p for p in load_library()['salts'] if p['formula'] == 'KH2PO4']
REAGENTS = [p for p in catalogue_ph_reagents() if p['chemicalFormula'] == 'KOH']
EQUILIBRIUM = dict(
    water_totals={},
    water_mass_kg=1000,
    water_analysis_id='declared-ion-free',
    carbon_boundary='closed',
    temperature_c=25,
    phases=[],
)


def plan(target_ph, **changes):
    request = dict(
        final_volume=VolumeLitres(1000),
        equilibrium=EQUILIBRIUM,
        ph_adjustment=dict(
            products=REAGENTS, maximum_reagent_volume_litres=5, correct_mixed_ph=True
        ),
    )
    return plan_fertilizer_workflow(
        PRODUCTS, {'K': 150, 'N_NO3': 40, 'P': 25}, {}, target_ph, **(request | changes)
    )


def selected(workflow):
    return workflow.stages['ph_adjustment'].value


class PhIntervalPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.point_57 = selected(plan(5.7))
        cls.point_60 = selected(plan(6.0))
        cls.outside = plan((5.7, 6.0))
        cls.inside = plan((5.0, 5.3))

    def test_a_mix_inside_the_interval_needs_no_reagent(self):
        result = selected(self.inside)
        self.assertEqual(result.direction, 'none')
        self.assertEqual(result.selected.reagent_volume_litres, 0.0)
        self.assertEqual(result.selected.status, 'not_needed')
        self.assertEqual(result.interval, (5.0, 5.3))
        self.assertTrue(5.0 <= result.unadjusted_ph <= 5.3)

    def test_a_mix_outside_the_interval_is_moved_to_the_nearest_bound_not_the_midpoint(self):
        result = selected(self.outside)
        self.assertEqual(result.interval, (5.7, 6.0))
        self.assertEqual(result.target_ph, 5.7)
        self.assertNotEqual(result.target_ph, 5.85)
        self.assertEqual(result.direction, 'base')

    def test_the_nearest_bound_uses_the_same_reagent_as_that_point_target(self):
        chosen = selected(self.outside).selected
        reference = self.point_57.selected
        self.assertAlmostEqual(
            chosen.reagent_volume_litres, reference.reagent_volume_litres, places=9
        )
        self.assertLess(chosen.reagent_volume_litres, self.point_60.selected.reagent_volume_litres)

    def test_the_achieved_ph_is_inside_the_interval(self):
        final = selected(self.outside).selected.target.ph
        self.assertTrue(5.7 - PH_TOLERANCE <= final <= 6.0 + PH_TOLERANCE)

    def test_a_zero_width_interval_is_the_point_target(self):
        same = selected(plan((5.8, 5.8)))
        point = selected(plan(5.8))
        self.assertEqual(same.target_ph, point.target_ph)
        self.assertEqual(same.direction, point.direction)
        self.assertAlmostEqual(
            same.selected.reagent_volume_litres, point.selected.reagent_volume_litres, places=9
        )

    def test_the_workflow_reports_the_aimed_ph_after_planning(self):
        self.assertEqual(self.outside.target_ph, 5.7)
        self.assertEqual(self.outside.ph_interval, (5.7, 6.0))
        self.assertIsNone(plan((5.7, 6.0), equilibrium=None, ph_adjustment=None).target_ph)

    def test_invalid_intervals_are_refused(self):
        cases = {
            'invalid_value': [(6.0, 5.7), (5.7,), (5.7, 5.8, 5.9), ('a', 6.0), (True, 6.0)],
            'out_of_range': [(-1.0, 6.0), (5.0, 15.0), (float('nan'), 6.0), (5.0, float('inf'))],
        }
        for code, intervals in cases.items():
            for interval in intervals:
                with self.subTest(interval=interval):
                    with self.assertRaises(DeliveryError) as raised:
                        plan(interval)
                    self.assertEqual(raised.exception.code, code)


class LegacyStageTests(unittest.TestCase):
    def test_a_single_purpose_stage_does_not_silently_pick_a_point(self):
        water, curve, reagent = inputs()
        workflow = plan_fertilizer_workflow(
            [water_products()[5]],
            {'K': 10},
            water['ions'],
            (6.0, 6.5),
            final_volume=VolumeLitres(100),
            titration=dict(
                water_analysis=water,
                curve=curve,
                reagent=reagent,
                maximum_reagent_volume=VolumeLitres(1),
            ),
        )
        stage = workflow.stages['titration']
        self.assertEqual((stage.status, stage.error_code), ('blocked', 'unsupported_ph_interval'))
        self.assertIn('ph_adjustment', stage.message)


class PhIntervalReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        flow = plan((5.7, 6.0))
        cls.summary = summarize_batch(flow, PRODUCTS, title='T', water_label='RO')
        cls.report = render_report(cls.summary).split('<pre id="flahax-result-data">')[0]

    def test_the_summary_carries_the_interval_and_the_bound_it_aimed_at(self):
        self.assertEqual(self.summary['target_ph_interval'], [5.7, 6.0])
        self.assertEqual(self.summary['target_ph'], 5.7)
        self.assertEqual(self.summary['ph']['interval']['aimed_at'], 5.7)

    def test_the_report_states_the_interval_and_invents_no_midpoint(self):
        self.assertIn('5.7', self.report)
        self.assertIn('6', self.report)
        self.assertIn('nearest bound', self.report)
        self.assertNotIn('5.85', self.report)

    def test_a_point_summary_has_no_interval(self):
        point = summarize_batch(plan(5.8), PRODUCTS, title='T', water_label='RO')
        self.assertIsNone(point['target_ph_interval'])
        self.assertIsNone(point['ph']['interval'])


class PhIntervalInterfaceTests(unittest.TestCase):
    def test_the_json_workflow_accepts_an_interval(self):
        from flahax.planning_cli import execute

        payload = dict(
            salts=PRODUCTS,
            targets={'K': 150, 'N_NO3': 40, 'P': 25},
            water={},
            target_ph=[5.7, 6.0],
            final_volume_litres=1000,
        )
        self.assertEqual(execute('workflow', payload).ph_interval, (5.7, 6.0))

    def test_batch_takes_both_bounds_or_neither(self):
        base = dict(water='ro', formula='Tomato (Howard Resh)')
        for changes in ({'ph_min': 5.7}, {'ph_max': 6.0}):
            with self.subTest(changes=changes):
                with self.assertRaises(DeliveryError) as raised:
                    run_batch(BatchOptions(**(base | changes)))
                self.assertEqual(raised.exception.code, 'invalid_value')

    def test_the_command_refuses_a_point_with_an_interval_or_half_an_interval(self):
        base = ['--formula', 'Tomato (Howard Resh)', '--water', 'ro']
        for extra in (
            ['--ph', '5.8', '--ph-min', '5.7', '--ph-max', '6.0'],
            ['--ph-min', '5.7'],
            ['--ph-max', '6.0'],
        ):
            with self.subTest(extra=extra):
                with (
                    contextlib.redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit) as raised,
                ):
                    main(base + extra)
                self.assertEqual(raised.exception.code, 2)

    def test_the_command_takes_an_interval(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'batch'
            main(
                [
                    '--formula',
                    'Tomato (Howard Resh)',
                    '--water',
                    'ro',
                    '--ph-min',
                    '5.7',
                    '--ph-max',
                    '6.0',
                    '--output',
                    str(out),
                ]
            )
            summary = json.loads((out / 'summary.json').read_text())
        self.assertEqual(summary['target_ph_interval'], [5.7, 6.0])


if __name__ == '__main__':
    unittest.main()
