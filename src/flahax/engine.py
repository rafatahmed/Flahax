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
    RESTRICTED_IONS,
    InputError,
    assay_conflict,
    assay_drift,
    is_carbonate,
    validate_profile,
)

EPS = 1e-10
# Grams below this do not appear in the recipe.
KEEP_GRAMS = 1e-6
# A recipe is feasible when every requested ion is inside this Δ%.
TOLERANCE_PCT = 1.0


def load_library() -> dict:
    """Salt library, water profiles, and crop formulas shipped with the package."""
    text = files("flahax").joinpath("data/library.json").read_text(encoding="utf-8")
    return json.loads(text)


def ppm_per_gram(percent: float) -> float:
    """ppm in 1 litre from 1 gram of salt at an element percentage."""
    return float(percent) * 10.0


def gap_for(targets: dict, water: dict | None = None) -> dict:
    targets = validate_profile(targets, "targets")
    water = validate_profile(water or {}, "water")
    gap = {}
    for symbol in dict.fromkeys([*targets, *water]):
        if symbol not in targets:
            gap[symbol] = None
            continue
        gap[symbol] = targets[symbol] - water.get(symbol, 0.0)
    return gap


def _matvec(rows: list[list[float]], vec: list[float]) -> list[float]:
    return [sum(a * b for a, b in zip(row, vec)) for row in rows]


def _lstsq(columns: list[list[float]], b: list[float]) -> list[float]:
    """Least squares by Householder QR. columns are the active salt vectors."""
    if not columns:
        return []
    n = len(columns)
    m = len(b)
    matrix = [[columns[j][i] for j in range(n)] for i in range(m)]
    beta = b[:]
    for k in range(min(n, m)):
        sigma = math.sqrt(sum(matrix[i][k] * matrix[i][k] for i in range(k, m)))
        if sigma < EPS:
            raise ValueError("rank deficient least squares block")
        if matrix[k][k] < 0:
            sigma = -sigma
        reflector = [0.0] * m
        reflector[k] = matrix[k][k] + sigma
        for i in range(k + 1, m):
            reflector[i] = matrix[i][k]
        norm = sum(value * value for value in reflector)
        if norm < EPS:
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
        if abs(matrix[i][i]) < EPS:
            raise ValueError("rank deficient least squares block")
        total = beta[i] - sum(matrix[i][j] * solution[j] for j in range(i + 1, n))
        solution[i] = total / matrix[i][i]
    return solution


def nnls(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Lawson-Hanson non-negative least squares. matrix is rows × columns."""
    if not matrix:
        return []
    cols = [[matrix[r][c] for r in range(len(matrix))] for c in range(len(matrix[0]))]
    m = len(matrix)
    n = len(cols)
    x = [0.0] * n
    passive: list[int] = []
    active = list(range(n))

    def residual() -> list[float]:
        pred = _matvec(matrix, x)
        return [rhs[i] - pred[i] for i in range(m)]

    for _ in range(n * 4):
        resid = residual()
        weights = [sum(col[i] * resid[i] for i in range(m)) for col in cols]
        if not active:
            break
        enter = max(active, key=lambda j: weights[j])
        if weights[enter] <= EPS:
            break
        passive.append(enter)
        active.remove(enter)
        while True:
            try:
                sub = _lstsq([cols[j] for j in passive], rhs)
            except ValueError:
                passive.remove(enter)
                active.append(enter)
                break
            if all(value >= -EPS for value in sub):
                for j in range(n):
                    x[j] = 0.0
                for j, value in zip(passive, sub):
                    x[j] = max(0.0, value)
                break
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
                break
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


def _fit(salts: list[dict], targets: dict, water: dict, ridge: float) -> dict:
    """Non-negative grams. ridge is an L2 penalty on grams, not a salt count."""
    symbols = list(dict.fromkeys([
        *targets.keys(),
        *(symbol for salt in salts for symbol in salt["elements"]),
    ]))
    matrix = []
    rhs = []
    for symbol in symbols:
        target = targets.get(symbol)
        rates = [ppm_per_gram(salt["elements"].get(symbol, 0.0)) for salt in salts]
        background = float(water.get(symbol) or 0.0)
        if target is not None and target > 0:
            matrix.append([rate / target for rate in rates])
            rhs.append((target - background) / target)
        else:
            matrix.append([rate / 100.0 for rate in rates])
            rhs.append(-background / 100.0)
    if ridge > 0 and salts:
        for index in range(len(salts)):
            row = [0.0] * len(salts)
            row[index] = ridge
            matrix.append(row)
            rhs.append(0.0)
    grams = nnls(matrix, rhs)
    achieved = forward(salts, grams, water)
    loss, rows = score(achieved, targets)
    return {"grams": grams, "loss": loss, "rows": rows}


def solve_weights(salts: list[dict], targets: dict, water: dict | None = None, ridge: float = 0.0) -> dict:
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
            chosen.append({
                "id": salt["id"],
                "name": salt["name"],
                "gramsPerLitre": round(gram, 6),
            })
    return chosen


def _delta_map(rows: list[dict]) -> dict[str, float]:
    return {
        row["symbol"]: abs(row["deltaPct"])
        for row in rows
        if row["deltaPct"] is not None
    }


def _still_within(new_rows: list[dict], old_rows: list[dict]) -> bool:
    previous = _delta_map(old_rows)
    for symbol, delta in _delta_map(new_rows).items():
        limit = max(previous.get(symbol, 0.0), TOLERANCE_PCT)
        if delta > limit + 1e-6:
            return False
    return True


def _supplies(salt: dict, symbol: str) -> bool:
    return float(salt["elements"].get(symbol) or 0.0) > 0


def _simplify(salts: list[dict], targets: dict, water: dict, solved: dict, ridge: float) -> dict:
    """Drop a salt when the refit still meets every requested ion."""
    grams = solved["grams"][:]
    rows = solved["rows"]
    active = [index for index, gram in enumerate(grams) if gram > KEEP_GRAMS]
    changed = True
    while changed:
        changed = False
        for index in sorted(active, key=lambda item: grams[item]):
            others = [item for item in active if item != index]
            requested = [symbol for symbol, ppm in targets.items() if ppm > 0 and _supplies(salts[index], symbol)]
            if any(
                symbol for symbol in requested
                if not any(_supplies(salts[item], symbol) for item in others)
            ):
                continue
            trial = _fit([salts[item] for item in others], targets, water, ridge)
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


def _eligible(library: list[dict], targets: dict, allow_ions: frozenset[str], allow_carbonates: bool):
    excluded = []
    ready = []
    for salt in library:
        conflict = assay_conflict(salt)
        if conflict is not None:
            excluded.append({"id": salt.get("id"), "name": salt.get("name"), "reason": conflict})
            continue
        if is_carbonate(salt) and not allow_carbonates:
            excluded.append({
                "id": salt.get("id"),
                "name": salt.get("name"),
                "reason": f"{salt.get('name')} contains carbonate, which is not dissolved in a default recipe",
            })
            continue
        carried = RESTRICTED_IONS.intersection(salt["elements"])
        blocked = {ion for ion in carried if ion not in targets and ion not in allow_ions}
        if blocked:
            excluded.append({
                "id": salt.get("id"),
                "name": salt.get("name"),
                "reason": (
                    f"{salt.get('name')} carries {', '.join(sorted(blocked))}, "
                    "which this formula does not ask for"
                ),
            })
            continue
        ready.append(salt)
    return ready, excluded


def _missed(rows: list[dict], targets: dict) -> list[str]:
    deltas = _delta_map(rows)
    return [
        symbol for symbol, ppm in targets.items()
        if ppm > 0 and deltas.get(symbol, 0.0) > TOLERANCE_PCT
    ]


def _recover(library, ready, excluded, targets, missed):
    """Admit held-back salts only for requested ions the first fit missed."""
    warnings = []
    by_id = {salt.get("id"): salt for salt in library}
    ready_ids = {salt.get("id") for salt in ready}
    for symbol in missed:
        holders = []
        for item in excluded:
            salt = by_id.get(item["id"])
            if salt is None or salt.get("id") in ready_ids or not _supplies(salt, symbol):
                continue
            if "carries" not in item["reason"]:
                continue
            holders.append(salt)
        if not holders:
            supplied = any(
                _supplies(salt, symbol) for salt in library if assay_conflict(salt) is None
            )
            if not supplied:
                warnings.append(f"No salt in this library supplies {symbol}.")
            continue
        for salt in holders:
            carried = sorted(RESTRICTED_IONS.intersection(salt["elements"]) - set(targets))
            extra = f" It also carries {', '.join(carried)}." if carried else ""
            already = any(_supplies(item, symbol) for item in ready)
            if already:
                warnings.append(
                    f"{salt['name']} is included because {symbol} stayed outside "
                    f"{TOLERANCE_PCT:g}% without it.{extra}"
                )
            else:
                warnings.append(
                    f"{salt['name']} is included because it is the only source of {symbol}.{extra}"
                )
            ready.append(salt)
            ready_ids.add(salt.get("id"))
            excluded = [item for item in excluded if item["id"] != salt["id"]]
    return ready, excluded, warnings


def _report(rows: list[dict], grams: list[float], warnings: list[str]) -> dict:
    deltas = [abs(row["deltaPct"]) for row in rows if row["deltaPct"] is not None]
    undesired = [
        {"symbol": row["symbol"], "ppm": round(row["final"], 4)}
        for row in rows
        if row["target"] is None and row["final"] > 0.01
    ]
    return {
        "feasible": bool(deltas) and max(deltas) <= TOLERANCE_PCT,
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
) -> dict:
    """Solve against every salt the formula and the assays allow."""
    targets = validate_profile(targets, "targets")
    if not targets:
        raise InputError("targets are required")
    water = validate_profile(water or {}, "water")
    allowed = frozenset(allow_ions or ())
    if allowed:
        validate_profile({ion: 0.0 for ion in allowed}, "allow_ions")
    salts, excluded = _eligible(library, targets, allowed, allow_carbonates)
    if not salts:
        raise InputError("no salt remains after the assay and ion checks")
    warnings: list[str] = []
    solved = _simplify(salts, targets, water, _fit(salts, targets, water, ridge), ridge)
    missed = _missed(solved["rows"], targets)
    if missed:
        salts, excluded, recovered = _recover(library, salts, excluded, targets, missed)
        warnings.extend(recovered)
        if recovered:
            solved = _simplify(salts, targets, water, _fit(salts, targets, water, ridge), ridge)
    solved["salts"] = _chosen(salts, solved["grams"])
    solved["saltIds"] = [item["id"] for item in solved["salts"]]
    by_id = {salt.get("id"): salt for salt in salts}
    for item in solved["salts"]:
        drift = assay_drift(by_id[item["id"]])
        if drift:
            warnings.append(drift)
    solved["excluded"] = excluded
    solved.update(_report(solved["rows"], solved["grams"], warnings))
    return solved
