# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""N1: independently witnessed cases through the public recipe interface."""

from copy import deepcopy
import random
import unittest

from flahax import plan_ratio_recipe
from flahax.delivery_contracts import DeliveryError
from flahax.product_conversion import material_inventory
from tests.ratio_allocation_cases import (
    cases,
    independent_witness,
    infeasibility_certificate,
    BASES,
    LABELS,
    MASS,
)


def orderings(count):
    base = list(range(count))
    result = [base, base[::-1], base[1:] + base[:1], base[2:] + base[:2]]
    for seed in (7, 19):
        order = base[:]
        random.Random(seed).shuffle(order)
        result.append(order)
    assert len({tuple(x) for x in result}) == 6
    return result


def exercise(case, order_index=0):
    name, expected, request, _proof = case
    req = deepcopy(request)
    order = orderings(len(req['products']))[order_index]
    req['products'] = [req['products'][i] for i in order]
    witness = independent_witness(request) if expected == 'feasible' else None
    certificate = infeasibility_certificate(case) if expected == 'infeasible' else None
    try:
        result = plan_ratio_recipe(**req)
    except DeliveryError as exc:
        assert expected == 'infeasible', (name, order_index, exc.code, str(exc))
        assert exc.code.startswith('ratio_'), (name, exc.code)
        return {
            'case': name,
            'order': order,
            'expected': expected,
            'status': 'passed',
            'solver_error': exc.code,
            'certificate': certificate,
            'qualification': (
                'Infeasibility follows from the independent certificate, '
                'not the local solver error'
            ),
        }
    assert expected == 'feasible', (name, 'infeasible input returned a recipe')
    rounded = result['rounded_verification']
    check = result['uncertainty_verification']
    assert rounded['status'] == 'passed', (name, order_index, rounded['status'])
    assert check['status'] == 'passed', (name, order_index, check['failed_checks'])
    assert check['scenario_count'] == 128, (name, check['scenario_count'])
    assert all(x['complete'] for x in check['ph_refinement']['scenarios'])
    assert check['all_scenario_ph_in_range']
    assert result['nutrient_ceiling_reserve']['fraction'] == 0.05
    assert check['worst_ratio_relative_error'] <= 0.01 + 1e-10
    assert check['worst_concentration_relative_error'] <= 0.02
    assert set(check['phase_maxima']) == {'CaHPO4:2H2O', 'CaHPO4', 'Hydroxylapatite'}
    assert all(x['si'] < -0.3000001 for x in check['phase_maxima'].values())
    for k, limits in check['elemental_mg_l_ranges'].items():
        assert limits[1] <= req['maximum_concentrations'][k] * 0.95, (name, k, limits)
    # Direct elemental sum is independent of recipe allocation/reconstruction.
    totals = {
        k: req['water']['totals_mol_kg'][b]
        * req['water']['source_water_mass_kg']
        / req['volume_litres']
        * 1000
        * m
        for k, b, m in zip(LABELS, BASES, MASS)
    }
    for row in rounded['ingredients']:
        percentages = material_inventory(row['product'])['nutrient_percent']
        for k in LABELS:
            totals[k] += row['grams'] / req['volume_litres'] * 10 * percentages.get(k, 0)
    for k in LABELS:
        assert abs(totals[k] - rounded['elemental_mg_l'][k]) < 1e-10, (name, k)
    counted = [totals[k] / mass for k, mass in zip(LABELS, MASS)]
    assert abs(sum(counted) / req['counted_mmol_l'] - 1) <= 0.001
    equivalents = [v * z for v, z in zip(counted, (1, 2, 2, 1, 1, 2))]
    for values, target in (
        (equivalents[:3], req['cation_shares']),
        (equivalents[3:], req['anion_shares']),
    ):
        for actual, share in zip(values, target):
            assert abs(actual / sum(values) - share / sum(target)) <= 1e-5
    assert abs(result['charge_closure_error_mol_kg']) <= 1e-10
    return {
        'case': name,
        'order': order,
        'expected': expected,
        'status': 'passed',
        'independent_witness': witness,
        'request': req,
        'allocation_evidence': result['allocation_evidence'],
        'rounded_grams': {x['name']: x['grams'] for x in rounded['ingredients']},
        'counted_mmol_l': rounded['counted_mmol_l'],
        'ratio_error': check['worst_ratio_relative_error'],
        'count_error': check['worst_concentration_relative_error'],
        'nutrient_ranges': check['elemental_mg_l_ranges'],
        'phase_maxima': check['phase_maxima'],
        'scenario_count': check['scenario_count'],
        'ph_evaluations': check['ph_refinement']['total_ph_evaluations'],
        'charge_closure_error': result['charge_closure_error_mol_kg'],
        'independent_elemental_mg_l': totals,
    }


class AllocationReliabilityTests(unittest.TestCase):
    pass


def install(case):
    def test(self):
        for index in range(6 if case[1] == 'feasible' else 1):
            with self.subTest(order=index):
                exercise(case, index)

    setattr(AllocationReliabilityTests, 'test_' + case[0].replace('.', '_'), test)


for _case in cases():
    install(_case)
