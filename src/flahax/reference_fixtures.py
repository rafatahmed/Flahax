"""Dependency-free loader and comparator for checked-in PHREEQC golden fixtures.

Fixtures are test evidence, not a PHREEQC runtime integration. Each carries the
reference input, expected selected outputs, source URL, database identity, and
numeric tolerance used to compare a future FlahaX equilibrium solver.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .delivery_contracts import DeliveryError


FIXTURE_SCHEMA_VERSION = "1"


def load_reference_fixture(path: str | Path) -> dict:
    """Load and validate one checked-in PHREEQC golden-fixture document."""
    fixture_path = Path(path)
    try:
        source = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeliveryError("invalid_fixture", f"cannot read reference fixture {fixture_path}") from exc
    if not isinstance(source, dict) or source.get("schemaVersion") != FIXTURE_SCHEMA_VERSION:
        raise DeliveryError("invalid_fixture", "reference fixture has an unsupported schema version")
    reference = source.get("reference")
    expected = source.get("expected")
    input_text = source.get("phreeqcInput")
    if not isinstance(reference, dict) or not isinstance(expected, dict) or not isinstance(input_text, str):
        raise DeliveryError("invalid_fixture", "reference fixture needs reference, expected, and phreeqcInput")
    for field in ("sourceUrl", "software", "database", "activityModel"):
        if not isinstance(reference.get(field), str) or not reference[field]:
            raise DeliveryError("invalid_fixture", f"reference.{field} is required")
    digest = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
    if source.get("inputSha256") != digest:
        raise DeliveryError("invalid_fixture", "reference fixture inputSha256 does not match phreeqcInput")
    tolerance = expected.get("absoluteTolerance")
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or tolerance < 0:
        raise DeliveryError("invalid_fixture", "expected.absoluteTolerance must be a non-negative finite number")
    values = expected.get("values")
    if not isinstance(values, dict) or not values:
        raise DeliveryError("invalid_fixture", "expected.values must be a non-empty object")
    for key, value in values.items():
        if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DeliveryError("invalid_fixture", "expected.values must map names to numbers")
    return source


def assert_reference_result(fixture: Mapping[str, Any], actual: Mapping[str, Any]) -> None:
    """Raise AssertionError when a solver output differs from a golden fixture."""
    if not isinstance(fixture, Mapping) or not isinstance(actual, Mapping):
        raise TypeError("fixture and actual must be mappings")
    expected = fixture["expected"]
    tolerance = float(expected["absoluteTolerance"])
    for name, wanted in expected["values"].items():
        if name not in actual:
            raise AssertionError(f"reference result is missing {name}")
        try:
            found = float(actual[name])
        except (TypeError, ValueError) as exc:
            raise AssertionError(f"reference result {name} is not numeric") from exc
        if not math.isfinite(found) or abs(found - wanted) > tolerance:
            raise AssertionError(
                f"reference result {name} is {found!r}; expected {wanted!r} ± {tolerance:g}"
            )
