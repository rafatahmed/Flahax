# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Versioned input contracts for future FlahaX delivery planning.

These records deliberately contain no tank assignment, pH calculation,
or hardware I/O. They make the source data for those later steps
explicit, validated, and auditable while the nutrient solver remains
unchanged.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .composition import IONS, InputError, validate_profile
from .float_sum import float_sum
from .inputs import DeliveryError, number

DELIVERY_SCHEMA_VERSION = "0.1"
DELIVERY_MODES = frozenset({"batch"})


def _error(code: str, message: str) -> None:
    raise DeliveryError(code, message)


def _map(value: Any, label: str) -> dict:
    if value is None:
        _error("missing_field", f"{label} is required")
    if not isinstance(value, dict):
        _error("invalid_type", f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if value is None:
        _error("missing_field", f"{label} is required")
    if not isinstance(value, str) or not value.strip():
        _error("invalid_value", f"{label} must be a non-empty string")
    return value.strip()


def _timestamp(value: Any, label: str) -> str:
    text = _text(value, label)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        _error("invalid_value", f"{label} must be an ISO 8601 timestamp")
    return text


def _record(payload: Any, kind: str) -> tuple[dict, dict]:
    source = _map(payload, kind)
    version = source.get("schemaVersion")
    if version != DELIVERY_SCHEMA_VERSION:
        _error(
            "unsupported_schema",
            f"{kind}.schemaVersion must be {DELIVERY_SCHEMA_VERSION!r}",
        )
    record = {
        "schemaVersion": DELIVERY_SCHEMA_VERSION,
        "id": _text(source.get("id"), f"{kind}.id"),
        "source": _text(source.get("source"), f"{kind}.source"),
        "revision": _text(source.get("revision"), f"{kind}.revision"),
        "recordedAt": _timestamp(source.get("recordedAt"), f"{kind}.recordedAt"),
    }
    return source, record


def _element_assay(value: Any, label: str) -> dict[str, float]:
    assay = _map(value, label)
    if not assay:
        _error("missing_field", f"{label} must contain at least one element")
    clean: dict[str, float] = {}
    for symbol, raw in assay.items():
        if symbol == "N":
            _error("ambiguous_unit", f"{label} must split total N into N_NO3 and N_NH4")
        if symbol not in IONS:
            _error("unknown_ion", f"{label} has unknown ion {symbol}")
        clean[symbol] = number(raw, f"{label}.{symbol}", minimum=0.0, type_code="invalid_type")
        if clean[symbol] > 100.0:
            _error("out_of_range", f"{label}.{symbol} cannot exceed 100%")
    if float_sum(clean.values()) > 100.5:
        _error("out_of_range", f"{label} adds to more than 100%")
    return clean


def validate_water_analysis(payload: Any) -> dict:
    """Validate a versioned water-analysis record without inventing
    measurements.
    """
    source, record = _record(payload, "waterAnalysis")
    try:
        ions = validate_profile(source.get("ions"), "waterAnalysis.ions")
    except InputError as exc:
        _error("invalid_ions", str(exc))
    result = {
        **record,
        "ions": ions,
        "temperatureC": number(
            source.get("temperatureC"),
            "waterAnalysis.temperatureC",
            minimum=None,
            type_code="invalid_type",
        ),
    }
    if "pH" in source:
        result["pH"] = number(
            source["pH"], "waterAnalysis.pH", minimum=0.0, type_code="invalid_type"
        )
        if result["pH"] > 14.0:
            _error("out_of_range", "waterAnalysis.pH cannot exceed 14")
    if "alkalinityMgLAsCaCO3" in source:
        result["alkalinityMgLAsCaCO3"] = number(
            source["alkalinityMgLAsCaCO3"],
            "waterAnalysis.alkalinityMgLAsCaCO3",
            minimum=0.0,
            type_code="invalid_type",
        )
    return result


def validate_product_assay(payload: Any) -> dict:
    """Validate a fertilizer, acid, or base product record and elemental
    assay.
    """
    source, record = _record(payload, "productAssay")
    kind = _text(source.get("kind"), "productAssay.kind")
    if kind not in {"fertilizer", "acid", "base"}:
        _error("invalid_value", "productAssay.kind must be fertilizer, acid, or base")
    result = {
        **record,
        "name": _text(source.get("name"), "productAssay.name"),
        "kind": kind,
        "elements": _element_assay(source.get("elements"), "productAssay.elements"),
    }
    if "densityKgPerL" in source:
        result["densityKgPerL"] = number(
            source["densityKgPerL"],
            "productAssay.densityKgPerL",
            minimum=0.0,
            type_code="invalid_type",
        )
        if result["densityKgPerL"] == 0:
            _error("out_of_range", "productAssay.densityKgPerL must be greater than 0")
    if "normalityMeqPerL" in source:
        result["normalityMeqPerL"] = number(
            source["normalityMeqPerL"],
            "productAssay.normalityMeqPerL",
            minimum=0.0,
            type_code="invalid_type",
        )
        if result["normalityMeqPerL"] == 0:
            _error("out_of_range", "productAssay.normalityMeqPerL must be greater than 0")
    return result


def validate_compatibility_rule(payload: Any) -> dict:
    """Validate one sourced hard compatibility rule for concentrated
    stocks.
    """
    source, record = _record(payload, "compatibilityRule")
    product_ids = source.get("productIds")
    if not isinstance(product_ids, list) or len(product_ids) < 2:
        _error("invalid_value", "compatibilityRule.productIds needs at least two product ids")
    clean_ids = [_text(value, "compatibilityRule.productIds[]") for value in product_ids]
    if len(set(clean_ids)) != len(clean_ids):
        _error("invalid_value", "compatibilityRule.productIds must not repeat an id")
    return {
        **record,
        "productIds": clean_ids,
        "constraint": "separate"
        if source.get("constraint") == "separate"
        else _invalid_constraint(),
        "reason": _text(source.get("reason"), "compatibilityRule.reason"),
        "temperatureMinC": number(
            source.get("temperatureMinC"),
            "compatibilityRule.temperatureMinC",
            minimum=None,
            type_code="invalid_type",
        ),
        "temperatureMaxC": number(
            source.get("temperatureMaxC"),
            "compatibilityRule.temperatureMaxC",
            minimum=None,
            type_code="invalid_type",
        ),
    }


def _invalid_constraint() -> str:
    _error("invalid_value", "compatibilityRule.constraint must be 'separate'")


def validate_solubility_limit(payload: Any) -> dict:
    """Validate a sourced, temperature-bounded stock solubility
    limit.
    """
    source, record = _record(payload, "solubilityLimit")
    minimum = number(
        source.get("temperatureMinC"),
        "solubilityLimit.temperatureMinC",
        minimum=None,
        type_code="invalid_type",
    )
    maximum = number(
        source.get("temperatureMaxC"),
        "solubilityLimit.temperatureMaxC",
        minimum=None,
        type_code="invalid_type",
    )
    if maximum < minimum:
        _error("out_of_range", "solubilityLimit.temperatureMaxC is below temperatureMinC")
    concentration = number(
        source.get("maxGramsPerLitre"),
        "solubilityLimit.maxGramsPerLitre",
        minimum=0.0,
        type_code="invalid_type",
    )
    if concentration == 0:
        _error("out_of_range", "solubilityLimit.maxGramsPerLitre must be greater than 0")
    clean = {
        **record,
        "productId": _text(source.get("productId"), "solubilityLimit.productId"),
        "maxGramsPerLitre": concentration,
        "temperatureMinC": minimum,
        "temperatureMaxC": maximum,
    }
    if source.get("basis") is not None:
        # What the g/L is a concentration of (Q23); absent means it is not verified.
        clean["basis"] = _text(source.get("basis"), "solubilityLimit.basis")
    return clean


def validate_titration_curve(payload: Any) -> dict:
    """Validate measured acid/base demand points for one water/reagent
    pair.
    """
    source, record = _record(payload, "titrationCurve")
    points = source.get("points")
    if not isinstance(points, list) or len(points) < 2:
        _error("invalid_value", "titrationCurve.points must contain at least two points")
    clean_points = []
    previous_demand = -1.0
    direction: int | None = None
    previous_p_h: float | None = None
    for index, point in enumerate(points):
        item = _map(point, f"titrationCurve.points[{index}]")
        demand = number(
            item.get("demandMeqPerL"),
            f"titrationCurve.points[{index}].demandMeqPerL",
            minimum=0.0,
            type_code="invalid_type",
        )
        p_h = number(
            item.get("pH"),
            f"titrationCurve.points[{index}].pH",
            minimum=0.0,
            type_code="invalid_type",
        )
        if p_h > 14.0:
            _error("out_of_range", f"titrationCurve.points[{index}].pH cannot exceed 14")
        if demand <= previous_demand:
            _error("invalid_value", "titrationCurve demandMeqPerL values must strictly increase")
        if previous_p_h is not None:
            delta = p_h - previous_p_h
            if delta == 0:
                _error("invalid_value", "titrationCurve pH values must change between points")
            point_direction = 1 if delta > 0 else -1
            if direction is not None and point_direction != direction:
                _error("invalid_value", "titrationCurve pH values must be strictly monotonic")
            direction = point_direction
        previous_demand = demand
        previous_p_h = p_h
        clean_points.append({"demandMeqPerL": demand, "pH": p_h})
    return {
        **record,
        "waterAnalysisId": _text(source.get("waterAnalysisId"), "titrationCurve.waterAnalysisId"),
        "reagentId": _text(source.get("reagentId"), "titrationCurve.reagentId"),
        "points": clean_points,
    }


def validate_pump_calibration(payload: Any) -> dict:
    """Validate a field calibration record; it does not command a
    pump.
    """
    source, record = _record(payload, "pumpCalibration")
    flow = number(
        source.get("flowLitresPerMinute"),
        "pumpCalibration.flowLitresPerMinute",
        minimum=0.0,
        type_code="invalid_type",
    )
    if flow == 0:
        _error("out_of_range", "pumpCalibration.flowLitresPerMinute must be greater than 0")
    deviation = number(
        source.get("standardDeviationLitresPerMinute"),
        "pumpCalibration.standardDeviationLitresPerMinute",
        minimum=0.0,
        type_code="invalid_type",
    )
    minimum_volume = number(
        source.get("validMinLitres"),
        "pumpCalibration.validMinLitres",
        minimum=0.0,
        type_code="invalid_type",
    )
    maximum_volume = number(
        source.get("validMaxLitres"),
        "pumpCalibration.validMaxLitres",
        minimum=0.0,
        type_code="invalid_type",
    )
    if maximum_volume < minimum_volume:
        _error("out_of_range", "pumpCalibration.validMaxLitres is below validMinLitres")
    density = number(
        source.get("stockDensityKgPerL"),
        "pumpCalibration.stockDensityKgPerL",
        minimum=0.0,
        type_code="invalid_type",
    )
    if density == 0:
        _error("out_of_range", "pumpCalibration.stockDensityKgPerL must be greater than 0")
    return {
        **record,
        "channelId": _text(source.get("channelId"), "pumpCalibration.channelId"),
        "stockDensityKgPerL": density,
        "testTemperatureC": number(
            source.get("testTemperatureC"),
            "pumpCalibration.testTemperatureC",
            minimum=None,
            type_code="invalid_type",
        ),
        "flowLitresPerMinute": flow,
        "standardDeviationLitresPerMinute": deviation,
        "validMinLitres": minimum_volume,
        "validMaxLitres": maximum_volume,
    }


def validate_delivery_request(payload: Any) -> dict:
    """Validate the P0 batch-planning request envelope and its
    referenced records.
    """
    source = _map(payload, "deliveryRequest")
    if source.get("schemaVersion") != DELIVERY_SCHEMA_VERSION:
        _error(
            "unsupported_schema",
            f"deliveryRequest.schemaVersion must be {DELIVERY_SCHEMA_VERSION!r}",
        )
    mode = source.get("mode")
    if mode not in DELIVERY_MODES:
        _error("unsupported_mode", "deliveryRequest.mode must be 'batch' in version 0.1")
    return {
        "schemaVersion": DELIVERY_SCHEMA_VERSION,
        "mode": mode,
        "waterAnalysis": validate_water_analysis(source.get("waterAnalysis")),
        "products": [validate_product_assay(item) for item in _required_list(source, "products")],
        "compatibilityRules": [
            validate_compatibility_rule(item)
            for item in _required_list(source, "compatibilityRules")
        ],
        "solubilityLimits": [
            validate_solubility_limit(item) for item in _required_list(source, "solubilityLimits")
        ],
        "titrationCurves": [
            validate_titration_curve(item) for item in _required_list(source, "titrationCurves")
        ],
        "pumpCalibrations": [
            validate_pump_calibration(item) for item in _required_list(source, "pumpCalibrations")
        ],
    }


def _required_list(source: dict, field: str) -> list:
    value = source.get(field)
    if not isinstance(value, list):
        _error("missing_field", f"deliveryRequest.{field} must be a list")
    return value


def make_audit_record(request: dict, *, model_version: str) -> dict:
    """Return a deterministic audit record for a validated delivery
    request.
    """
    validated = validate_delivery_request(request)
    return {
        "schemaVersion": DELIVERY_SCHEMA_VERSION,
        "modelVersion": _text(model_version, "modelVersion"),
        "mode": validated["mode"],
        "waterAnalysisId": validated["waterAnalysis"]["id"],
        "productIds": [item["id"] for item in validated["products"]],
        "compatibilityRuleIds": [item["id"] for item in validated["compatibilityRules"]],
        "solubilityLimitIds": [item["id"] for item in validated["solubilityLimits"]],
        "titrationCurveIds": [item["id"] for item in validated["titrationCurves"]],
        "pumpCalibrationIds": [item["id"] for item in validated["pumpCalibrations"]],
    }
