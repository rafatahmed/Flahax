# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Rational objective-gap certificates for a relaxation of the joint problem."""

from fractions import Fraction as F
from .engine import nnls
from .joint_problem import _profile_doses, _number


def objective_certificate(problem, fertilizer_doses, reagent_dose):
    """Bound objective suboptimality without assuming nonlinear convexity.

    Charge and phase equations are dropped, retaining all linear hard bounds.
    Any feasible joint point is feasible for this relaxation. A verified dual
    value therefore bounds the joint optimum from below. Rational arithmetic
    refers to the actual binary input values, not rounded decimal displays.
    The reported gap is an exact fraction; floating values are for display only.
    """
    doses = _profile_doses(fertilizer_doses, problem.fertilizers)
    q = _number(reagent_dose, 'reagent dose')
    sources = (*problem.fertilizers, problem.reagent)
    x = [F(doses.get(s.product_id, 0)) for s in problem.fertilizers] + [F(q)]
    positive = [(k, t) for k, t in problem.targets.items() if t > 0]
    a = [[1000 * F(s.nutrients.get(k, 0)) / F(t) for s in sources] for k, t in positive]
    b = [(F(t) - F(problem.water.get(k, 0))) / F(t) for k, t in positive]
    limits = dict(problem.maximum_concentrations)
    limits.update({k: 0 for k, t in problem.targets.items() if t == 0})
    bounds = [
        ([1000 * F(s.nutrients.get(k, 0)) for s in sources], F(cap) - F(problem.water.get(k, 0)))
        for k, cap in limits.items()
    ]
    volume = F(problem.final_volume_litres)
    bounds.append(([F(0)] * (len(sources) - 1) + [volume], F(problem.maximum_reagent_mass_g)))
    bounds.append(
        ([F(s.solvent_fraction) * volume / 1000 for s in sources], F(problem.solvent_mass_kg))
    )
    if problem.reagent.density_kg_per_litre is not None:
        cap = problem.final_volume_litres
        if problem.maximum_reagent_volume_litres is not None:
            cap = min(cap, problem.maximum_reagent_volume_litres)
        bounds.append(
            (
                [F(0)] * (len(sources) - 1)
                + [volume / (1000 * F(problem.reagent.density_kg_per_litre))],
                F(cap),
            )
        )
    feasible = all(sum(v * d for v, d in zip(row, x)) <= bound for row, bound in bounds)
    residual = [sum(v * d for v, d in zip(row, x)) - target for row, target in zip(a, b)]
    loss = sum((r * r for r in residual), F(0))
    witness = ([F(0)] * len(positive), [F(0)] * len(bounds))
    if not positive:
        lower = F(0)
    else:
        columns = list(zip(*a))
        gradient = [2 * sum(v * r for v, r in zip(col, residual)) for col in columns]
        # Numerical multipliers only propose a certificate. Nonnegativity and
        # every dual inequality are enforced below with exact rational arithmetic.
        try:
            multipliers = nnls(
                [[float(row[j]) for row, _ in bounds] for j in range(len(x))],
                [-float(g) for g in gradient],
            )
        except (ValueError, OverflowError):
            multipliers = [0.0] * len(bounds)
        multipliers = [F(max(0.0, v)) for v in multipliers]
        candidates = [(F(0), *witness)]
        for lambdas in ([F(0)] * len(bounds), multipliers):
            c = [
                sum(lam * row[j] for lam, (row, _) in zip(lambdas, bounds)) for j in range(len(x))
            ]
            shift = max(
                [F(0)]
                + [
                    -(g + v) / (2 * sum(col))
                    for g, v, col in zip(gradient, c, columns)
                    if sum(col) > 0
                ]
            )
            dual = [r + shift for r in residual]
            assert all(
                2 * sum(v * r for v, r in zip(col, dual)) + offset >= 0
                for col, offset in zip(columns, c)
            )
            value = (
                -2 * sum(v * r for v, r in zip(b, dual))
                - sum(r * r for r in dual)
                - sum(lam * bound for lam, (_, bound) in zip(lambdas, bounds))
            )
            candidates.append((value, dual, lambdas))
        lower, *witness = max(candidates, key=lambda item: item[0])

    return dict(
        dualVector=[str(v) for v in witness[0]],
        upperMultipliers=[str(v) for v in witness[1]],
        exactLoss=str(loss),
        exactLowerBound=str(lower),
        exactGap=str(loss - lower),
        loss=float(loss),
        lowerBound=float(lower),
        gap=float(loss - lower),
        linearFeasible=feasible,
        dualFeasible=True,
    )
