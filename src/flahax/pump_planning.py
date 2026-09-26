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
    calibration_id: str; channel_id: str; requested_volume: VolumeLitres; runtime: DurationMinutes
    volume_uncertainty: VolumeLitres; requires_operator_verification: bool = True

def plan_pump_command(calibration: Mapping[str, Any], requested_volume: VolumeLitres, available_volume: VolumeLitres, runtime_standard_deviation_minutes: float = .01, *, as_of: datetime | None = None, max_calibration_age_days: float = 30.) -> PumpCommand:
    """Calculate a bounded command; this function performs no device I/O."""
    if not isinstance(requested_volume, VolumeLitres) or not isinstance(available_volume, VolumeLitres):
        raise DeliveryError("invalid_type", "requested and available volumes must be VolumeLitres")
    if not math.isfinite(runtime_standard_deviation_minutes) or runtime_standard_deviation_minutes < 0 or not math.isfinite(max_calibration_age_days) or max_calibration_age_days < 0:
        raise DeliveryError("out_of_range", "runtime standard deviation must be finite and non-negative")
    item=validate_pump_calibration(calibration)
    reference = as_of or datetime.now(timezone.utc)
    if reference.tzinfo is None: raise DeliveryError("invalid_value", "as_of must be timezone-aware")
    recorded=datetime.fromisoformat(item["recordedAt"].replace("Z","+00:00"))
    if (reference-recorded).total_seconds() > max_calibration_age_days*86400:
        raise DeliveryError("stale_calibration", "pump calibration exceeds allowed age")
    if not item["validMinLitres"] <= requested_volume.value <= item["validMaxLitres"]:
        raise DeliveryError("out_of_calibration_range", "requested volume is outside calibration range")
    if requested_volume.value > available_volume.value:
        raise DeliveryError("dry_tank_risk", "requested volume exceeds available stock")
    flow=FlowLitresPerMinute(item["flowLitresPerMinute"]); runtime=DurationMinutes(requested_volume.value/flow.value)
    uncertainty=math.sqrt((runtime.value*item["standardDeviationLitresPerMinute"])**2+(flow.value*runtime_standard_deviation_minutes)**2)
    return PumpCommand(item["id"],item["channelId"],requested_volume,runtime,VolumeLitres(max(uncertainty,1e-15)))
