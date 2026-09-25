"""FlahaX salt-combination search.

The crop formula is fixed. This season's water is subtracted from it.
The gap is what the salts must cover. Grams are per litre of working
solution and cannot be negative. The objective is the sum of squared
percentage errors on elements that have a target.

Not imported by the FlahaFAST application.
"""

from __future__ import annotations

import json
from importlib.resources import files

EPS = 1e-10


def load_library() -> dict:
    """Salt library, water profiles, and crop formulas shipped with the package."""
    text = files("flahax").joinpath("data/library.json").read_text(encoding="utf-8")
    return json.loads(text)


def ppm_per_gram(percent: float) -> float:
    """ppm in 1 litre from 1 gram of salt at an element percentage."""
    return float(percent) * 10.0


def gap_for(targets: dict, water: dict | None = None) -> dict:
    water = water or {}
    symbols = set(targets) | set(water)
    gap = {}
    for symbol in symbols:
        target = targets.get(symbol)
        if target is None:
            gap[symbol] = None
            continue
        gap[symbol] = float(target) - float(water.get(symbol) or 0.0)
    return gap


def _transpose(rows: list[list[float]]) -> list[list[float]]:
    return [list(col) for col in zip(*rows)]


def _matvec(rows: list[list[float]], vec: list[float]) -> list[float]:
    return [sum(a * b for a, b in zip(row, vec)) for row in rows]


def _solve_square(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting."""
    n = len(rhs)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < EPS:
            raise ValueError("singular least squares block")
        a[col], a[pivot] = a[pivot], a[col]
        div = a[col][col]
        for j in range(col, n + 1):
            a[col][j] /= div
        for r in range(n):
            if r == col:
                continue
            factor = a[r][col]
            for j in range(col, n + 1):
                a[r][j] -= factor * a[col][j]
    return [a[i][n] for i in range(n)]


def _lstsq(columns: list[list[float]], b: list[float]) -> list[float]:
    """Least squares: columns are the active salt vectors."""
    if not columns:
        return []
    ata = []
    for i, left in enumerate(columns):
        row = []
        for right in columns:
            row.append(sum(x * y for x, y in zip(left, right)))
        ata.append(row)
    atb = [sum(x * y for x, y in zip(col, b)) for col in columns]
    return _solve_square(ata, atb)


def nnls(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Lawson-Hanson non-negative least squares. matrix is rows × columns."""
    if not matrix:
        return []
    cols = _transpose(matrix)
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
        w = [sum(col[i] * resid[i] for i in range(m)) for col in cols]
        if not active:
            break
        enter = max(active, key=lambda j: w[j])
        if w[enter] <= EPS:
            break
        passive.append(enter)
        active.remove(enter)
        while True:
            sub = _lstsq([cols[j] for j in passive], rhs)
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


def solve_weights(salts: list[dict], targets: dict, water: dict | None = None, sparsity: float = 0.0) -> dict:
    """Non-negative grams per litre minimizing squared Δ%."""
    water = water or {}
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
            # No target: a light penalty so MAP's ammonium does not outrank a real miss.
            matrix.append([rate / 100.0 for rate in rates])
            rhs.append(-background / 100.0)
    if sparsity > 0 and salts:
        for index in range(len(salts)):
            row = [0.0] * len(salts)
            row[index] = sparsity
            matrix.append(row)
            rhs.append(0.0)
    grams = nnls(matrix, rhs)
    achieved = forward(salts, grams, water)
    loss, rows = score(achieved, targets)
    chosen = []
    for salt, gram in zip(salts, grams):
        # Micronutrient salts are often well under 0.0005 g/L. Keep them.
        if gram > 1e-6:
            chosen.append({
                "id": salt["id"],
                "name": salt["name"],
                "gramsPerLitre": round(gram, 6),
            })
    return {"salts": chosen, "grams": grams, "loss": loss, "rows": rows}


LIBRARY = [
    {"id": "CaNO3", "name": "Calcium nitrate (ag grade)", "elements": {"N_NO3": 14.4, "N_NH4": 1.1, "Ca": 19.0}},
    {"id": "KNO3", "name": "Potassium nitrate", "elements": {"N_NO3": 13.856, "K": 38.67}},
    {"id": "MKP", "name": "Monopotassium phosphate", "elements": {"P": 22.758, "K": 28.732}},
    {"id": "MAP", "name": "Monoammonium phosphate", "elements": {"N_NH4": 12.18, "P": 26.924}},
    {"id": "SOP", "name": "Potassium sulfate", "elements": {"K": 44.873, "S": 18.402}},
    {"id": "MgSO4", "name": "Magnesium sulfate", "elements": {"Mg": 9.86, "S": 13.01}},
]


def _usable(salt: dict) -> bool:
    """Skip empty rows and the two placeholder salts. Every real salt stays eligible."""
    if not salt.get("elements"):
        return False
    if salt.get("formula") == "Input Formula Here":
        return False
    if str(salt.get("name", "")).lower().startswith("test_"):
        return False
    return True


def recommend(library: list[dict], targets: dict, water: dict | None = None) -> dict:
    """Solve against every usable salt. Positive grams are the chosen combination."""
    water = water or {}
    salts = [salt for salt in library if _usable(salt)]
    solved = solve_weights(salts, targets, water, sparsity=0.02)
    solved["saltIds"] = [item["id"] for item in solved["salts"]]
    return solved
