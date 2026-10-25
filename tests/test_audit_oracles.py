# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Validate independent audit witnesses and reject misleading qualifications."""

from fractions import Fraction
from types import SimpleNamespace
import unittest

from tests.audit_oracles import (
    carbon_free_phosphate_witness,
    competition_is_explicitly_qualified,
)


class AuditOracleTests(unittest.TestCase):
    def test_original_alkalinity_has_a_carbon_free_proton_inventory(self):
        alkalinity = Fraction('0.0008859033379310278')
        state = carbon_free_phosphate_witness(alkalinity)
        self.assertTrue(all(value >= 0 for value in state.values()))
        self.assertEqual(state['H2PO4'] + state['HPO4'], Fraction('0.001'))
        self.assertEqual(state['HPO4'] + state['OH'] - state['H'], alkalinity)
        self.assertEqual(
            state['Na'] + state['H'] - state['H2PO4'] - 2 * state['HPO4'] - state['OH'], 0
        )
        self.assertEqual(state['C'], 0)
        # This independent conservation assertion rejects any positive invented carbon.
        self.assertNotEqual(state['C'] + Fraction('0.000898'), 0)

    def test_prescribed_inventory_refuses_negative_species(self):
        for value in ('-1', '0.1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                carbon_free_phosphate_witness(value)

    def test_explicit_pair_qualification_and_rejection_of_generic_disclaimers(self):
        pair = ('Dtp-5', 'Cu+2')
        record = dict(code='omitted_competition', components=list(pair))
        self.assertTrue(
            competition_is_explicitly_qualified(SimpleNamespace(model_limitations=[record]), pair)
        )
        for invalid in (
            None,
            'accuracy not established',
            [],
            ['accuracy not established'],
            [dict(code='omitted_competition', components=['Dtp-5'])],
            [dict(code='omitted_competition', components=['Dtp-5', 'Fe+3'])],
            [dict(code='omitted_competition', components='Dtp-5 Cu+2')],
            [dict(code='unknown', components=list(pair))],
        ):
            with self.subTest(invalid=invalid):
                self.assertFalse(
                    competition_is_explicitly_qualified(
                        SimpleNamespace(model_limitations=invalid), pair
                    )
                )
        self.assertFalse(competition_is_explicitly_qualified(SimpleNamespace(), pair))


if __name__ == '__main__':
    unittest.main()
