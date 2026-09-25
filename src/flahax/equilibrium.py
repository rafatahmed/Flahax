"""Narrow, transparent aqueous-equilibrium kernels for FlahaX.

This module intentionally does not claim full PHREEQC coverage. Its first
kernel solves the carbonate--calcium system used by the checked-in PHREEQC
Example 3 fixture: open CO2 at 25 °C, calcite equilibrium, and Davies ion
activity coefficients. Future kernels must declare their supported species,
constants, gas boundary, and reference fixtures equally explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .delivery_contracts import DeliveryError


DAVIES_A_25C = 0.509
LOG_K_CO2_HENRY_25C = -1.47
LOG_K1_CARBONIC_25C = -6.35
LOG_K2_CARBONIC_25C = -10.33
LOG_K_WATER_25C = -14.0
LOG_K_CALCITE_25C = -8.45
LOG_K_GYPSUM_25C = -4.58
LOG_K_ANHYDRITE_25C = -4.36
# PHREEQC Version 3 master phreeqc.dat: Ca+2 + SO4-2 = CaSO4, log K 2.14.
LOG_BETA_CASO4_25C = 2.14


@dataclass(frozen=True, slots=True)
class CalciteCo2Equilibrium:
    """Open-CO2 calcite equilibrium at 25 °C, using the Davies model."""

    ph: float
    ionic_strength: float
    calcium_molal: float
    bicarbonate_molal: float
    carbonate_molal: float
    co2_molal: float
    si_calcite: float
    si_co2_gas: float


@dataclass(frozen=True, slots=True)
class GypsumEquilibrium:
    """Pure-water gypsum equilibrium at 25 °C using Davies activities.

    The supported aqueous species are free ``Ca+2`` and ``SO4-2`` plus the
    neutral ``CaSO4`` ion pair. It does not include HSO4-, Mg, phosphate,
    background electrolyte, or temperature correction.
    """

    ionic_strength: float
    free_calcium_molal: float
    free_sulfate_molal: float
    calcium_sulfate_molal: float
    total_calcium_molal: float
    total_sulfate_molal: float
    si_gypsum: float
    si_anhydrite: float


def calcite_co2_reference_values(result: CalciteCo2Equilibrium) -> dict[str, float]:
    """Map the supported kernel result to PHREEQC-fixture output names."""
    if not isinstance(result, CalciteCo2Equilibrium):
        raise TypeError("result must be a CalciteCo2Equilibrium value")
    return {
        "ph": result.ph,
        "ionicStrength": result.ionic_strength,
        "calciumMolal": result.calcium_molal,
        "bicarbonateMolal": result.bicarbonate_molal,
        "carbonateMolal": result.carbonate_molal,
        "co2Molal": result.co2_molal,
        "si.Calcite": result.si_calcite,
        "si.CO2(g)": result.si_co2_gas,
    }


def gypsum_reference_values(result: GypsumEquilibrium) -> dict[str, float]:
    """Map the supported gypsum kernel result to fixture output names."""
    if not isinstance(result, GypsumEquilibrium):
        raise TypeError("result must be a GypsumEquilibrium value")
    return {
        "si.Gypsum": result.si_gypsum,
        "si.Anhydrite": result.si_anhydrite,
    }


def davies_gamma(charge: int, ionic_strength: float) -> float:
    """Activity coefficient from the Davies equation at 25 °C."""
    if ionic_strength < 0 or not math.isfinite(ionic_strength):
        raise DeliveryError("out_of_range", "ionic strength must be finite and non-negative")
    if charge == 0:
        return 1.0
    root = math.sqrt(ionic_strength)
    log_gamma = -DAVIES_A_25C * charge * charge * (root / (1.0 + root) - 0.3 * ionic_strength)
    return 10.0 ** log_gamma


def _species_at_ph(ph: float, ionic_strength: float, log_pco2: float) -> dict[str, float]:
    gamma_1 = davies_gamma(1, ionic_strength)
    gamma_2 = davies_gamma(2, ionic_strength)
    a_h = 10.0 ** -ph
    a_co2 = 10.0 ** (LOG_K_CO2_HENRY_25C + log_pco2)
    a_hco3 = 10.0 ** LOG_K1_CARBONIC_25C * a_co2 / a_h
    a_co3 = 10.0 ** LOG_K2_CARBONIC_25C * a_hco3 / a_h
    a_ca = 10.0 ** LOG_K_CALCITE_25C / a_co3
    a_oh = 10.0 ** LOG_K_WATER_25C / a_h
    return {
        "h": a_h / gamma_1,
        "oh": a_oh / gamma_1,
        "co2": a_co2,
        "hco3": a_hco3 / gamma_1,
        "co3": a_co3 / gamma_2,
        "ca": a_ca / gamma_2,
        "a_ca": a_ca,
        "a_co3": a_co3,
    }


def _charge_residual(ph: float, ionic_strength: float, log_pco2: float) -> float:
    species = _species_at_ph(ph, ionic_strength, log_pco2)
    return 2.0 * species["ca"] + species["h"] - species["hco3"] - 2.0 * species["co3"] - species["oh"]


def solve_calcite_co2_equilibrium(log_pco2: float, temperature_c: float = 25.0) -> CalciteCo2Equilibrium:
    """Solve open-CO2 calcite equilibrium with charge balance and Davies activities.

    Supported domain is exactly 25 °C. The equations are mass action for CO2,
    carbonic acid, water, and calcite; electroneutrality; and iterative ionic
    strength/activity-coefficient consistency. It deliberately excludes ion
    pairing and all other phases, so it is a reference-tested kernel rather
    than a general replacement for PHREEQC.
    """
    if not math.isfinite(log_pco2):
        raise DeliveryError("invalid_value", "log_pco2 must be finite")
    if temperature_c != 25.0:
        raise DeliveryError("unsupported_temperature", "calcite CO2 kernel currently supports 25 °C only")
    ionic_strength = 0.005
    ph = 7.0
    for _ in range(100):
        lower, upper = 3.0, 12.0
        for _ in range(100):
            midpoint = (lower + upper) / 2.0
            residual = _charge_residual(midpoint, ionic_strength, log_pco2)
            if residual > 0:
                lower = midpoint
            else:
                upper = midpoint
        ph = (lower + upper) / 2.0
        species = _species_at_ph(ph, ionic_strength, log_pco2)
        updated = 0.5 * (
            species["h"] + species["oh"] + species["hco3"] + 4.0 * species["co3"] + 4.0 * species["ca"]
        )
        if abs(updated - ionic_strength) < 1e-12:
            ionic_strength = updated
            break
        ionic_strength = (ionic_strength + updated) / 2.0
    species = _species_at_ph(ph, ionic_strength, log_pco2)
    si_calcite = math.log10(species["a_ca"] * species["a_co3"]) - LOG_K_CALCITE_25C
    return CalciteCo2Equilibrium(
        ph=ph,
        ionic_strength=ionic_strength,
        calcium_molal=species["ca"],
        bicarbonate_molal=species["hco3"],
        carbonate_molal=species["co3"],
        co2_molal=species["co2"],
        si_calcite=si_calcite,
        si_co2_gas=log_pco2,
    )


def solve_gypsum_equilibrium(temperature_c: float = 25.0) -> GypsumEquilibrium:
    """Solve gypsum-saturated pure water at 25 °C.

    For the dissolution reaction ``Gypsum = Ca+2 + SO4-2 + 2 H2O``, this
    solves ``a_Ca * a_SO4 = 10**logK``. Electroneutrality gives equal free
    calcium and sulfate molalities; their divalent charge gives
    ``I = 4 m_free``. The neutral complex obeys
    ``m_CaSO4 = 10**logBeta * a_Ca * a_SO4`` and contributes to totals but
    not ionic strength. Anhydrite is evaluated at the same ion activity
    product. This is deliberately a pure-water, 25 °C kernel.
    """
    if temperature_c != 25.0:
        raise DeliveryError("unsupported_temperature", "gypsum kernel currently supports 25 °C only")
    target_iap = 10.0 ** LOG_K_GYPSUM_25C
    lower, upper = 0.0, 0.2
    for _ in range(100):
        free_molal = (lower + upper) / 2.0
        gamma = davies_gamma(2, 4.0 * free_molal)
        if (gamma * free_molal) ** 2 < target_iap:
            lower = free_molal
        else:
            upper = free_molal
    free_molal = (lower + upper) / 2.0
    ionic_strength = 4.0 * free_molal
    gamma = davies_gamma(2, ionic_strength)
    activity = gamma * free_molal
    iap = activity * activity
    calcium_sulfate = 10.0 ** LOG_BETA_CASO4_25C * iap
    total = free_molal + calcium_sulfate
    return GypsumEquilibrium(
        ionic_strength=ionic_strength,
        free_calcium_molal=free_molal,
        free_sulfate_molal=free_molal,
        calcium_sulfate_molal=calcium_sulfate,
        total_calcium_molal=total,
        total_sulfate_molal=total,
        si_gypsum=math.log10(iap) - LOG_K_GYPSUM_25C,
        si_anhydrite=math.log10(iap) - LOG_K_ANHYDRITE_25C,
    )
