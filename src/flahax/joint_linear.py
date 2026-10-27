# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Bounded linear least-squares trial steps, with explicit iteration budgets."""

import math
from .engine import _lstsq, ROUNDOFF


def bounded_lstsq(matrix, rhs, lower, upper, budget):
    """Active-set box least squares; rank failure cannot certify joint feasibility.

    The box is a trust region, not a newly imposed bound on the joint problem.
    The dual roundoff test uses the existing NNLS per-column arithmetic scale.
    """
    n = len(lower)
    cols = list(zip(*matrix))
    width = [hi - lo for lo, hi in zip(lower, upper)]
    if len(cols) != n or len(upper) != n or any(w < 0 or not math.isfinite(w) for w in width):
        raise ValueError('invalid least-squares box')
    shifted = [b - math.fsum(a * lo for a, lo in zip(row, lower)) for row, b in zip(matrix, rhs)]
    x = [0.0] * n
    free = []
    rejected = set()
    allowance = 10 * max(len(matrix), n) * ROUNDOFF
    for _ in range(budget):
        residual = [
            math.fsum(v * d for v, d in zip(row, x)) - b for row, b in zip(matrix, shifted)
        ]
        gradient = [math.fsum(v * r for v, r in zip(col, residual)) for col in cols]
        sizes = [
            math.fsum(
                abs(v) * (abs(b) + math.fsum(abs(a * d) for a, d in zip(row, x)))
                for v, b, row in zip(col, shifted, matrix)
            )
            for col in cols
        ]
        if not all(math.isfinite(v) for v in gradient + sizes):
            raise ValueError('nonfinite bounded linear system')
        candidates = [
            j
            for j in range(n)
            if j not in free
            and j not in rejected
            and width[j] > 0
            and (
                (x[j] == 0 and gradient[j] < -allowance * sizes[j])
                or (x[j] == width[j] and gradient[j] > allowance * sizes[j])
            )
        ]
        if not candidates:
            return [lo + v for lo, v in zip(lower, x)]
        entering = max(candidates, key=lambda j: abs(gradient[j]))
        free.append(entering)
        old = x.copy()
        while free:
            adjusted = [
                b - math.fsum(row[j] * x[j] for j in range(n) if j not in free)
                for row, b in zip(matrix, shifted)
            ]
            try:
                norms = [math.hypot(*cols[j]) for j in free]
                solution = _lstsq(
                    [[v / scale for v in cols[j]] for j, scale in zip(free, norms)], adjusted
                )
                solution = [v / scale for v, scale in zip(solution, norms)]
            except ValueError:
                free.remove(entering)
                rejected.add(entering)
                break
            trial = dict(zip(free, solution))
            blockers = []
            for j, z in trial.items():
                if z < 0:
                    blockers.append((x[j] / (x[j] - z), j, 0.0))
                elif z > width[j]:
                    blockers.append(((width[j] - x[j]) / (z - x[j]), j, width[j]))
            if not blockers:
                for j, z in trial.items():
                    x[j] = z
                break
            alpha, index, endpoint = min(blockers)
            for j, z in trial.items():
                x[j] = min(width[j], max(0.0, x[j] + alpha * (z - x[j])))
            x[index] = endpoint
            free.remove(index)
        if x != old:
            rejected.clear()
    raise ValueError('bounded linear step budget exhausted')
