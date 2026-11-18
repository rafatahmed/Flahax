# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Bind measured batch pH and calibration evidence to a specific
preparation.
"""

import hashlib
import json
import math
from datetime import datetime, timezone

from .stock_evidence import _common, _number, _text, _within


def preparation_fingerprint(recipe, evidence):
    """Identify physical dosing instructions and model bounds, excluding
    pH records.
    """
    material = {
        "version": 1,
        "volume_litres": recipe["volume_litres"],
        "water_mass_kg": recipe["water_mass_kg"],
        "temperature_c": recipe["temperature_c"],
        "ph_range": recipe["rounded_verification"]["ph_range"],
        "target_ph": recipe["target_ph"],
        "phases": recipe["rounded_verification"]["selected_phases"],
        "si_required_below": recipe["rounded_verification"]["si_required_below"],
        "stock_specification": recipe["stock_delivery"]["specification"],
        "stocks": recipe["stock_delivery"]["stocks"],
        "uncertainty": recipe["uncertainty_verification"]["assumptions"],
        "identities": {
            formula: {k: row[k] for k in ("stock_id", "dispenser_id")}
            for formula, row in evidence["assignments"].items()
        },
        "vessel_id": evidence["final_volume"]["assignment"]["vessel_id"],
    }

    def normalize(value):
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [normalize(v) for v in value]
        if type(value) in (int, float):
            return float(value)
        return value

    payload = json.dumps(
        normalize(material), sort_keys=True, allow_nan=False, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _timestamp(record, key, now):
    raw = _text(record, key)
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{key} must include a timezone")
    value = value.astimezone(timezone.utc)
    if value > now or value.date().isoformat() != record["measured_on"]:
        raise ValueError(f"{key} is future-dated or disagrees with measured_on in UTC")
    return value


def check_batch_ph(recipe, evidence, fingerprint, vessel_id, other_ids):
    """Require contained pH error interval and applicable, chronological
    records.
    """
    check = {"status": "missing" if evidence is None else "failed"}
    if evidence is None:
        return check, {"code": "missing_batch_ph_evidence"}
    now = datetime.now(timezone.utc)
    try:
        if not isinstance(evidence, dict) or set(evidence) != {
            "assignment",
            "calibration",
            "measurement",
        }:
            raise ValueError("Batch pH requires assignment, calibration and measurement")
        assignment = evidence["assignment"]
        keys = {
            "batch_id",
            "vessel_id",
            "meter_id",
            "electrode_id",
            "calibration_record_id",
            "measurement_record_id",
        }
        if not isinstance(assignment, dict) or set(assignment) != keys:
            raise ValueError("Batch pH assignment is incomplete")
        for key in keys:
            _text(assignment, key)
        if assignment["vessel_id"] != vessel_id:
            raise ValueError("pH measurement vessel does not match final-volume assignment")
        calibration, measurement = evidence["calibration"], evidence["measurement"]
        base = {
            "record_id",
            "source",
            "method",
            "measured_on",
            "valid_until",
            "temperature_c",
            "uncertainty_basis",
            "meter_id",
            "electrode_id",
        }
        calibration_fields = {
            "calibrated_at",
            "ph_min",
            "ph_max",
            "maximum_absolute_bias_ph",
            "absolute_uncertainty_ph",
            "coverage",
            "buffers",
        }
        measurement_fields = {
            "measured_at",
            "batch_id",
            "vessel_id",
            "calibration_record_id",
            "preparation_fingerprint",
            "indicated_ph",
            "additional_uncertainty_ph",
            "application",
        }
        for row, extra, identity_key in (
            (calibration, calibration_fields, "calibration_record_id"),
            (measurement, measurement_fields, "measurement_record_id"),
        ):
            _common(row, now.date(), recipe["temperature_c"])
            if set(row) != base | extra:
                raise ValueError("Unexpected or missing pH record fields")
            if row["record_id"] != assignment[identity_key] or row["record_id"] in other_ids:
                raise ValueError("pH record ID mismatched or reused")
            for key in ("meter_id", "electrode_id"):
                if row.get(key) != assignment[key]:
                    raise ValueError("Meter or electrode does not match assignment")
        if calibration["record_id"] == measurement["record_id"]:
            raise ValueError("Calibration and measurement require distinct record IDs")
        calibrated_at = _timestamp(calibration, "calibrated_at", now)
        measured_at = _timestamp(measurement, "measured_at", now)
        if measured_at < calibrated_at:
            raise ValueError("Batch pH reading predates its calibration")
        for key in ("batch_id", "vessel_id", "calibration_record_id"):
            if measurement.get(key) != assignment[key]:
                raise ValueError("Batch, vessel or calibration reference does not match")
        if fingerprint is None or measurement.get("preparation_fingerprint") != fingerprint:
            raise ValueError("pH reading is not bound to these rounded preparation instructions")
        if measurement.get("application") != "final_mixed_batch_no_unaccounted_additions":
            raise ValueError(
                "Reading must describe the final mixed batch with all additions accounted"
            )
        low, high = recipe["rounded_verification"]["ph_range"]
        cal_low, cal_high = _number(calibration, "ph_min"), _number(calibration, "ph_max")
        if not 0 <= cal_low <= low <= high <= cal_high <= 14:
            raise ValueError("Calibration range does not cover the recipe pH interval")
        if calibration.get("coverage") != "entire_declared_range":
            raise ValueError("Calibration must bound errors throughout its stated pH range")
        buffers = calibration["buffers"]
        if not isinstance(buffers, list) or len(buffers) < 2:
            raise ValueError("At least two referenced calibration buffers are required")
        ph_values, refs = [], set()
        for buffer in buffers:
            if not isinstance(buffer, dict) or set(buffer) != {"reference", "certified_ph"}:
                raise ValueError(
                    "Each buffer requires reference and certified_ph at record temperature"
                )
            reference = _text(buffer, "reference")
            ph = _number(buffer, "certified_ph")
            if reference in refs or ph > 14:
                raise ValueError("Invalid or duplicate buffer reference")
            refs.add(reference)
            ph_values.append(ph)
        if min(ph_values) > cal_low or max(ph_values) < cal_high or len(set(ph_values)) < 2:
            raise ValueError("Referenced buffers do not bracket the validated pH range")
        reading = _number(measurement, "indicated_ph")
        if reading > 14:
            raise ValueError("pH reading outside supported range")
        bias = _number(calibration, "maximum_absolute_bias_ph")
        calibration_error = _number(calibration, "absolute_uncertainty_ph")
        batch_error = _number(measurement, "additional_uncertainty_ph")
        total_error = bias + calibration_error + batch_error
        if not math.isfinite(total_error):
            raise ValueError("Combined pH uncertainty must be finite")
        lower, upper = reading - total_error, reading + total_error
        check.update(
            **assignment,
            preparation_fingerprint=fingerprint,
            indicated_ph=reading,
            total_uncertainty_ph=total_error,
            measured_interval_ph=[lower, upper],
            required_interval_ph=[low, high],
        )
        if not _within(low, lower) or not _within(upper, high):
            raise ValueError("Measured batch pH uncertainty interval leaves the required pH range")
        check["status"] = "passed"
        return check, None
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return check, {"code": "batch_ph_record_check_failed", "message": str(exc)}
