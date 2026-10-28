# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent complex-step/Decimal oracle for phase-free charge sensitivities.

This verification tool does not call the production analytic derivative or its
rational elimination. Both Decimal precisions must agree under the caller's
criterion; neither precision is a production stopping default.
"""

import cmath
import math
from decimal import Decimal as D, localcontext
from flahax.aqueous_model import chemistry


def _decimal_solve(matrix, rhs, precision):
    with localcontext() as context:
        context.prec = precision
        n, count = len(matrix), len(rhs[0])
        a = [[+v for v in row] + [+v for v in target] for row, target in zip(matrix, rhs)]
        # Gauss-Jordan, independently of the production forward/back substitution.
        for k in range(n):
            pivot = max(range(k, n), key=lambda j: abs(a[j][k]))
            a[k], a[pivot] = a[pivot], a[k]
            if not a[k][k]:
                raise ValueError('singular independent sensitivity system')
            divisor = a[k][k]
            a[k] = [v / divisor for v in a[k]]
            for j in range(n):
                if j != k:
                    factor = a[j][k]
                    a[j] = [v - factor * w for v, w in zip(a[j], a[k])]
        return [row[n : n + count] for row in a]


def independent_charge_gradient(problem, state, agreement_tolerance):
    """Differentiate species by complex steps, then solve at 80 and 160 digits."""
    eq = state['equilibrium']
    if problem.phases or any(eq.precipitated.values()):
        raise ValueError('independent phase sensitivity is unsupported')
    sources = (*problem.fertilizers, problem.reagent)
    bases = list(dict.fromkeys([*eq.totals, *[b for s in sources for b in s.components]]))
    records = [
        r
        for r in chemistry()['aqueous']
        if r['name'] != 'H2O' and set(r['powers']) <= set(bases) | {'H+', 'H2O'}
    ]
    n = len(bases)
    variables = [math.log10(eq.activities[b]) if b in eq.totals else 0.0 for b in bases]
    variables += [eq.ionic_strength, eq.water_activity]

    def species(record, values):
        strength, water = values[-2:]
        z = record['charge']
        root = cmath.sqrt(strength)
        gamma = -0.509 * z * z * (root / (1 + root) - 0.3 * strength) if z else 0.1 * strength
        powers = record['powers']
        result = 10 ** (
            record['beta'] - problem.target_ph * powers.get('H+', 0) - gamma
        ) * water ** powers.get('H2O', 0)
        for j, b in enumerate(bases):
            if powers.get(b, 0):
                activity = 10 ** values[j] if b in eq.totals else values[j]
                result *= activity ** powers[b]
        return result

    # Imaginary perturbations avoid subtracting two nearly equal charge values.
    step = 1e-100
    partials = []
    for record in records:
        row = []
        for j in range(n + 2):
            values = list(map(complex, variables))
            values[j] += complex(0, step)
            value = species(record, values).imag / step
            if not math.isfinite(value):
                raise ValueError('nonfinite independent sensitivity')
            row.append(D(value))
        partials.append(row)
    # Preserve tiny individual species terms when assembling balance derivatives.
    with localcontext() as context:
        context.prec = 160
        matrix = [
            [
                sum(D(r['powers'].get(b, 0)) * row[j] for r, row in zip(records, partials))
                for j in range(n + 2)
            ]
            for b in bases
        ]
        matrix.append(
            [
                D(j == n)
                - sum(D(r['charge']) ** 2 * row[j] / 2 for r, row in zip(records, partials))
                for j in range(n + 2)
            ]
        )
        matrix.append(
            [
                D(j == n + 1)
                + (sum(row[j] for row in partials) / D(55.5084) if eq.water_activity > 0.9 else 0)
                for j in range(n + 2)
            ]
        )
        rhs = [
            [
                D(s.components.get(b, 0))
                * D(problem.final_volume_litres)
                / D(problem.solvent_mass_kg)
                for s in sources
            ]
            for b in bases
        ] + [[D(0)] * len(sources) for _ in range(2)]
        charge = [
            sum(D(r['charge']) * row[j] for r, row in zip(records, partials)) for j in range(n + 2)
        ]
        results = []
        for precision in (80, 160):
            response = _decimal_solve(matrix, rhs, precision)
            results.append(
                [sum(v * row[c] for v, row in zip(charge, response)) for c in range(len(sources))]
            )
        if any(
            abs(a - b) > D(agreement_tolerance) * max(abs(a), abs(b)) for a, b in zip(*results)
        ):
            raise ValueError('independent sensitivity precision unresolved')
        return list(map(float, results[-1]))
