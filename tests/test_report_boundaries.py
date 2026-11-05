# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Legacy report inputs cannot promote missing evidence or failed constraints."""

import unittest
from unittest.mock import patch
from flahax import DeliveryError, VolumeLitres, load_library, plan_fertilizer_workflow
from flahax import grower_report as report
from flahax.stock_solubility import SolubilityRow


class ReportBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.pool = [p for p in load_library()['salts'] if p['formula'] == 'KNO3']
        self.flow = plan_fertilizer_workflow(
            self.pool,
            {'K': 10, 'N_NO3': 10 * 14.0067 / 39.0983},
            {},
            6.5,
            final_volume=VolumeLitres(100),
        )
        # Explicit legacy fixture: mutated stages have no canonical identity.
        self.flow.canonical_result = None

    def summary(self, flow=None, **kw):
        return report.summarize_batch(
            flow or self.flow, self.pool, title='Legacy test', water_label='RO', **kw
        )

    def test_missing_batch_and_invalid_tank_count_refuse_report(self):
        for count in (0, True, '2'):
            with self.assertRaises(DeliveryError) as caught:
                self.summary(available_tanks=count)
            self.assertEqual(caught.exception.code, 'invalid_value')
        del self.flow.stages['batch']
        with self.assertRaises(DeliveryError) as caught:
            self.summary()
        self.assertEqual(caught.exception.code, 'missing_field')

    def test_absent_ph_plan_preserves_review_or_block(self):
        del self.flow.stages['ph_adjustment']
        self.assertEqual(self.summary()['status'], 'requires_review')
        self.flow.stages['formulation'].status = 'blocked'
        self.assertEqual(self.summary()['status'], 'blocked')

    def test_structural_tanks_cannot_promote_a_stage_to_ready(self):
        self.flow.stages['ph_adjustment'].status = 'calculated'
        self.flow.stages['formulation'].status = 'calculated'
        self.assertEqual(self.summary()['status'], 'requires_review')
        self.flow.stages['formulation'].status = 'requires_review'
        self.flow.stages['formulation'].message = 'External review concern'
        self.assertEqual(self.summary()['status'], 'requires_review')

    def test_qualified_solubility_failure_blocks_and_ok_does_not_approve_mixture(self):
        self.flow.stages['ph_adjustment'].status = 'calculated'
        row = SolubilityRow('A', self.pool[0]['name'], 100, 50, 'exceeds', 'synthetic')
        for status, expected in [('exceeds', 'blocked'), ('ok', 'requires_review')]:
            from dataclasses import replace

            with patch.object(
                report, 'check_stock_solubility', return_value=[replace(row, status=status)]
            ):
                self.assertEqual(self.summary()['status'], expected)

    def test_laboratory_decision_change_is_visible_and_requires_review(self):
        self.flow.stages['ph_adjustment'].status = 'calculated'
        self.flow.stages['formulation'].status = 'calculated'
        water, limits = report._water_and_limits(self.flow, self.flow.recommendation)
        limits.append(
            dict(
                symbol='Na',
                decision='within_limit',
                analyticalPpm=1,
                maximumPpm=2,
                balancingChangesDecision=True,
                note='Synthetic laboratory/model limit difference',
            )
        )
        with patch.object(report, '_water_and_limits', return_value=(water, limits)):
            summary = self.summary()
        self.assertEqual(summary['status'], 'requires_review')
        self.assertIn(limits[0]['note'], summary['warnings'])

    def test_long_plot_labels_wrap_without_dropping_words(self):
        label = 'A product label with several words beyond the available single line width'
        svg = report.bars('Test', [label], [('Values', [1])], 'g')
        for word in label.split():
            self.assertIn(word, svg)
        self.assertGreater(svg.count('<text x="12"'), 1)


class ReportCalculationFailureTests(unittest.TestCase):
    def test_ec_failure_keeps_a_partial_report_without_a_total_estimate(self):
        from tests.test_ph_adjustment import RO

        pool = [p for p in load_library()['salts'] if p['formula'] == 'KNO3']
        flow = plan_fertilizer_workflow(
            pool,
            {'K': 10},
            {},
            6.5,
            final_volume=VolumeLitres(100),
            equilibrium=RO | {'water_mass_kg': 100},
        )
        with patch.object(
            report,
            'calculate_ec_from_totals',
            side_effect=DeliveryError('not_supported', 'Injected EC refusal'),
        ):
            summary = report.summarize_batch(flow, pool, title='Test', water_label='RO')
        self.assertEqual(summary['ec']['status'], 'not_supported')
        self.assertIsNone(summary['ec']['ec25_ms_cm'])
        self.assertIn('Injected EC refusal', summary['ec']['message'])
