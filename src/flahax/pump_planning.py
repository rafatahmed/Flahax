# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Hardware-neutral, bounded pump runtime planning."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Mapping
from .delivery_contracts import DeliveryError, validate_pump_calibration
from .delivery_quantities import DurationMinutes, FlowLitresPerMinute, VolumeLitres


@dataclass(frozen=True, slots=True)
class PumpCommand:
    """A volume for one calibrated pump channel and its run time; the operator verifies it."""

    calibration_id: str
    channel_id: str
    requested_volume: VolumeLitres
    runtime: DurationMinutes
    volume_uncertainty: VolumeLitres
    requires_operator_verification: bool = True


def plan_pump_command(
    calibration: Mapping[str, Any],
    requested_volume: VolumeLitres,
    available_volume: VolumeLitres,
    runtime_standard_deviation_minutes: float = 0.01,
    *,
    as_of: datetime | None = None,
    max_calibration_age_days: float = 30.0,
) -> PumpCommand:
    """Calculate a bounded command; this function performs no device I/O."""
    if not isinstance(requested_volume, VolumeLitres) or not isinstance(
        available_volume, VolumeLitres
    ):
        raise DeliveryError("invalid_type", "requested and available volumes must be VolumeLitres")
    for label, value in (
        ('runtime standard deviation', runtime_standard_deviation_minutes),
        ('maximum calibration age', max_calibration_age_days),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DeliveryError('invalid_type', f'{label} must be a number')
        if not math.isfinite(value) or value < 0:
            raise DeliveryError('out_of_range', f'{label} must be finite and non-negative')
    item = validate_pump_calibration(calibration)
    reference = datetime.now(timezone.utc) if as_of is None else as_of
    if not isinstance(reference, datetime) or reference.utcoffset() is None:
        raise DeliveryError("invalid_value", "as_of must be timezone-aware")
    recorded = datetime.fromisoformat(item["recordedAt"].replace("Z", "+00:00"))
    if recorded.utcoffset() is None:
        raise DeliveryError('invalid_value', 'calibration timestamp must be timezone-aware')
    age_days = (reference - recorded).total_seconds() / 86400
    if age_days < 0:
        raise DeliveryError('future_calibration', 'calibration is later than as_of')
    if age_days > max_calibration_age_days:
        raise DeliveryError("stale_calibration", "pump calibration exceeds allowed age")
    if not item["validMinLitres"] <= requested_volume.value <= item["validMaxLitres"]:
        raise DeliveryError(
            "out_of_calibration_range", "requested volume is outside calibration range"
        )
    if requested_volume.value > available_volume.value:
        raise DeliveryError("dry_tank_risk", "requested volume exceeds available stock")
    flow = FlowLitresPerMinute(item["flowLitresPerMinute"])
    runtime = DurationMinutes(requested_volume.value / flow.value)
    uncertainty = math.hypot(
        runtime.value * item["standardDeviationLitresPerMinute"],
        flow.value * runtime_standard_deviation_minutes,
    )
    return PumpCommand(
        item["id"],
        item["channelId"],
        requested_volume,
        runtime,
        VolumeLitres(max(uncertainty, 1e-15)),
    )
