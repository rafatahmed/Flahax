# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Fixed-pH Mg/NH4/phosphate reference-mixture speciation at 25 °C."""

from __future__ import annotations
from dataclasses import dataclass
import math
from .ammonia import ammonia_speciation
from .delivery_contracts import DeliveryError
from .equilibrium import LOG_BETA_CASO4_25C, davies_gamma
from .phosphate import LOG_BETA_H2PO4_25C, LOG_BETA_H3PO4_25C, LOG_BETA_HPO4_25C
from .phosphate_complexes import (
    LOG_BETA_MG_H2PO4,
    LOG_BETA_MG_HPO4,
    LOG_BETA_MG_PO4,
    LOG_BETA_NA_HPO4,
)
from .struvite import struvite_saturation_index
from .competition import calcium_sulfate_struvite_competition
from .phosphate import orthophosphate_speciation


@dataclass(frozen=True, slots=True)
class StruviteMixtureSpeciation:
    """Free magnesium, ammonium and phosphate and the struvite saturation index of a mixture at a
    pH.
    """

    magnesium_molal: float
    ammoniacal_nitrogen_molal: float
    phosphate_molal: float
    sodium_molal: float
    ph: float
    ionic_strength: float
    free_magnesium_molal: float
    ammonium_molal: float
    free_phosphate_molal: float
    struvite_si: float


@dataclass(frozen=True, slots=True)
class ChargeBalancedStruviteMixture:
    """A struvite mixture solved for charge balance, with the gypsum check when calcium and sulfate
    are present.
    """

    ph: float
    ionic_strength: float
    charge_residual: float
    mixture: StruviteMixtureSpeciation
    gypsum_si: float | None = None
    free_calcium_molal: float = 0.0
    free_sulfate_molal: float = 0.0
    calcium_sulfate_molal: float = 0.0


def _calcium_sulfate_free_totals(
    calcium_total: float, sulfate_total: float, ionic_strength: float
) -> tuple[float, float, float]:
    """Conserve Ca/SO4 totals with neutral CaSO4(aq) at fixed I."""
    gamma = davies_gamma(2, ionic_strength)
    # Solve for the free amount of the limiting component. Rationalizing the
    # positive quadratic root avoids subtracting nearly equal numbers. Unlike
    # the former fixed-point iteration, this cannot silently return a cycle.
    limiting, excess = min(calcium_total, sulfate_total), abs(calcium_total - sulfate_total)
    constant = 10.0**LOG_BETA_CASO4_25C * gamma**2
    linear = 1 + constant * excess
    free = 2 * limiting / (linear + math.sqrt(linear**2 + 4 * constant * limiting))
    pair = limiting - free
    return calcium_total - pair, sulfate_total - pair, pair


def struvite_mixture_speciation(
    magnesium_molal: float,
    ammoniacal_nitrogen_molal: float,
    phosphate_molal: float,
    sodium_molal: float,
    ph: float,
    ionic_strength: float,
) -> StruviteMixtureSpeciation:
    """Solve Mg/P and NHx mass balances at supplied pH and ionic strength."""
    values = (
        magnesium_molal,
        ammoniacal_nitrogen_molal,
        phosphate_molal,
        sodium_molal,
        ph,
        ionic_strength,
    )
    if (
        not all(math.isfinite(v) for v in values)
        or min(values[:4]) <= 0
        or not 0 <= ph <= 14
        or not 0 <= ionic_strength <= 0.1
    ):
        raise DeliveryError("out_of_range", "invalid fixed-pH struvite mixture inputs")
    g1, g2, g3 = (davies_gamma(z, ionic_strength) for z in (1, 2, 3))
    ah = 10**-ph
    ana = sodium_molal * g1

    def at(mg):
        amg = mg * g2
        hpo = 10**LOG_BETA_HPO4_25C * ah
        h2 = 10**LOG_BETA_H2PO4_25C * ah**2
        h3 = 10**LOG_BETA_H3PO4_25C * ah**3
        b = (
            1 / g3
            + hpo / g2
            + h2 / g1
            + h3
            + 10**LOG_BETA_MG_PO4 * amg / g1
            + 10**LOG_BETA_MG_HPO4 * amg * hpo
            + 10**LOG_BETA_MG_H2PO4 * amg * h2 / g1
            + 10**LOG_BETA_NA_HPO4 * ana * hpo / g1
        )
        apo = phosphate_molal / b
        complexes = (
            10**LOG_BETA_MG_PO4 * amg * apo / g1
            + 10**LOG_BETA_MG_HPO4 * amg * hpo * apo
            + 10**LOG_BETA_MG_H2PO4 * amg * h2 * apo / g1
        )
        return apo, complexes

    lo, hi = 0.0, magnesium_molal
    for _ in range(100):
        mg = (lo + hi) / 2
        _, complexes = at(mg)
        if mg + complexes < magnesium_molal:
            lo = mg
        else:
            hi = mg
    mg = (lo + hi) / 2
    apo, _ = at(mg)
    nh = ammonia_speciation(ammoniacal_nitrogen_molal, ph, ionic_strength)
    return StruviteMixtureSpeciation(
        magnesium_molal,
        ammoniacal_nitrogen_molal,
        phosphate_molal,
        sodium_molal,
        ph,
        ionic_strength,
        mg,
        nh.ammonium_molal,
        apo / g3,
        struvite_saturation_index(mg * g2, nh.ammonium_activity, apo),
    )


def solve_charge_balanced_struvite_mixture(
    magnesium_molal: float,
    ammoniacal_nitrogen_molal: float,
    phosphate_molal: float,
    sodium_molal: float,
    chloride_molal: float,
    calcium_molal: float = 0.0,
    sulfate_molal: float = 0.0,
) -> ChargeBalancedStruviteMixture:
    """Solve pH/I for the reduced Mg/NHx/P/Na/Cl aqueous system.

    This is not a complete fertilizer-water solver: calcium, sulfate,
    carbonate, other counter-ions, and solid precipitation are excluded.
    """
    if not all(
        math.isfinite(v) and v >= 0 for v in (chloride_molal, calcium_molal, sulfate_molal)
    ):
        raise DeliveryError(
            "out_of_range",
            "counter-ion and calcium/sulfate molalities must be finite and non-negative",
        )
    ionic_strength = 0.005
    ph = 7.0
    for _ in range(60):

        def residual(candidate_ph: float):
            mix = struvite_mixture_speciation(
                magnesium_molal,
                ammoniacal_nitrogen_molal,
                phosphate_molal,
                sodium_molal,
                candidate_ph,
                ionic_strength,
            )
            free_ca, free_so4, _ = _calcium_sulfate_free_totals(
                calcium_molal, sulfate_molal, ionic_strength
            )
            phosphate = orthophosphate_speciation(phosphate_molal, candidate_ph, ionic_strength)
            h = 10 ** (-candidate_ph) / davies_gamma(1, ionic_strength)
            oh = 10 ** (-14 + candidate_ph) / davies_gamma(1, ionic_strength)
            return (
                2 * mix.free_magnesium_molal
                + mix.ammonium_molal
                + sodium_molal
                + 2 * free_ca
                + h
                - 3 * phosphate.po4_molal
                - 2 * phosphate.hpo4_molal
                - phosphate.h2po4_molal
                - chloride_molal
                - 2 * free_so4
                - oh
            )

        lo, hi = 0.0, 14.0
        for _ in range(80):
            mid = (lo + hi) / 2
            if residual(mid) > 0:
                lo = mid
            else:
                hi = mid
        ph = (lo + hi) / 2
        mix = struvite_mixture_speciation(
            magnesium_molal,
            ammoniacal_nitrogen_molal,
            phosphate_molal,
            sodium_molal,
            ph,
            ionic_strength,
        )
        phosphate = orthophosphate_speciation(phosphate_molal, ph, ionic_strength)
        free_ca, free_so4, pair = _calcium_sulfate_free_totals(
            calcium_molal, sulfate_molal, ionic_strength
        )
        updated = 0.5 * (
            4 * mix.free_magnesium_molal
            + mix.ammonium_molal
            + sodium_molal
            + chloride_molal
            + 4 * free_ca
            + 4 * free_so4
            + 9 * phosphate.po4_molal
            + 4 * phosphate.hpo4_molal
            + phosphate.h2po4_molal
        )
        if abs(updated - ionic_strength) < 1e-10:
            break
        ionic_strength = (ionic_strength + updated) / 2
    else:
        raise DeliveryError("nonconvergent", "legacy struvite ionic-strength iteration limit")
    gypsum_si = None
    if calcium_molal and sulfate_molal:
        gamma2 = davies_gamma(2, ionic_strength)
        gypsum_si = calcium_sulfate_struvite_competition(
            free_ca * gamma2,
            free_so4 * gamma2,
            mix.free_magnesium_molal * gamma2,
            ammonia_speciation(ammoniacal_nitrogen_molal, ph, ionic_strength).ammonium_activity,
            mix.free_phosphate_molal * davies_gamma(3, ionic_strength),
        ).gypsum_si
    return ChargeBalancedStruviteMixture(
        ph, ionic_strength, residual(ph), mix, gypsum_si, free_ca, free_so4, pair
    )
