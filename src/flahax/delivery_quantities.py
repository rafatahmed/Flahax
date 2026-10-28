# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Immutable, unit-bearing quantities and final-solution recipe adaptation.

All planning arithmetic uses base units (g, L, mg/L, °C, and min) and retains
full floating-point precision. Presentation rounding belongs to a caller after
constraint checks have completed.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from .composition import IONS, InputError, assay_conflict, validate_profile
from .delivery_contracts import DeliveryError
from .engine import _report, forward, score


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
    """A mass in grams, finite and not negative."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _value(self.value, "mass grams", minimum=0.0))


@dataclass(frozen=True, slots=True)
class VolumeLitres:
    """A volume in litres, finite and above zero."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _value(self.value, "volume litres", minimum=0.0, strict=True)
        )


@dataclass(frozen=True, slots=True)
class SolventBasis:
    """Final solution volume and final solvent-water mass, including carrier/hydrate water.

    Neither density nor volume alone determines solvent mass. A stated final inventory
    already includes water supplied by reagents and dissolved hydrates; never add it twice.
    These are accounting inputs, not independently verified measurements.
    """

    final_volume_litres: float
    water_mass_kg: float

    def __post_init__(self):
        for name in ('final_volume_litres', 'water_mass_kg'):
            object.__setattr__(
                self, name, _value(getattr(self, name), name, minimum=0, strict=True)
            )

    @classmethod
    def from_solution_mass(cls, final_volume_litres, density_kg_per_litre, nonwater_mass_kg):
        """Subtract all nonwater mass from density times final solution volume.

        Nonwater mass includes solutes, reagent solute and any suspended material.
        An elemental nutrient sum is not a complete nonwater mass measurement.
        """
        volume = _value(final_volume_litres, 'final_volume_litres', minimum=0, strict=True)
        density = _value(density_kg_per_litre, 'density_kg_per_litre', minimum=0, strict=True)
        nonwater = _value(nonwater_mass_kg, 'nonwater_mass_kg', minimum=0)
        return cls(volume, density * volume - nonwater)

    @classmethod
    def from_water_ledger(
        cls,
        final_volume_litres,
        *,
        source_water_kg,
        reagent_carrier_water_kg,
        dissolved_hydrate_water_kg,
    ):
        """Sum disjoint, explicitly quantified water contributions after dissolution.

        Unknown carrier or hydrate water must not be passed as zero. This does not
        infer dissolution, hydrate stoichiometry or reagent purity from nutrient assays.
        """
        entries = dict(
            source_water_kg=source_water_kg,
            reagent_carrier_water_kg=reagent_carrier_water_kg,
            dissolved_hydrate_water_kg=dissolved_hydrate_water_kg,
        )
        return cls(final_volume_litres, sum(_value(v, k, minimum=0) for k, v in entries.items()))

    def mg_per_litre_to_molality(self, concentration, molar_mass):
        """Convert mg/L of a stated component to mol/kg solvent water."""
        mg = _value(concentration, 'concentration mg/L', minimum=0)
        mw = _value(molar_mass, 'molar mass g/mol', minimum=0, strict=True)
        return mg * self.final_volume_litres / (1000 * mw * self.water_mass_kg)

    def molality_to_mg_per_litre(self, molality, molar_mass):
        """Convert mol/kg water to mg/L on the same component basis."""
        molal = _value(molality, 'molality mol/kg water', minimum=0)
        mw = _value(molar_mass, 'molar mass g/mol', minimum=0, strict=True)
        return molal * mw * 1000 * self.water_mass_kg / self.final_volume_litres

    def grams_per_litre_to_grams_per_kg_water(self, dose):
        """Normalize product mass by final solvent mass without a density assumption."""
        return _value(dose, 'dose g/L', minimum=0) * self.final_volume_litres / self.water_mass_kg


@dataclass(frozen=True, slots=True)
class GramsPerLitre:
    """A concentration in grams per litre, finite and not negative."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _value(self.value, "grams per litre", minimum=0.0))


@dataclass(frozen=True, slots=True)
class MilligramsPerLitre:
    """A concentration in milligrams per litre, finite and not negative."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _value(self.value, "milligrams per litre", minimum=0.0))


@dataclass(frozen=True, slots=True)
class MilliEquivalentsPerLitre:
    """A concentration in milliequivalents per litre, finite and not negative."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _value(self.value, "milliequivalents per litre", minimum=0.0)
        )


@dataclass(frozen=True, slots=True)
class TemperatureCelsius:
    """A temperature in degrees Celsius, not below absolute zero."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _value(self.value, "temperature Celsius", minimum=-273.15)
        )


@dataclass(frozen=True, slots=True)
class FlowLitresPerMinute:
    """A flow in litres per minute, finite and above zero."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _value(self.value, "flow litres per minute", minimum=0.0, strict=True)
        )


@dataclass(frozen=True, slots=True)
class DurationMinutes:
    """A duration in minutes, finite and not negative."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _value(self.value, "duration minutes", minimum=0.0))


@dataclass(frozen=True, slots=True)
class InjectionRatio:
    """Final-solution litres produced per one litre of injected stock."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _value(self.value, "injection ratio", minimum=0.0, strict=True)
        )


@dataclass(frozen=True, slots=True)
class SaltDose:
    """One fertilizer in the recipe: its dose in the final solution and the mass for the whole
    volume.
    """

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
        """The mass of all fertilizers in the recipe."""
        return MassGrams(sum(item.mass.value for item in self.salts))


def final_solution_recipe(
    recommendation: Mapping[str, Any], final_volume: VolumeLitres
) -> FinalSolutionRecipe:
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
        dose = GramsPerLitre(
            _value(
                raw.get("gramsPerLitre"),
                f"recommendation.salts[{index}].gramsPerLitre",
                minimum=0.0,
                strict=True,
            )
        )
        seen.add(salt_id)
        doses.append(
            SaltDose(salt_id, name.strip(), dose, MassGrams(dose.value * final_volume.value))
        )
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
            raise DeliveryError(
                "unknown_ion", f"elemental_mass_fractions has unknown ion {symbol}"
            )
        fraction = _value(raw_fraction, f"elemental_mass_fractions.{symbol}", minimum=0.0)
        if fraction > 1.0:
            raise DeliveryError(
                "out_of_range", f"elemental_mass_fractions.{symbol} cannot exceed 1"
            )
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
            raise DeliveryError(
                "invalid_type", f"contribution.{symbol} must be a MilligramsPerLitre value"
            )
        final[symbol] = final.get(symbol, 0.0) + amount.value
    return score(final, clean_targets)


def rescore_weighed_recipe(
    products: list[dict],
    masses: Mapping[str, MassGrams],
    final_volume: VolumeLitres,
    targets: Mapping[str, Any],
    water: Mapping[str, Any] | None = None,
    *,
    maximum_concentrations: Mapping[str, Any] | None = None,
) -> dict:
    """Recalculate nutrient results from actual masses without fitting new doses.

    ``masses`` maps product IDs to weighed grams. Omitted products contribute zero.
    Supply the original targets, water and effective maxima, including any caller
    ammonium policy. Feasibility is recalculated; no planned flag is inherited.
    This nutrient assessment does not establish pH, stock or physical suitability.
    """
    if not isinstance(final_volume, VolumeLitres):
        raise DeliveryError('invalid_type', 'final_volume must be a VolumeLitres value')
    if not isinstance(products, list) or not isinstance(masses, Mapping):
        raise DeliveryError('invalid_type', 'products must be a list and masses an object')
    by_id = {}
    for product in products:
        if not isinstance(product, dict) or not isinstance(product.get('id'), str):
            raise DeliveryError('invalid_type', 'each product requires a string id')
        key = product['id']
        if not key.strip() or key in by_id or assay_conflict(product):
            raise DeliveryError('invalid_value', 'product IDs must be unique and assays valid')
        by_id[key] = product
    doses = []
    selected = []
    for key, mass in masses.items():
        if key not in by_id:
            raise DeliveryError('unknown_product', f'unknown weighed product {key}')
        if not isinstance(mass, MassGrams):
            raise DeliveryError('invalid_type', 'weighed masses must be MassGrams values')
        doses.append(GramsPerLitre(mass.value / final_volume.value).value)
        selected.append(by_id[key])
    if not all(
        isinstance(value, Mapping)
        for value in (
            targets,
            water if water is not None else {},
            maximum_concentrations if maximum_concentrations is not None else {},
        )
    ):
        raise DeliveryError('invalid_type', 'targets, water and maxima must be objects')
    clean_targets = validate_profile(dict(targets), 'targets')
    if not clean_targets:
        raise InputError('targets are required')
    clean_water = validate_profile(dict(water or {}), 'water')
    maxima = validate_profile(dict(maximum_concentrations or {}), 'maximum_concentrations')
    achieved = forward(selected, doses, clean_water)
    loss, rows = score(achieved, clean_targets)
    result = dict(loss=loss, rows=rows, **_report(rows, doses, [], maxima))
    result['salts'] = [
        dict(id=p['id'], name=p.get('name', p['id']), gramsPerLitre=dose)
        for p, dose in zip(selected, doses)
        if dose > 0
    ]
    result['requirementConflicts'] = [
        dict(
            symbol=symbol,
            reason='target_above_maximum',
            targetPpm=target,
            maximumPpm=maxima[symbol],
        )
        for symbol, target in clean_targets.items()
        if symbol in maxima and target > maxima[symbol]
    ]
    if result['requirementConflicts']:
        result['feasible'] = False
    return result
