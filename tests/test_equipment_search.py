# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Equipment-aware dose search (D4, contract Q19, Q20, Q27).

When the declared equipment cannot hold a recipe, an explicitly requested search
looks for product combinations that fit it. The equipment is never changed and no
separation rule is waived. The mode and the declared equipment are recorded in the
result, and nothing runs unless the search was asked for.
"""

import json
import unittest

from flahax import (
    InjectionRatio,
    StockTank,
    TemperatureCelsius,
    VolumeLitres,
    plan_fertilizer_workflow,
)
from flahax.evaluated_remedies import available_product_search
from tests.test_evaluated_remedies import product
from tests.test_stock_planning import record


def limit(product_id, grams_per_litre):
    return record(
        f'limit-{product_id}',
        productId=product_id,
        maxGramsPerLitre=grams_per_litre,
        temperatureMinC=10,
        temperatureMaxC=30,
    )


def stocks(tanks=(('A', 1.0),)):
    return dict(
        injection_ratio=InjectionRatio(100),
        tanks=[StockTank(name, VolumeLitres(litres)) for name, litres in tanks],
        temperature=TemperatureCelsius(20),
        compatibility_rules=[],
        solubility_limits=[limit('K', 250), limit('K50', 250)],
    )


def plan(options=(), **changes):
    # K at 1000 mg/L from a 10 % product is 10 g/L, a 1000 g/L stock at 1:100 and
    # above its 250 g/L limit; a 50 % product needs 2 g/L, a 200 g/L stock.
    request = dict(
        salts=[product('K', K=10)],
        targets={'K': 1000},
        water={},
        target_ph=5.5,
        final_volume=VolumeLitres(10),
        stocks=stocks(),
        remedy_options=options,
    )
    return plan_fertilizer_workflow(**(request | changes))


SEARCH = available_product_search([product('K50', K=50)], on_equipment_miss=True)


class EquipmentSearchTests(unittest.TestCase):
    def test_the_baseline_does_not_fit_the_declared_equipment(self):
        stage = plan().stages['stocks']
        self.assertIsNotNone(stage.error_code)

    def test_nothing_is_searched_unless_the_search_was_requested(self):
        result = plan()
        self.assertEqual(result.remedies['evaluations'], 0)
        self.assertEqual(result.remedies['mode'], 'analyze_supplied_doses')

    def test_an_equipment_miss_runs_the_requested_search_in_find_mode(self):
        result = plan([SEARCH])
        self.assertEqual(result.remedies['evaluations'], 1)
        self.assertEqual(result.remedies['mode'], 'find_suitable_doses')

    def test_the_search_leaves_the_declared_equipment_unchanged(self):
        result = plan([SEARCH])
        candidate = json.loads(result.remedies['options'][0]['snapshot'])
        baseline = json.loads(result.canonical_result.payload)
        self.assertEqual(candidate['inputs']['stocks'], baseline['inputs']['stocks'])
        declared = result.remedies['declared_equipment']
        self.assertEqual(declared['tanks'], [{'tank_id': 'A', 'capacity_litres': 1.0}])
        self.assertEqual(declared['injection_ratio'], 100)
        self.assertEqual(declared['temperature_c'], 20)

    def test_a_fitting_candidate_resolves_the_equipment_requirement(self):
        option = plan([SEARCH]).remedies['options'][0]
        self.assertIn('equipment:fit', option['resolved_requirements'])

    def test_equipment_that_already_fits_runs_no_search(self):
        fitted = dict(stocks(), solubility_limits=[limit('K', 2000)])
        result = plan([SEARCH], stocks=fitted)
        self.assertEqual(result.remedies['evaluations'], 0)
        self.assertEqual(result.remedies['mode'], 'analyze_supplied_doses')

    def test_a_search_that_finds_no_fit_keeps_the_original_and_the_requirement(self):
        hopeless = available_product_search([product('K20', K=20)], on_equipment_miss=True)
        result = plan([hopeless])
        self.assertIn('equipment:fit', {r['id'] for r in result.remedies['requirements']})
        self.assertIsNotNone(result.stages['stocks'].error_code)
        option = result.remedies['options'][0]
        self.assertNotIn('equipment:fit', option['resolved_requirements'])


if __name__ == '__main__':
    unittest.main()
