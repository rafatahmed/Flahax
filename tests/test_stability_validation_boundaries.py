# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Incomplete or inconsistent synthetic observations cannot establish stability."""

import copy
import unittest

from flahax.batch_stability import assess_batch_stability
from flahax.stock_evidence import assess_stock_evidence
from tests.test_batch_stability import observations, old_records
from tests.test_stock_evidence import reference_recipe


class StabilityValidationBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipe = copy.deepcopy(reference_recipe())
        cls.recipe['stock_verification'] = assess_stock_evidence(cls.recipe, old_records())
        cls.recipe['verified'] = cls.recipe['stock_verification']['verified']
        cls.evidence = observations(cls.recipe)

    def test_invalid_record_shapes_and_measurement_bounds_are_rejected(self):
        cases = (
            ((), {}),
            (('assignment',), {}),
            (('policy',), {}),
            (('policy', 'required_hours'), [0, 0]),
            (('policy', 'maximum_delay_hours'), 24),
            (('policy', 'minimum_retention_fraction'), 1.01),
            (('protocol',), {}),
            (('protocol', 'filter_pore_um'), 0.5),
            (('protocol', 'turbidity_sample'), 'filtered'),
            (('observations',), []),
            (('observations', 1), {}),
            (('observations', 1, 'sampled_at'), 24),
            (('observations', 1, 'sampled_at'), '2020-01-01T00:00:00'),
            (('observations', 1, 'sampled_at'), self.evidence['observations'][0]['sampled_at']),
            (('observations', 1, 'ph_measurement'), {}),
            (
                ('observations', 1, 'ph_measurement', 'measured_at'),
                self.evidence['observations'][0]['sampled_at'],
            ),
            (('observations', 0, 'ph_measurement', 'measured_ph'), 6.29),
            (('observations', 1, 'turbidity_ntu'), {}),
            (('observations', 1, 'turbidity_ntu', 'uncertainty_basis'), 'standard_error'),
            (('observations', 1, 'turbidity_ntu', 'value'), 1e308),
            (('observations', 1, 'volume_litres', 'value'), 0),
            (('observations', 1, 'dissolved_calcium_mg_l', 'value'), 1e308),
            (('observations', 0, 'dissolved_calcium_mg_l', 'value'), 0),
        )
        for path, value in cases:
            record = copy.deepcopy(self.evidence)
            if path:
                target = record
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                if path == ('observations', 1, 'turbidity_ntu', 'value'):
                    target['absolute_uncertainty'] = 1e308
            else:
                record = value
            with self.subTest(path=path):
                result = assess_batch_stability(self.recipe, record)
                self.assertEqual(result['status'], 'invalid_evidence', result)
                self.assertFalse(result['stable'])

    def test_initial_volume_outside_preparation_bound_fails_stability(self):
        record = copy.deepcopy(self.evidence)
        record['observations'][0]['volume_litres']['value'] = 9.9
        result = assess_batch_stability(self.recipe, record)
        self.assertEqual(result['status'], 'not_stable')
        self.assertIn('initial_volume', result['observation_checks'][0]['failed_checks'])
