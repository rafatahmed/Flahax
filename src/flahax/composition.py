"""Ion schema, formula stoichiometry, and the checks that follow from them.

A salt is usable when its assay is made of known ions and, if the formula
parses, those percentages are the composition of that formula. Nothing here
names a product.
"""

from __future__ import annotations

import math
import re

# Ions the mass balance knows. Total "N" is absent on purpose: nitrate and
# ammonium are different rows, and a single N figure cannot be split safely.
IONS = frozenset({
    "N_NO3", "N_NH4", "P", "K", "Ca", "Mg", "S",
    "Fe", "Mn", "Zn", "B", "Cu", "Mo", "Na", "Cl", "Si",
})

# Ions a default recipe must not introduce unless the formula asks for them
# or the caller allows them. Admitted later only when no other salt supplies
# a requested element.
RESTRICTED_IONS = frozenset({"Na", "Cl"})

ATOMIC = {
    "H": 1.00784,
    "B": 10.81,
    "C": 12.011,
    "N": 14.0067,
    "O": 15.999,
    "Na": 22.989769,
    "Mg": 24.305,
    "Si": 28.085,
    "P": 30.973762,
    "S": 32.06,
    "Cl": 35.45,
    "K": 39.0983,
    "Ca": 40.078,
    "Mn": 54.938044,
    "Fe": 55.845,
    "Cu": 63.546,
    "Zn": 65.38,
    "Mo": 95.95,
}

_TOKEN = re.compile(r"[A-Z][a-z]?|\(|\)|\d+")


class InputError(ValueError):
    """The caller passed a profile or a salt the balance cannot use."""


def _finite(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise InputError(f"{value!r} is not a concentration") from exc
    if not math.isfinite(number):
        raise InputError(f"{value!r} is not a finite concentration")
    return number


def validate_profile(profile: dict, label: str) -> dict[str, float]:
    """Return a copy of a ppm map, or raise InputError."""
    if not isinstance(profile, dict):
        raise InputError(f"{label} must be a map of ion symbol to ppm")
    clean: dict[str, float] = {}
    for symbol, raw in profile.items():
        if symbol == "N":
            raise InputError(
                f"{label} uses N. Nitrate and ammonium are N_NO3 and N_NH4; "
                "a total-N figure is not split automatically."
            )
        if symbol not in IONS:
            raise InputError(f"{label} has unknown ion {symbol}")
        number = _finite(raw)
        if number < 0:
            raise InputError(f"{label} {symbol} is {number}, which is below 0 ppm")
        clean[symbol] = number
    return clean


def _split_terms(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced formula")
        if char == "." and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(char)
    if depth != 0:
        raise ValueError("unbalanced formula")
    parts.append("".join(buf))
    return [part for part in parts if part]


def _parse_group(tokens: list[str], index: int) -> tuple[dict, int]:
    atoms: dict[str, float] = {}
    nitrate = 0.0
    ammonium = 0.0
    carbonate = 0.0

    def add(source: dict, scale: float) -> None:
        nonlocal nitrate, ammonium, carbonate
        for key, amount in source["atoms"].items():
            atoms[key] = atoms.get(key, 0.0) + amount * scale
        nitrate += source["nitrate"] * scale
        ammonium += source["ammonium"] * scale
        carbonate += source["carbonate"] * scale

    while index < len(tokens) and tokens[index] != ")":
        token = tokens[index]
        if token == "(":
            inner, index = _parse_group(tokens, index + 1)
            if index >= len(tokens) or tokens[index] != ")":
                raise ValueError("unbalanced formula")
            index += 1
            scale = 1.0
            if index < len(tokens) and tokens[index].isdigit():
                scale = float(tokens[index])
                index += 1
            add(inner, scale)
            continue
        if not token[:1].isalpha() or token not in ATOMIC:
            raise ValueError(f"cannot read {token}")
        # Anion groups are one unit so a following multiplier applies once.
        if (
            token == "N"
            and index + 2 < len(tokens)
            and tokens[index + 1] == "O"
            and tokens[index + 2] == "3"
        ):
            atoms["N"] = atoms.get("N", 0.0) + 1.0
            atoms["O"] = atoms.get("O", 0.0) + 3.0
            nitrate += 1.0
            index += 3
            continue
        if (
            token == "N"
            and index + 2 < len(tokens)
            and tokens[index + 1] == "H"
            and tokens[index + 2] == "4"
        ):
            atoms["N"] = atoms.get("N", 0.0) + 1.0
            atoms["H"] = atoms.get("H", 0.0) + 4.0
            ammonium += 1.0
            index += 3
            continue
        if (
            token == "C"
            and index + 2 < len(tokens)
            and tokens[index + 1] == "O"
            and tokens[index + 2] == "3"
        ):
            atoms["C"] = atoms.get("C", 0.0) + 1.0
            atoms["O"] = atoms.get("O", 0.0) + 3.0
            carbonate += 1.0
            index += 3
            continue
        index += 1
        count = 1.0
        if index < len(tokens) and tokens[index].isdigit():
            count = float(tokens[index])
            index += 1
        atoms[token] = atoms.get(token, 0.0) + count
    return {
        "atoms": atoms,
        "nitrate": nitrate,
        "ammonium": ammonium,
        "carbonate": carbonate,
    }, index


def parse_formula(formula: str) -> dict | None:
    """Element moles, nitrate moles, ammonium moles, and carbonate groups.

    Returns None when the text is a trade name rather than a formula.
    """
    text = str(formula or "").strip()
    if not text or not re.fullmatch(r"[A-Za-z0-9().]+", text):
        return None
    try:
        combined = {
            "atoms": {},
            "nitrate": 0.0,
            "ammonium": 0.0,
            "carbonate": 0.0,
        }
        for term in _split_terms(text):
            tokens = _TOKEN.findall(term)
            if "".join(tokens) != term or not tokens:
                return None
            index = 0
            scale = 1.0
            if tokens[0].isdigit():
                scale = float(tokens[0])
                index = 1
                if index >= len(tokens):
                    return None
            group, index = _parse_group(tokens, index)
            if index != len(tokens):
                return None
            for key, amount in group["atoms"].items():
                combined["atoms"][key] = combined["atoms"].get(key, 0.0) + amount * scale
            combined["nitrate"] += group["nitrate"] * scale
            combined["ammonium"] += group["ammonium"] * scale
            combined["carbonate"] += group["carbonate"] * scale
        if not combined["atoms"]:
            return None
        return combined
    except (ValueError, KeyError):
        return None


def theoretical_assay(formula: str) -> dict[str, float] | None:
    """Nutrient percentages implied by a parseable formula."""
    parsed = parse_formula(formula)
    if parsed is None:
        return None
    mass = sum(ATOMIC[element] * count for element, count in parsed["atoms"].items())
    if mass <= 0:
        return None

    def percent(moles: float, element: str) -> float:
        return moles * ATOMIC[element] / mass * 100.0

    assay = {
        element: percent(count, element)
        for element, count in parsed["atoms"].items()
        if element in ATOMIC and element not in {"H", "O", "C"}
    }
    if parsed["nitrate"]:
        assay["N_NO3"] = percent(parsed["nitrate"], "N")
    if parsed["ammonium"]:
        assay["N_NH4"] = percent(parsed["ammonium"], "N")
    assay.pop("N", None)
    return assay


def _within_assay(found: float, expected: float) -> bool:
    limit = max(0.75, abs(expected) * 0.04)
    return abs(found - expected) <= limit


def _cleaned_assay(salt: dict) -> tuple[dict[str, float] | None, str | None]:
    elements = salt.get("elements")
    name = salt.get("name") or salt.get("id") or "salt"
    if not isinstance(elements, dict) or not elements:
        return None, f"{name} has no element assay"
    cleaned: dict[str, float] = {}
    for symbol, raw in elements.items():
        if symbol not in IONS:
            return None, f"{name} lists {symbol}, which is not a balance ion"
        try:
            number = float(raw)
        except (TypeError, ValueError):
            return None, f"{name} has a non-numeric {symbol} assay"
        if not math.isfinite(number) or number < 0 or number > 100:
            return None, f"{name} has an impossible {symbol} assay of {raw}"
        cleaned[symbol] = number
    if sum(cleaned.values()) > 100.5:
        return None, f"{name} assays add to more than 100%"
    formula = str(salt.get("formula") or "")
    if formula == "Input Formula Here" or str(name).lower().startswith("test_"):
        return None, f"{name} is a placeholder row"
    return cleaned, None


def assay_conflict(salt: dict) -> str | None:
    """Why this row must not be dosed.

    A parsed formula rejects an element it cannot contain. A percentage that
    disagrees with the written formula is reported by assay_drift and still
    dosed from the stored assay, because a missing hydrate is not the same
    fault as an element the compound does not have.
    """
    cleaned, problem = _cleaned_assay(salt)
    if problem is not None or cleaned is None:
        return problem
    expected = theoretical_assay(str(salt.get("formula") or ""))
    if expected is None:
        return None
    name = salt.get("name") or salt.get("id") or "salt"
    formula = salt.get("formula")
    for symbol, found in cleaned.items():
        predicted = expected.get(symbol, 0.0)
        if predicted < 0.2 and found >= 0.75:
            return (
                f"{name} lists {symbol} at {found:g}%, while {formula} contains {predicted:.2f}%"
            )
    return None


def assay_drift(salt: dict) -> str | None:
    """Stored assay versus the formula, when both describe the same elements."""
    if assay_conflict(salt) is not None:
        return None
    cleaned, _problem = _cleaned_assay(salt)
    if cleaned is None:
        return None
    expected = theoretical_assay(str(salt.get("formula") or ""))
    if expected is None:
        return None
    name = salt.get("name") or salt.get("id") or "salt"
    formula = salt.get("formula")
    drifts = []
    for symbol, found in cleaned.items():
        predicted = expected.get(symbol, 0.0)
        if not _within_assay(found, predicted):
            drifts.append(f"{symbol} assay {found:g}% vs formula {predicted:.2f}%")
    for symbol, predicted in expected.items():
        if predicted < 0.75:
            continue
        if symbol not in cleaned and not _within_assay(0.0, predicted):
            drifts.append(f"{symbol} missing from the assay, formula {predicted:.2f}%")
    if not drifts:
        return None
    return f"{name} ({formula}) was dosed from its stored assay: {'; '.join(drifts)}."


def is_carbonate(salt: dict) -> bool:
    parsed = parse_formula(str(salt.get("formula") or ""))
    return bool(parsed and parsed["carbonate"] > 0)
