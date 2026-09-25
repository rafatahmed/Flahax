"""Generic thermodynamic entities for the growing fertilizer-chemistry model.

The records are deliberately data-driven: a phase is defined by its dissolved
species stoichiometry and a source-specific log K. This module contains no
unsourced fertilizer constants and no product-name chemistry.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from .delivery_contracts import DeliveryError


@dataclass(frozen=True, slots=True)
class MineralPhase:
    """A dissolution phase with log K for one named database and temperature."""

    name: str
    dissolved_species: Mapping[str, float]
    log_k: float
    database: str
    temperature_c: float

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise DeliveryError("invalid_value", "phase name must be a non-empty string")
        if not isinstance(self.database, str) or not self.database.strip():
            raise DeliveryError("missing_field", "phase database is required")
        if not isinstance(self.dissolved_species, Mapping) or not self.dissolved_species:
            raise DeliveryError("missing_field", "phase dissolved_species is required")
        clean = {}
        for species, coefficient in self.dissolved_species.items():
            if not isinstance(species, str) or not species:
                raise DeliveryError("invalid_value", "phase species names must be non-empty strings")
            if isinstance(coefficient, bool):
                raise DeliveryError("invalid_type", "phase coefficients must be numeric")
            try:
                value = float(coefficient)
            except (TypeError, ValueError) as exc:
                raise DeliveryError("invalid_type", "phase coefficients must be numeric") from exc
            if not math.isfinite(value) or value == 0:
                raise DeliveryError("invalid_value", "phase coefficients must be finite and non-zero")
            clean[species] = value
        if not math.isfinite(float(self.log_k)) or not math.isfinite(float(self.temperature_c)):
            raise DeliveryError("invalid_value", "phase log_k and temperature_c must be finite")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "database", self.database.strip())
        object.__setattr__(self, "dissolved_species", clean)
        object.__setattr__(self, "log_k", float(self.log_k))
        object.__setattr__(self, "temperature_c", float(self.temperature_c))


def phase_saturation_index(phase: MineralPhase, activities: Mapping[str, float]) -> float:
    """Return SI = log10(IAP) - log K from explicitly supplied activities."""
    if not isinstance(phase, MineralPhase):
        raise DeliveryError("invalid_type", "phase must be a MineralPhase value")
    if not isinstance(activities, Mapping):
        raise DeliveryError("invalid_type", "activities must be an object")
    log_iap = 0.0
    for species, coefficient in phase.dissolved_species.items():
        if species not in activities:
            raise DeliveryError("missing_species", f"activity for {species} is required by {phase.name}")
        try:
            activity = float(activities[species])
        except (TypeError, ValueError) as exc:
            raise DeliveryError("invalid_type", f"activity for {species} must be numeric") from exc
        if not math.isfinite(activity) or activity <= 0:
            raise DeliveryError("out_of_range", f"activity for {species} must be finite and greater than 0")
        log_iap += coefficient * math.log10(activity)
    return log_iap - phase.log_k
