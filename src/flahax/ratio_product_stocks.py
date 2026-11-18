# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Volumetric delivery of declared products with pure-water stock
carrier.
"""

import math

from .delivery_contracts import DeliveryError
from .ratio_stocks import prepare_stock_delivery, validate_stocks


def validate_product_stocks(options, sources, uncertainty):
    """Require product-mass concentrations and explicit stock density
    intervals.
    """
    extra = {'basis', 'density_kg_l', 'carrier'}
    if (
        not isinstance(options, dict)
        or not extra <= options.keys()
        or options['basis'] != 'product_mass'
        or options['carrier'] != 'demineralized_water'
        or uncertainty.get('mode') != 'water_product_elemental'
        or uncertainty.get('water_mass_model') != 'closed_batch_mass_balance'
    ):
        raise DeliveryError(
            'invalid_product_stock_dosing',
            'Use product_mass g/L, demineralized_water carrier and elemental closed-batch bounds',
        )
    names = [row['name'] for row in sources]
    validate_stocks({k: v for k, v in options.items() if k not in extra}, names)
    densities = options['density_kg_l']
    if not isinstance(densities, dict) or set(densities) != set(names):
        raise DeliveryError('invalid_product_stock_dosing', 'Bound every stock density in kg/L')
    for name, pair in densities.items():
        if (
            not isinstance(pair, (list, tuple))
            or len(pair) != 2
            or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in pair
            )
            or not 0 < pair[0] <= pair[1]
        ):
            raise DeliveryError('invalid_product_stock_dosing', 'Invalid stock density interval')
        if (
            options['concentrations_g_l'][name] * (1 + options['concentration_relative_error'])
            > 1000 * pair[0]
        ):
            raise DeliveryError(
                'invalid_product_stock_dosing', 'Product mass exceeds minimum total stock mass'
            )


def prepare_product_stocks(recipe, options, uncertainty):
    """Round mL doses and retain separate product assay and delivery
    uncertainty.
    """
    adapter = dict(
        recipe,
        ingredients=[
            dict(formula=row['name'], grams=row['grams']) for row in recipe['ingredients']
        ],
    )
    result = prepare_stock_delivery(adapter, options, uncertainty['volume_error_litres'])
    maximum_mass = 0.0
    for row in result['stocks']:
        name = row.pop('formula')
        row['name'] = name
        row['density_kg_l_bounds'] = options['density_kg_l'][name]
        minimum_carrier = (
            (row['dose_ml'] - row['dose_error_ml'])
            * (
                options['density_kg_l'][name][0]
                - row['concentration_g_l'] * (1 + options['concentration_relative_error']) / 1000
            )
            / 1000
        )
        if row['effective_grams_bounds'][-1] > 0:
            minimum_carrier -= uncertainty['weighing_error_g'] / 1000
        if minimum_carrier < 0:
            raise DeliveryError(
                'ratio_stock_carrier_infeasible',
                'Stock mass cannot contain the product delivery bounds and weighing allowance',
            )
        row['minimum_carrier_mass_kg'] = minimum_carrier
        maximum_mass += (
            (row['dose_ml'] + row['dose_error_ml']) * (options['density_kg_l'][name][1]) / 1000
        )
    result['maximum_stock_mass_kg'] = maximum_mass
    result['concentration_basis'] = (
        'Grams of supplied product per litre of final stock, before product assay factors. '
        'Stock concentration and dispenser bounds are additional to the declared product '
        'weighing allowance; product elemental/ingredient assay bounds remain separate. '
        'All stock carrier is demineralized water. Density bounds constrain total input mass; '
        'carrier replaces pure make-up water and does not add nutrients.'
    )
    result['preparation'] = (
        'One separately prepared stock per declared product, including pH reagents. '
        'Make up to final batch volume including all stock doses. Stock storage stability, '
        'reactive impurities and physical verification remain outside this calculation.'
    )
    return result


def product_mass_bounds(row, options):
    """Combine the delivered product interval with the retained weighing
    allowance.
    """
    dose = row['grams']
    low, high = row.get('stock_product_mass_bounds_g', (dose, dose))
    error = options['weighing_error_g'] if high > 0 else 0
    return low - error, high + error
