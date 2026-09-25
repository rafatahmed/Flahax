"""Fixed-activity struvite saturation boundary at 25 °C."""
from __future__ import annotations
import math
from .delivery_contracts import DeliveryError

LOG_K_STRUVITE_25C = -13.26

def struvite_saturation_index(magnesium_activity: float, ammonium_activity: float, phosphate_activity: float) -> float:
    """Return SI for MgNH4PO4:6H2O; inputs must be free-ion activities."""
    values = (magnesium_activity, ammonium_activity, phosphate_activity)
    if not all(math.isfinite(value) and value > 0 for value in values):
        raise DeliveryError("out_of_range", "struvite activities must be positive and finite")
    return sum(math.log10(value) for value in values) - LOG_K_STRUVITE_25C
