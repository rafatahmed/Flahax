# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Calibration records must have unambiguous identities and bounded errors."""

import unittest

from flahax.stock_evidence import assess_stock_evidence
from tests.test_stock_evidence import records, reference_recipe


class CalibrationValidationBoundaryTests(unittest.TestCase):
    def test_invalid_stock_records_cannot_verify_preparation(self):
        for path, value in (
            (('assignments',), {}),
            (('assays',), {}),
            (('assays', 0), None),
            (('assays', 0, 'unexpected'), 1),
            (('assays', 0, 'measured_concentration_g_l'), True),
            (('assignments', 'KH2PO4'), {}),
            (('assignments', 'KOH', 'stock_id'), 'stock-0'),
        ):
            evidence = records()
            target = evidence
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path):
                result = assess_stock_evidence(reference_recipe(), evidence)
                self.assertFalse(result['verified'])
                self.assertTrue(result['failures'])
        evidence = records()
        assignment = evidence['assignments']['KH2PO4']
        assignment['assay_record_id'], assignment['calibration_record_id'] = (
            assignment['calibration_record_id'],
            assignment['assay_record_id'],
        )
        result = assess_stock_evidence(reference_recipe(), evidence)
        self.assertFalse(result['verified'])
        self.assertEqual(result['stock_checks'][0]['status'], 'failed')

    def test_ph_records_reject_extra_fields_duplicate_ids_and_unbounded_errors(self):
        for change in ('extra', 'same_id', 'buffer_shape', 'duplicate_buffer', 'overflow'):
            evidence = records()
            batch = evidence['batch_ph']
            calibration = batch['calibration']
            if change == 'extra':
                calibration['unexpected'] = 1
            elif change == 'same_id':
                batch['assignment']['measurement_record_id'] = calibration['record_id']
                batch['measurement']['record_id'] = calibration['record_id']
            elif change == 'buffer_shape':
                calibration['buffers'][0] = {}
            elif change == 'duplicate_buffer':
                calibration['buffers'][1]['reference'] = calibration['buffers'][0]['reference']
            else:
                calibration['maximum_absolute_bias_ph'] = 1e308
                calibration['absolute_uncertainty_ph'] = 1e308
            with self.subTest(change=change):
                result = assess_stock_evidence(reference_recipe(), evidence)
                self.assertFalse(result['verified'])
                self.assertEqual(result['batch_ph_check']['status'], 'failed')
