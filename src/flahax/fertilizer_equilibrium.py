"""Bounded 25 °C fertilizer-ion equilibrium and precipitation screening.

This is a dependency-free reduced model for a fully stated macronutrient
solution.  It deliberately uses analytical totals and named reactions; product
names and unspecified chelates are never inferred as free ions.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from .ammonia import ammonia_speciation
from .competition import carbonate_competition
from .delivery_contracts import DeliveryError
from .equilibrium import davies_gamma
from .phosphate_complexes import (
    LOG_BETA_CA_H2PO4,
    LOG_BETA_CA_HPO4,
    LOG_BETA_CA_PO4,
    LOG_BETA_MG_H2PO4,
    LOG_BETA_MG_HPO4,
    LOG_BETA_MG_PO4,
    LOG_BETA_NA_HPO4,
    LOG_K_HYDROXYAPATITE_HPO4,
)
from .phosphate import LOG_BETA_H2PO4_25C, LOG_BETA_H3PO4_25C, LOG_BETA_HPO4_25C
from .phase_allocation import PhaseAllocation, phase_allocation


LOG_BETA_CARBONATE_BICARBONATE = 10.329
LOG_BETA_CARBONATE_CO2 = 16.681
LOG_BETA_CASO4 = 2.25
LOG_K_CALCITE = -8.48
LOG_K_GYPSUM = -4.58
MAX_IONIC_STRENGTH = 0.1


@dataclass(frozen=True, slots=True)
class FertilizerTotals:
    """Analytical molal totals for the supported 25 °C aqueous system."""

    calcium: float = 0.0
    magnesium: float = 0.0
    phosphate: float = 0.0
    carbonate: float = 0.0
    sulfate: float = 0.0
    ammonium: float = 0.0
    nitrate: float = 0.0
    potassium: float = 0.0
    sodium: float = 0.0
    chloride: float = 0.0

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise DeliveryError("out_of_range", f"{name} total must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class FertilizerEquilibrium:
    """Species, activities, saturation indices, and equilibrium allocations."""

    totals: FertilizerTotals
    ph: float
    ionic_strength: float
    species: Mapping[str, float]
    activities: Mapping[str, float]
    saturation_indices: Mapping[str, float]
    phase_allocations: tuple[PhaseAllocation, ...]

    @property
    def precipitation_moles(self) -> Mapping[str, float]:
        return {item.phase: item.precipitated_moles for item in self.phase_allocations}


@dataclass(frozen=True, slots=True)
class NitricAcidTargetPlan:
    """Closed-carbon initial acid requirement at a requested target pH."""

    initial: FertilizerEquilibrium
    target: FertilizerEquilibrium
    nitric_acid_molal: float


def _valid_ph(value: float) -> float:
    if not math.isfinite(value) or not 0 <= value <= 14:
        raise DeliveryError("out_of_range", "pH must be finite and in [0, 14]")
    return value


def _carbonate(total: float, ph: float, gamma1: float, gamma2: float) -> dict[str, float]:
    hydrogen_activity = 10.0 ** -ph
    denominator = (
        1.0 / gamma2
        + 10.0 ** LOG_BETA_CARBONATE_BICARBONATE * hydrogen_activity / gamma1
        + 10.0 ** LOG_BETA_CARBONATE_CO2 * hydrogen_activity**2
    )
    carbonate_activity = total / denominator if total else 0.0
    return {
        "CO3-2": carbonate_activity / gamma2,
        "HCO3-": 10.0 ** LOG_BETA_CARBONATE_BICARBONATE * carbonate_activity * hydrogen_activity / gamma1,
        "CO2": 10.0 ** LOG_BETA_CARBONATE_CO2 * carbonate_activity * hydrogen_activity**2,
    }


def _phosphate_complexes(calcium: float, magnesium: float, phosphate: float, sodium: float, ph: float, g1: float, g2: float, g3: float) -> dict[str, float]:
    """Fixed-point mass balance for the declared Ca/Mg/Na phosphate complexes."""
    if not phosphate:
        return {name: 0.0 for name in ("ca", "mg", "po4", "hpo4", "h2po4", "hap_si")}
    h = 10.0 ** -ph
    ca, mg = calcium * g2, magnesium * g2
    acid_factor = 1 / g3 + 10.0 ** LOG_BETA_HPO4_25C * h / g2 + 10.0 ** LOG_BETA_H2PO4_25C * h**2 / g1 + 10.0 ** LOG_BETA_H3PO4_25C * h**3
    po = phosphate / acid_factor
    for _ in range(60):
        hpo = 10.0 ** LOG_BETA_HPO4_25C * po * h
        h2 = 10.0 ** LOG_BETA_H2PO4_25C * po * h**2
        h3 = 10.0 ** LOG_BETA_H3PO4_25C * po * h**3
        ca_factor = 1 / g2 + 10.0 ** LOG_BETA_CA_HPO4 * hpo + 10.0 ** LOG_BETA_CA_H2PO4 * h2 / g1 + 10.0 ** LOG_BETA_CA_PO4 * po / g1
        mg_factor = 1 / g2 + 10.0 ** LOG_BETA_MG_HPO4 * hpo + 10.0 ** LOG_BETA_MG_H2PO4 * h2 / g1 + 10.0 ** LOG_BETA_MG_PO4 * po / g1
        next_ca = calcium / ca_factor if calcium else 0.0
        next_mg = magnesium / mg_factor if magnesium else 0.0
        na = sodium * g1
        p_factor = (1 / g3 + 10.0 ** LOG_BETA_HPO4_25C * h / g2 + 10.0 ** LOG_BETA_H2PO4_25C * h**2 / g1 + 10.0 ** LOG_BETA_H3PO4_25C * h**3 + 10.0 ** LOG_BETA_CA_HPO4 * next_ca * g2 * 10.0 ** LOG_BETA_HPO4_25C * h + 10.0 ** LOG_BETA_MG_HPO4 * next_mg * g2 * 10.0 ** LOG_BETA_HPO4_25C * h + 10.0 ** LOG_BETA_CA_H2PO4 * next_ca * g2 * 10.0 ** LOG_BETA_H2PO4_25C * h**2 / g1 + 10.0 ** LOG_BETA_MG_H2PO4 * next_mg * g2 * 10.0 ** LOG_BETA_H2PO4_25C * h**2 / g1 + 10.0 ** LOG_BETA_CA_PO4 * next_ca * g2 / g1 + 10.0 ** LOG_BETA_MG_PO4 * next_mg * g2 / g1 + 10.0 ** LOG_BETA_NA_HPO4 * na * 10.0 ** LOG_BETA_HPO4_25C * h / g1)
        next_po = phosphate / p_factor
        if max(abs(next_ca-ca), abs(next_mg-mg), abs(next_po-po)) < 1e-14:
            ca, mg, po = next_ca, next_mg, next_po
            break
        ca, mg, po = (ca + next_ca) / 2, (mg + next_mg) / 2, (po + next_po) / 2
    hpo = 10.0 ** LOG_BETA_HPO4_25C * po * h
    h2 = 10.0 ** LOG_BETA_H2PO4_25C * po * h**2
    return {"ca": ca / g2, "mg": mg / g2, "po4": po / g3, "hpo4": hpo / g2, "h2po4": h2 / g1, "hap_si": 5 * math.log10(max(ca, 1e-300)) + 3 * math.log10(max(hpo, 1e-300)) + 4 * ph - LOG_K_HYDROXYAPATITE_HPO4}


def _at_fixed_ionic_strength(totals: FertilizerTotals, ph: float, ionic_strength: float) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    gamma1, gamma2, gamma3 = (davies_gamma(charge, ionic_strength) for charge in (1, 2, 3))
    sulfate = totals.sulfate
    calcium_available = totals.calcium
    phosphate_result = None
    pair = 0.0
    for _ in range(20):
        if totals.phosphate:
            phosphate_result = _phosphate_complexes(calcium_available, totals.magnesium, totals.phosphate, totals.sodium, ph, gamma1, gamma2, gamma3)
            free_calcium = phosphate_result["ca"]
            free_magnesium = phosphate_result["mg"]
            free_phosphate = phosphate_result["po4"]
            hpo4 = phosphate_result["hpo4"]
            h2po4 = phosphate_result["h2po4"]
        else:
            free_calcium, free_magnesium = calcium_available, totals.magnesium
            free_phosphate = hpo4 = h2po4 = 0.0
        next_pair = 10.0 ** LOG_BETA_CASO4 * (free_calcium * gamma2) * (sulfate * gamma2)
        next_pair = min(next_pair, totals.calcium, totals.sulfate)
        next_calcium = max(0.0, totals.calcium - next_pair)
        next_sulfate = max(0.0, totals.sulfate - next_pair)
        if max(abs(next_pair - pair), abs(next_calcium - calcium_available), abs(next_sulfate - sulfate)) < 1e-14:
            pair, calcium_available, sulfate = next_pair, next_calcium, next_sulfate
            break
        pair = (pair + next_pair) / 2.0
        calcium_available = (calcium_available + next_calcium) / 2.0
        sulfate = (sulfate + next_sulfate) / 2.0
    carbonate = _carbonate(totals.carbonate, ph, gamma1, gamma2)
    ammonia = ammonia_speciation(totals.ammonium, ph, ionic_strength) if totals.ammonium else None
    species = {
        "Ca+2": free_calcium,
        "Mg+2": free_magnesium,
        "PO4-3": free_phosphate,
        "HPO4-2": hpo4,
        "H2PO4-": h2po4,
        "SO4-2": sulfate,
        "CaSO4": pair,
        "NH4+": ammonia.ammonium_molal if ammonia else 0.0,
        "NH3": ammonia.ammonia_molal if ammonia else 0.0,
        "NO3-": totals.nitrate,
        "K+": totals.potassium,
        "Na+": totals.sodium,
        "Cl-": totals.chloride,
        **carbonate,
    }
    activities = {
        name: amount * (gamma3 if name == "PO4-3" else gamma2 if name in {"Ca+2", "Mg+2", "HPO4-2", "SO4-2", "CO3-2"} else gamma1 if name in {"NH4+", "H2PO4-", "NO3-", "K+", "Na+", "Cl-", "HCO3-"} else 1.0)
        for name, amount in species.items()
    }
    activities["H+"] = 10.0 ** -ph
    activities["OH-"] = 10.0 ** (ph - 14.0)
    saturation = {
        "Calcite": math.log10(max(activities["Ca+2"] * activities["CO3-2"], 1e-300)) - LOG_K_CALCITE,
        "Gypsum": math.log10(max(activities["Ca+2"] * activities["SO4-2"], 1e-300)) - LOG_K_GYPSUM,
        "Hydroxyapatite": phosphate_result["hap_si"] if phosphate_result else float("-inf"),
        "Struvite": math.log10(max(activities["Mg+2"] * activities["NH4+"] * activities["PO4-3"], 1e-300)) + 13.26,
    }
    return species, activities, saturation


def _ionic_strength(species: Mapping[str, float]) -> float:
    charges = {"Ca+2": 2, "Mg+2": 2, "PO4-3": -3, "HPO4-2": -2, "H2PO4-": -1, "SO4-2": -2, "NH4+": 1, "NO3-": -1, "K+": 1, "Na+": 1, "Cl-": -1, "CO3-2": -2, "HCO3-": -1}
    return 0.5 * sum(species[name] * charge**2 for name, charge in charges.items())


def _fixed_ph_equilibrium(totals: FertilizerTotals, ph: float) -> FertilizerEquilibrium:
    ionic_strength = 0.01
    for _ in range(30):
        species, activities, saturation = _at_fixed_ionic_strength(totals, ph, ionic_strength)
        updated = _ionic_strength(species)
        if updated > MAX_IONIC_STRENGTH:
            raise DeliveryError("activity_model_out_of_range", "Davies model is limited to I <= 0.1 mol/kgw")
        if abs(updated - ionic_strength) < 1e-9:
            return FertilizerEquilibrium(totals, ph, updated, species, activities, saturation, ())
        ionic_strength = (ionic_strength + updated) / 2.0
    raise DeliveryError("nonconvergent", "fertilizer ionic-strength iteration did not converge")


def _remove_for_phase(totals: FertilizerTotals, phase: str, amount: float) -> FertilizerTotals:
    values = {name: getattr(totals, name) for name in totals.__dataclass_fields__}
    stoichiometry = {
        "Calcite": {"calcium": 1, "carbonate": 1},
        "Gypsum": {"calcium": 1, "sulfate": 1},
        "Hydroxyapatite": {"calcium": 5, "phosphate": 3},
        "Struvite": {"magnesium": 1, "ammonium": 1, "phosphate": 1},
    }[phase]
    for name, coefficient in stoichiometry.items():
        values[name] = max(0.0, values[name] - coefficient * amount)
    return FertilizerTotals(**values)


def _phase_limit(totals: FertilizerTotals, phase: str) -> float:
    coefficients = {
        "Calcite": (("calcium", 1), ("carbonate", 1)),
        "Gypsum": (("calcium", 1), ("sulfate", 1)),
        "Hydroxyapatite": (("calcium", 5), ("phosphate", 3)),
        "Struvite": (("magnesium", 1), ("ammonium", 1), ("phosphate", 1)),
    }[phase]
    return min(getattr(totals, name) / coefficient for name, coefficient in coefficients)


def solve_fertilizer_equilibrium(totals: FertilizerTotals, ph: float, *, allow_precipitation: bool = True) -> FertilizerEquilibrium:
    """Solve the declared 25 °C system at a specified pH.

    ``allow_precipitation`` applies named equilibrium allocations only for
    supersaturated phases. It is an equilibrium amount, not a kinetic or
    storage-stability prediction.
    """
    if not isinstance(totals, FertilizerTotals):
        raise DeliveryError("invalid_type", "totals must be FertilizerTotals")
    ph = _valid_ph(ph)
    current = totals
    allocations: list[PhaseAllocation] = []
    if allow_precipitation:
        for _ in range(4):
            result = _fixed_ph_equilibrium(current, ph)
            changed = False
            for phase in ("Hydroxyapatite", "Calcite", "Gypsum", "Struvite"):
                if result.saturation_indices[phase] <= 1e-8:
                    continue
                upper = _phase_limit(current, phase)
                if upper <= 0:
                    continue
                low, high = 0.0, upper * (1 - 1e-12)
                for _ in range(30):
                    middle = (low + high) / 2.0
                    candidate = _fixed_ph_equilibrium(_remove_for_phase(current, phase, middle), ph)
                    if candidate.saturation_indices[phase] > 0:
                        low = middle
                    else:
                        high = middle
                amount = high
                if amount > 1e-15:
                    # The aqueous mixture starts with no newly formed solid.
                    # A positive final phase inventory is precipitation under
                    # PhaseAllocation's documented sign convention.
                    allocations.append(phase_allocation(phase, 0.0, amount))
                    current = _remove_for_phase(current, phase, amount)
                    changed = True
                    break
            if not changed:
                break
    result = _fixed_ph_equilibrium(current, ph)
    return FertilizerEquilibrium(result.totals, result.ph, result.ionic_strength, result.species, result.activities, result.saturation_indices, tuple(allocations))


def _alkalinity(result: FertilizerEquilibrium) -> float:
    s = result.species
    return s["HCO3-"] + 2 * s["CO3-2"] + s["HPO4-2"] + 2 * s["PO4-3"] + result.activities["OH-"] / davies_gamma(1, result.ionic_strength) - result.activities["H+"] / davies_gamma(1, result.ionic_strength)


def plan_nitric_acid_target(totals: FertilizerTotals, initial_ph: float, target_ph: float) -> NitricAcidTargetPlan:
    """Return the closed-carbon strong-acid requirement for a lower target pH."""
    initial = solve_fertilizer_equilibrium(totals, _valid_ph(initial_ph), allow_precipitation=False)
    target = solve_fertilizer_equilibrium(totals, _valid_ph(target_ph), allow_precipitation=False)
    dose = _alkalinity(initial) - _alkalinity(target)
    if dose < 0:
        raise DeliveryError("wrong_reagent_direction", "target needs base rather than nitric acid")
    return NitricAcidTargetPlan(initial, target, dose)
