# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent allocation witnesses and a bounded public-workflow case matrix.

The oracle never calls the FlahaX allocator. It shares material interpretation and
speciation, then solves linear inventory equations by Gaussian elimination and a
one-dimensional charge bisection. Independent thermodynamics belongs to N2.
"""

from copy import deepcopy
import json
from pathlib import Path

from flahax.aqueous_model import solve
from flahax.product_conversion import material_inventory

ROOT = Path(__file__).resolve().parents[1]
LABELS = ('K', 'Ca', 'Mg', 'N_NO3', 'P', 'S')
BASES = ('K+', 'Ca+2', 'Mg+2', 'NO3-', 'PO4-3', 'SO4-2')
MASS = (39.0983, 40.078, 24.305, 14.0067, 30.973762, 32.06)
VALENCE = (1, 2, 2, 1, 1, 2)


def base_request(strength=1.2):
    req = json.loads((ROOT / 'examples/steiner-nutrient-reserve-search.json').read_text())
    for key in ('strength_range', 'scan_points', 'strength_tolerance'):
        req.pop(key)
    req['counted_mmol_l'] = strength
    return req


def remove_products(req, indices):
    req['products'] = [p for i, p in enumerate(req['products']) if i not in indices]
    names = {p['product']['name'] for p in req['products']}
    opts = req['uncertainty']
    opts['product_element_factors'] = {
        k: v for k, v in opts['product_element_factors'].items() if k in names
    }
    opts['physical_preparation']['product_solvent_fractions'] = {
        k: v
        for k, v in opts['physical_preparation']['product_solvent_fractions'].items()
        if k in names
    }


def cases():
    result = []
    for strength in (1.0, 1.1, 1.2, 1.26):
        result.append(
            (
                f'feasible_{strength}',
                'feasible',
                base_request(strength),
                'Independent nonnegative inventory/charge witness',
            )
        )
    for name, indices, zero, group, positive in (
        ('no_calcium', {1}, 'Ca+2', 'cation', 'K+'),
        ('no_magnesium', {2, 3}, 'Mg+2', 'cation', 'K+'),
        ('no_phosphate', {0, 4}, 'PO4-3', 'anion', 'NO3-'),
    ):
        req = base_request()
        remove_products(req, indices)
        req['water']['totals_mol_kg'][zero] = 0
        result.append(
            (
                name,
                'infeasible',
                req,
                f'{zero} has zero supply but positive required share; {group} '
                f'total must be zero, contradicting positive water {positive}',
            )
        )
    req = base_request()
    req['maximum_concentrations']['Na'] = 0.05
    result.append(
        (
            'water_sodium_ceiling',
            'infeasible',
            req,
            'Water alone supplies 0.068969307 mg/L Na > reserved ceiling 0.0475',
        )
    )
    req = base_request()
    clone = deepcopy(req['products'][1])
    old = clone['product']['name']
    clone['product']['name'] = 'Redundant calcium nitrate'
    req['products'].append(clone)
    opts = req['uncertainty']
    opts['product_element_factors'][clone['product']['name']] = deepcopy(
        opts['product_element_factors'][old]
    )
    opts['physical_preparation']['product_solvent_fractions'][clone['product']['name']] = [
        0.9799,
        0.98,
    ]
    result.append(
        (
            'redundant_calcium',
            'feasible',
            req,
            'Six-source independent witness extends by a zero dose for the redundant source',
        )
    )
    req = base_request()
    req['cation_shares'] = [50, 50, 0]
    result.append(
        (
            'zero_magnesium_share',
            'infeasible',
            req,
            'Zero target Mg contradicts positive source-water Mg; '
            'nonnegative doses cannot remove it',
        )
    )
    req = base_request()
    req['maximum_concentrations']['N_NO3'] = 0
    result.append(
        (
            'zero_nitrate_headroom',
            'infeasible',
            req,
            'Zero nitrate-N ceiling contradicts positive source-water nitrate',
        )
    )
    req = base_request(0.001)
    result.append(
        (
            'water_above_count',
            'infeasible',
            req,
            'Water supplies 0.0097 mmol/L counted nutrients > requested count 0.001',
        )
    )
    return result


def linear_solve(matrix, rhs):
    """Small independent pivoted elimination, not NNLS or FlahaX root finding."""
    rows = [list(a) + [b] for a, b in zip(matrix, rhs)]
    n = len(rhs)
    for j in range(n):
        pivot = max(range(j, n), key=lambda i: abs(rows[i][j]))
        rows[j], rows[pivot] = rows[pivot], rows[j]
        assert abs(rows[j][j]) > 1e-14, 'singular independent witness equations'
        scale = rows[j][j]
        rows[j] = [x / scale for x in rows[j]]
        for i in range(n):
            if i == j:
                continue
            scale = rows[i][j]
            rows[i] = [a - scale * b for a, b in zip(rows[i], rows[j])]
    return [row[-1] for row in rows]


def independent_witness(req):
    """Find a nominal feasible witness without invoking recipe allocation."""
    sources = req['products'][:6]
    inv = [material_inventory(p['product']) for p in sources]
    volume = req['volume_litres']
    water_mass = req['water_mass_kg']
    source_mass = req['water']['source_water_mass_kg']
    wt = req['water']['totals_mol_kg']
    background = [wt[b] * source_mass / volume * 1000 for b in BASES]
    coefficients = [
        [x['nutrient_percent'].get(k, 0) * 10 / volume / m for x in inv]
        for k, m in zip(LABELS, MASS)
    ]
    rows = []
    rhs = []
    for offset, raw in ((0, req['cation_shares']), (3, req['anion_shares'])):
        shares = [v / sum(raw) for v in raw]
        for j in range(2):
            rows.append(
                [
                    coefficients[offset + j][p] * VALENCE[offset + j]
                    - shares[j]
                    * sum(coefficients[offset + i][p] * VALENCE[offset + i] for i in range(3))
                    for p in range(6)
                ]
            )
            rhs.append(
                -(
                    background[offset + j] * VALENCE[offset + j]
                    - shares[j]
                    * sum(background[offset + i] * VALENCE[offset + i] for i in range(3))
                )
            )
    rows += [[sum(coefficients[i][p] for i in range(6)) for p in range(6)], [0, 0, 0, 0, 0, 1]]
    rhs += [req['counted_mmol_l'] - sum(background), 0]
    source_charge = (
        solve(wt, req['water']['measured_ph']).charge_balance * source_mass / water_mass
    )

    def trial(base_g):
        doses = linear_solve(rows, rhs[:-1] + [base_g])
        totals = {k: v * source_mass / water_mass for k, v in wt.items()}
        for g, inventory in zip(doses, inv):
            for k, v in inventory['components_moles_per_gram'].items():
                totals[k] = totals.get(k, 0) + g * v / water_mass
        if min(doses) < 0 or any(v < 0 for v in totals.values()):
            return None
        charge = solve(totals, req['ph']).charge_balance - source_charge
        return doses, totals, charge

    previous = None
    for i in range(81):
        x = i / 40
        value = trial(x)
        if value is not None and previous is not None and previous[1][2] * value[2] <= 0:
            low, high = previous[0], x
            break
        if value is not None:
            previous = (x, value)
    else:
        raise AssertionError('No independent nonnegative charge bracket')
    left = trial(low)[2]
    for _ in range(50):
        mid = (low + high) / 2
        value = trial(mid)
        if value[2] * left > 0:
            low = mid
            left = value[2]
        else:
            high = mid
    doses, totals, charge = trial((low + high) / 2)
    amounts = [
        b + sum(c * g for c, g in zip(row, doses)) for b, row in zip(background, coefficients)
    ]
    assert abs(sum(amounts) - req['counted_mmol_l']) < 1e-10
    assert abs(charge) < 1e-12 and min(doses) >= 0
    maxima = {
        phase: max(solve(totals, ph).saturation_indices[phase] for ph in (6.28, 6.30, 6.32))
        for phase in ('CaHPO4:2H2O', 'CaHPO4', 'Hydroxylapatite')
    }
    assert all(si < -0.3000001 for si in maxima.values())
    return {
        'grams': doses + ([0.0] if len(req['products']) == 7 else []),
        'analytical_mmol_l': dict(zip(LABELS, amounts)),
        'charge_error_mol_kg': charge,
        'linear_residual_max': max(
            abs(sum(a * g for a, g in zip(row, doses)) - b) for row, b in zip(rows[:-1], rhs[:-1])
        ),
        'nominal_phase_maxima': maxima,
        'scope': (
            'Independent inventory/charge allocation; '
            'shared material interpretation and speciation; '
            'uncertainty is checked by public workflow separately'
        ),
    }


def infeasibility_certificate(case):
    """Check a necessary linear condition, independently of the allocator."""
    name, expected, req, explanation = case
    assert expected == 'infeasible'
    wt = req['water']['totals_mol_kg']
    inventories = [material_inventory(p['product'])['nutrient_percent'] for p in req['products']]
    ratio = req['water']['source_water_mass_kg'] / req['volume_litres']
    if name in ('no_calcium', 'no_magnesium', 'no_phosphate'):
        element, basis, group, index, positive = {
            'no_calcium': ('Ca', 'Ca+2', 'cation_shares', 1, 'K+'),
            'no_magnesium': ('Mg', 'Mg+2', 'cation_shares', 2, 'K+'),
            'no_phosphate': ('P', 'PO4-3', 'anion_shares', 1, 'NO3-'),
        }[name]
        assert wt[basis] == 0 and all(p.get(element, 0) == 0 for p in inventories)
        assert req[group][index] > 0 and wt[positive] > 0
        detail = {
            'zero_supply': element,
            'required_share': req[group][index],
            'positive_group_water_component': positive,
        }
    elif name == 'zero_magnesium_share':
        assert req['cation_shares'][2] == 0 and wt['Mg+2'] > 0
        detail = {'water_Mg_mmol_l': wt['Mg+2'] * ratio * 1000, 'required_Mg': 0}
    elif name == 'water_above_count':
        water_count = sum(wt[b] for b in BASES) * ratio * 1000
        assert water_count > req['counted_mmol_l']
        detail = {'water_count_mmol_l': water_count, 'target': req['counted_mmol_l']}
    else:
        key, basis, mass = (
            ('Na', 'Na+', 22.989769)
            if name == 'water_sodium_ceiling'
            else ('N_NO3', 'NO3-', 14.0067)
        )
        water_amount = wt[basis] * ratio * 1000 * mass
        cap = req['maximum_concentrations'][key] * (1 - req['nutrient_ceiling_reserve'])
        assert water_amount > cap
        detail = {'element': key, 'water_mg_l': water_amount, 'effective_ceiling': cap}
    return {
        'case': name,
        'explanation': explanation,
        'certificate': detail,
        'scope': (
            'Nonnegative addition cannot remove existing inventory; '
            'necessary linear constraints already contradict'
        ),
    }
