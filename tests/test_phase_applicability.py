# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Synthetic evidence envelopes test policy logic, not physical applicability."""

from copy import deepcopy
from types import SimpleNamespace
import math
import unittest

from flahax.aqueous_model import chemistry
from flahax.delivery_contracts import DeliveryError
from flahax.saturation_policy import SI_THRESHOLD, assess_saturation, describe


def sample(phase='MnHPO4', si=1.0, solid=0):
    return SimpleNamespace(
        saturation_indices={phase: si},
        precipitated={phase: solid},
        totals={},
        ph=6.0,
        ionic_strength=0.01,
    )


def record(phase):
    return {
        'phase': phase,
        'reviewed': True,
        'source': 'Synthetic policy-test evidence only',
        'review_id': 'synthetic-review',
        'decision': 'review_only',
        'conditions': {
            'temperature_c': [25, 25],
            'ph': [5, 7],
            'ionic_strength': [0, 0.02],
            'holding_time_hours': [0, 1],
            'redox': 'declared-test-redox',
            'matrix_id': 'synthetic-matrix',
        },
    }


CONDITIONS = {
    'temperature_c': 25,
    'holding_time_hours': 0.5,
    'redox': 'declared-test-redox',
    'matrix_id': 'synthetic-matrix',
}


class ApplicabilityTests(unittest.TestCase):
    def test_review_vs_hard_phases_without_and_with_evidence(self):
        from flahax.saturation_policy import REVIEW

        for row in chemistry()['phases']:
            phase = row['name']
            with self.subTest(phase=phase):
                missing = assess_saturation(sample(phase))
                if phase in REVIEW:
                    self.assertFalse(missing['blocks'])
                    self.assertTrue(missing['review'])
                else:
                    self.assertTrue(missing['blocks'])
                matching = assess_saturation(
                    sample(phase), conditions=CONDITIONS, evidence={phase: record(phase)}
                )
                self.assertFalse(matching['blocks'])
                self.assertFalse(matching['mixing_approved'])
                self.assertEqual(
                    matching['applicability'][phase]['status'], 'applicable_for_review'
                )
                self.assertTrue(matching['review'])

    def test_missing_outside_and_wrong_phase_evidence_keeps_review_only_for_mn_hpo4(self):
        # MnHPO4 stays REVIEW-class (#78): missing/out-of-envelope evidence does not hard-block.
        phase = 'MnHPO4'
        variants = [
            (None, CONDITIONS),
            ({phase: record(phase)}, {}),
            ({phase: record(phase)}, {**CONDITIONS, 'holding_time_hours': 2}),
            ({phase: record('Vivianite')}, CONDITIONS),
        ]
        for evidence, conditions in variants:
            with self.subTest(evidence=evidence, conditions=conditions):
                result = assess_saturation(sample(), conditions=conditions, evidence=evidence)
                self.assertFalse(result['blocks'])
                self.assertFalse(result['mixing_approved'])
                self.assertTrue(result['review'])

    def test_state_conditions_override_caller_and_boundaries_are_inclusive(self):
        # Hard phase: out-of-envelope evidence cannot demote CaHPO4 off the block list.
        evidence = {'CaHPO4': record('CaHPO4')}
        state = sample(phase='CaHPO4')
        state.ph = 8
        result = assess_saturation(state, conditions={**CONDITIONS, 'ph': 6}, evidence=evidence)
        self.assertTrue(result['blocks'])
        for value in (0, 1):
            self.assertFalse(
                assess_saturation(
                    sample(phase='CaHPO4'),
                    conditions={**CONDITIONS, 'holding_time_hours': value},
                    evidence=evidence,
                )['blocks']
            )
        self.assertTrue(
            assess_saturation(
                sample(phase='CaHPO4'),
                conditions={**CONDITIONS, 'holding_time_hours': math.nextafter(1.0, math.inf)},
                evidence=evidence,
            )['blocks']
        )

    def test_uncertain_sign_does_not_become_kinetic_permission(self):
        for si in (-SI_THRESHOLD, 0, SI_THRESHOLD):
            result = assess_saturation(
                sample(si=si), conditions=CONDITIONS, evidence={'MnHPO4': record('MnHPO4')}
            )
            self.assertTrue(result['blocks'])
            self.assertEqual(result['thermodynamic']['MnHPO4']['status'], 'uncertain_sign')
        self.assertFalse(assess_saturation(sample(si=-2 * SI_THRESHOLD))['blocks'])
        self.assertTrue(
            assess_saturation(sample(si=0.1), si_uncertainty={'MnHPO4': 0.2})['blocks']
        )

    def test_allocated_solids_override_matching_evidence_and_negative_si(self):
        for amount in (1e-15, 1e-6):
            result = assess_saturation(
                sample(si=-1, solid=amount),
                conditions=CONDITIONS,
                evidence={'MnHPO4': record('MnHPO4')},
            )
            self.assertTrue(result['blocks'])
            self.assertEqual(result['solids']['MnHPO4'], amount)
        for amount in (-1, math.nan, math.inf, True):
            result = assess_saturation(sample(solid=amount))
            self.assertTrue(result['blocks'])
            self.assertTrue(result['invalid_solids'])
            self.assertTrue(any('invalid solid' in line for line in describe(result)))

    def test_nonfinite_indices_and_invalid_uncertainty_fail_closed(self):
        for si in (math.nan, math.inf, True, 'invalid'):
            self.assertTrue(assess_saturation(sample(si=si))['blocks'])
        self.assertFalse(assess_saturation(sample(si=-math.inf))['blocks'])
        for widths in ({'MnHPO4': -1}, {'MnHPO4': math.nan}, {'MnHPO4': True}, {'other': 0}):
            with self.assertRaises(DeliveryError):
                assess_saturation(sample(), si_uncertainty=widths)
        for kw in ({'conditions': []}, {'evidence': []}, {'si_uncertainty': []}):
            with self.assertRaises(DeliveryError):
                assess_saturation(sample(), **kw)

    def test_malformed_or_unreviewed_envelopes_cannot_exempt_hard_phases(self):
        phase = 'CaHPO4'
        for field, value in (
            ('reviewed', False),
            ('source', ''),
            ('review_id', ''),
            ('decision', 'approve'),
            ('conditions', {}),
        ):
            item = record(phase)
            item[field] = value
            self.assertTrue(
                assess_saturation(
                    sample(phase=phase), conditions=CONDITIONS, evidence={phase: item}
                )['blocks']
            )
        for constraint in ([2, 1], [0], [0, math.inf], None):
            item = deepcopy(record(phase))
            item['conditions']['holding_time_hours'] = constraint
            self.assertTrue(
                assess_saturation(
                    sample(phase=phase), conditions=CONDITIONS, evidence={phase: item}
                )['blocks']
            )

    def test_unknown_conditions_and_interval_overflow_cannot_qualify(self):
        phase = 'CaHPO4'
        for key, value in (
            ('temperature_c', '25'),
            ('redox', 'unknown'),
            ('matrix_id', 'unspecified'),
        ):
            item = record(phase)
            item['conditions'][key] = value
            result = assess_saturation(
                sample(phase=phase),
                conditions={**CONDITIONS, key: value},
                evidence={phase: item},
            )
            self.assertTrue(result['blocks'])
        result = assess_saturation(sample(si=1e308), si_uncertainty={'MnHPO4': 1e308})
        self.assertTrue(result['blocks'])
        self.assertEqual(result['thermodynamic']['MnHPO4']['status'], 'invalid_interval')

    def test_invalid_measurements_and_extra_conditions_fail_closed(self):
        for value in (True, float('nan'), 'unmeasured'):
            result = assess_saturation(
                sample(),
                conditions={**CONDITIONS, 'holding_time_hours': value},
                evidence={'MnHPO4': record('MnHPO4')},
            )
            self.assertEqual(result['applicability']['MnHPO4']['status'], 'invalid_conditions')
        result = assess_saturation(
            sample(),
            conditions={**CONDITIONS, 'redox': 'different'},
            evidence={'MnHPO4': record('MnHPO4')},
        )
        self.assertEqual(
            result['applicability']['MnHPO4']['status'], 'outside_evidence_conditions'
        )
        item = record('MnHPO4')
        item['conditions']['extra_source_condition'] = None
        result = assess_saturation(
            sample(),
            conditions={**CONDITIONS, 'extra_source_condition': 'present'},
            evidence={'MnHPO4': item},
        )
        self.assertEqual(
            result['applicability']['MnHPO4']['status'], 'invalid_evidence_conditions'
        )
