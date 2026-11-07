# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Whole-recipe trial steps on the charge surface, subject to the original linear caps."""

import math

from .aqueous_model import linear


def _dot(row, x):
    return math.fsum(a * b for a, b in zip(row, x))


def _active_step(hessian, gradient, charge, limits, budget):
    """Minimize the local quadratic over a feasible active set, starting at zero."""
    n = len(gradient)
    position = [0.0] * n
    active = []
    for _ in range(budget):
        rows = [charge, *(limits[i][0] for i in active)]
        bounds = [0.0, *(limits[i][1] for i in active)]
        kkt = [[*hessian[j], *(row[j] for row in rows)] for j in range(n)] + [
            [*row, *([0.0] * len(rows))] for row in rows
        ]
        result = linear(kkt, [-g for g in gradient] + bounds)
        proposal = result[:n]
        direction = [p - x for p, x in zip(proposal, position)]
        blockers = []
        for i, (row, bound) in enumerate(limits):
            if i in active:
                continue
            slope = _dot(row, direction)
            if slope > 0 and _dot(row, proposal) > bound:
                alpha = max(0.0, (bound - _dot(row, position)) / slope)
                blockers.append((min(1.0, alpha), i))
        if blockers:
            alpha, index = min(blockers)
            position = [x + alpha * d for x, d in zip(position, direction)]
            active.append(index)
            continue
        multipliers = result[n + 1 :]
        if not multipliers or min(multipliers) >= 0:
            return proposal, result[n]
        position = proposal
        active.pop(multipliers.index(min(multipliers)))
    return None


def whole_mix_direction(point, residual, matrix, constraints, budget):
    """Solve for all doses together with the linearized charge equality and nutrient caps."""
    # A nonnegative source of a nutrient explicitly capped at zero cannot be used.
    fixed = {
        j
        for row, bound in constraints
        if bound == 0 and all(a >= 0 for a in row)
        for j, a in enumerate(row)
        if a > 0
    }
    indices = [j for j in range(len(point)) if j not in fixed]
    if not indices:
        return None
    columns = [[row[j] for row in matrix[:-1]] for j in indices]
    scales = [math.hypot(*col) or abs(matrix[-1][j]) or 1.0 for j, col in zip(indices, columns)]
    columns = [[a / s for a in col] for col, s in zip(columns, scales)]
    charge = [matrix[-1][j] / s for j, s in zip(indices, scales)]
    norm = math.hypot(*charge)
    if not norm:
        return None
    # A small diagonal regularizes duplicate nutrient columns in the trial model.
    # The solver checks stationarity on the original unregularized problem.
    hessian = [
        [_dot(a, b) + (1e-10 if i == j else 0.0) for j, b in enumerate(columns)]
        for i, a in enumerate(columns)
    ]
    gradient = [_dot(col, residual[:-1]) for col in columns]
    limits = []
    for row, bound in constraints:
        reduced = [row[j] / s for j, s in zip(indices, scales)]
        size = math.hypot(*reduced)
        if size:
            limits.append(([a / size for a in reduced], max(0.0, bound - _dot(row, point)) / size))
    step = _active_step(hessian, gradient, [v / norm for v in charge], limits, budget)
    if step is None:
        return None
    reduced, multiplier = step
    direction = [0.0] * len(point)
    for j, value, scale in zip(indices, reduced, scales):
        direction[j] = value / scale
    return direction, 2 * multiplier / norm


def feasible_endpoint(point, direction, alpha, constraints):
    """Round a trial inward at active caps; the ordinary evaluator still checks every limit."""
    trial = [max(0.0, x + alpha * dx) for x, dx in zip(point, direction)]
    for row, bound in constraints[len(point) :]:
        total = sum(a * x for a, x in zip(row, trial))
        # Leave room for rounding when the independent dose calculation sums
        # products in a different order from the linear feasibility check.
        interior = max(0.0, bound - 4 * math.ulp(bound))
        if total > interior:
            factor = max(0.0, math.nextafter(interior / total, 0.0))
            for j, coefficient in enumerate(row):
                if coefficient > 0:
                    trial[j] *= factor
    return trial


def _face_direction(point, current, matrix, constraints, active_tolerance, evaluate, matrix_at):
    """Newton refinement in the tangent space of positive doses and binding caps."""
    indices = [j for j, x in enumerate(point) if x > active_tolerance]
    if not indices:
        return None
    scales = [math.hypot(*(row[j] for row in matrix[:-1])) or 1.0 for j in indices]
    axes = []

    def orthogonal(vector):
        for basis in axes:
            projection = _dot(vector, basis)
            vector = [v - projection * b for v, b in zip(vector, basis)]
        norm = math.hypot(*vector)
        return [v / norm for v in vector] if norm > 1e-10 else None

    for row, bound in constraints[len(point) :]:
        if bound - _dot(row, point) <= active_tolerance * math.hypot(*row):
            normal = [row[j] / s for j, s in zip(indices, scales)]
            size = math.hypot(*normal)
            axis = orthogonal([v / size for v in normal]) if size else None
            if axis is not None:
                axes.append(axis)
    tangent = []
    for k in range(len(indices)):
        axis = orthogonal([float(i == k) for i in range(len(indices))])
        if axis is not None:
            axes.append(axis)
            direction = [0.0] * len(point)
            for i, s, v in zip(indices, scales, axis):
                direction[i] = v / s
            tangent.append(direction)
    if not tangent:
        return None

    nutrient = [[_dot(row, d) for row in matrix[:-1]] for d in tangent]
    charge = [_dot(matrix[-1], d) for d in tangent]
    gradient = [2 * _dot(col, current[1][:-1]) for col in nutrient]
    size = _dot(charge, charge)
    if not size:
        return None
    multiplier = -_dot(gradient, charge) / size
    hessian = []
    for i, direction in enumerate(tangent):
        # A derivative probe stays on the same side of every dose bound.
        h = min(
            [math.sqrt(math.ulp(1.0))] + [0.01 * x / abs(v) for x, v in zip(point, direction) if v]
        )
        if not h:
            return None
        probes = []
        for sign in (-1, 1):
            u = feasible_endpoint(point, direction, sign * h, constraints)
            value = evaluate(u, cold=True)
            if value is None:
                return None
            probes.append(matrix_at(value)[-1])
        derivative = [(b - a) / (2 * h) for a, b in zip(*probes)]
        hessian.append(
            [
                2 * _dot(nutrient[i], col) + multiplier * _dot(derivative, d)
                for col, d in zip(nutrient, tangent)
            ]
        )
    system = [
        [
            (hessian[i][j] + hessian[j][i]) / 2 + (1e-10 if i == j else 0)
            for j in range(len(tangent))
        ]
        + [charge[i]]
        for i in range(len(tangent))
    ] + [[*charge, 0.0]]
    solved = linear(system, [-v for v in gradient] + [-current[1][-1]])
    delta = [math.fsum(x * d[j] for x, d in zip(solved[:-1], tangent)) for j in range(len(point))]
    return delta, solved[-1]


def whole_mix_trial(
    point,
    current,
    matrix,
    constraints,
    radius,
    budget,
    charge_tolerance,
    evaluate,
    active_tolerance,
    matrix_at,
    improves_stationarity,
    charge_scale,
    refine=False,
):
    """Backtrack a simultaneous proposal and restore nonlinear charge before accepting it."""
    from .delivery_contracts import DeliveryError

    try:
        if refine:
            proposal = _face_direction(
                point, current, matrix, constraints, active_tolerance, evaluate, matrix_at
            )
        else:
            proposal = whole_mix_direction(point, current[1], matrix, constraints, 4 * len(point))
    except (DeliveryError, ArithmeticError, ValueError):
        return None
    if proposal is None:
        return None
    direction, multiplier = proposal
    size = max(map(abs, direction), default=0.0)
    if not math.isfinite(size) or not size:
        return None
    alpha = min(1.0, radius / size)
    for _ in range(budget):
        u = feasible_endpoint(point, direction, alpha, constraints)
        if u == point:
            break
        value = evaluate(u)
        # Use the reagent as a charge pivot. If it is bound or unavailable, the
        # ordinary joint path can try other pivots; no constraint is discarded.
        for _ in range(budget):
            if value is None or value[0]['chargeResidual'] == 0:
                break
            if not refine and abs(value[0]['chargeResidual']) <= charge_tolerance:
                break
            if not matrix[-1][-1]:
                break
            correction = [0.0] * len(point)
            correction[-1] = -value[1][-1] / matrix[-1][-1]
            adjusted = feasible_endpoint(u, correction, 1.0, constraints)
            if adjusted == u or abs(adjusted[-1] - point[-1]) > radius:
                break
            check = evaluate(adjusted)
            if check is None or abs(check[1][-1]) >= abs(value[1][-1]):
                break
            u, value = adjusted, check
        if value is not None and abs(value[0]['chargeResidual']) <= charge_tolerance:
            objective_change = float(value[3] - current[3])
            actual = objective_change + multiplier * (value[1][-1] - current[1][-1])
            predicted = objective_change + multiplier * _dot(
                matrix[-1], [y - x for x, y in zip(point, u)]
            )
            if (
                refine
                and actual <= 2 * abs(multiplier) * charge_tolerance / charge_scale
                and improves_stationarity(u, value)
            ):
                return u, value
            if not refine and (
                actual < 0
                or (
                    predicted < 0
                    and actual <= abs(multiplier) * (abs(value[1][-1]) + abs(current[1][-1]))
                )
            ):
                return u, value
        alpha /= 2
    return None
