#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Explicit fixed-pH mixed catalogue chemistry and a precipitation example."""

from flahax import (
    convert_catalogue_product_dose,
    solve_catalogue_product_doses,
    calculate_equilibrium_ph,
)
from .common import catalogue, rejection, show


def run():
    products = catalogue()
    doses = {
        'Calcium Nitrate (ag grade)': 0.15,
        'Magnesium Sulfate (Heptahydrate)': 0.10,
        'Potassium Monobasic Phosphate': 0.05,
        'Potassium Nitrate': 0.10,
        'Iron DTPA': 0.004,
        'Iron EDDHA': 0.003,
        'Mn EDTA': 0.002,
        'Boric Acid': 0.002,
        'Sodium Molybdate (Dihydrate)': 0.0001,
        'Urea': 0.005,
    }
    # Fixed pH is an imposed boundary, not a predicted pH of this recipe.
    mixed = solve_catalogue_product_doses(
        doses, 6.0, water_totals={'Na+': 0.002, 'Cl-': 0.002}, allow_precipitation=False
    )
    # A dilute calcium/phosphate mixture with an imposed pH boundary.
    precipitation = solve_catalogue_product_doses(
        {'Calcium Nitrate (ag grade)': 0.4, 'Potassium Monobasic Phosphate': 0.1},
        7.4,
        allow_precipitation=True,
    )
    return dict(
        assumptions=[
            'Synthetic fixed-pH demonstrations, not the pepper mixture.',
            'Product doses are g/kg-water, NOT g/L.',
            'Aqueous-only SI diagnoses risk; positive SI is not an allocated solid.',
            'Precipitation allocation uses a separate dilute calcium/phosphate case.',
        ],
        catalogue_conversions_at_001_g_per_kg_water={
            name: convert_catalogue_product_dose(product, 0.01)
            for name, product in products.items()
        },
        product_doses_g_per_kg_water=doses,
        mixed=mixed.aqueous,
        precipitation=precipitation.aqueous,
        expected_davies_rejection=rejection(
            lambda: calculate_equilibrium_ph(
                {'Na+': 0.2, 'Cl-': 0.2},
                complete_analysis=True,
                carbon_boundary='closed',
                phases=[],
            )
        ),
    )


if __name__ == '__main__':
    show(run())
