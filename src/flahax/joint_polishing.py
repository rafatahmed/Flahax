# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Positive-curvature proposals for correlated nutrient sources on the charge manifold."""

import math


def block_polish_direction(
    problem,
    point,
    value,
    matrix,
    scales,
    constraints,
    charge_scale,
    charge_tolerance,
    sensitivity_tolerance,
    radius,
    budget,
    evaluate,
    candidate,
    active_tolerance=0.0,
):
    """Return a verified positive-curvature two-source proposal, or no proposal."""
    from . import joint_solver as solver

    if candidate is None:
        return None
    j = candidate[2]
    n = len(point)
    pivots = [i for i in range(n) if point[i] > active_tolerance and matrix[-1][i]]
    pivot = n - 1 if n - 1 in pivots else max(pivots, key=lambda i: abs(matrix[-1][i]))
    gradient = [
        2 * math.fsum(r * a[i] for r, a in zip(value[1][:-1], matrix[:-1])) for i in range(n)
    ]
    multiplier = -gradient[pivot] / matrix[-1][pivot]
    reduced = [gradient[i] + multiplier * matrix[-1][i] for i in range(n)]
    col = [r[j] for r in matrix[:-1]]
    norm = math.hypot(*col)
    if not norm:
        return None
    correlated = []
    for k in range(n):
        if k in (j, pivot) or point[k] <= active_tolerance:
            continue
        other = [r[k] for r in matrix[:-1]]
        size = math.hypot(*other)
        if size:
            correlated.append((math.fsum(a * b for a, b in zip(col, other)) / (norm * size), k))
    if not correlated:
        return None
    correlation, k = max(correlated)
    if correlation <= 0:
        return None
    indices = [j, k]
    hessian = []
    for coordinate in indices:
        h = (
            min(
                1.0,
                solver._chemical_widths(problem, value, scales, radius)[coordinate],
                point[coordinate] if point[coordinate] > 0 else 1,
            )
            * sensitivity_tolerance
        )
        direction = [0.0] * n
        direction[coordinate] = h
        direction[pivot] = -h * matrix[-1][coordinate] / matrix[-1][pivot]
        f = solver._fraction(point, direction, constraints)
        if not f:
            direction = [-v for v in direction]
            f = solver._fraction(point, direction, constraints)
        probe = [max(0, x + f * d) for x, d in zip(point, direction)]
        v = evaluate(probe)
        if v is None:
            return None
        for _ in range(budget):
            if abs(v[0]['chargeResidual']) <= charge_tolerance:
                break
            d = [0.0] * n
            d[pivot] = -v[1][-1] / matrix[-1][pivot]
            f = solver._fraction(probe, d, constraints)
            u = [max(0, x + f * y) for x, y in zip(probe, d)]
            w = evaluate(u)
            if w is None or abs(w[1][-1]) >= abs(v[1][-1]):
                break
            probe, v = u, w
        if (
            abs(v[0]['chargeResidual']) > charge_tolerance
            or probe[coordinate] == point[coordinate]
        ):
            return None
        m = solver._implicit_matrix(problem, v, scales, charge_scale)
        g = [2 * math.fsum(r * a[i] for r, a in zip(v[1][:-1], matrix[:-1])) for i in range(n)]
        if not m[-1][pivot]:
            return None
        r = [g[i] - g[pivot] * m[-1][i] / m[-1][pivot] for i in indices]
        hessian.append(
            [
                (a - reduced[i]) / (probe[coordinate] - point[coordinate])
                for a, i in zip(r, indices)
            ]
        )
    a = hessian[0][0]
    d = hessian[1][1]
    b = (hessian[0][1] + hessian[1][0]) / 2
    det = a * d - b * b
    if a <= 0 or d <= 0 or det <= 0:
        return None
    u = -(d * reduced[j] - b * reduced[k]) / det
    v = -(-b * reduced[j] + a * reduced[k]) / det
    direction = [0.0] * n
    direction[j] = u
    direction[k] = v
    direction[pivot] = -(u * matrix[-1][j] + v * matrix[-1][k]) / matrix[-1][pivot]
    if not all(map(math.isfinite, direction)):
        return None
    return direction, multiplier, j
