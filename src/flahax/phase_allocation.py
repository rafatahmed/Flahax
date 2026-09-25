"""Explicit phase-mass allocation records for equilibrium reference cases."""
from __future__ import annotations
from dataclasses import dataclass
import math
from .delivery_contracts import DeliveryError

@dataclass(frozen=True, slots=True)
class PhaseAllocation:
    phase: str; initial_moles: float; final_moles: float; delta_moles: float
    @property
    def dissolved_moles(self) -> float: return max(0., self.delta_moles)
    @property
    def precipitated_moles(self) -> float: return max(0., -self.delta_moles)

def phase_allocation(phase: str, initial_moles: float, final_moles: float) -> PhaseAllocation:
    """Record a phase result; positive delta means dissolution to aqueous phase."""
    if not isinstance(phase,str) or not phase.strip(): raise DeliveryError("invalid_value","phase is required")
    if not all(math.isfinite(v) and v>=0 for v in (initial_moles,final_moles)): raise DeliveryError("out_of_range","phase moles must be finite and non-negative")
    return PhaseAllocation(phase,initial_moles,final_moles,initial_moles-final_moles)
