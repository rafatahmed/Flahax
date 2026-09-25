"""Fixed-input ammonium/ammonia speciation at 25 °C."""
from __future__ import annotations
from dataclasses import dataclass
import math
from .delivery_contracts import DeliveryError
from .equilibrium import davies_gamma

LOG_K_NH4_TO_NH3_25C = -9.252

@dataclass(frozen=True, slots=True)
class AmmoniaSpeciation:
    total_ammoniacal_nitrogen_molal: float
    ph: float
    ionic_strength: float
    ammonium_molal: float
    ammonia_molal: float
    ammonium_activity: float

def ammonia_speciation(total_ammoniacal_nitrogen_molal: float, ph: float, ionic_strength: float) -> AmmoniaSpeciation:
    """Split analytical NHx between NH4+ and neutral NH3 at fixed pH/I."""
    if not all(math.isfinite(v) for v in (total_ammoniacal_nitrogen_molal, ph, ionic_strength)):
        raise DeliveryError("invalid_value", "ammonia inputs must be finite")
    if total_ammoniacal_nitrogen_molal < 0 or not 0 <= ph <= 14 or not 0 <= ionic_strength <= .1:
        raise DeliveryError("out_of_range", "invalid ammonia total, pH, or ionic strength")
    gamma = davies_gamma(1, ionic_strength)
    ratio = 10.0 ** (LOG_K_NH4_TO_NH3_25C + ph)
    ammonium_activity = total_ammoniacal_nitrogen_molal / (1 / gamma + ratio)
    return AmmoniaSpeciation(total_ammoniacal_nitrogen_molal, ph, ionic_strength, ammonium_activity / gamma, ammonium_activity * ratio, ammonium_activity)
