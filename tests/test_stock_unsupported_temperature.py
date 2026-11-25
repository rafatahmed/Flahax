# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""A stock plan keeps its quantities when the evidence does not cover the temperature
(D5, D6, contract Q21).

The assignment and concentrations are returned, the unsupported aspect is stated, and
nothing is labelled verified or approved on the missing evidence. A limit that is known
and exceeded still fails.
"""

import unittest

from flahax import (
    DeliveryError,
    InjectionRatio,
    StockTank,
    TemperatureCelsius,
    VolumeLitres,
    plan_stocks,
)
from tests.test_stock_assignments import synthetic_model
from tests.test_stock_planning import limits, recipe, rule

TANKS = [StockTank('A', VolumeLitres(2)), StockTank('B', VolumeLitres(2))]


def plan(temperature, *, limit_records=None, model=None):
    return plan_stocks(
        recipe(),
        InjectionRatio(100),
        TANKS,
        [rule()],
        limits() if limit_records is None else limit_records,
        TemperatureCelsius(temperature),
        mixture_model=model,
    )


class UnsupportedTemperatureTests(unittest.TestCase):
    def test_quantities_are_kept_when_the_temperature_is_outside_every_recorded_range(self):
        stock = plan(40)
        self.assertEqual(
            sorted((s.salt_id, s.concentration.value) for t in stock.tanks for s in t.salts),
            [('calcium-nitrate', 50.0), ('phosphate', 25.0)],
        )
        self.assertEqual(len(stock.tanks), 2)  # the separation rule is still applied

    def test_the_unsupported_aspects_are_stated_per_product(self):
        unverified = plan(40).unverified
        self.assertEqual([u['salt_id'] for u in unverified], ['calcium-nitrate', 'phosphate'])
        first = unverified[0]
        self.assertEqual(first['aspect'], 'solubility_limit')
        self.assertEqual(first['requested_temperature_c'], 40)
        self.assertEqual(first['recorded_ranges_c'], [[10, 30]])

    def test_a_product_with_no_limit_record_at_all_has_no_recorded_range(self):
        only_calcium = [r for r in limits() if r['productId'] == 'calcium-nitrate']
        (unverified,) = plan(20, limit_records=only_calcium).unverified
        self.assertEqual(unverified['salt_id'], 'phosphate')
        self.assertEqual(unverified['recorded_ranges_c'], [])

    def test_nothing_is_approved_or_qualified_on_unsupported_evidence(self):
        stock = plan(40, model=synthetic_model)
        self.assertFalse(stock.mixture_approved)
        self.assertEqual(stock.status, 'requires_review')

    def test_a_supported_temperature_has_nothing_unverified(self):
        self.assertEqual(plan(20).unverified, ())

    def test_a_known_limit_that_is_exceeded_still_fails(self):
        with self.assertRaises(DeliveryError) as caught:
            plan(20, limit_records=limits(calcium_limit=10))
        self.assertEqual(caught.exception.code, 'solubility_exceeded')

    def test_limit_ids_list_only_the_limits_that_were_used(self):
        self.assertEqual(plan(40).solubility_limit_ids, ())
        self.assertEqual(len(plan(20).solubility_limit_ids), 2)


if __name__ == '__main__':
    unittest.main()
