# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The glossary and ``group_tanks`` agree: more than two tanks are allowed, and the
effective assignment is in the result (D7, contract Q22).

Choice recorded: the glossary describes the multi-group behavior of ``group_tanks``;
the code is not constrained to a fixed A/B.
"""

import unittest

from flahax import summarize_batch
from tests.test_glossary_stock_terms import GLOSSARY, entry
from tests.test_grower_outputs import PACKAGED, PACKAGED_PRODUCTS, workflow

BY_NAME = {p['name']: p for p in PACKAGED_PRODUCTS}


def three_tank_summary():
    rule = dict(
        schemaVersion='0.1',
        id='test-calcium-manganese',
        source='test',
        revision='1',
        recordedAt='2026-10-22T00:00:00Z',
        productIds=[BY_NAME['Calcium Nitrate (ag grade)']['id'], BY_NAME['Mn EDTA']['id']],
        constraint='separate',
        reason='test separation',
        temperatureMinC=0,
        temperatureMaxC=50,
    )
    flow = workflow('Tomato (Howard Resh)', library=PACKAGED)
    return summarize_batch(
        flow, PACKAGED_PRODUCTS, title='Tomato', water_label='RO', rules=[rule], available_tanks=3
    )


class EffectiveAssignmentTests(unittest.TestCase):
    def test_a_grouping_beyond_two_tanks_shows_every_group_in_the_result(self):
        tanks = three_tank_summary()['tanks']
        self.assertEqual(tanks['required_tanks'], 3)
        self.assertEqual([t['name'] for t in tanks['tanks']], ['A', 'B', 'C'])
        self.assertTrue(all(t['products'] for t in tanks['tanks']))

    def test_every_dosed_product_is_in_exactly_one_group(self):
        tanks = three_tank_summary()['tanks']['tanks']
        placed = [p['id'] for t in tanks for p in t['products']]
        self.assertEqual(len(placed), len(set(placed)))
        self.assertIn(BY_NAME['Mn EDTA']['id'], placed)

    def test_the_glossary_says_the_assignment_may_exceed_two_tanks(self):
        text = entry('Tank A / Tank B')
        self.assertIn('more than two', text)
        self.assertIn('tanks.tanks', text)

    def test_the_glossary_choice_is_recorded_in_its_stock_assignment_entry(self):
        self.assertIn('fewest tanks', entry('Stock assignment'))
        self.assertNotIn('fixed A/B', GLOSSARY)


if __name__ == '__main__':
    unittest.main()
