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
    CONSENT_IONS,
    RESTRICTED_IONS,
    InputError,
    assay_conflict,
    assay_drift,
    is_carbonate,
    target_ion_balance,
    validate_profile,
)
from .nutrient_acceptance import assess_incidental, name_sources
from .product_conversion import counterion_sodium_mg_per_l

# Rank and feasibility threshold, relative to the problem's column scale.
EPS = 1e-10
# Column additions allowed per column before NNLS reports non-convergence (#55).
NNLS_ADDITION_FACTOR = 4
# Smallest Cholesky pivot, relative to the column's squared norm, accepted by the Gram
# path (#59); below it the subproblem is ill-conditioned and Householder decides.
GRAM_PIVOT_FLOOR = 1e-8
# Pivot ratio below which the Gram solution is refined against the original columns.
GRAM_REFINE_BELOW = 1e-4
# Double-precision unit round-off, for scale-aware NNLS optimality tests.
ROUNDOFF = 2.220446049250313e-16
# Grams below this do not appear in the recipe.
KEEP_GRAMS = 1e-6
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
# Default ceiling on incidental NH4-N (#54): the smaller of 10% of the formula's total
# target N and 1.5 mmol/L NH4. Owner decisions (2026-10-20) based on Dutch soilless
# practice: NH4 at 5-15% of total N with at most 1-1.5 mmol/L (Van der Lugt et al.
# 2016 handbook, after De Kreij, Voogt et al.), "heavy fruit bearing - max 90:10"
# NO3:NH4 (Voogt, WUR lecture, edepot.wur.nl/13081), and Dutch standard solutions at
# 5.9-8.8% NH4-N for most crops. Dickson & Fisher (2019, doi:10.21273/HORTSCI13959-19)
# cite 5-10% (hydroponics) / 10-15% (substrate) to Sonneveld & Voogt (2009) without a
# page; that primary text has not been verified.
AMMONIUM_FRACTION = 0.10
AMMONIUM_CAP_MG_PER_L = 1.5 * 14.0067
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
        if norm < rank_tol * rank_tol:
            raise ValueError("rank deficient least squares block")
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
        if abs(matrix[i][i]) < rank_tol:
            raise ValueError("rank deficient least squares block")
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
) -> list[float]:
    """Lawson-Hanson non-negative least squares. matrix is rows × columns.

    x0, when given, is a non-negative starting point (warm start, #59): its positive
    entries form the initial passive set. The problem is convex, so the optimum is
    the same; a nearby start needs far fewer column additions. gram, when given, is a
    _LazyGram of this same matrix, shared by calls that change only rhs.
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
    cross = [sum(a * b for a, b in zip(ci, rhs)) for ci in cols]
    cross_size = [sum(abs(a * b) for a, b in zip(ci, rhs)) for ci in cols]

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
    return x


def score(achieved: dict, targets: dict) -> tuple[float, list[dict]]:
    loss = 0.0
    rows = []
    symbols = list(dict.fromkeys([*targets.keys(), *achieved.keys()]))
    for symbol in symbols:
        target = targets.get(symbol)
        final = float(achieved.get(symbol) or 0.0)
        delta = None
        if target is not None and target > 0:
            delta = ((final - target) / target) * 100.0
            loss += (delta / 100.0) ** 2
        elif final > 0:
            loss += (final / 100.0) ** 2
        rows.append({"symbol": symbol, "target": target, "final": final, "deltaPct": delta})
    return loss, rows


def forward(salts: list[dict], grams: list[float], water: dict | None = None) -> dict:
    water = water or {}
    achieved = {symbol: float(value) for symbol, value in water.items()}
    for salt, gram in zip(salts, grams):
        if gram <= 0:
            continue
        for symbol, percent in salt["elements"].items():
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
    """Non-negative grams. ridge is an L2 penalty on grams, not a salt count.

    An incidental ion with a stated positive maximum is not penalized; an ion in
    ceilings, as (weight, aim mg/L), is pulled toward that aim. The matrix depends only
    on which ions have ceiling rows (aims change rhs alone), so grams_cache, when given,
    shares one Gram cache per set of ceiling ions.
    """
    maxima = maxima or {}
    ceilings = ceilings or {}
    symbols = list(
        dict.fromkeys(
            [
                *targets.keys(),
                *(symbol for salt in salts for symbol in salt["elements"]),
            ]
        )
    )
    matrix = []
    rhs = []
    for symbol in symbols:
        target = targets.get(symbol)
        rates = [ppm_per_gram(salt["elements"].get(symbol, 0.0)) for salt in salts]
        background = float(water.get(symbol) or 0.0)
        if target is not None and target > 0:
            matrix.append([rate / target for rate in rates])
            rhs.append((target - background) / target)
        elif symbol in ceilings:
            weight, aim = ceilings[symbol]
            limit = maxima[symbol]
            matrix.append([weight * rate / limit for rate in rates])
            rhs.append(weight * (aim - background) / limit)
        elif maxima.get(symbol, 0.0) > 0:
            continue
        else:
            matrix.append([rate / 100.0 for rate in rates])
            rhs.append(-background / 100.0)
    if ridge > 0 and salts:
        for index in range(len(salts)):
            row = [0.0] * len(salts)
            row[index] = ridge
            matrix.append(row)
            rhs.append(0.0)
    gram = None
    if grams_cache is not None and matrix:
        key = tuple(sorted(ceilings))
        gram = grams_cache.get(key)
        if gram is None:
            gram = grams_cache[key] = _LazyGram([list(column) for column in zip(*matrix)])
    grams = nnls(matrix, rhs, x0, gram)
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
    """Fit, then hold any incidental ion that passed its stated maximum on that maximum.

    The fit is convex, so a binding ceiling's optimum lies on the limit (#68). Each
    ceiling ion gets a row of moderate weight aimed at aim - shift, where aim is the
    limit less CEILING_MARGIN (so round-off cannot leave it exceeded) and the shift is
    the scaled Lagrange multiplier. The ion's excess over its aim falls as the shift
    grows, so each shift is found by a bracketed (Illinois) search; a ceiling whose
    shift reaches zero with the ion below its aim is released. Each refit starts from
    the last doses. A remainder after CEILING_STEPS is reported by _report as a limit
    violation.

    A ceiling the water alone already reaches cannot be met: any product carrying that
    ion only adds to the violation, which is the infinite-multiplier limit of the
    search. Those products are left out of the fit directly (#86); searching instead
    grew the shift without bound, and with a second binding ceiling NNLS failed.
    """
    unreachable = {
        symbol
        for symbol, limit in maxima.items()
        if limit > 0
        and symbol not in targets
        and float(water.get(symbol) or 0.0) >= limit * (1 - CEILING_MARGIN)
    }
    if unreachable:
        keep = [
            i
            for i, salt in enumerate(salts)
            if not any(salt["elements"].get(s, 0.0) for s in unreachable)
        ]
        solved = _fit_within(
            [salts[i] for i in keep],
            targets,
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
            if limit <= 0 or symbol in targets:
                continue
            value = final.get(symbol, 0.0)
            if symbol not in search:
                if value <= limit + 1e-12:
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
            if lo is None:
                shift = secant if 0 <= secant < shift else shift / 2  # come back down
            elif hi is None:
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


def solve_weights(
    salts: list[dict], targets: dict, water: dict | None = None, ridge: float = 0.0
) -> dict:
    """Non-negative grams per litre minimizing squared Δ%."""
    targets = validate_profile(targets, "targets")
    water = validate_profile(water or {}, "water")
    for salt in salts:
        conflict = assay_conflict(salt)
        if conflict is not None:
            raise InputError(conflict)
    solved = _fit(salts, targets, water, ridge)
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
                    "gramsPerLitre": round(gram, 6),
                }
            )
    return chosen


def _delta_map(rows: list[dict]) -> dict[str, float]:
    return {row["symbol"]: abs(row["deltaPct"]) for row in rows if row["deltaPct"] is not None}


def _still_within(new_rows: list[dict], old_rows: list[dict]) -> bool:
    previous = _delta_map(old_rows)
    for symbol, delta in _delta_map(new_rows).items():
        limit = max(previous.get(symbol, 0.0), TOLERANCE_PCT)
        if delta > limit + 1e-6:
            return False
    return True


def _supplies(salt: dict, symbol: str) -> bool:
    return float(salt["elements"].get(symbol) or 0.0) > 0


def _simplify(
    salts: list[dict],
    targets: dict,
    water: dict,
    solved: dict,
    ridge: float,
    maxima: dict | None = None,
) -> dict:
    """Drop a salt when the refit still meets every requested ion."""
    grams = solved["grams"][:]
    rows = solved["rows"]
    active = [index for index, gram in enumerate(grams) if gram > KEEP_GRAMS]
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
            if not _still_within(trial["rows"], rows):
                continue
            grams = [0.0] * len(salts)
            for item, gram in zip(others, trial["grams"]):
                grams[item] = gram
            rows = trial["rows"]
            active = [item for item in others if grams[item] > KEEP_GRAMS]
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
        ready.append(salt)
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
            ready.append(salt)
            ready_ids.add(salt.get("id"))
            excluded = [item for item in excluded if item["id"] != salt["id"]]
    return ready, excluded, warnings


def _target_misses(salts: list[dict], targets: dict, water: dict, drop=frozenset()) -> set[str]:
    """Positive targets still missed by a least-squares fit on target rows alone."""
    kept = {symbol: ppm for symbol, ppm in targets.items() if ppm > 0 and symbol not in drop}
    if not kept or not salts:
        return set(kept)
    matrix, rhs = [], []
    for symbol, target in kept.items():
        matrix.append([ppm_per_gram(salt["elements"].get(symbol, 0.0)) / target for salt in salts])
        rhs.append((target - float(water.get(symbol) or 0.0)) / target)
    achieved = forward(salts, nnls(matrix, rhs), water)
    return {
        symbol
        for symbol, target in kept.items()
        if abs(achieved.get(symbol, 0.0) - target) / target * 100.0 > TOLERANCE_PCT
    }


def _diagnose(library, targets, water, rows, maxima, allowed, allow_carbonates) -> list[dict]:
    """Explain each missed positive target (#39). A least-squares diagnosis on the
    target rows alone: it names a cause, it does not prove infeasibility."""
    missed = [
        row for row in rows if row["deltaPct"] is not None and abs(row["deltaPct"]) > TOLERANCE_PCT
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
        if limit > 0 and ion not in targets and final.get(ion, 0.0) >= limit * (1 - 1e-6)
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
        }
        if not any(_supplies(salt, symbol) for salt in usable):
            item["reason"] = "no_source"
        elif not base:
            item["reason"] = "limited_by_ceiling" if binding else "incidental_tradeoff"
            item["bindingLimits"] = binding
        else:
            others = [t for t, ppm in targets.items() if ppm > 0 and t != symbol]
            item["reason"] = "conflicting_targets"
            item["conflictsWith"] = [t for t in others if reachable_without(t)]
            if consent:
                if with_chloride is None:
                    with_chloride = not _target_misses(usable, targets, water)
                item["reachableWithChloride"] = with_chloride
        out.append(item)
    return out


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
        }
    if record.get("identityId") or record.get("analysisBasis"):
        return {
            "recordId": record["id"],
            "identityId": record.get("identityId"),
            "analysisBasis": record.get("analysisBasis") or "unattributed",
            "documents": _documents(record.get("source")),
            "flags": [],
        }
    return {
        "recordId": record["id"],
        "identityId": None,
        "analysisBasis": "unattributed",
        "documents": [],
        "flags": [],
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
        "feasible": bool(deltas)
        and max(deltas) <= TOLERANCE_PCT
        and not incidental["limitViolations"],
        **incidental,
        "maxAbsDeltaPct": round(max(deltas), 4) if deltas else None,
        "undesiredIons": undesired,
        "totalGramsPerLitre": round(sum(gram for gram in grams if gram > 0), 6),
        "warnings": warnings,
    }


def recommend(
    library: list[dict],
    targets: dict,
    water: dict | None = None,
    *,
    allow_ions: frozenset[str] | set[str] | None = None,
    allow_carbonates: bool = False,
    ridge: float = 0.02,
    maximum_concentrations: dict | None = None,
    max_ammonium_fraction: float | None = AMMONIUM_FRACTION,
) -> dict:
    """Select eligible products and fit non-negative product g/L.

    Args:
        library: Product records with id, name, formula and elemental mass
            percentages in elements. Use load_library()['salts'] deliberately.
        targets: Required nonempty elemental mg/L map; nitrogen forms are
            separate N_NO3, N_NH4 and N_UREA keys, not generic total N.
        water: Source-water elemental mg/L; omitted entries default to zero.
        allow_ions: Explicit exceptions to the default restricted-ion filter.
        allow_carbonates: Permit carbonate products in nutrient fitting only;
            this does not establish dissolution or stock compatibility.
        ridge: L2 dose penalty, not a limit on the number of products.
        maximum_concentrations: Optional mg/L ceilings for incidental ions, for
            example {"Cl": 70}. An ion with a positive ceiling is admitted like
            allow_ions and is not penalized up to the ceiling; a fit above it is
            solved again with the ion held on the ceiling as a constraint, and any
            excess that cannot be removed is reported in limitViolations with
            feasible False. Omitted keeps the default.
        max_ammonium_fraction: When targets omit N_NH4 (an explicit 0 means
            none wanted) and no N_NH4 maximum is given, incidental NH4-N may reach this share of
            the total target N (N_NO3 + N_NH4 + N_UREA), capped at 1.5 mmol/L
            NH4 (21.01 mg/L N). Default 0.10 (Dutch soilless practice; users may
            raise it, e.g. to 0.15); None keeps the penalty-only fit.

    Returns:
        Dictionary containing identity-bearing salts with gramsPerLitre,
        nutrient rows, feasibility, incidental review, warnings and exclusions.
        Each salt carries provenance (recordId, identityId, analysisBasis,
        documents, flags) taken from the record that produced it, or
        analysisBasis "unattributed"; identitiesSha256 pins the catalogue.
        Chelate counterion sodium (D2) is added to the Na row and incidental
        review after the fit; it never affects eligibility, the fit or grams.
        The raw grams vector follows the internal eligible/recovered product
        order, NOT necessarily the original library order. Use salts for
        product-to-dose mapping. Feasible is positive-target fit within 1%,
        not chemical, stock or operational approval.

    Raises:
        InputError: Invalid targets/water or no eligible products. Inspect
            exclusions and warnings for skipped or recovered candidates.
    """
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
        total_n = sum(targets.get(key, 0.0) for key in ("N_NO3", "N_NH4", "N_UREA"))
        # An explicit N_NH4 target (including 0, "none wanted") keeps its own row.
        if total_n > 0 and "N_NH4" not in targets and "N_NH4" not in maxima:
            limit = min(max_ammonium_fraction * total_n, AMMONIUM_CAP_MG_PER_L)
            if limit > 0:
                maxima["N_NH4"] = limit
                ammonium_limit = {
                    "mgPerL": limit,
                    "fractionOfTotalN": max_ammonium_fraction,
                    "absoluteCapMgPerL": AMMONIUM_CAP_MG_PER_L,
                    "basis": AMMONIUM_BASIS,
                }
    salts, excluded = _eligible(library, targets, allowed, allow_carbonates)
    if not salts:
        raise InputError("no salt remains after the assay and ion checks")
    warnings: list[str] = []
    balance = target_ion_balance(targets)
    if balance["exceedsWarning"]:
        side = "cations" if balance["imbalancePercent"] > 0 else "anions"
        warnings.append(
            f"The formula is not electrically balanced: cations {balance['cationsMeqPerL']:.2f} "
            f"vs "
            f"anions {balance['anionsMeqPerL']:.2f} meq/L ({balance['imbalancePercent']:+.1f}%). "
            f"No salt combination meets every target exactly; the excess {side} need counter-ions "
            "the formula does not list."
        )
    solved = _simplify(
        salts, targets, water, _fit_within(salts, targets, water, ridge, maxima), ridge, maxima
    )
    short = _short(solved["rows"], targets)
    if short:
        salts, excluded, recovered = _recover(library, salts, excluded, targets, short)
        warnings.extend(recovered)
        if recovered:
            solved = _simplify(
                salts,
                targets,
                water,
                _fit_within(salts, targets, water, ridge, maxima),
                ridge,
                maxima,
            )
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

    solved["identitiesSha256"] = IDENTITIES_SHA256
    solved["excluded"] = excluded
    counterion_na = counterion_sodium_mg_per_l(
        [(by_id[item["id"]], item["gramsPerLitre"]) for item in solved["salts"]]
    )
    if counterion_na > 0:
        na_row = next((row for row in solved["rows"] if row["symbol"] == "Na"), None)
        if na_row is None:
            na_row = {"symbol": "Na", "target": None, "final": 0.0, "deltaPct": None}
            solved["rows"].append(na_row)
        na_row["final"] += counterion_na
        if na_row["target"] is not None and na_row["target"] > 0:
            na_row["deltaPct"] = 100.0 * (na_row["final"] - na_row["target"]) / na_row["target"]
        warnings.append(
            "Incidental Na includes formula counterion sodium (chelates D2, "
            f"CH - micro borax/molybdate): {counterion_na:.4f} mg/L."
        )
    solved.update(_report(solved["rows"], solved["grams"], warnings, maxima))
    name_sources(solved, solved["salts"], salts, water)
    solved["ammoniumLimit"] = ammonium_limit
    solved["targetIonBalance"] = balance
    solved["unmetTargets"] = _diagnose(
        library, targets, water, solved["rows"], maxima, allowed, allow_carbonates
    )
    return solved
