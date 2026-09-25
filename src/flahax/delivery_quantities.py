"""Immutable, unit-bearing quantities and final-solution recipe adaptation.

All planning arithmetic uses base units (g, L, mg/L, °C, and min) and retains
full floating-point precision. Presentation rounding belongs to a caller after
constraint checks have completed.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from .composition import IONS, InputError, validate_profile
from .delivery_contracts import DeliveryError
from .engine import score


def _value(raw: Any, label: str, *, minimum: float | None = None, strict: bool = False) -> float:
    if isinstance(raw, bool):
        raise DeliveryError("invalid_type", f"{label} must be a number")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise DeliveryError("invalid_type", f"{label} must be a number") from exc
    if not math.isfinite(value):
        raise DeliveryError("invalid_value", f"{label} must be finite")
    if minimum is not None and (value <= minimum if strict else value < minimum):
        comparison = "greater than" if strict else "at least"
        raise DeliveryError("out_of_range", f"{label} must be {comparison} {minimum:g}")
    return value


@dataclass(frozen=True, slots=True)
class MassGrams:
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _value(self.value, "mass grams", minimum=0.0))


@dataclass(frozen=True, slots=True)
class VolumeLitres:
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _value(self.value, "volume litres", minimum=0.0, strict=True))


@dataclass(frozen=True, slots=True)
class GramsPerLitre:
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _value(self.value, "grams per litre", minimum=0.0))


@dataclass(frozen=True, slots=True)
class MilligramsPerLitre:
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _value(self.value, "milligrams per litre", minimum=0.0))


@dataclass(frozen=True, slots=True)
class MilliEquivalentsPerLitre:
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _value(self.value, "milliequivalents per litre", minimum=0.0))


@dataclass(frozen=True, slots=True)
class TemperatureCelsius:
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _value(self.value, "temperature Celsius", minimum=-273.15))


@dataclass(frozen=True, slots=True)
class FlowLitresPerMinute:
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _value(self.value, "flow litres per minute", minimum=0.0, strict=True))


@dataclass(frozen=True, slots=True)
class DurationMinutes:
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _value(self.value, "duration minutes", minimum=0.0))


@dataclass(frozen=True, slots=True)
class InjectionRatio:
    """Final-solution litres produced per one litre of injected stock."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _value(self.value, "injection ratio", minimum=0.0, strict=True))


@dataclass(frozen=True, slots=True)
class SaltDose:
    salt_id: str
    name: str
    dose: GramsPerLitre
    mass: MassGrams


@dataclass(frozen=True, slots=True)
class FinalSolutionRecipe:
    """A recommendation expressed for a concrete final batch volume."""

    final_volume: VolumeLitres
    feasible: bool
    salts: tuple[SaltDose, ...]

    @property
    def total_mass(self) -> MassGrams:
        return MassGrams(sum(item.mass.value for item in self.salts))


def final_solution_recipe(recommendation: Mapping[str, Any], final_volume: VolumeLitres) -> FinalSolutionRecipe:
    """Adapt a FlahaX recommendation to exact salt masses for a final batch.

    The function consumes only ``result['salts']`` and retains its feasibility
    flag. It does not reinterpret the solver's nutrient balance or round doses.
    """
    if not isinstance(recommendation, Mapping):
        raise DeliveryError("invalid_type", "recommendation must be an object")
    if not isinstance(final_volume, VolumeLitres):
        raise DeliveryError("invalid_type", "final_volume must be a VolumeLitres value")
    salts = recommendation.get("salts")
    if not isinstance(salts, list):
        raise DeliveryError("missing_field", "recommendation.salts must be a list")
    seen: set[str] = set()
    doses = []
    for index, raw in enumerate(salts):
        if not isinstance(raw, Mapping):
            raise DeliveryError("invalid_type", f"recommendation.salts[{index}] must be an object")
        salt_id = raw.get("id")
        name = raw.get("name")
        if not isinstance(salt_id, str) or not salt_id.strip():
            raise DeliveryError("missing_field", f"recommendation.salts[{index}].id is required")
        if salt_id in seen:
            raise DeliveryError("invalid_value", f"recommendation.salts repeats {salt_id}")
        if not isinstance(name, str) or not name.strip():
            raise DeliveryError("missing_field", f"recommendation.salts[{index}].name is required")
        dose = GramsPerLitre(_value(raw.get("gramsPerLitre"), f"recommendation.salts[{index}].gramsPerLitre", minimum=0.0, strict=True))
        seen.add(salt_id)
        doses.append(SaltDose(salt_id, name.strip(), dose, MassGrams(dose.value * final_volume.value)))
    feasible = recommendation.get("feasible")
    if not isinstance(feasible, bool):
        raise DeliveryError("missing_field", "recommendation.feasible must be a boolean")
    return FinalSolutionRecipe(final_volume, feasible, tuple(doses))


def elemental_contribution(
    reagent_mass: MassGrams,
    elemental_mass_fractions: Mapping[str, Any],
    final_volume: VolumeLitres,
) -> dict[str, MilligramsPerLitre]:
    """Convert a reagent's elemental mass fractions into final ppm additions."""
    if not isinstance(reagent_mass, MassGrams):
        raise DeliveryError("invalid_type", "reagent_mass must be a MassGrams value")
    if not isinstance(final_volume, VolumeLitres):
        raise DeliveryError("invalid_type", "final_volume must be a VolumeLitres value")
    if not isinstance(elemental_mass_fractions, Mapping) or not elemental_mass_fractions:
        raise DeliveryError("missing_field", "elemental_mass_fractions must be a non-empty object")
    contribution = {}
    total_fraction = 0.0
    for symbol, raw_fraction in elemental_mass_fractions.items():
        if symbol == "N":
            raise DeliveryError("ambiguous_unit", "split total N into N_NO3 and N_NH4")
        if symbol not in IONS:
            raise DeliveryError("unknown_ion", f"elemental_mass_fractions has unknown ion {symbol}")
        fraction = _value(raw_fraction, f"elemental_mass_fractions.{symbol}", minimum=0.0)
        if fraction > 1.0:
            raise DeliveryError("out_of_range", f"elemental_mass_fractions.{symbol} cannot exceed 1")
        total_fraction += fraction
        if total_fraction > 1.000001:
            raise DeliveryError("out_of_range", "elemental_mass_fractions adds to more than 1")
        contribution[symbol] = MilligramsPerLitre(
            reagent_mass.value * fraction * 1000.0 / final_volume.value
        )
    return contribution


def rescore_with_reagent(
    achieved: Mapping[str, Any],
    targets: Mapping[str, Any],
    contribution: Mapping[str, MilligramsPerLitre],
) -> tuple[float, list[dict]]:
    """Add a reagent's ppm contribution and score the resulting ion balance."""
    try:
        final = validate_profile(dict(achieved), "achieved")
        clean_targets = validate_profile(dict(targets), "targets")
    except (TypeError, InputError) as exc:
        raise DeliveryError("invalid_ions", str(exc)) from exc
    if not isinstance(contribution, Mapping):
        raise DeliveryError("invalid_type", "contribution must be an object")
    for symbol, amount in contribution.items():
        if symbol not in IONS:
            raise DeliveryError("unknown_ion", f"contribution has unknown ion {symbol}")
        if not isinstance(amount, MilligramsPerLitre):
            raise DeliveryError("invalid_type", f"contribution.{symbol} must be a MilligramsPerLitre value")
        final[symbol] = final.get(symbol, 0.0) + amount.value
    return score(final, clean_targets)
