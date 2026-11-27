# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Composed delivery plans reject inconsistent evidence (#348, roadmap H5).

Two layers are covered. The stage planners (``plan_ph``, ``plan_pump_command``) refuse mismatched
record ids, changed assays, bad titration curves and stale or unusable calibrations. The
composer (``compose_delivery_plan``, ``delivery_report``) refuses stage values whose own fields
contradict each other, for example a pH plan changed after it was planned. A stage value does not
keep the records it came from, so a plan altered consistently cannot be detected here; that
limit is part of the contract.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import math
import unittest

from flahax import DeliveryError, VolumeLitres
from flahax.delivery_plan import compose_delivery_plan, delivery_report
from flahax.delivery_quantities import DurationMinutes, MassGrams, MilliEquivalentsPerLitre
from flahax.ph_planning import plan_ph
from flahax.pump_planning import plan_pump_command
from tests import test_delivery_plan
from tests.test_ph_planning import inputs
from tests.test_pump_planning import CALIBRATION_AS_OF, calibration

RECORDED = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)  # 12:00 at +03:00


class PhRecordRejectionTests(unittest.TestCase):
    """plan_ph refuses inconsistent water, curve and reagent records."""

    CASES = (
        ('curve names another water analysis', lambda w, c, r: c.update(waterAnalysisId='x')),
        ('curve names another reagent', lambda w, c, r: c.update(reagentId='x')),
        ('an acid curve with a base reagent', lambda w, c, r: r.update(kind='base')),
        ('an unknown reagent kind', lambda w, c, r: r.update(kind='zzz')),
        ('reagent strength zero', lambda w, c, r: r.update(normalityMeqPerL=0)),
        ('reagent strength negative', lambda w, c, r: r.update(normalityMeqPerL=-5)),
        ('reagent density zero', lambda w, c, r: r.update(densityKgPerL=0)),
        ('reagent assay implausibly large', lambda w, c, r: r.update(elements={'N_NO3': 1380.0})),
        ('reagent assay above 100 percent', lambda w, c, r: r.update(elements={'N_NO3': 500})),
        ('reagent assay negative', lambda w, c, r: r.update(elements={'N_NO3': -5})),
        ('reagent assay empty', lambda w, c, r: r.update(elements={})),
        ('reagent assay names an unknown ion', lambda w, c, r: r.update(elements={'Zz': 5})),
        (
            'curve repeats a pH',
            lambda w, c, r: c.update(
                points=[{'demandMeqPerL': 0, 'pH': 7.4}, {'demandMeqPerL': 1.2, 'pH': 7.4}]
            ),
        ),
        (
            'curve is not monotone',
            lambda w, c, r: c.update(
                points=[
                    {'demandMeqPerL': 0, 'pH': 7.4},
                    {'demandMeqPerL': 1.2, 'pH': 6.0},
                    {'demandMeqPerL': 0.5, 'pH': 5.0},
                ]
            ),
        ),
        (
            'curve demand negative',
            lambda w, c, r: c.update(
                points=[{'demandMeqPerL': -1, 'pH': 7.4}, {'demandMeqPerL': 1.2, 'pH': 6.0}]
            ),
        ),
        (
            'curve has one point',
            lambda w, c, r: c.update(points=[{'demandMeqPerL': 0, 'pH': 7.4}]),
        ),
        (
            'curve demand is NaN',
            lambda w, c, r: c.update(
                points=[
                    {'demandMeqPerL': float('nan'), 'pH': 7.4},
                    {'demandMeqPerL': 1.2, 'pH': 6.0},
                ]
            ),
        ),
        ('water temperature missing', lambda w, c, r: w.pop('temperatureC')),
        ('water pH missing', lambda w, c, r: w.pop('pH')),
        ('water pH beyond the scale', lambda w, c, r: w.update(pH=15)),
        ('water alkalinity negative', lambda w, c, r: w.update(alkalinityMgLAsCaCO3=-5)),
        ('water id blank', lambda w, c, r: w.update(id=' ')),
        ('water record time unreadable', lambda w, c, r: w.update(recordedAt='yesterday')),
        ('water schema unsupported', lambda w, c, r: w.update(schemaVersion='9.9')),
        ('water revision missing', lambda w, c, r: w.pop('revision')),
    )

    def test_each_inconsistent_record_is_refused_with_a_delivery_error(self):
        for label, change in self.CASES:
            with self.subTest(label):
                water, curve, reagent = inputs()
                change(water, curve, reagent)
                with self.assertRaises(DeliveryError) as raised:
                    plan_ph(
                        water,
                        curve,
                        reagent,
                        6.7,
                        VolumeLitres(100),
                        VolumeLitres(1),
                        {'N_NO3': 100},
                        {'N_NO3': 111.592},
                    )
                self.assertTrue(raised.exception.code)

    def test_mismatched_ids_use_their_own_code(self):
        for change in (
            lambda w, c, r: c.update(waterAnalysisId='x'),
            lambda w, c, r: c.update(reagentId='x'),
            lambda w, c, r: r.update(kind='base'),
        ):
            water, curve, reagent = inputs()
            change(water, curve, reagent)
            with self.assertRaises(DeliveryError) as raised:
                plan_ph(water, curve, reagent, 6.7, VolumeLitres(100), VolumeLitres(1), {}, {})
            self.assertEqual(raised.exception.code, 'mismatched_record')

    def test_the_unchanged_records_still_plan(self):
        water, curve, reagent = inputs()
        plan = plan_ph(water, curve, reagent, 6.7, VolumeLitres(100), VolumeLitres(1), {}, {})
        self.assertAlmostEqual(plan.reagent_volume_litres, 0.006)


class CalibrationRejectionTests(unittest.TestCase):
    """plan_pump_command refuses stale, future and unusable calibrations."""

    def plan(self, change=lambda c: None, as_of=CALIBRATION_AS_OF, **options):
        record = calibration()
        change(record)
        return plan_pump_command(
            record, VolumeLitres(0.12), VolumeLitres(1), as_of=as_of, **options
        )

    def code(self, **kwargs):
        with self.assertRaises(DeliveryError) as raised:
            self.plan(**kwargs)
        return raised.exception.code

    def test_the_age_limit_is_inclusive_and_beyond_it_is_stale(self):
        self.plan(as_of=RECORDED + timedelta(days=30))
        self.assertEqual(
            self.code(as_of=RECORDED + timedelta(days=30, minutes=1)), 'stale_calibration'
        )
        self.assertEqual(
            self.code(as_of=CALIBRATION_AS_OF + timedelta(days=60)), 'stale_calibration'
        )
        self.assertEqual(self.code(max_calibration_age_days=0), 'stale_calibration')

    def test_a_calibration_from_the_future_is_refused(self):
        self.assertEqual(
            self.code(change=lambda c: c.update(recordedAt='2027-01-01T00:00:00Z')),
            'future_calibration',
        )

    def test_unusable_records_and_limits_are_refused(self):
        cases = (
            (lambda c: c.update(recordedAt='2026-09-25T12:00:00'), 'invalid_value'),
            (lambda c: c.update(recordedAt='soon'), 'invalid_value'),
            (lambda c: c.pop('recordedAt'), 'missing_field'),
            (lambda c: c.update(channelId=' '), 'invalid_value'),
            (lambda c: c.update(id=''), 'invalid_value'),
            (lambda c: c.update(flowLitresPerMinute=0), 'out_of_range'),
            (lambda c: c.update(flowLitresPerMinute=float('nan')), 'invalid_value'),
            (lambda c: c.update(standardDeviationLitresPerMinute=-1), 'out_of_range'),
            (lambda c: c.update(validMinLitres=5, validMaxLitres=1), 'out_of_range'),
            (lambda c: c.update(schemaVersion='2'), 'unsupported_schema'),
            (lambda c: c.update(stockDensityKgPerL=0), 'out_of_range'),
        )
        for change, code in cases:
            with self.subTest(code=code):
                self.assertEqual(self.code(change=change), code)

    def test_a_bad_age_limit_is_refused(self):
        for limit in (float('nan'), -1):
            with self.subTest(limit=limit):
                self.assertEqual(self.code(max_calibration_age_days=limit), 'out_of_range')


class ComposedPlanRejectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = test_delivery_plan.DeliveryPlanTests().make_plan()
        water, curve, reagent = inputs()
        cls.ph = plan_ph(
            water,
            curve,
            reagent,
            6.7,
            cls.base.recipe.final_volume,
            VolumeLitres(1),
            {'N_NO3': 100},
            {'N_NO3': 111.592},
        )
        cls.audit = {'modelVersion': 'test'}

    def compose(self, ph_plan=None, **changes):
        plan = replace(self.base, **changes)
        return compose_delivery_plan(
            plan.recipe,
            plan.stocks,
            self.ph if ph_plan is None else ph_plan,
            plan.commands,
            plan.audit_record,
        )

    def test_the_unaltered_plan_composes(self):
        plan = self.compose()
        self.assertEqual(plan.state, 'draft')
        self.assertIs(plan.ph_plan, self.ph)

    def test_a_ph_plan_that_contradicts_itself_is_refused(self):
        ph = self.ph
        cases = {
            'a positive volume with zero mass': replace(ph, reagent_mass=MassGrams(0.0)),
            'a positive volume with zero demand': replace(
                ph, demand=MilliEquivalentsPerLitre(0.0)
            ),
            'an unknown direction': replace(ph, direction='sideways'),
            'a blank water analysis id': replace(ph, water_analysis_id=' '),
            'a missing reagent id': replace(ph, reagent_id=''),
            'a blank curve id': replace(ph, titration_curve_id=''),
            'a non-string channel id': replace(ph, reagent_channel_id=None),
            'a target beyond the scale': replace(ph, target_ph=99.0),
            'a NaN target': replace(ph, target_ph=float('nan')),
            'a NaN loss': replace(ph, loss=float('nan')),
            'no measurement after mixing': replace(ph, post_mix_measurement_required=False),
        }
        for label, altered in cases.items():
            with self.subTest(label):
                with self.assertRaises(DeliveryError) as raised:
                    self.compose(ph_plan=altered)
                self.assertEqual(raised.exception.code, 'cross_stage_constraint')

    def test_a_zero_volume_pH_plan_is_still_a_valid_no_reagent_plan(self):
        zero = replace(self.ph, reagent_volume_litres=0, reagent_mass=MassGrams(0.0))
        self.assertEqual(self.compose(ph_plan=zero).state, 'draft')

    def test_a_pump_command_that_cannot_describe_a_run_is_refused(self):
        command = self.base.commands[0]
        cases = {
            'a blank calibration id': replace(command, calibration_id=' '),
            'zero runtime': replace(command, runtime=DurationMinutes(0.0)),
            'NaN uncertainty': replace(command, volume_uncertainty=_NanVolume()),
        }
        for label, altered in cases.items():
            with self.subTest(label):
                with self.assertRaises(DeliveryError) as raised:
                    self.compose(commands=(altered,))
                self.assertEqual(raised.exception.code, 'cross_stage_constraint')

    def test_a_stock_plan_whose_approval_contradicts_its_status_is_refused(self):
        stocks = self.base.stocks
        cases = {
            'approved status without approval': replace(stocks, status='qualified'),
            'approval with a review status': replace(stocks, mixture_approved=True),
            'an unknown status': replace(stocks, status='garbage'),
            'approval with an incomplete search': replace(
                stocks, status='qualified', mixture_approved=True, search_complete=False
            ),
            'approval with unverified limits': replace(
                stocks, status='qualified', mixture_approved=True, unverified=({'id': 'x'},)
            ),
            'approval with an incompatible assessment': replace(
                stocks,
                status='qualified',
                mixture_approved=True,
                mixture_assessments=({'status': 'incompatible'},),
            ),
        }
        for label, altered in cases.items():
            with self.subTest(label):
                with self.assertRaises(DeliveryError) as raised:
                    self.compose(stocks=altered)
                self.assertEqual(raised.exception.code, 'cross_stage_constraint')

    def test_an_approved_complete_stock_plan_composes(self):
        approved = replace(
            self.base.stocks,
            status='qualified',
            mixture_approved=True,
            unverified=(),
            search_complete=True,
            mixture_assessments=({'status': 'compatible'},),
        )
        self.assertTrue(self.compose(stocks=approved).stocks.mixture_approved)

    def test_a_report_revalidates_a_plan_changed_after_composition(self):
        plan = self.compose()
        self.assertIn('pH target: 6.7', delivery_report(plan))
        altered = replace(plan, ph_plan=replace(self.ph, post_mix_measurement_required=False))
        with self.assertRaises(DeliveryError):
            delivery_report(altered)

    def test_a_refused_composition_leaves_every_input_unchanged(self):
        base = self.base
        audit = dict(self.audit)
        before = (base.recipe, base.stocks, self.ph, base.commands, dict(audit))
        with self.assertRaises(DeliveryError):
            compose_delivery_plan(
                base.recipe,
                base.stocks,
                replace(self.ph, target_ph=99.0),
                base.commands,
                audit,
            )
        self.assertEqual(before, (base.recipe, base.stocks, self.ph, base.commands, audit))

    def test_the_composed_plan_keeps_its_own_copy_of_the_audit_record(self):
        audit = dict(self.audit)
        plan = compose_delivery_plan(
            self.base.recipe, self.base.stocks, self.ph, self.base.commands, audit
        )
        audit['modelVersion'] = 'changed afterwards'
        self.assertEqual(plan.audit_record['modelVersion'], 'test')
        self.assertTrue(math.isfinite(plan.ph_plan.reagent_volume_litres))


class EquilibriumPlanRejectionTests(unittest.TestCase):
    """The same field checks apply to the equilibrium pH plan."""

    @classmethod
    def setUpClass(cls):
        from tests import test_equilibrium_delivery as fixtures

        fixtures.EquilibriumDeliveryTests.setUpClass()
        cls.plan = fixtures.EquilibriumDeliveryTests().compose()

    def compose(self, ph_plan):
        p = self.plan
        return compose_delivery_plan(p.recipe, p.stocks, ph_plan, p.commands, p.audit_record)

    def test_the_unaltered_plan_composes(self):
        self.assertEqual(self.compose(self.plan.ph_plan).state, 'draft')

    def test_an_altered_equilibrium_plan_is_refused(self):
        ph = self.plan.ph_plan
        cases = {
            'a positive volume with zero mass': replace(ph, reagent_mass=MassGrams(0.0)),
            'a blank water analysis id': replace(ph, water_analysis_id=''),
            'a blank reagent id': replace(ph, reagent_id=' '),
            'a target below the scale': replace(ph, target_ph=-1.0),
            'an infinite loss': replace(ph, loss=float('inf')),
            'no measurement after mixing': replace(ph, post_mix_measurement_required=False),
        }
        for label, altered in cases.items():
            with self.subTest(label):
                with self.assertRaises(DeliveryError):
                    self.compose(altered)


class _NanVolume:
    """A stand-in for a volume whose value is NaN (VolumeLitres refuses to hold one)."""

    value = float('nan')


if __name__ == '__main__':
    unittest.main()
