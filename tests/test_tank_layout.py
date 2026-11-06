# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The A/B tank layout (decisions G20-G22): micronutrients and calcium in A, the rest in B."""

import json
from types import SimpleNamespace
import unittest

from flahax import group_tanks, summarize_batch
from flahax.grower_report import _extra_tank_note
from flahax.tank_grouping import CLASS_RULES, MICRO_PHOSPHATE
from tests.test_grower_outputs import PACKAGED, PACKAGED_PRODUCTS, workflow

BY_NAME = {p['name']: p for p in PACKAGED_PRODUCTS}
MICROS = (
    'Iron EDTA',
    'Mn EDTA',
    'Zn EDTA',
    'Copper EDTA',
    'Iron DTPA',
    'Boric Acid',
    'Sodium Molybdate (Dihydrate)',
    'Micro Combi Mix 2',
    'Zinc Sulfate (Monohydrate)',
    'Copper Sulfate (pentahydrate)',
    'Iron II Sulfate (Hepahydrate)',
)
TANK_B = (
    'Magnesium Sulfate (Heptahydrate)',
    'Potassium Monobasic Phosphate',
    'Potassium Sulfate',
    'Ammonium Monobasic Phosphate',
)


def rows(*names, dose=0.1):
    return [dict(id=BY_NAME[n]['id'], name=n, gramsPerLitre=dose) for n in names]


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.grouping = group_tanks(
            rows('Calcium Nitrate (ag grade)', 'Potassium Nitrate', *MICROS, *TANK_B),
            PACKAGED_PRODUCTS,
        )

    def test_two_tanks_with_micronutrients_and_calcium_in_a(self):
        self.assertEqual([t.name for t in self.grouping.tanks], ['A', 'B'])
        for name in ('Calcium Nitrate (ag grade)', *MICROS):
            with self.subTest(product=name):
                self.assertEqual(self.grouping.tank_of(name), 'A')

    def test_magnesium_sulfate_goes_with_the_phosphates_in_b(self):
        for name in TANK_B:
            with self.subTest(product=name):
                self.assertEqual(self.grouping.tank_of(name), 'B')

    def test_micronutrient_sulfates_are_not_separated_from_calcium(self):
        pairs = {frozenset(p[:2]) for p in self.grouping.separations}
        for name in ('Zinc Sulfate (Monohydrate)', 'Copper Sulfate (pentahydrate)'):
            self.assertNotIn(frozenset((name, 'Calcium Nitrate (ag grade)')), pairs)

    def test_the_magnesium_phosphate_rule_is_gone_and_no_rule_names_gypsum(self):
        pairs = {frozenset(p[:2]) for p in self.grouping.separations}
        self.assertNotIn(
            frozenset(('Magnesium Sulfate (Heptahydrate)', 'Potassium Monobasic Phosphate')),
            pairs,
        )
        self.assertFalse([r for r in CLASS_RULES if 'magnesium' in r[:2]])
        text = json.dumps([CLASS_RULES, self.grouping.separations, MICRO_PHOSPHATE]).lower()
        self.assertNotIn('gypsum', text)
        self.assertIn(
            'calcium and sulfate precipitate in a concentrate', [r[2] for r in CLASS_RULES]
        )

    def test_calcium_nitrate_is_never_with_a_phosphate_or_a_macro_sulfate(self):
        calcium = self.grouping.tank_of('Calcium Nitrate (ag grade)')
        for name in TANK_B:
            self.assertNotEqual(self.grouping.tank_of(name), calcium, name)

    def test_micronutrients_stay_out_of_the_phosphate_tank(self):
        reasons = {p[2] for p in self.grouping.separations}
        self.assertIn(MICRO_PHOSPHATE, reasons)


class WithoutCalciumTests(unittest.TestCase):
    def test_magnesium_sulfate_still_joins_the_phosphate_and_micronutrients_stay_in_a(self):
        grouping = group_tanks(
            rows(
                'Magnesium Sulfate (Heptahydrate)',
                'Potassium Monobasic Phosphate',
                'Mn EDTA',
                'Potassium Nitrate',
                dose=0.5,
            ),
            PACKAGED_PRODUCTS,
        )
        self.assertEqual(grouping.tank_of('Mn EDTA'), 'A')
        self.assertEqual(grouping.tank_of('Potassium Monobasic Phosphate'), 'B')
        self.assertEqual(grouping.tank_of('Magnesium Sulfate (Heptahydrate)'), 'B')


class ThirdTankTests(unittest.TestCase):
    def test_a_batch_that_needs_more_tanks_names_the_pair_and_the_rule(self):
        flow = workflow('Lettuce 2 (Howard Resh)', library=PACKAGED)
        summary = summarize_batch(
            flow,
            PACKAGED_PRODUCTS,
            title='Lettuce',
            water_label='RO',
            available_tanks=1,
        )
        self.assertEqual(summary['tanks']['required_tanks'], 2)
        self.assertEqual(summary['status'], 'blocked')
        [note] = [w for w in summary['warnings'] if w.startswith('Stock assignment needs')]
        self.assertRegex(note, r'needs a second tank: .+ cannot share with .+ \(.+\)')
        # The precipitation screen may detect gypsum; the tank plan never names it.
        self.assertNotIn('gypsum', json.dumps(summary['tanks']).lower())
        self.assertNotIn('gypsum', note.lower())

    def test_a_caller_rule_forces_a_real_third_tank_and_the_note_names_it(self):
        flow = workflow('Tomato (Howard Resh)', library=PACKAGED)
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
        summary = summarize_batch(
            flow, PACKAGED_PRODUCTS, title='Tomato', water_label='RO', rules=[rule]
        )
        self.assertEqual(summary['tanks']['required_tanks'], 3)
        self.assertEqual(summary['status'], 'blocked')
        [note] = [w for w in summary['warnings'] if w.startswith('Stock assignment needs')]
        self.assertRegex(note, r'needs a third tank: .+ cannot share with .+ \(.+\)')

    def test_the_note_wording_for_a_third_tank_and_for_an_unnamed_pair(self):
        def tank(*names):
            return SimpleNamespace(products=[SimpleNamespace(name=n) for n in names])

        grouping = SimpleNamespace(
            tanks=[tank('P1'), tank('P2'), tank('P3')],
            separations=[
                ('P1', 'P2', 'rule zero'),
                ('P1', 'P3', 'rule one'),
                ('P2', 'P3', 'rule two'),
            ],
        )
        self.assertEqual(
            _extra_tank_note(grouping, 2),
            'Stock assignment needs a third tank: P3 cannot share with P1 (rule one). '
            'No separation is waived.',
        )
        self.assertTrue(
            _extra_tank_note(grouping, 1).startswith('Stock assignment needs a second')
        )
        grouping.separations = []
        self.assertEqual(
            _extra_tank_note(grouping, 2),
            'Stock assignment needs 3 tanks; only 2 supplied. No separation is waived.',
        )
        self.assertIn('fourth tank', _extra_tank_note(grouping_with(4), 3))
        self.assertIn('5th tank', _extra_tank_note(grouping_with(5), 4))


def grouping_with(count):
    names = [f'P{i}' for i in range(count)]
    return SimpleNamespace(
        tanks=[SimpleNamespace(products=[SimpleNamespace(name=n)]) for n in names],
        separations=[(names[-1], names[0], 'a rule')],
    )


if __name__ == '__main__':
    unittest.main()
