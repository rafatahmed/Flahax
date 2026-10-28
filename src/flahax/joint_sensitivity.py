# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Implicit charge derivatives of the selected, phase-free aqueous equations.

Mass-action, component balances, ionic strength and water activity are differentiated
simultaneously. No chemical coefficient or acceptance threshold is introduced.
"""

import math
from fractions import Fraction as F
from .aqueous_model import chemistry, LN10
from .delivery_contracts import DeliveryError


def _exact_linear(matrix, rhs):
    """Solve several right-hand sides without losing small balance contributions."""
    n = len(matrix)
    count = len(rhs[0])
    rows = [row.copy() + values.copy() for row, values in zip(matrix, rhs)]
    for k in range(n):
        pivot = max(range(k, n), key=lambda i: abs(rows[i][k]))
        rows[k], rows[pivot] = rows[pivot], rows[k]
        if not rows[k][k]:
            raise DeliveryError('unresolved_sensitivity', 'singular equilibrium sensitivity')
        for i in range(k + 1, n):
            factor = rows[i][k] / rows[k][k]
            for j in range(k + 1, n + count):
                rows[i][j] -= factor * rows[k][j]
    result = [[F(0)] * count for _ in range(n)]
    for i in range(n - 1, -1, -1):
        for c in range(count):
            result[i][c] = (
                rows[i][n + c] - sum(rows[i][j] * result[j][c] for j in range(i + 1, n))
            ) / rows[i][i]
    if any(
        sum(a * result[j][c] for j, a in enumerate(row)) != target[c]
        for row, target in zip(matrix, rhs)
        for c in range(count)
    ):
        raise DeliveryError('unresolved_sensitivity', 'sensitivity linear residual')
    return result


def equilibrium_charge_gradient(problem, state):
    """Return d(charge mol/kg solvent)/d(product g/L), in problem source order.

    This differentiates aqueous_model's fixed-pH, variable-I mass-action equations.
    Positive components use log activities; absent components use their one-sided
    free-activity limit. The active water-activity floor has zero water derivative.
    Selected phases and an ambiguous floor boundary are unsupported, not feasible
    or infeasible conclusions. The supplied equilibrium must be freshly qualified
    separately; this derivative is not a physical-applicability certificate.
    """
    sources = (*problem.fertilizers, problem.reagent)
    eq = state.get('equilibrium')
    if (
        eq is None
        or problem.phases
        or any(eq.precipitated.values())
        or any(s.components is None for s in sources)
    ):
        raise DeliveryError('unresolved_sensitivity', 'phase-free complete chemistry required')
    bases = list(dict.fromkeys([*eq.totals, *[b for s in sources for b in s.components]]))
    n = len(bases)
    dimension = n + 2
    strength, water = eq.ionic_strength, eq.water_activity
    if strength <= 0 or water <= 0:
        raise DeliveryError('unresolved_sensitivity', 'invalid equilibrium activity state')
    root = math.sqrt(strength)
    permitted = set(bases) | {'H+', 'H2O'}
    records = [
        r for r in chemistry()['aqueous'] if r['name'] != 'H2O' and set(r['powers']) <= permitted
    ]
    amount_sum = sum(F(eq.species.get(r['name'], 0)) for r in records)
    floor = water == 0.9
    if floor and amount_sum <= F(55.5084) * (1 - F(0.9)):
        raise DeliveryError('unresolved_sensitivity', 'water-activity floor boundary')
    derivatives = []
    for record in records:
        powers, z = record['powers'], record['charge']
        amount = F(eq.species.get(record['name'], 0))
        if amount in (F(1e-300), F(1e100)):
            raise DeliveryError('unresolved_sensitivity', 'mass-action clipping boundary')
        absent = [b for b in bases if b not in eq.totals and powers.get(b, 0)]
        partials = []
        for basis in bases:
            power = powers.get(basis, 0)
            if basis in eq.totals:
                partials.append(amount * F(power) * F(LN10))
            elif absent == [basis] and power == 1:
                log_gamma = (
                    -0.509 * z * z * (root / (1 + root) - 0.3 * strength) if z else 0.1 * strength
                )
                exponent = (
                    record['beta']
                    - problem.target_ph * powers.get('H+', 0)
                    + math.log10(water) * powers.get('H2O', 0)
                    - log_gamma
                    + math.fsum(
                        v * math.log10(eq.activities[b])
                        for b, v in powers.items()
                        if b in eq.totals
                    )
                )
                try:
                    partials.append(F(10**exponent))
                except (OverflowError, ValueError) as error:
                    raise DeliveryError(
                        'unresolved_sensitivity', 'nonfinite boundary derivative'
                    ) from error
            else:
                if basis in absent and (power < 0 or 0 < power < 1):
                    raise DeliveryError('unresolved_sensitivity', 'singular boundary power')
                partials.append(F(0))
        # These are derivatives of the coefficients already used by aqueous_model.
        gamma_prime = -0.509 * z * z * (1 / (2 * root * (1 + root) ** 2) - 0.3) if z else 0.1
        partials += [
            -amount * F(LN10) * F(gamma_prime),
            amount * F(powers.get('H2O', 0)) / F(water),
        ]
        derivatives.append(partials)
    matrix = [
        [
            sum(F(r['powers'].get(b, 0)) * d[j] for r, d in zip(records, derivatives))
            for j in range(dimension)
        ]
        for b in bases
    ]
    matrix.append(
        [
            F(j == n) - sum(F(r['charge']) ** 2 * d[j] / 2 for r, d in zip(records, derivatives))
            for j in range(dimension)
        ]
    )
    matrix.append(
        [
            F(j == n + 1) + (0 if floor else sum(d[j] for d in derivatives) / F(55.5084))
            for j in range(dimension)
        ]
    )
    rhs = [
        [
            F(s.components.get(b, 0)) * F(problem.final_volume_litres) / F(problem.solvent_mass_kg)
            for s in sources
        ]
        for b in bases
    ] + [[F(0)] * len(sources) for _ in range(2)]
    charge = [
        sum(F(r['charge']) * d[j] for r, d in zip(records, derivatives)) for j in range(dimension)
    ]
    # q^T J^-1 B = z^T B, where J^T z = q. One exact adjoint solve
    # avoids carrying a separate large rational solution for every product.
    adjoint = _exact_linear([list(row) for row in zip(*matrix)], [[q] for q in charge])
    try:
        gradient = [
            float(sum(z[0] * row[c] for z, row in zip(adjoint, rhs))) for c in range(len(sources))
        ]
    except OverflowError as error:
        raise DeliveryError('unresolved_sensitivity', 'nonfinite charge sensitivity') from error
    if not all(map(math.isfinite, gradient)):
        raise DeliveryError('unresolved_sensitivity', 'nonfinite charge sensitivity')
    return gradient
