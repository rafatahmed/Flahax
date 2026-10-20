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
    validate_profile,
)
from .nutrient_acceptance import assess_incidental
from .product_conversion import counterion_sodium_mg_per_l

# Rank and feasibility threshold, relative to the problem's column scale.
EPS = 1e-10
# Double-precision unit round-off, for scale-aware NNLS optimality tests.
ROUNDOFF = 2.220446049250313e-16
# Grams below this do not appear in the recipe.
KEEP_GRAMS = 1e-6
# A recipe is feasible when every requested ion is inside this Δ%.
TOLERANCE_PCT = 1.0
# Doublings of the pull on an incidental ion above its stated maximum (weight up to 2**12).
CEILING_STEPS = 13
# Relative aim below a stated maximum (1 ppm of the limit).
CEILING_MARGIN = 1e-6
# Default ceiling on incidental NH4-N as a share of the formula's total N (#54).
# Owner decision (2026-10-20) within the ammonium share attributed to Sonneveld &
# Voogt (2009), Plant Nutrition of Greenhouse Crops, Springer, doi:10.1007/978-90-481-2532-6
# (about 5-10 % of total N in hydroponics, 10-15 % in substrate culture).
AMMONIUM_FRACTION = 0.10
AMMONIUM_BASIS = ("incidental NH4-N up to 10% of total target N; owner decision within the "
                  "ammonium share attributed to Sonneveld & Voogt (2009), "
                  "doi:10.1007/978-90-481-2532-6")


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
    # Columns found numerically dependent on the passive set; skipped until x changes,
    # as in Lawson-Hanson, so one dependent column cannot block the others.
    rejected: set[int] = set()
    # Optimality (dual) test at round-off level, scaled by |A| and |b|. A fixed
    # absolute threshold stopped early on small or near-dependent problems (#36).
    scale = max((abs(v) for row in matrix for v in row), default=0.0)
    scale *= math.sqrt(sum(v * v for v in rhs))
    dual_tol = 10.0 * max(m, n) * ROUNDOFF * scale

    def residual() -> list[float]:
        pred = _matvec(matrix, x)
        return [rhs[i] - pred[i] for i in range(m)]

    additions = 0
    while additions < n * 4:
        resid = residual()
        weights = [sum(col[i] * resid[i] for i in range(m)) for col in cols]
        candidates = [j for j in active if j not in rejected]
        if not candidates:
            break
        enter = max(candidates, key=lambda j: weights[j])
        if weights[enter] <= dual_tol:
            break
        passive.append(enter)
        active.remove(enter)
        try:
            sub = _lstsq([cols[j] for j in passive], rhs)
        except ValueError:
            passive.remove(enter)
            active.append(enter)
            rejected.add(enter)
            continue
        additions += 1
        rejected.clear()
        while True:
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
            # A subset of independent columns stays independent.
            sub = _lstsq([cols[j] for j in passive], rhs)
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


def _fit(salts: list[dict], targets: dict, water: dict, ridge: float,
         maxima: dict | None = None, ceilings: dict[str, float] | None = None) -> dict:
    """Non-negative grams. ridge is an L2 penalty on grams, not a salt count.

    An incidental ion with a stated positive maximum is not penalized; an ion in
    ceilings exceeded that maximum and is pulled toward it with the given weight.
    """
    maxima = maxima or {}
    ceilings = ceilings or {}
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
        elif symbol in ceilings:
            # Aim just under the maximum so round-off cannot leave it exceeded.
            limit, weight = maxima[symbol] * (1 - CEILING_MARGIN), ceilings[symbol]
            matrix.append([weight * rate / limit for rate in rates])
            rhs.append(weight * (limit - background) / limit)
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
    grams = nnls(matrix, rhs)
    achieved = forward(salts, grams, water)
    loss, rows = score(achieved, targets)
    return {"grams": grams, "loss": loss, "rows": rows}


def _fit_within(salts: list[dict], targets: dict, water: dict, ridge: float, maxima: dict) -> dict:
    """Fit, then pull any incidental ion that passed its stated maximum back toward it."""
    solved = _fit(salts, targets, water, ridge, maxima)
    ceilings: dict[str, float] = {}
    # Escalate the pull on each exceeded ion until it is within its maximum; a
    # remainder after the cap is reported by _report as a limit violation.
    for _ in range(CEILING_STEPS):
        final = {row["symbol"]: float(row["final"] or 0.0) for row in solved["rows"]}
        over = [symbol for symbol, limit in maxima.items()
                if limit > 0 and symbol not in targets and final.get(symbol, 0.0) > limit + 1e-12]
        if not over:
            break
        for symbol in over:
            ceilings[symbol] = ceilings.get(symbol, 0.5) * 2.0
        solved = _fit(salts, targets, water, ridge, maxima, ceilings)
    return solved


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


def _simplify(salts: list[dict], targets: dict, water: dict, solved: dict, ridge: float,
              maxima: dict | None = None) -> dict:
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
            trial = _fit_within([salts[item] for item in others], targets, water, ridge, maxima or {})
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


def _short(rows: list[dict], targets: dict) -> list[str]:
    """Requested ions that finished more than the tolerance below target.

    An overshoot is not a reason to add another salt. A chloride or sodium
    salt can only add its ions. It cannot pull an element back down.
    """
    final = {row["symbol"]: float(row["final"] or 0.0) for row in rows}
    floor = 1.0 - TOLERANCE_PCT / 100.0
    return [
        symbol for symbol, ppm in targets.items()
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
                warnings.append(f"No salt in this library supplies {symbol}.")
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


def _documents(value) -> list[dict]:
    """Flatten a document reference, a list of them, or a {role: reference} map to a list."""
    if isinstance(value, dict) and value and all(
            item is None or isinstance(item, dict) for item in value.values()):
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
    return {"recordId": record["id"], "identityId": None, "analysisBasis": "unattributed",
            "documents": [], "flags": []}


def _report(rows: list[dict], grams: list[float], warnings: list[str], maxima: dict | None = None) -> dict:
    deltas = [abs(row["deltaPct"]) for row in rows if row["deltaPct"] is not None]
    undesired = [
        {"symbol": row["symbol"], "ppm": round(row["final"], 4)}
        for row in rows
        if row["target"] is None and row["final"] > 0.01
    ]
    incidental = assess_incidental(rows, maxima)
    return {
        "feasible": bool(deltas) and max(deltas) <= TOLERANCE_PCT and not incidental["limitViolations"],
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
            pulled back, and any remaining excess is reported in
            limitViolations with feasible False. Omitted keeps the default.
        max_ammonium_fraction: When targets omit N_NH4 (an explicit 0 means
            none wanted) and no N_NH4 maximum is given, incidental NH4-N may reach this share of
            the total target N (N_NO3 + N_NH4 + N_UREA). Default 0.10
            (Sonneveld & Voogt 2009); None keeps the penalty-only fit.

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
        if (isinstance(max_ammonium_fraction, bool) or not isinstance(max_ammonium_fraction, (int, float))
                or not 0 <= max_ammonium_fraction <= 1):
            raise InputError("max_ammonium_fraction must be a number in [0, 1]")
        total_n = sum(targets.get(key, 0.0) for key in ("N_NO3", "N_NH4", "N_UREA"))
        # An explicit N_NH4 target (including 0, "none wanted") keeps its own row.
        if total_n > 0 and "N_NH4" not in targets and "N_NH4" not in maxima:
            limit = max_ammonium_fraction * total_n
            if limit > 0:
                maxima["N_NH4"] = limit
                ammonium_limit = {"mgPerL": limit, "fractionOfTotalN": max_ammonium_fraction,
                                  "basis": AMMONIUM_BASIS}
    salts, excluded = _eligible(library, targets, allowed, allow_carbonates)
    if not salts:
        raise InputError("no salt remains after the assay and ion checks")
    warnings: list[str] = []
    solved = _simplify(salts, targets, water, _fit_within(salts, targets, water, ridge, maxima), ridge, maxima)
    short = _short(solved["rows"], targets)
    if short:
        salts, excluded, recovered = _recover(library, salts, excluded, targets, short)
        warnings.extend(recovered)
        if recovered:
            solved = _simplify(salts, targets, water, _fit_within(salts, targets, water, ridge, maxima),
                               ridge, maxima)
    solved["salts"] = _chosen(salts, solved["grams"])
    chosen_names = {item["name"] for item in solved["salts"]}
    warnings = [
        note for note in warnings
        if " is included" not in note or note.split(" is included", 1)[0] in chosen_names
    ]
    solved["saltIds"] = [item["id"] for item in solved["salts"]]
    by_id = {salt.get("id"): salt for salt in salts}
    for item in solved["salts"]:
        item["provenance"] = _provenance(by_id[item["id"]])
        drift = assay_drift(by_id[item["id"]])
        if drift:
            warnings.append(drift)
    from .materials import IDENTITIES_SHA256  # local: keeps engine importable without the catalogue at load
    solved["identitiesSha256"] = IDENTITIES_SHA256
    solved["excluded"] = excluded
    counterion_na = counterion_sodium_mg_per_l(
        [(by_id[item["id"]], item["gramsPerLitre"]) for item in solved["salts"]])
    if counterion_na > 0:
        na_row = next((row for row in solved["rows"] if row["symbol"] == "Na"), None)
        if na_row is None:
            na_row = {"symbol": "Na", "target": None, "final": 0.0, "deltaPct": None}
            solved["rows"].append(na_row)
        na_row["final"] += counterion_na
        if na_row["target"] is not None and na_row["target"] > 0:
            na_row["deltaPct"] = 100.0 * (na_row["final"] - na_row["target"]) / na_row["target"]
        warnings.append("Incidental Na includes formula counterion sodium (chelates D2, "
                        f"CH - micro borax/molybdate): {counterion_na:.4f} mg/L.")
    solved.update(_report(solved["rows"], solved["grams"], warnings, maxima))
    solved["ammoniumLimit"] = ammonium_limit
    return solved
