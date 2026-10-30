#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""User-supplied pepper targets; do not invent a complete water analysis."""

from flahax import VolumeLitres, plan_fertilizer_workflow, solve_weights
from .common import catalogue, show
from .pepper_stock_review import review

TARGETS = dict(
    N_NO3=128,
    N_NH4=0,
    P=58,
    K=211,
    Ca=104,
    Mg=40,
    S=54,
    Fe=5,
    Mn=2,
    Zn=0.3,
    B=0.7,
    Cu=0.1,
    Mo=0.1,
    Na=0,
)
NAMES = [
    'Boric Acid',
    'Calcium Nitrate (ag grade)',
    'Iron II Sulfate (Hepahydrate)',
    'Mg Nitrate',
    'Mn EDTA',
    'Potassium Nitrate',
    'Copper Sulfate (pentahydrate)',
    'Potassium Sulfate',
    'Zinc Sulfate (Monohydrate)',
    'Sodium Molybdate (Dihydrate)',
    'Potassium Monobasic Phosphate',
    'Phosphoric Acid (75%)',
]


def run():
    products = catalogue()
    salts = [products[name] for name in NAMES]
    water = {ion: 20 if ion == 'Ca' else 0 for ion in TARGETS}
    workflow = plan_fertilizer_workflow(
        salts, TARGETS, water, 6.5, final_volume=VolumeLitres(1000)
    )
    assert workflow.nutrient_gap['Ca'] == 84
    assert workflow.stages['chemistry'].status == 'needs_input'
    return dict(
        assumptions=[
            '1000 L illustrative final batch; targets and water in mg/L.',
            'No invented chloride, alkalinity, acid density or measured titration curve.',
            'Catalogue Phosphoric Acid (75%) P assay needs commercial-grade confirmation.',
            'The explicit zero Na target prohibits sodium-carrying products; '
            'unavailable clean sources block the formulation.',
            'N_NH4 0 sets no ammonium requirement: incidental NH4-N from calcium nitrate '
            'is held within min(10 % of total N, 1.5 mmol/L), Dutch soilless practice '
            '(De Kreij, Voogt et al.).',
        ],
        targets_mg_per_l=TARGETS,
        water_mg_per_l=water,
        workflow=workflow,
        stock_allocation_review=review(workflow.recommendation, 1000),
        alternative_raw_least_squares=solve_weights(salts, TARGETS, water),
    )


if __name__ == '__main__':
    show(run())
