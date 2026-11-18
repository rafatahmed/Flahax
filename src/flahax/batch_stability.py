# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Measured, time-bounded clarity and dissolved nutrient retention
assessment.
"""

import copy
import hashlib
import json
import math
from datetime import datetime, timezone

from .composition import ATOMIC
from .ph_evidence import check_batch_ph
from .stock_evidence import _number, _text, _within


def _time(raw, now):
    if not isinstance(raw, str):
        raise ValueError("Sampling timestamps must be timezone-qualified strings")
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Sampling timestamps require a timezone")
    value = value.astimezone(timezone.utc)
    if value > now:
        raise ValueError("Future observations are not measured evidence")
    return value


def _interval(record):
    if not isinstance(record, dict) or set(record) != {
        "value",
        "absolute_uncertainty",
        "instrument_id",
        "calibration_reference",
        "method",
        "source",
        "uncertainty_basis",
    }:
        raise ValueError("Each measurement requires value, bound and instrument/method provenance")
    for key in ("instrument_id", "calibration_reference", "method", "source"):
        _text(record, key)
    if record["uncertainty_basis"] != "total_bounded_error":
        raise ValueError("Measurement errors must include bias and calibration uncertainty")
    value, error = _number(record, "value"), _number(record, "absolute_uncertainty")
    if not math.isfinite(value + error):
        raise ValueError("Measurement interval must be finite")
    return max(0.0, value - error), value + error


def assess_batch_stability(recipe, evidence):
    """Gate stability on verified preparation, all observations and a
    complete schedule.
    """
    result = {
        "status": "unverified",
        "stable": False,
        "failures": [],
        "observation_checks": [],
        "observed_hours": None,
        "records_sha256": None,
        "scope": "Observed clarity and dissolved Ca/P retention for this batch and "
        "recorded conditions only. No continuous-time, future-life or all-nutrient guarantee. "
        "Reports and calibration references are not independently authenticated.",
    }
    if evidence is None:
        result["failures"] = [{"code": "missing_stability_records"}]
        return result
    if not recipe.get("verified", False):
        result["failures"] = [{"code": "preparation_not_verified"}]
        return result
    try:
        if not isinstance(evidence, dict) or set(evidence) != {
            "assignment",
            "policy",
            "protocol",
            "observations",
        }:
            raise ValueError(
                "Stability records require assignment, policy, protocol and observations"
            )
        encoded = json.dumps(evidence, sort_keys=True, allow_nan=False, separators=(",", ":"))
        result["records_sha256"] = hashlib.sha256(encoded.encode()).hexdigest()
        result["records"] = copy.deepcopy(evidence)
        verified = recipe["stock_verification"]
        ph_records = verified["records"]["batch_ph"]
        assignment = evidence["assignment"]
        if not isinstance(assignment, dict) or set(assignment) != {
            "batch_id",
            "vessel_id",
            "preparation_fingerprint",
        }:
            raise ValueError(
                "Stability assignment requires batch, vessel and preparation fingerprint"
            )
        for key in assignment:
            _text(assignment, key)
            if assignment[key] != verified["batch_ph_check"][key]:
                raise ValueError("Stability records do not match the verified measured batch")
        policy = evidence["policy"]
        if not isinstance(policy, dict) or set(policy) != {
            "required_hours",
            "maximum_delay_hours",
            "maximum_turbidity_ntu",
            "minimum_retention_fraction",
            "initial_nutrient_relative_tolerance",
        }:
            raise ValueError("Specify all five stability acceptance policy fields")
        hours = policy["required_hours"]
        if (
            not isinstance(hours, list)
            or len(hours) < 2
            or hours[0] != 0
            or any(
                isinstance(h, bool) or not isinstance(h, (int, float)) or not math.isfinite(h)
                for h in hours
            )
            or any(b <= a for a, b in zip(hours, hours[1:]))
        ):
            raise ValueError("Sampling schedule must start at zero and strictly increase")
        delay = _number(policy, "maximum_delay_hours")
        if delay >= min(b - a for a, b in zip(hours, hours[1:])):
            raise ValueError("Sampling windows cannot overlap")
        turbidity_limit = _number(policy, "maximum_turbidity_ntu")
        retention = _number(policy, "minimum_retention_fraction", positive=True)
        initial_tolerance = _number(policy, "initial_nutrient_relative_tolerance")
        if retention > 1 or initial_tolerance >= 1:
            raise ValueError("Retention must be <=1 and initial tolerance <1")
        protocol = evidence["protocol"]
        if not isinstance(protocol, dict) or set(protocol) != {
            "protocol_id",
            "source",
            "storage_conditions",
            "filter_pore_um",
            "dissolved_basis",
            "material_accounting",
            "turbidity_sample",
        }:
            raise ValueError("A complete observation and material-accounting protocol is required")
        for key in ("protocol_id", "source", "storage_conditions"):
            _text(protocol, key)
        if _number(protocol, "filter_pore_um", positive=True) > 0.45:
            raise ValueError(
                "Dissolved analyses require a consistent filter of 0.45 micrometres or finer"
            )
        if protocol["turbidity_sample"] != "representative_unfiltered_batch":
            raise ValueError("Clarity must be measured on representative unfiltered batch samples")
        if (
            protocol["dissolved_basis"] != "filtered_elemental_Ca_and_total_dissolved_P"
            or protocol["material_accounting"] != "no_additions_withdrawals_count_as_loss"
        ):
            raise ValueError("Use a consistent filtered elemental basis and no replenishment")
        observations = evidence["observations"]
        if not isinstance(observations, list) or not observations:
            raise ValueError("Measured observations are required")
        now = datetime.now(timezone.utc)
        start = _time(ph_records["measurement"]["measured_at"], now)
        previous = None
        baseline = None
        seen_ids = set()
        measured_hours = []
        numeric_failures = []
        for index, row in enumerate(observations):
            if not isinstance(row, dict) or set(row) != {
                "observation_id",
                "sampled_at",
                "turbidity_ntu",
                "dissolved_calcium_mg_l",
                "dissolved_phosphorus_mg_l",
                "volume_litres",
                "ph_measurement",
            }:
                raise ValueError(
                    "Observation fields must include all measurements and sample time"
                )
            identity = _text(row, "observation_id")
            if identity in seen_ids:
                raise ValueError("Duplicate observation IDs")
            seen_ids.add(identity)
            sampled = _time(row["sampled_at"], now)
            if (previous is not None and sampled <= previous) or (index == 0 and sampled != start):
                raise ValueError(
                    "Observations must increase from the verified initial pH sample time"
                )
            previous = sampled
            elapsed = (sampled - start).total_seconds() / 3600
            measured_hours.append(elapsed)
            ph_measurement = row["ph_measurement"]
            if (
                not isinstance(ph_measurement, dict)
                or _time(ph_measurement.get("measured_at"), now) != sampled
            ):
                raise ValueError(
                    "Each sampling time requires its own contemporaneous batch pH reading"
                )
            if index == 0 and ph_measurement != ph_records["measurement"]:
                raise ValueError("Baseline pH record must match the verified initial measurement")
            ph_assignment = dict(
                ph_records["assignment"], measurement_record_id=ph_measurement.get("record_id")
            )
            other_ids = {
                r["record_id"] for k in ("assays", "calibrations") for r in verified["records"][k]
            }
            other_ids.add(verified["records"]["final_volume"]["calibration"]["record_id"])
            other_ids.update(r["ph_measurement"]["record_id"] for r in observations[:index])
            ph_check, ph_failure = check_batch_ph(
                recipe,
                {
                    "assignment": ph_assignment,
                    "calibration": ph_records["calibration"],
                    "measurement": ph_measurement,
                },
                assignment["preparation_fingerprint"],
                assignment["vessel_id"],
                other_ids,
            )
            turbidity = _interval(row["turbidity_ntu"])
            volume = _interval(row["volume_litres"])
            if volume[0] <= 0:
                raise ValueError("Measured volume lower bound must remain positive")
            mass = {}
            for element, key in (
                ("Ca", "dissolved_calcium_mg_l"),
                ("P", "dissolved_phosphorus_mg_l"),
            ):
                concentration = _interval(row[key])
                mass[element] = [concentration[0] * volume[0], concentration[1] * volume[1]]
                if not all(math.isfinite(v) for v in mass[element]):
                    raise ValueError("Dissolved nutrient mass interval must be finite")
            check = {
                "observation_id": identity,
                "hours": elapsed,
                "status": "passed",
                "turbidity_upper_ntu": turbidity[1],
                "dissolved_mass_mg": mass,
                "ph_check": ph_check,
                "retention_lower_bounds": {},
            }
            reasons = []
            if ph_failure is not None:
                reasons.append("batch_ph")
            if not _within(turbidity[1], turbidity_limit):
                reasons.append("turbidity")
            if index == 0:
                baseline = mass
                allowed_volume = recipe["uncertainty_verification"]["assumptions"][
                    "volume_error_litres"
                ]
                if not _within(recipe["volume_litres"] - allowed_volume, volume[0]) or not _within(
                    volume[1], recipe["volume_litres"] + allowed_volume
                ):
                    reasons.append("initial_volume")
                for element in ("Ca", "P"):
                    target = (
                        recipe["rounded_verification"]["analytical_mmol_l"][element]
                        * ATOMIC[element]
                        * recipe["volume_litres"]
                    )
                    if target <= 0 or mass[element][0] <= 0:
                        raise ValueError("Positive initial dissolved Ca and P are required")
                    if not _within(
                        target * (1 - initial_tolerance), mass[element][0]
                    ) or not _within(mass[element][1], target * (1 + initial_tolerance)):
                        reasons.append(f"initial_{element}_recovery")
            else:
                for element in ("Ca", "P"):
                    lower = mass[element][0] / baseline[element][1]
                    check["retention_lower_bounds"][element] = lower
                    if not _within(retention, lower):
                        reasons.append(f"{element}_retention")
            if reasons:
                check.update(status="failed", failed_checks=reasons)
                numeric_failures.append(
                    {"code": "observation_failed", "observation_id": identity, "checks": reasons}
                )
            result["observation_checks"].append(check)
        missing = [
            h for h in hours if not any(h <= actual <= h + delay for actual in measured_hours)
        ]
        result.update(
            observed_hours=measured_hours[-1],
            policy=copy.deepcopy(policy),
            observation_start=start.isoformat(),
            observation_end=previous.isoformat(),
            missing_required_hours=missing,
        )
        result["failures"] = list(numeric_failures)
        if missing:
            result["failures"].append(
                {"code": "incomplete_observation_schedule", "missing_hours": missing}
            )
        result["status"] = (
            "not_stable"
            if numeric_failures
            else ("insufficient_evidence" if missing else "stable")
        )
        result["stable"] = result["status"] == "stable"
        result["qualified_duration_hours"] = hours[-1] if result["stable"] else None
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        result["status"] = "invalid_evidence"
        result["failures"].append({"code": "invalid_stability_records", "message": str(exc)})
    return result
