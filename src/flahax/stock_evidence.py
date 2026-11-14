"""Fail-closed assessment of stock, dispenser and final-volume records."""

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


def _final_volume_check(recipe, evidence, today, other_record_ids):
    check = {"status": "missing" if evidence is None else "failed"}
    if evidence is None:
        return check, {"code": "missing_final_volume_calibration"}
    try:
        if not isinstance(evidence, dict) or set(evidence) != {"assignment", "calibration"}:
            raise ValueError("Final volume requires assignment and calibration objects")
        assignment = evidence["assignment"]
        if not isinstance(assignment, dict) or set(assignment) != {
            "vessel_id",
            "calibration_record_id",
        }:
            raise ValueError("Final-volume assignment requires vessel and calibration IDs")
        for key in assignment:
            _text(assignment, key)
        record = evidence["calibration"]
        _common(record, today, recipe["temperature_c"])
        required = {
            "record_id",
            "source",
            "method",
            "measured_on",
            "valid_until",
            "temperature_c",
            "uncertainty_basis",
            "vessel_id",
            "nominal_volume_litres",
            "measured_volume_litres",
            "absolute_uncertainty_litres",
            "capacity_basis",
            "application",
        }
        if set(record) != required:
            raise ValueError("Unexpected or missing final-volume calibration fields")
        if record["record_id"] in other_record_ids:
            raise ValueError("Final-volume record ID duplicates another record")
        if (
            record["record_id"] != assignment["calibration_record_id"]
            or record.get("vessel_id") != assignment["vessel_id"]
        ):
            raise ValueError(
                "Final-volume calibration does not match the assigned vessel or record"
            )
        if (
            record.get("capacity_basis") != "to_contain"
            or record.get("application") != "final_solution_including_stocks"
        ):
            raise ValueError("Calibration must apply to contained final solution including stocks")
        nominal = _number(record, "nominal_volume_litres", positive=True)
        measured = _number(record, "measured_volume_litres", positive=True)
        uncertainty = _number(record, "absolute_uncertainty_litres")
        if nominal != recipe["volume_litres"]:
            raise ValueError("Calibrated volume mark does not match the recipe's final volume")
        allowed = recipe["uncertainty_verification"]["assumptions"]["volume_error_litres"]
        deviation = abs(measured - nominal) + uncertainty
        check.update(
            **assignment,
            measured_volume_litres=measured,
            measured_interval_litres=[measured - uncertainty, measured + uncertainty],
            total_deviation_litres=deviation,
            allowed_deviation_litres=allowed,
        )
        if measured - uncertainty <= 0 or not _within(deviation, allowed):
            raise ValueError("Final-volume bias plus uncertainty exceeds the modeled volume bound")
        check["status"] = "passed"
        return check, None
    except (ValueError, TypeError, KeyError) as exc:
        return check, {"code": "final_volume_record_check_failed", "message": str(exc)}


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
        "final_volume_check": {"status": "not_checked"},
        "batch_ph_check": {"status": "not_checked"},
        "preparation_fingerprint": None,
        "records_sha256": None,
        "scope": "Supplied-record applicability and numerical recipe checks only. "
        "Certificate authenticity, actual dispensing, actual batch filling, "
        "and physical solution stability are not independently verified.",
    }
    if evidence is None:
        result["failures"].append({"code": "missing_stock_evidence"})
        result["failures"].append({"code": "missing_final_volume_calibration"})
        result["final_volume_check"] = {"status": "missing"}
        result["batch_ph_check"] = {"status": "missing"}
        result["failures"].append({"code": "missing_batch_ph_evidence"})
        return result
    try:
        if (
            not isinstance(evidence, dict)
            or not {"assignments", "assays", "calibrations"} <= set(evidence)
            or set(evidence)
            - {"assignments", "assays", "calibrations", "final_volume", "batch_ph"}
        ):
            raise ValueError("Evidence requires stock records and final-volume calibration")
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
    volume_check, failure = _final_volume_check(
        recipe, evidence.get("final_volume"), today, indexed
    )
    result["final_volume_check"] = volume_check
    if failure is not None:
        result["failures"].append(failure)
    from .ph_evidence import preparation_fingerprint, check_batch_ph

    fingerprint = None
    if volume_check["status"] == "passed":
        fingerprint = preparation_fingerprint(recipe, evidence)
    result["preparation_fingerprint"] = fingerprint
    record_ids = set(indexed)
    if volume_check["status"] == "passed":
        record_ids.add(volume_check["calibration_record_id"])
    ph_check, failure = check_batch_ph(
        recipe, evidence.get("batch_ph"), fingerprint, volume_check.get("vessel_id"), record_ids
    )
    result["batch_ph_check"] = ph_check
    if failure is not None:
        result["failures"].append(failure)
    result["evidence_status"] = "failed" if result["failures"] else "passed"
    if numerical != "passed":
        result["failures"].append({"code": "numerical_checks_not_passed", "status": numerical})
    if not result["failures"]:
        result.update(status="verified", verified=True)
    return result
