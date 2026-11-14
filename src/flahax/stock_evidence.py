"""Fail-closed assessment of operator-supplied stock and dispenser records."""

import copy
import hashlib
import json
import math
from datetime import datetime, timezone, date


def _text(record, key):
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} requires a nonempty string")
    return value


def _number(record, key, *, positive=False):
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{key} requires a finite number")
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{key} is outside its allowed range")
    return value


def _common(record, today, temperature):
    if not isinstance(record, dict):
        raise ValueError("Record must be an object")
    for key in ("record_id", "source", "method"):
        _text(record, key)
    dates = []
    for key in ("measured_on", "valid_until"):
        raw = _text(record, key)
        parsed = date.fromisoformat(raw)
        if parsed.isoformat() != raw:
            raise ValueError(f"{key} must use YYYY-MM-DD")
        dates.append(parsed)
    if not dates[0] <= today <= dates[1]:
        raise ValueError("Record is future-dated, expired or has reversed dates")
    if _number(record, "temperature_c") != temperature:
        raise ValueError("Record temperature does not match the recipe")
    if record.get("uncertainty_basis") != "total_bound_through_valid_until":
        raise ValueError("A total error bound valid through expiry is required")


def _within(value, limit):
    # Only floating-point arithmetic allowance, not a relaxed physical bound.
    return value <= limit + 1e-12 * max(1, abs(limit))


def assess_stock_evidence(recipe, evidence):
    """Verify applicability and bounds of records, separately from their authenticity."""
    today = datetime.now(timezone.utc).date()
    numerical = recipe["uncertainty_verification"]["status"]
    result = {
        "status": "unverified",
        "verified": False,
        "numerical_status": numerical,
        "evidence_status": "missing" if evidence is None else "failed",
        "assessment_date_utc": today.isoformat(),
        "failures": [],
        "stock_checks": [],
        "records_sha256": None,
        "scope": "Supplied-record applicability and numerical recipe checks only. "
        "Certificate authenticity, actual dispensing, final-volume measurement, "
        "and physical solution stability are not independently verified.",
    }
    if evidence is None:
        result["failures"].append({"code": "missing_stock_evidence"})
        return result
    try:
        if not isinstance(evidence, dict) or set(evidence) != {
            "assignments",
            "assays",
            "calibrations",
        }:
            raise ValueError("Evidence requires assignments, assays and calibrations")
        canonical = json.dumps(evidence, sort_keys=True, allow_nan=False, separators=(",", ":"))
        result["records_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
        result["records"] = copy.deepcopy(evidence)
        assignments = evidence["assignments"]
        formulae = {row["formula"] for row in recipe["stock_delivery"]["stocks"]}
        if not isinstance(assignments, dict) or set(assignments) != formulae:
            raise ValueError("Assignments must bind all six formulae to stock and dispenser IDs")
        indexed = {}
        for kind in ("assays", "calibrations"):
            rows = evidence[kind]
            if not isinstance(rows, list):
                raise ValueError(f"{kind} must be a list")
            for row in rows:
                _common(row, today, recipe["temperature_c"])
                common_fields = {
                    "record_id",
                    "source",
                    "method",
                    "measured_on",
                    "valid_until",
                    "temperature_c",
                    "uncertainty_basis",
                    "stock_id",
                }
                detail_fields = (
                    {
                        "formula",
                        "measured_concentration_g_l",
                        "absolute_uncertainty_g_l",
                        "concentration_basis",
                        "reactive_impurities",
                    }
                    if kind == "assays"
                    else {
                        "dispenser_id",
                        "dose_min_ml",
                        "dose_max_ml",
                        "maximum_absolute_bias_ml",
                        "absolute_uncertainty_ml",
                        "coverage",
                    }
                )
                if set(row) != common_fields | detail_fields:
                    raise ValueError(f"Unexpected or missing fields in {kind} record")
                identity = row["record_id"]
                if identity in indexed:
                    raise ValueError("Duplicate record IDs are ambiguous")
                indexed[identity] = (kind, row)
        used_stock_ids = set()
        used_record_ids = set()
        for assignment in assignments.values():
            if not isinstance(assignment, dict) or set(assignment) != {
                "stock_id",
                "dispenser_id",
                "assay_record_id",
                "calibration_record_id",
            }:
                raise ValueError("Assignment requires stock, dispenser, assay and calibration IDs")
            for key in assignment:
                _text(assignment, key)
            if assignment["stock_id"] in used_stock_ids:
                raise ValueError("Single-compound stocks require distinct stock IDs")
            used_stock_ids.add(assignment["stock_id"])
            used_record_ids.update(
                (assignment["assay_record_id"], assignment["calibration_record_id"])
            )
        if set(indexed) != used_record_ids:
            raise ValueError(
                "Every supplied record must be assigned and every reference must exist"
            )
    except (ValueError, TypeError, OverflowError) as exc:
        result["failures"].append({"code": "invalid_stock_evidence", "message": str(exc)})
        return result

    spec = recipe["stock_delivery"]["specification"]
    for dose in recipe["stock_delivery"]["stocks"]:
        formula = dose["formula"]
        assignment = assignments[formula]
        check = {"formula": formula, **assignment, "status": "failed"}
        try:
            assay_kind, assay = indexed[assignment["assay_record_id"]]
            calibration_kind, calibration = indexed[assignment["calibration_record_id"]]
            if assay_kind != "assays" or calibration_kind != "calibrations":
                raise ValueError("Record reference has the wrong kind")
            if assay.get("stock_id") != assignment["stock_id"] or assay.get("formula") != formula:
                raise ValueError("Assay stock identity or compound/hydrate does not match")
            if (
                assay.get("concentration_basis") != "specified_compound_equivalent_g_l"
                or assay.get("reactive_impurities") != "excluded_by_measurement"
            ):
                raise ValueError(
                    "Compound-specific assay and reactive-impurity assessment required"
                )
            measured = _number(assay, "measured_concentration_g_l", positive=True)
            uncertainty = _number(assay, "absolute_uncertainty_g_l")
            nominal = dose["concentration_g_l"]
            required = nominal * spec["concentration_relative_error"]
            error = abs(measured - nominal) + uncertainty
            check.update(assay_total_deviation_g_l=error, allowed_deviation_g_l=required)
            if measured - uncertainty <= 0 or not _within(error, required):
                raise ValueError(
                    "Measured assay interval exceeds the modeled concentration bounds"
                )
            if (
                calibration.get("dispenser_id") != assignment["dispenser_id"]
                or calibration.get("stock_id") != assignment["stock_id"]
            ):
                raise ValueError("Calibration must match the dispenser and stock liquid")
            if calibration.get("coverage") != "entire_declared_range":
                raise ValueError("A bound covering the entire calibrated dose range is required")
            low = _number(calibration, "dose_min_ml")
            high = _number(calibration, "dose_max_ml", positive=True)
            if not low <= dose["dose_ml"] <= high:
                raise ValueError("Rounded dose is outside the calibrated range")
            bias = _number(calibration, "maximum_absolute_bias_ml")
            uncertainty = _number(calibration, "absolute_uncertainty_ml")
            check.update(
                dosing_total_error_ml=bias + uncertainty,
                allowed_dosing_error_ml=dose["dose_error_ml"],
            )
            if not _within(bias + uncertainty, dose["dose_error_ml"]):
                raise ValueError("Calibration bias plus uncertainty exceeds the dosing bound")
            check["status"] = "passed"
        except (ValueError, KeyError, TypeError) as exc:
            result["failures"].append(
                {"code": "stock_record_check_failed", "formula": formula, "message": str(exc)}
            )
        result["stock_checks"].append(check)
    result["evidence_status"] = "failed" if result["failures"] else "passed"
    if numerical != "passed":
        result["failures"].append({"code": "numerical_checks_not_passed", "status": numerical})
    if not result["failures"]:
        result.update(status="verified", verified=True)
    return result
