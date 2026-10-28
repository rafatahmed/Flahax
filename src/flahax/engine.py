# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""FlahaX salt-combination search.

The crop formula is fixed. This season's water is subtracted from it.
The gap is what the salts must cover. Grams are per litre of working
solution and cannot be negative. The objective is the sum of squared
percentage errors on elements that have a target.

The salt rows come from library.json. A formula that parses is checked
against its assay before it can be dosed.
"""

from __future__ import annotations

import json
import math
from importlib.resources import files

from .composition import (
    ATOMIC,
    ATOMIC_CONVENTION,
    CONSENT_IONS,
    RESTRICTED_IONS,
    InputError,
    assay_conflict,
    assay_drift,
    is_carbonate,
    target_ion_balance,
    validate_profile,
)
from .nutrient_acceptance import (
    assess_incidental,
    incidental_ammonium_limit,
    name_sources,
    with_ammonium_achieved,
)
from .nutrient_ledger import N_AGGREGATE, N_FORMS, elemental_nitrogen
from .product_conversion import counterion_sodium_mg_per_l, material_inventory

# Rank and feasibility threshold, relative to the problem's column scale.
EPS = 1e-10
# Column additions allowed per column before NNLS reports non-convergence (#55).
NNLS_ADDITION_FACTOR = 4
# Smallest Cholesky pivot, relative to the column's squared norm, accepted by the Gram
# path (#59); below it the subproblem is ill-conditioned and Householder decides.
GRAM_PIVOT_FLOOR = 1e-8
# Pivot ratio below which the Gram solution is refined against the original columns.
GRAM_REFINE_BELOW = 1e-4
# Binary64 spacing at one (2^-52), twice round-to-nearest unit roundoff.
ROUNDOFF = 2.220446049250313e-16
# Only exact zero doses are omitted; every positive binary64 dose is authoritative.
KEEP_GRAMS = 0.0
# A recipe is feasible when every requested ion is inside this Δ%.
TOLERANCE_PCT = 1.0
# A binding ceiling is met as a constraint (#68): a row of moderate weight whose aim is
# shifted by the Lagrange multiplier, searched until the ion sits on its aim (see
# _fit_within). A huge penalty weight instead (1024, #56) left the objective so flat in
# double precision that doses were fixed only to ~2e-3 g/L and depended on the start.
CEILING_WEIGHT = 8.0
CEILING_STEPS = 60
# Converged when every active ceiling ion is within this fraction of its limit of its aim.
CEILING_TOLERANCE = 1e-9
# Catalogue products with this role adjust pH only (#75): formulation never selects them.
PH_REAGENT = "ph_reagent"
# Relative aim below a stated maximum (1 ppm of the limit).
CEILING_MARGIN = 1e-6
# Default incidental NH4-N ceiling (#54 / owner 2026-10-28): min(10% of target N, 1.5 mmol/L).
# Dutch soilless practice (De Kreij, Voogt et al.; Voogt "max 90:10"). None opts out.
AMMONIUM_FRACTION = 0.10
AMMONIUM_CAP_MG_PER_L = 1.5 * ATOMIC["N"]
AMMONIUM_BASIS = (
    "incidental NH4-N up to min(10% of total target N, 1.5 mmol/L); owner "
    "decision based on Dutch soilless practice (De Kreij, Voogt et al.; Voogt "
    "'max 90:10'); see docs for references"
)


def load_library() -> dict:
    """Salt library, water profiles, and crop formulas shipped with the package."""
    text = files("flahax").joinpath("data/library.json").read_text(encoding="utf-8")
    return json.loads(text)


def ppm_per_gram(percent: float) -> float:
    """ppm in 1 litre from 1 gram of salt at an element percentage."""
    return float(percent) * 10.0


def gap_for(targets: dict, water: dict | None = None) -> dict:
    """Return target minus water in elemental mg/L, without clipping deficits.

    Missing water concentrations default to zero in this low-level helper.
    Water-only symbols have a None gap; negative gaps mean water exceeds the
    target, not that fertilizer can remove the excess. Invalid nutrient maps
    raise InputError. This is nutrient accounting, not an acid/base analysis.
    """
    targets = validate_profile(targets, "targets")
    water = validate_profile(water or {}, "water")
    gap = {}
    for symbol in dict.fromkeys([*targets, *water]):
        if symbol not in targets:
            gap[symbol] = None
            continue
        if symbol == N_AGGREGATE:
            gap[symbol] = targets[symbol] - elemental_nitrogen(water)
            continue
        gap[symbol] = targets[symbol] - water.get(symbol, 0.0)
    return gap


def _lstsq(columns: list[list[float]], b: list[float]) -> list[float]:
    """Least squares by Householder QR. columns are the active salt vectors."""
    if not columns:
        return []
    n = len(columns)
    m = len(b)
    matrix = [[columns[j][i] for j in range(n)] for i in range(m)]
    beta = b[:]
    # Rank tests are relative so that rescaling a problem does not change its rank.
    rank_tol = EPS * max(math.sqrt(sum(v * v for v in column)) for column in columns)
    if rank_tol == 0.0:
        raise ValueError("rank deficient least squares block")
    for k in range(min(n, m)):
        sigma = math.sqrt(sum(matrix[i][k] * matrix[i][k] for i in range(k, m)))
        if sigma < rank_tol:
            raise ValueError("rank deficient least squares block")
        if matrix[k][k] < 0:
            sigma = -sigma
        reflector = [0.0] * m
        reflector[k] = matrix[k][k] + sigma
        for i in range(k + 1, m):
            reflector[i] = matrix[i][k]
        norm = sum(value * value for value in reflector)
        # The sign choice makes norm >= 2 * sigma**2; sigma already passed rank_tol.
        for j in range(k, n):
            dot = sum(reflector[i] * matrix[i][j] for i in range(k, m))
            factor = 2.0 * dot / norm
            for i in range(k, m):
                matrix[i][j] -= factor * reflector[i]
        dot = sum(reflector[i] * beta[i] for i in range(k, m))
        factor = 2.0 * dot / norm
        for i in range(k, m):
            beta[i] -= factor * reflector[i]
        for i in range(k + 1, m):
            matrix[i][k] = 0.0
        matrix[k][k] = -sigma
    solution = [0.0] * n
    for i in range(min(n, m) - 1, -1, -1):
        # Each diagonal is -sigma, already checked before the reflector was applied.
        total = beta[i] - sum(matrix[i][j] * solution[j] for j in range(i + 1, n))
        solution[i] = total / matrix[i][i]
    return solution


class _LazyGram:
    """Column inner products computed on first use and cached for one NNLS solve."""

    def __init__(self, cols):
        self.cols = cols
        self.rows = [dict() for _ in cols]

    def __getitem__(self, i):
        return _GramRow(self, i)


class _GramRow:
    __slots__ = ("gram", "i")

    def __init__(self, gram, i):
        self.gram, self.i = gram, i

    def __getitem__(self, j):
        i = self.i
        a, b = (i, j) if i <= j else (j, i)
        cache = self.gram.rows[a]
        value = cache.get(b)
        if value is None:
            value = cache[b] = sum(x * y for x, y in zip(self.gram.cols[a], self.gram.cols[b]))
        return value


def _gram_lstsq(gram, cross, cols, rhs, passive):
    """Least squares on the passive columns from a precomputed Gram matrix (#59).

    Cholesky on G[P,P] plus two refinement steps against the original columns
    (corrected semi-normal equations). Returns None when a pivot shows poor
    conditioning, so the caller uses Householder and keeps its rank decisions.
    """
    k = len(passive)
    chol = [[0.0] * k for _ in range(k)]
    weakest = 1.0
    for i in range(k):
        gi = gram[passive[i]]
        for j in range(i + 1):
            value = gi[passive[j]] - sum(chol[i][t] * chol[j][t] for t in range(j))
            if i == j:
                if value <= GRAM_PIVOT_FLOOR * gi[passive[i]]:
                    return None
                weakest = min(weakest, value / gi[passive[i]])
                chol[i][i] = math.sqrt(value)
            else:
                chol[i][j] = value / chol[j][j]

    def solve(vector):
        y = [0.0] * k
        for i in range(k):
            y[i] = (vector[i] - sum(chol[i][t] * y[t] for t in range(i))) / chol[i][i]
        z = [0.0] * k
        for i in range(k - 1, -1, -1):
            z[i] = (y[i] - sum(chol[t][i] * z[t] for t in range(i + 1, k))) / chol[i][i]
        return z

    z = solve([cross[j] for j in passive])
    picked = [cols[j] for j in passive]
    m = len(rhs)
    # Well-conditioned subproblems are already accurate; refine only weak ones.
    for _ in range(0 if weakest > GRAM_REFINE_BELOW else 2):
        residual = [rhs[r] - sum(z[i] * picked[i][r] for i in range(k)) for r in range(m)]
        delta = solve([sum(col[r] * residual[r] for r in range(m)) for col in picked])
        z = [a + b for a, b in zip(z, delta)]
    return z


def nnls(
    matrix: list[list[float]],
    rhs: list[float],
    x0: list[float] | None = None,
    gram: "_LazyGram | None" = None,
    *,
    diagnostics: dict | None = None,
) -> list[float]:
    """Lawson-Hanson non-negative least squares. matrix is rows × columns.

    x0, when given, is a non-negative starting point (warm start, #59): its positive
    entries form the initial passive set. The problem is convex, so the optimum is
    the same; a nearby start needs far fewer column additions. gram, when given, is a
    _LazyGram of this same matrix, shared by calls that change only rhs.
    Optional diagnostics receives direct residual/KKT checks and rank exclusions;
    numerical stationarity is not a certificate for downstream recipe policies.
    """
    if not matrix:
        return []
    cols = [[matrix[r][c] for r in range(len(matrix))] for c in range(len(matrix[0]))]
    m = len(matrix)
    n = len(cols)
    x = [0.0] * n
    passive: list[int] = []
    active = list(range(n))
    # Columns found numerically dependent on the passive set; skipped until x changes,
    # as in Lawson-Hanson, so one dependent column cannot block the others.
    rejected: set[int] = set()
    # Optimality (dual) test at round-off level, per column (#68): weight j is
    # cross[j] - sum_k G[j][k] x[k], whose rounding error is bounded by a multiple of
    # ROUNDOFF times the sum of the magnitudes of its terms. A fixed threshold stopped
    # early on small or near-dependent problems (#36); one global |A||b| scale stopped
    # early when a heavily weighted row (an incidental-ion ceiling) inflated it for
    # columns that row does not touch.
    bound = 10.0 * max(m, n) * ROUNDOFF

    # A caller solving several right-hand sides for one matrix may share its Gram cache.
    gram = _LazyGram(cols) if gram is None else gram
    # Reject unrepresentable Gram scales before a zero/NaN dual weight can be
    # mistaken for optimality. Zero columns remain legitimate inactive columns.
    for j, column in enumerate(cols):
        diagonal = gram[j][j]
        if not math.isfinite(diagonal) or (diagonal == 0 and any(column)):
            raise InputError(
                'NNLS column products exceed floating-point range; rescale the problem'
            )
    cross = [sum(a * b for a, b in zip(ci, rhs)) for ci in cols]
    cross_size = [sum(abs(a * b) for a, b in zip(ci, rhs)) for ci in cols]
    if not all(map(math.isfinite, cross_size)):
        raise InputError('NNLS right-hand-side products exceed floating-point range')

    def least_squares(chosen: list[int]) -> list[float]:
        sub = _gram_lstsq(gram, cross, cols, rhs, chosen)
        return _lstsq([cols[j] for j in chosen], rhs) if sub is None else sub

    def settle(sub: list[float]) -> None:
        """Move x toward the passive-set least-squares solution, dropping columns
        that reach zero, until that solution is feasible."""
        nonlocal passive
        while True:
            if all(value >= -EPS for value in sub):
                for j in range(n):
                    x[j] = 0.0
                for j, value in zip(passive, sub):
                    x[j] = max(0.0, value)
                return
            alpha = min(
                x[j] / (x[j] - trial)
                for j, trial in zip(passive, sub)
                if trial < 0 and x[j] > trial
            )
            for j, trial in zip(passive, sub):
                x[j] = x[j] + alpha * (trial - x[j])
            stay = []
            for j in passive:
                if x[j] <= EPS:
                    x[j] = 0.0
                    active.append(j)
                else:
                    stay.append(j)
            passive = stay
            if not passive:
                return
            # A subset of independent columns stays independent.
            sub = least_squares(passive)

    if x0 is not None and len(x0) == n and all(math.isfinite(v) and v >= 0 for v in x0):
        start = [j for j in range(n) if x0[j] > EPS]
        if start:
            try:
                sub = least_squares(start)
            except ValueError:
                pass  # dependent start columns: fall back to the cold start
            else:
                for j in start:
                    x[j] = x0[j]
                passive = start
                active = [j for j in range(n) if j not in start]
                settle(sub)

    additions = 0
    while True:
        # Dual weights A^T(b - Ax) from cached Gram entries over the passive columns.
        support = [j for j in range(n) if x[j] != 0.0]
        weights = []
        sizes = []
        for i in range(n):
            row = gram[i]
            terms = [row[j] * x[j] for j in support]
            weights.append(cross[i] - sum(terms))
            sizes.append(cross_size[i] + sum(map(abs, terms)))
        candidates = [j for j in active if j not in rejected and weights[j] > bound * sizes[j]]
        if not candidates:
            break
        enter = max(candidates, key=lambda j: weights[j])
        if additions >= NNLS_ADDITION_FACTOR * n:
            # Not optimal yet; returning x would hand back a non-optimal fit silently (#55).
            raise InputError(
                f"NNLS did not reach optimality within {NNLS_ADDITION_FACTOR * n} column additions"
            )
        passive.append(enter)
        active.remove(enter)
        try:
            sub = least_squares(passive)
        except ValueError:
            passive.remove(enter)
            active.append(enter)
            rejected.add(enter)
            continue
        additions += 1
        rejected.clear()
        settle(sub)
    if diagnostics is not None:
        residual = [math.fsum(a * v for a, v in zip(row, x)) - y for row, y in zip(matrix, rhs)]
        gradient = [math.fsum(a * r for a, r in zip(column, residual)) for column in cols]
        allowances = [bound * size for size in sizes]
        violations = [abs(g) if value > 0 else max(0.0, -g) for g, value in zip(gradient, x)]
        diagnostics.update(
            residual=residual,
            residual_norm=math.hypot(*residual),
            gradient=gradient,
            optimality_allowances=allowances,
            optimality_passed=all(v <= a for v, a in zip(violations, allowances)),
            rejected_columns=sorted(rejected),
            column_additions=additions,
            condition_estimate=None,
            qualification='numerical KKT check of the supplied least-squares problem only; '
            'rank exclusions and input rounding can limit forward accuracy',
        )
    return x


def score(achieved: dict, targets: dict) -> tuple[float, list[dict]]:
    """The squared-relative-error loss and one row per nutrient (target, final and percent
    difference). Only strictly positive targets contribute to the loss.

    Aggregate ``N`` is scored against elemental N (N_NO3 + N_NH4 + N_UREA), not as a
    separate ion row invented from a form split.
    """
    loss = 0.0
    rows = []
    symbols = list(dict.fromkeys([*targets.keys(), *achieved.keys()]))
    for symbol in symbols:
        target = targets.get(symbol)
        if symbol == N_AGGREGATE:
            final = elemental_nitrogen(achieved)
        else:
            final = float(achieved.get(symbol) or 0.0)
        delta = None
        if target is not None and target > 0:
            delta = ((final - target) / target) * 100.0
            loss += (delta / 100.0) ** 2
        rows.append({"symbol": symbol, "target": target, "final": final, "deltaPct": delta})
    return loss, rows


class _InventoriedProduct(dict):
    """Internal per-fit cache; source assay remains untouched."""

    def __init__(self, product):
        super().__init__(product)
        self.inventory = material_inventory(product)


def _nutrients(product):
    inventory = getattr(product, 'inventory', None)
    return (inventory if inventory is not None else material_inventory(product))[
        'nutrient_percent'
    ]


def _delivery_rate(salt: dict, symbol: str) -> float:
    """mg/L per g/L of salt for a nutrient key, including aggregate elemental N."""
    nutrients = _nutrients(salt)
    if symbol == N_AGGREGATE:
        return sum(ppm_per_gram(nutrients.get(form, 0.0)) for form in N_FORMS)
    return ppm_per_gram(nutrients.get(symbol, 0.0))


def _concentration(profile: dict, symbol: str) -> float:
    """mg/L of a nutrient key on a form map; aggregate N is the form sum."""
    if symbol == N_AGGREGATE:
        return elemental_nitrogen(profile)
    return float(profile.get(symbol) or 0.0)


def forward(salts: list[dict], grams: list[float], water: dict | None = None) -> dict:
    """Nutrient concentrations (mg/L) from the water plus each salt's grams per litre.

    Returns form keys only. Aggregate elemental N is
    ``elemental_nitrogen(forward(...))``, never a duplicated ion invented here.
    """
    water = water or {}
    achieved = {symbol: float(value) for symbol, value in water.items()}
    for salt, gram in zip(salts, grams):
        if gram <= 0:
            continue
        for symbol, percent in _nutrients(salt).items():
            achieved[symbol] = achieved.get(symbol, 0.0) + gram * ppm_per_gram(percent)
    return achieved


def _fit(
    salts: list[dict],
    targets: dict,
    water: dict,
    ridge: float,
    maxima: dict | None = None,
    ceilings: dict[str, tuple[float, float]] | None = None,
    x0: list[float] | None = None,
    grams_cache: dict | None = None,
) -> dict:
    """Minimize positive-target squared relative errors with nonnegative doses.

    No dose or incidental-nutrient penalty enters the objective. An ion in
    ceilings, as (weight, aim mg/L), is pulled toward that aim. The matrix depends only
    on which ions have ceiling rows (aims change rhs alone), so grams_cache, when given,
    shares one Gram cache per set of ceiling ions.
    """
    _validate_ridge(ridge)
    maxima = maxima or {}
    ceilings = ceilings or {}
    # Include ceiling keys so aggregate N maxima (absent from salt assays) get a
    # matrix row; form ions already appear via nutrient_percent.
    symbols = list(
        dict.fromkeys(
            [
                *targets.keys(),
                *(symbol for salt in salts for symbol in _nutrients(salt)),
                *ceilings.keys(),
            ]
        )
    )
    matrix = []
    rhs = []
    for symbol in symbols:
        target = targets.get(symbol)
        rates = [_delivery_rate(salt, symbol) for salt in salts]
        if symbol == N_AGGREGATE:
            background = elemental_nitrogen(water)
        else:
            background = float(water.get(symbol) or 0.0)
        if target is not None and target > 0:
            matrix.append([rate / target for rate in rates])
            rhs.append((target - background) / target)
        if symbol in ceilings:
            weight, aim = ceilings[symbol]
            limit = maxima[symbol]
            matrix.append([weight * rate / limit for rate in rates])
            rhs.append(weight * (aim - background) / limit)
    gram = None
    if grams_cache is not None and matrix:
        key = tuple(sorted(ceilings))
        gram = grams_cache.get(key)
        if gram is None:
            gram = grams_cache[key] = _LazyGram([list(column) for column in zip(*matrix)])
    grams = nnls(matrix, rhs, x0, gram) if matrix else [0.0] * len(salts)
    achieved = forward(salts, grams, water)
    loss, rows = score(achieved, targets)
    return {"grams": grams, "loss": loss, "rows": rows}


def _fit_within(
    salts: list[dict],
    targets: dict,
    water: dict,
    ridge: float,
    maxima: dict,
    x0: list[float] | None = None,
) -> dict:
    """Fit with structural zero requirements and every stated nutrient maximum.

    The fit is convex, so a binding ceiling's optimum lies on the limit (#68). Each
    ceiling ion gets a row of moderate weight aimed at aim - shift, where aim is the
    limit less CEILING_MARGIN (so round-off cannot leave it exceeded) and the shift is
    the scaled Lagrange multiplier. The ion's excess over its aim falls as the shift
    grows, so each shift is found by a bracketed (Illinois) search; a ceiling whose
    shift reaches zero with the ion below its aim is released. Each refit starts from
    the last doses. A remainder after CEILING_STEPS is reported by _report as a limit
    violation.

    At a ceiling already reached by water, products carrying that ion cannot be added;
    Water above the ceiling remains an explicit violation. This is the
    infinite-multiplier limit of the search. Those products are left out directly (#86);
    searching instead
    grew the shift without bound, and with a second binding ceiling NNLS failed.
    """
    # Nonnegative product contributions cannot cancel an explicit zero.
    maxima = dict(maxima)
    maxima.update({symbol: 0.0 for symbol, target in targets.items() if target == 0})
    unreachable = {
        symbol
        for symbol, limit in maxima.items()
        if limit == 0 or _concentration(water, symbol) >= limit
    }
    if unreachable:
        keep = [
            i
            for i, salt in enumerate(salts)
            if not any(_delivery_rate(salt, s) > 0 for s in unreachable)
        ]
        solved = _fit_within(
            [salts[i] for i in keep],
            {s: v for s, v in targets.items() if s not in unreachable or v > 0},
            water,
            ridge,
            {s: v for s, v in maxima.items() if s not in unreachable},
            None if x0 is None else [x0[i] for i in keep],
        )
        grams = [0.0] * len(salts)
        for index, value in zip(keep, solved["grams"]):
            grams[index] = value
        achieved = forward(salts, grams, water)
        loss, rows = score(achieved, targets)
        return {"grams": grams, "loss": loss, "rows": rows}
    cache: dict = {}
    solved = _fit(salts, targets, water, ridge, maxima, x0=x0, grams_cache=cache)
    # symbol -> [shift, (lo shift, lo excess > 0) or None, (hi shift, hi excess < 0) or None, side]
    search: dict[str, list] = {}
    for _ in range(CEILING_STEPS):
        final = {row["symbol"]: float(row["final"] or 0.0) for row in solved["rows"]}
        converged = True
        for symbol, limit in maxima.items():
            # Nonpositive ceilings were eliminated by the unreachable-supply recursion.
            value = _concentration(final, symbol)
            if symbol not in search:
                if value <= limit:
                    continue
                search[symbol] = [0.0, None, None, 0]
                converged = False
                continue
            state = search[symbol]
            shift, excess = state[0], value - limit * (1 - CEILING_MARGIN)
            if abs(excess) <= CEILING_TOLERANCE * limit:
                continue
            if excess < 0 and shift == 0.0:
                del search[symbol]  # the ceiling does not bind
                continue
            converged = False
            side = 1 if excess > 0 else -1
            last = state[1] if side > 0 else state[2]
            if side > 0:
                state[1] = (shift, excess)
            else:
                state[2] = (shift, excess)
            lo, hi = state[1], state[2]
            # While NNLS keeps its active set the excess is affine in the shift, so a
            # secant through two points on one side lands on the root.
            secant = (
                shift - excess * (shift - last[0]) / (excess - last[1])
                if last is not None and last[1] != excess
                else math.nan
            )
            # A new search either records its positive excess at shift zero or is removed;
            # consequently every retained search has a lower endpoint.
            if hi is None:
                growth = max(2 * shift, shift + excess, 1e-12 * limit)
                shift = secant if shift < secant <= 4 * growth else growth  # expand to a bracket
            else:
                # Illinois: halve the retained end's excess when the same side repeats.
                g_lo, g_hi = lo[1], hi[1]
                if state[3] == side == 1:
                    g_hi /= 2
                    state[2] = (hi[0], g_hi)
                elif state[3] == side == -1:
                    g_lo /= 2
                    state[1] = (lo[0], g_lo)
                shift = (lo[0] * g_hi - hi[0] * g_lo) / (g_hi - g_lo)
                if not lo[0] < shift < hi[0]:
                    shift = (lo[0] + hi[0]) / 2
            state[0], state[3] = shift, side
        if converged:
            break
        ceilings = {
            symbol: (CEILING_WEIGHT, maxima[symbol] * (1 - CEILING_MARGIN) - state[0])
            for symbol, state in search.items()
        }
        solved = _fit(
            salts, targets, water, ridge, maxima, ceilings, x0=solved["grams"], grams_cache=cache
        )
    return solved


def _validate_ridge(ridge: float) -> None:
    """Reject retired regularization rather than silently changing the objective."""
    if isinstance(ridge, bool) or not isinstance(ridge, (int, float)) or ridge != 0:
        raise InputError(
            "ridge must be 0; dose regularization conflicts with accuracy-first fitting"
        )


def solve_weights(
    salts: list[dict], targets: dict, water: dict | None = None, ridge: float = 0.0
) -> dict:
    """Fit nonnegative g/L by positive-target squared relative error. ridge must be zero."""
    _validate_ridge(ridge)
    targets = validate_profile(targets, "targets")
    water = validate_profile(water or {}, "water")
    for salt in salts:
        conflict = assay_conflict(salt)
        if conflict is not None:
            raise InputError(conflict)
    solved = _fit_within(salts, targets, water, ridge, {})
    chosen = _chosen(salts, solved["grams"])
    solved.update(_report(solved["rows"], solved["grams"], []))
    solved["salts"] = chosen
    return solved


def _chosen(salts: list[dict], grams: list[float]) -> list[dict]:
    chosen = []
    for salt, gram in zip(salts, grams):
        if gram > KEEP_GRAMS:
            chosen.append(
                {
                    "id": salt["id"],
                    "name": salt["name"],
                    "gramsPerLitre": gram,
                }
            )
    return chosen


def _delta_map(rows: list[dict]) -> dict[str, float]:
    return {row["symbol"]: abs(row["deltaPct"]) for row in rows if row["deltaPct"] is not None}


def _still_within(new_rows: list[dict], old_rows: list[dict]) -> bool:
    previous = _delta_map(old_rows)
    current = _delta_map(new_rows)
    return current.keys() == previous.keys() and all(
        current[symbol] <= delta for symbol, delta in previous.items()
    )


def _supplies(salt: dict, symbol: str) -> bool:
    if symbol == N_AGGREGATE:
        return any(float(salt["elements"].get(form) or 0.0) > 0 for form in N_FORMS)
    return float(salt["elements"].get(symbol) or 0.0) > 0


def _simplify(
    salts: list[dict],
    targets: dict,
    water: dict,
    solved: dict,
    ridge: float,
    maxima: dict | None = None,
) -> dict:
    """Reduce product count only without degrading the original fit or hard limits.

    Binary64 comparisons are conservative: no extra accuracy allowance is granted
    for a preference. Numerically unequal but equivalent optima may retain more
    products. This is not a globally minimum-product-count search.
    """
    original_rows = solved["rows"]
    grams = solved["grams"][:]
    rows = solved["rows"]
    active = [index for index, gram in enumerate(grams) if gram > 0]
    changed = True
    while changed:
        changed = False
        for index in sorted(active, key=lambda item: grams[item]):
            others = [item for item in active if item != index]
            requested = [
                symbol
                for symbol, ppm in targets.items()
                if ppm > 0 and _supplies(salts[index], symbol)
            ]
            if any(
                symbol
                for symbol in requested
                if not any(_supplies(salts[item], symbol) for item in others)
            ):
                continue
            trial = _fit_within(
                [salts[item] for item in others],
                targets,
                water,
                ridge,
                maxima or {},
                x0=[grams[item] for item in others],
            )
            if (
                not _still_within(trial["rows"], original_rows)
                or trial["loss"] > solved["loss"]
                or assess_incidental(trial["rows"], maxima)["limitViolations"]
            ):
                continue
            grams = [0.0] * len(salts)
            for item, gram in zip(others, trial["grams"]):
                grams[item] = gram
            rows = trial["rows"]
            active = [item for item in others if grams[item] > 0]
            solved = {**trial, "grams": grams, "rows": rows}
            changed = True
            break
    solved["grams"] = grams
    solved["rows"] = rows
    return solved


def _eligible(
    library: list[dict], targets: dict, allow_ions: frozenset[str], allow_carbonates: bool
):
    excluded = []
    ready = []
    for salt in library:
        conflict = assay_conflict(salt)
        if conflict is not None:
            excluded.append({"id": salt.get("id"), "name": salt.get("name"), "reason": conflict})
            continue
        if salt.get("role") == PH_REAGENT:
            excluded.append(
                {
                    "id": salt.get("id"),
                    "name": salt.get("name"),
                    "reason": f"{salt.get('name')} is a pH reagent, not a nutrient salt",
                }
            )
            continue
        if is_carbonate(salt) and not allow_carbonates:
            excluded.append(
                {
                    "id": salt.get("id"),
                    "name": salt.get("name"),
                    "reason": f"{salt.get('name')} contains carbonate, which is not dissolved "
                    f"in a default recipe",
                }
            )
            continue
        carried = RESTRICTED_IONS.intersection(salt["elements"])
        blocked = {ion for ion in carried if ion not in targets and ion not in allow_ions}
        if blocked:
            excluded.append(
                {
                    "id": salt.get("id"),
                    "name": salt.get("name"),
                    "reason": (
                        f"{salt.get('name')} carries {', '.join(sorted(blocked))}, "
                        "which this formula does not ask for"
                    ),
                }
            )
            continue
        ready.append(_InventoriedProduct(salt))
    return ready, excluded


def _short(rows: list[dict], targets: dict) -> list[str]:
    """Requested ions that finished more than the tolerance below target.

    An overshoot is not a reason to add another salt. A chloride or sodium
    salt can only add its ions. It cannot pull an element back down.
    """
    final = {row["symbol"]: float(row["final"] or 0.0) for row in rows}
    floor = 1.0 - TOLERANCE_PCT / 100.0
    return [
        symbol
        for symbol, ppm in targets.items()
        if ppm > 0 and final.get(symbol, 0.0) < ppm * floor
    ]


def _recover(library, ready, excluded, targets, short):
    """Admit a held-back salt only when it is the only source of a short ion."""
    warnings = []
    by_id = {salt.get("id"): salt for salt in library}
    ready_ids = {salt.get("id") for salt in ready}
    for symbol in short:
        holders = []
        for item in excluded:
            salt = by_id.get(item["id"])
            if salt is None or salt.get("id") in ready_ids or not _supplies(salt, symbol):
                continue
            if "carries" not in item["reason"]:
                continue
            if CONSENT_IONS.intersection(salt["elements"]) - set(targets):
                continue
            holders.append(salt)
        if not holders:
            supplied = any(
                _supplies(salt, symbol) for salt in library if assay_conflict(salt) is None
            )
            if not supplied:
                warnings.append(f"None of the available products supplies {symbol}.")
            continue
        already = any(_supplies(item, symbol) for item in ready)
        for salt in holders:
            carried = sorted(RESTRICTED_IONS.intersection(salt["elements"]) - set(targets))
            extra = f" It also carries {', '.join(carried)}." if carried else ""
            if already:
                warnings.append(
                    f"{salt['name']} is included because {symbol} stayed more than "
                    f"{TOLERANCE_PCT:g}% short without it.{extra}"
                )
            else:
                warnings.append(
                    f"{salt['name']} is included because it is the only source of {symbol}.{extra}"
                )
            ready.append(_InventoriedProduct(salt))
            ready_ids.add(salt.get("id"))
            excluded = [item for item in excluded if item["id"] != salt["id"]]
    return ready, excluded, warnings


def _automatic_fit(library, salts, excluded, targets, water, ridge, maxima):
    """Grow the permitted supplied pool until no deficient nutrient adds a source.

    Every successful recovery adds an ID from the finite caller inventory. Each
    fit considers mixtures of the whole current pool; no target or limit changes.
    """
    warnings, attempts = [], []
    while True:
        attempts.append([salt['id'] for salt in salts])
        if salts:
            solved = _simplify(
                salts,
                targets,
                water,
                _fit_within(salts, targets, water, ridge, maxima),
                ridge,
                maxima,
            )
        else:
            loss, rows = score(forward([], [], water), targets)
            solved = dict(grams=[], rows=rows, loss=loss)
        short = _short(solved['rows'], targets)
        if not short:
            break
        previous_ids = {salt['id'] for salt in salts}
        salts, excluded, notes = _recover(library, salts, excluded, targets, short)
        warnings.extend(note for note in notes if note not in warnings)
        if {salt['id'] for salt in salts} == previous_ids:
            break
    if not salts:
        raise InputError("no salt remains after the assay and ion checks")
    return salts, excluded, solved, warnings, attempts


def _target_misses(salts: list[dict], targets: dict, water: dict, drop=frozenset()) -> set[str]:
    """Positive targets still missed by a least-squares fit on target rows alone."""
    kept = {symbol: ppm for symbol, ppm in targets.items() if ppm > 0 and symbol not in drop}
    if not kept or not salts:
        return set(kept)
    matrix, rhs = [], []
    for symbol, target in kept.items():
        matrix.append([_delivery_rate(salt, symbol) / target for salt in salts])
        rhs.append((target - _concentration(water, symbol)) / target)
    achieved = forward(salts, nnls(matrix, rhs), water)
    return {
        symbol
        for symbol, target in kept.items()
        if abs(_concentration(achieved, symbol) - target) / target * 100.0 > TOLERANCE_PCT
    }


def _diagnose(library, targets, water, rows, maxima, allowed, allow_carbonates) -> list[dict]:
    """Explain missed positive/zero targets with scoped structural proofs or
    non-certifying relaxed-search observations; never infer proof from a miss."""
    missed = [
        row
        for row in rows
        if (row["deltaPct"] is not None and abs(row["deltaPct"]) > TOLERANCE_PCT)
        or (row["target"] == 0 and row["final"] > 0)
    ]
    if not missed:
        return []
    usable = [
        salt
        for salt in library
        if assay_conflict(salt) is None
        and salt.get("role") != PH_REAGENT
        and (allow_carbonates or not is_carbonate(salt))
    ]
    consent = {ion for ion in CONSENT_IONS if ion not in targets and ion not in allowed}
    engine_pool = [salt for salt in usable if not consent.intersection(salt["elements"])]
    final = {row["symbol"]: float(row["final"] or 0.0) for row in rows}
    binding = sorted(
        ion
        for ion, limit in maxima.items()
        if limit > 0
        and _concentration(final, ion) >= limit * (1 - CEILING_MARGIN - CEILING_TOLERANCE)
    )
    base = _target_misses(engine_pool, targets, water)
    with_chloride = None
    dropped_ok: dict[str, bool] = {}  # each drop-one fit is shared by every missed target

    def reachable_without(target: str) -> bool:
        if target not in dropped_ok:
            dropped_ok[target] = not _target_misses(engine_pool, targets, water, {target})
        return dropped_ok[target]

    out = []
    for row in missed:
        symbol = row["symbol"]
        item = {
            "symbol": symbol,
            "target": row["target"],
            "final": row["final"],
            "deltaPct": row["deltaPct"],
            "status": "search_incomplete",
            "proofScope": None,
            "searchScope": "Target-only relaxed least-squares searches omit zero and maximum "
            "constraints; failed searches and observed binding limits are not proofs.",
        }
        sources = [salt for salt in usable if _supplies(salt, symbol)]
        zero_limits = {s for s, v in (maxima | targets).items() if v == 0}
        zero_limits.update(s for s, v in maxima.items() if v == 0)
        blocked_sources = [
            salt for salt in sources if any(_delivery_rate(salt, s) > 0 for s in zero_limits)
        ]
        if _concentration(water, symbol) > targets[symbol]:
            item["reason"] = "water_exceeds_target"
            item["waterPpm"] = _concentration(water, symbol)
        elif symbol in maxima and targets[symbol] > maxima[symbol]:
            item["reason"] = "target_above_maximum"
            item["maximumPpm"] = maxima[symbol]
        elif not sources:
            item["reason"] = "no_source"
        elif len(blocked_sources) == len(sources) and _concentration(water, symbol) < targets[symbol]:
            item["reason"] = "prohibited_by_zero_requirement"
            item["zeroRequirements"] = sorted(
                s for s in zero_limits if any(_delivery_rate(salt, s) > 0 for salt in sources)
            )
            item["blockedProducts"] = [salt.get("id") for salt in sources]
        elif not base:
            item["reason"] = "limited_by_ceiling" if binding else "fit_degradation"
            item["bindingLimits"] = binding
        else:
            others = [t for t, ppm in targets.items() if ppm > 0 and t != symbol]
            item["reason"] = "conflicting_targets"
            item["conflictsWith"] = [t for t in others if reachable_without(t)]
            if consent:
                if with_chloride is None:
                    with_chloride = not _target_misses(usable, targets, water)
                item["reachableWithChloride"] = with_chloride
        if item["reason"] in {
            "water_exceeds_target",
            "target_above_maximum",
            "no_source",
            "prohibited_by_zero_requirement",
        }:
            item["status"] = "proven_infeasible"
            item["proofScope"] = (
                "Declared nonnegative nutrient inventory, source water, zero requirements "
                "and maxima; no subtraction or excluded carbonate/pH-reagent source allowed. "
                "This is a nutrient constraint proof, not a physical or global chemistry claim."
            )
        out.append(item)
    return out


def _charge_report(result):
    """Refresh partial charge diagnostics from the final emitted nutrient inventory."""
    result["targetIonBalance"] = target_ion_balance(
        {row["symbol"]: row["target"] for row in result["rows"] if row["target"] is not None}
    )
    result["recipeIonBalance"] = target_ion_balance(
        {row["symbol"]: row["final"] for row in result["rows"]}
    )
    result["chargeAssessment"] = {
        "status": "partial_charge_inventory",
        "assayOnlyProducts": [
            item['recordId']
            for item in result['materialInventory']
            if item['status'] == 'assay_only'
        ],
        "limitation": "recipeIonBalance includes emitted nutrient counterions and water under "
        "the same convention as targetIonBalance. Full analytical components are recorded in "
        "materialInventory, but pH speciation, ligand charge and complete water chemistry "
        "are not established by these nutrient profiles. Neither balance proves infeasibility.",
    }


def _documents(value) -> list[dict]:
    """Flatten a document reference, a list of them, or a {role: reference} map to a list."""
    if (
        isinstance(value, dict)
        and value
        and all(item is None or isinstance(item, dict) for item in value.values())
    ):
        value = list(value.values())
    if isinstance(value, dict):
        return [dict(value)]
    return [dict(item) for item in (value or ()) if item]


def _provenance(record: dict) -> dict:
    """Provenance of the record that produced a salt entry; never guessed when absent."""
    own = record.get("provenance")
    if own:
        # A resolved record keeps its grade/lot documents and the shipped catalogue reference.
        documents = _documents(own.get("documents")) + _documents(own.get("source"))
        return {
            "recordId": own.get("recordId", record["id"]),
            "identityId": own.get("identityId"),
            "analysisBasis": own.get("analysisBasis", "unattributed"),
            "documents": documents,
            "flags": list(own.get("flags") or ()),
            "sourceStatus": own.get("sourceStatus", "declared_unattributed"),
            "assumptionStatus": own.get(
                "assumptionStatus", "declared_composition_not_independently_verified"
            ),
            "atomicMassConvention": own.get("atomicMassConvention", ATOMIC_CONVENTION),
        }
    if record.get("identityId") or record.get("analysisBasis"):
        return {
            "recordId": record["id"],
            "identityId": record.get("identityId"),
            "analysisBasis": record.get("analysisBasis") or "unattributed",
            "documents": _documents(record.get("source")),
            "flags": [],
            "sourceStatus": (
                "catalogue_documented" if record.get("source") else "catalogue_unattributed"
            ),
            "assumptionStatus": "declared_composition_not_independently_verified",
            "atomicMassConvention": ATOMIC_CONVENTION,
        }
    return {
        "recordId": record["id"],
        "identityId": None,
        "analysisBasis": "unattributed",
        "documents": [],
        "flags": [],
        "sourceStatus": "declared_unattributed",
        "assumptionStatus": "declared_composition_not_independently_verified",
        "atomicMassConvention": ATOMIC_CONVENTION,
    }


def _report(
    rows: list[dict], grams: list[float], warnings: list[str], maxima: dict | None = None
) -> dict:
    deltas = [abs(row["deltaPct"]) for row in rows if row["deltaPct"] is not None]
    undesired = [
        {"symbol": row["symbol"], "ppm": round(row["final"], 4)}
        for row in rows
        if row["target"] is None and row["final"] > 0.01
    ]
    incidental = assess_incidental(rows, maxima)
    return {
        "feasible": any(row["target"] is not None for row in rows)
        and (not deltas or max(deltas) <= TOLERANCE_PCT)
        and not incidental["limitViolations"],
        **incidental,
        "maxAbsDeltaPct": round(max(deltas), 4) if deltas else None,
        "undesiredIons": undesired,
        "totalGramsPerLitre": sum(gram for gram in grams if gram > 0),
        "warnings": warnings,
    }


def recommend(
    library: list[dict],
    targets: dict,
    water: dict | None = None,
    *,
    allow_ions: frozenset[str] | set[str] | None = None,
    allow_carbonates: bool = False,
    ridge: float = 0.0,
    maximum_concentrations: dict | None = None,
    max_ammonium_fraction: float | None = AMMONIUM_FRACTION,
) -> dict:
    """Select eligible products and fit non-negative product g/L.

    Args:
        library: Product records with id, name, formula and elemental mass
            percentages in elements. Use load_library()['salts'] deliberately.
        targets: Required nonempty elemental mg/L map. Nitrogen forms are
            separate N_NO3, N_NH4 and N_UREA keys; optional aggregate ``N`` is
            elemental total N (sum of those forms) without inventing a form
            split. Stated forms plus ``N`` must agree or validate_profile errors.
            An explicit zero prohibits positive contribution, unlike a missing key.
        water: Source-water elemental mg/L; omitted entries default to zero.
            Bare ``N`` is not a water ion (use form keys).
        allow_ions: Explicit exceptions to the default restricted-ion filter.
        allow_carbonates: Permit carbonate products in nutrient fitting only;
            this does not establish dissolution or stock compatibility.
        ridge: Retained compatibility argument; must be zero. Nonzero dose
            regularization raises InputError because it degrades target accuracy.
        maximum_concentrations: Optional hard mg/L ceilings for any nutrient, for
            example {"Cl": 70}. An ion with a positive ceiling is admitted like
            allow_ions. Untargeted nutrients are not penalized up to their ceiling;
            a fit above it is solved again with the ion held on the ceiling as a
            constraint, and any
            excess that cannot be removed is reported in limitViolations with
            feasible False. Omitted keeps the default.
        max_ammonium_fraction: When targets omit N_NH4 (an explicit 0 means
            none wanted) and no N_NH4 maximum is given, incidental NH4-N may reach this share of
            the total target N (form keys, or aggregate ``N`` when forms are omitted),
            capped at 1.5 mmol/L NH4-N (``AMMONIUM_CAP_MG_PER_L``). Default 0.10
            (Dutch soilless practice). None restores a fit with no ammonium ceiling.
            Applied policy is disclosed on ``ammoniumLimit`` (fraction, cap, achieved).

    Returns:
        Dictionary containing identity-bearing salts with gramsPerLitre,
        nutrient rows, feasibility, incidental review, warnings and exclusions.
        Each salt carries provenance (recordId, identityId, analysisBasis,
        documents, flags) taken from the record that produced it, or
        analysisBasis "unattributed"; identitiesSha256 pins the catalogue.
        Supported counterions are included in the fitting and forward nutrient
        inventory. materialInventory exposes conserved components and limitations;
        eligibility policy still uses the declared assay and explicit permissions.
        The raw grams vector follows the internal eligible/recovered product
        order, NOT necessarily the original library order. Use salts for
        product-to-dose mapping. Feasible requires positive-target fit within 1%,
        satisfied zero requirements and maxima, and no requirement conflicts.
        requirementConflicts identifies targets above maxima and water above limits.
        substitutionSearch records supplied and attempted product IDs and whether
        a nutrient-feasible candidate was found. Recovery never expands the supplied
        inventory; exhausted search is not a global infeasibility certificate.
        This is not chemical, stock or operational approval.

    Raises:
        InputError: Invalid targets/water or no eligible products. Inspect
            exclusions and warnings for skipped or recovered candidates.
    """
    _validate_ridge(ridge)
    targets = validate_profile(targets, "targets")
    if not targets:
        raise InputError("targets are required")
    water = validate_profile(water or {}, "water")
    allowed = frozenset(allow_ions or ())
    if allowed:
        validate_profile({ion: 0.0 for ion in allowed}, "allow_ions")
    maxima = validate_profile(maximum_concentrations or {}, "maximum_concentrations")
    allowed |= {ion for ion, limit in maxima.items() if limit > 0}
    ammonium_limit = None
    if max_ammonium_fraction is not None:
        if (
            isinstance(max_ammonium_fraction, bool)
            or not isinstance(max_ammonium_fraction, (int, float))
            or not 0 <= max_ammonium_fraction <= 1
        ):
            raise InputError("max_ammonium_fraction must be a number in [0, 1]")
        total_n = sum(targets.get(key, 0.0) for key in N_FORMS)
        if total_n <= 0 and N_AGGREGATE in targets:
            total_n = float(targets[N_AGGREGATE])
        # An explicit N_NH4 target (including 0, "none wanted") keeps its own row.
        if total_n > 0 and "N_NH4" not in targets and "N_NH4" not in maxima:
            ammonium_limit = incidental_ammonium_limit(
                total_n,
                max_ammonium_fraction,
                AMMONIUM_CAP_MG_PER_L,
                AMMONIUM_BASIS,
            )
            maxima["N_NH4"] = ammonium_limit["mgPerL"]
    salts, excluded = _eligible(library, targets, allowed, allow_carbonates)
    warnings: list[str] = []
    balance = target_ion_balance(targets)
    if balance["exceedsWarning"]:
        warnings.append(
            f"The requested nutrient subset is not electrically balanced under the stated "
            f"ion convention: cations {balance['cationsMeqPerL']:.2f} "
            f"vs "
            f"anions {balance['anionsMeqPerL']:.2f} meq/L ({balance['imbalancePercent']:+.1f}%). "
            "Untargeted counterions and other species may balance the subset; "
            "this check does not prove nutrient infeasibility."
        )
    salts, excluded, solved, recovered, attempts = _automatic_fit(
        library, salts, excluded, targets, water, ridge, maxima
    )
    warnings.extend(recovered)
    solved["salts"] = _chosen(salts, solved["grams"])
    chosen_names = {item["name"] for item in solved["salts"]}
    warnings = [
        note
        for note in warnings
        if " is included" not in note or note.split(" is included", 1)[0] in chosen_names
    ]
    solved["saltIds"] = [item["id"] for item in solved["salts"]]
    by_id = {salt.get("id"): salt for salt in salts}
    for item in solved["salts"]:
        item["provenance"] = _provenance(by_id[item["id"]])
        drift = assay_drift(by_id[item["id"]])
        if drift:
            warnings.append(drift)
    from .materials import (
        IDENTITIES_SHA256,
    )  # local: keeps engine importable without the catalogue at load

    solved['materialInventory'] = [
        dict(
            recordId=item['id'],
            name=item['name'],
            gramsPerLitre=item['gramsPerLitre'],
            **(
                getattr(by_id[item['id']], 'inventory', None)
                or material_inventory(by_id[item['id']])
            ),
        )
        for item in solved['salts']
    ]
    solved["identitiesSha256"] = IDENTITIES_SHA256
    solved["excluded"] = excluded
    counterion_na = counterion_sodium_mg_per_l(
        [(by_id[item["id"]], item["gramsPerLitre"]) for item in solved["salts"]]
    )
    if counterion_na > 0:
        warnings.append(
            "Fit includes formula counterion sodium (chelates D2, "
            f"CH - micro borax/molybdate): {counterion_na:.4f} mg/L."
        )
    solved.update(_report(solved["rows"], solved["grams"], warnings, maxima))
    name_sources(solved, solved["salts"], salts, water)
    achieved_nh4 = next(
        (row["final"] for row in solved["rows"] if row["symbol"] == "N_NH4"), 0.0
    )
    solved["ammoniumLimit"] = with_ammonium_achieved(ammonium_limit, achieved_nh4)
    solved["targetIonBalance"] = balance
    _charge_report(solved)
    solved["requirementConflicts"] = [
        {
            "symbol": symbol,
            "reason": "target_above_maximum",
            "targetPpm": target,
            "maximumPpm": maxima[symbol],
        }
        for symbol, target in targets.items()
        if symbol in maxima and target > maxima[symbol]
    ] + [
        {
            "symbol": symbol,
            "reason": "water_above_maximum",
            "waterPpm": _concentration(water, symbol),
            "maximumPpm": limit,
        }
        for symbol, limit in (maxima | {s: 0.0 for s, t in targets.items() if t == 0}).items()
        if _concentration(water, symbol) > limit
    ]
    if solved["requirementConflicts"]:
        solved["feasible"] = False
    solved["unmetTargets"] = _diagnose(
        library, targets, water, solved["rows"], maxima, allowed, allow_carbonates
    )
    solved['substitutionSearch'] = {
        'status': 'candidate_found' if solved['feasible'] else 'search_incomplete',
        'availableProductIds': [salt.get('id') for salt in library],
        'attemptedProductIds': attempts,
        'method': 'whole-pool nonnegative fitting with monotone permitted-source recovery',
        'scope': 'Caller-supplied inventory only; unchanged targets, water and hard limits. '
        'Input order breaks numerical ties. Exhaustion is not global infeasibility; '
        'structural proofs are recorded separately in unmetTargets.',
    }
    return solved
