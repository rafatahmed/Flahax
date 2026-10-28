# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent, deliberately small numerical oracles; no production imports.

Rational inputs are interpreted as supplied decimal text, not binary float bits.
Box least squares uses exhaustive faces, not the runtime optimization algorithm.
The acid oracle brackets a monotone charge equation using exact rational signs.
Reference comparisons require declared matched conditions and provenance; they
cannot authenticate those declarations or establish experimental accuracy.
"""

from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product


def rational(value):
    """Parse a finite decimal or rational without binary arithmetic."""
    return Fraction(str(value))


def linear_solution(matrix, rhs):
    """Solve a square rational system by elimination; return None if singular."""
    n = len(rhs)
    rows = [list(row) + [value] for row, value in zip(matrix, rhs)]
    for col in range(n):
        pivot = next((i for i in range(col, n) if rows[i][col]), None)
        if pivot is None:
            return None
        rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        rows[col] = [v / divisor for v in rows[col]]
        for i in range(n):
            if i != col:
                factor = rows[i][col]
                rows[i] = [v - factor * w for v, w in zip(rows[i], rows[col])]
    return tuple(row[-1] for row in rows)


def box_least_squares(matrix, target, lower, upper):
    """Minimize sum((A x - b)**2) over a finite box, at most six variables.

    Return an exact optimizer, squared residual and gradient A.T(Ax-b). Singular
    faces are skipped: a compact box always has an optimum on a face whose free
    columns are independent. Degenerate optima need not have unique coordinates.
    Weighted problems can be supplied as already scaled rows. This is not a
    general inequality, integer, nonlinear, or unbounded optimization oracle.
    """
    a = [list(map(rational, row)) for row in matrix]
    b, lo, hi = (list(map(rational, v)) for v in (target, lower, upper))
    n = len(lo)
    if not 1 <= n <= 6 or len(hi) != n or not a or len(a) != len(b):
        raise ValueError('require 1..6 variables and a nonempty rectangular problem')
    if any(len(row) != n for row in a) or any(low > h for low, h in zip(lo, hi)):
        raise ValueError('invalid matrix shape or reversed bounds')
    best = None
    for face in product((-1, 0, 1), repeat=n):
        free = [i for i, side in enumerate(face) if side == 0]
        x = [hi[i] if side == 1 else lo[i] for i, side in enumerate(face)]
        residual = [
            sum(row[j] * x[j] for j in range(n) if j not in free) - y for row, y in zip(a, b)
        ]
        gram = [[sum(row[i] * row[j] for row in a) for j in free] for i in free]
        rhs = [-sum(row[i] * r for row, r in zip(a, residual)) for i in free]
        solution = linear_solution(gram, rhs)
        if solution is None:
            continue
        for i, value in zip(free, solution):
            x[i] = value
        if any(v < low or v > h for v, low, h in zip(x, lo, hi)):
            continue
        residual = [sum(v * w for v, w in zip(row, x)) - y for row, y in zip(a, b)]
        objective = sum(r * r for r in residual)
        if best is None or objective < best['objective']:
            best = dict(
                x=tuple(x),
                objective=objective,
                gradient=tuple(sum(row[i] * r for row, r in zip(a, residual)) for i in range(n)),
            )
    return best


def acid_bracket(total, ka, kw='1e-14', *, digits=80):
    """Bracket H for ideal monoprotic acid plus water on a decimal grid.

    Solve H - Kw/H - Ka*C/(Ka+H) = 0. Its derivative is strictly positive.
    Return Decimal endpoints separated by at most 10**(-digits), with exact
    rational sign checks. This ideal, unbuffered system is not a Davies solution.
    The precision range 16..200 is a harness resource limit, not chemistry policy.
    """
    c, k, water = map(rational, (total, ka, kw))
    if c < 0 or k <= 0 or water <= 0:
        raise ValueError('require C >= 0, Ka > 0 and Kw > 0')
    if type(digits) is not int or not 16 <= digits <= 200:
        raise ValueError('digits must be an integer from 16 to 200')
    scale = 10**digits
    low, high = 0, (int(c + k + water) + 2) * scale
    while high - low > 1:
        mid = (low + high) // 2
        h = Fraction(mid, scale)
        sign = h - water / h - k * c / (k + h)
        if sign < 0:
            low = mid
        else:
            high = mid
    with localcontext() as context:
        context.prec = len(str(high)) + digits
        return Decimal(low).scaleb(-digits), Decimal(high).scaleb(-digits)


def error_account(actual, expected, *, absolute, relative):
    """Account exactly for |actual-reference| <= absolute + relative*|reference|.

    Tolerances must be justified by the caller. Zero-reference relative error is
    undefined (None). No division floor, hidden tolerance, or NaN pass is allowed.
    """
    a, e, atol, rtol = map(rational, (actual, expected, absolute, relative))
    if atol < 0 or rtol < 0:
        raise ValueError('negative comparison allowance')
    error = abs(a - e)
    allowance = atol + rtol * abs(e)
    return dict(
        passed=error <= allowance,
        actual=str(a),
        reference=str(e),
        absolute_error=str(error),
        relative_error=str(error / abs(e)) if e else None,
        absolute_allowance=str(atol),
        relative_allowance=str(rtol * abs(e)),
        total_allowance=str(allowance),
    )


CONDITIONS = frozenset(
    {
        'temperature_c',
        'units',
        'totals',
        'ph',
        'carbon_boundary',
        'redox',
        'phases',
        'charge_balance',
    }
)


def compare_reference(actual, expected, budgets):
    """Compare nonempty quantity maps only after matching declared conditions.

    Each record requires conditions, values, method, and nonempty sha256 provenance
    mapping. Shared hashes are reported, not treated as independent parameter
    evidence. Different methods are allowed and retained, with caller-owned budgets.
    Provenance file bytes must be verified separately by the capture/replay runner.
    """
    for record in (actual, expected):
        if set(record['conditions']) != CONDITIONS or not record['method']:
            raise ValueError('incomplete condition or method declaration')
        hashes = record['sha256']
        if not hashes or any(
            len(h) != 64 or any(c not in '0123456789abcdef' for c in h) for h in hashes.values()
        ):
            raise ValueError('require nonempty lowercase SHA-256 provenance')
    if actual['conditions'] != expected['conditions']:
        raise ValueError('reference conditions do not match')
    keys = set(expected['values'])
    if not keys or keys != set(actual['values']) or keys != set(budgets):
        raise ValueError('quantity and budget sets must match exactly and be nonempty')
    errors = {
        key: error_account(actual['values'][key], expected['values'][key], **budgets[key])
        for key in sorted(keys)
    }
    shared = sorted(set(actual['sha256'].values()) & set(expected['sha256'].values()))
    return dict(
        passed=all(item['passed'] for item in errors.values()),
        errors=errors,
        conditions=expected['conditions'],
        methods=[actual['method'], expected['method']],
        provenance=[actual['sha256'], expected['sha256']],
        shared_sha256=shared,
        parameter_independence='not established',
        physical_validation=False,
    )
