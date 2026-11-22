# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Ambiguous custom product names cannot silently alter a pH recommendation (P2)."""

from copy import deepcopy
import unittest

from flahax import VolumeLitres, load_library, plan_fertilizer_workflow, solve_weights
from flahax.composition import InputError
from flahax.delivery_contracts import DeliveryError
from flahax.product_conversion import catalogue_dose_totals


def products():
    library = load_library()['salts']
    pair = [deepcopy(next(p for p in library if p['formula'] == f)) for f in ('KH2PO4', 'KNO3')]
    for i, product in enumerate(pair):
        product.update(id=f'custom-collision-{i}', name='Shared custom product')
    return pair


class ProductNameCollisionTests(unittest.TestCase):
    def test_direct_fit_rejects_ambiguous_product_names(self):
        with self.assertRaisesRegex(InputError, 'Ambiguous product name'):
            solve_weights(products(), {'K': 150, 'N_NO3': 40, 'P': 25}, {})

    def test_direct_chemistry_rejects_both_sequence_and_mapping_collisions(self):
        pair = products()
        for supplied in (pair, {p['id']: p for p in pair}):
            with self.subTest(container=type(supplied).__name__):
                with self.assertRaises(DeliveryError) as caught:
                    catalogue_dose_totals({'Shared custom product': 0.1}, products=supplied)
                self.assertEqual(caught.exception.code, 'ambiguous_product_name')
                for product in pair:
                    self.assertIn(product['id'], str(caught.exception))

    def test_workflow_reports_both_products_before_ambiguous_ph_calculation(self):
        for pair in (products(), list(reversed(products()))):
            with self.subTest(order=[p['id'] for p in pair]):
                with self.assertRaises(InputError) as caught:
                    plan_fertilizer_workflow(
                        pair,
                        {'K': 150, 'N_NO3': 40, 'P': 25},
                        {},
                        5.8,
                        final_volume=VolumeLitres(1000),
                    )
                message = str(caught.exception)
                for identity in (
                    'Shared custom product',
                    'custom-collision-0',
                    'custom-collision-1',
                ):
                    self.assertIn(identity, message)


if __name__ == '__main__':
    unittest.main()
