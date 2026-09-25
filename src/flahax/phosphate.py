"""Narrow orthophosphate acid/base speciation from PHREEQC `phreeqc.dat`.

This module calculates only the four uncomplexed orthophosphate forms at a
specified pH and ionic strength. It is a building block, not a fertilizer
compatibility decision: Ca/Mg complexes, counter-ions, solids, and a charge
balance solve are intentionally outside this function.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .delivery_contracts import DeliveryError
from .equilibrium import davies_gamma


# PHREEQC Version 3 phreeqc.dat, reactions written from PO4-3.
LOG_BETA_HPO4_25C = 12.346
LOG_BETA_H2PO4_25C = 19.553
LOG_BETA_H3PO4_25C = 21.721


@dataclass(frozen=True, slots=True)
class OrthophosphateSpeciation:
    """Uncomplexed phosphate species at a specified pH and ionic strength."""

    total_phosphate_molal: float
    ph: float
    ionic_strength: float
    po4_molal: float
    hpo4_molal: float
    h2po4_molal: float
    h3po4_molal: float
    po4_activity: float
    hpo4_activity: float
    h2po4_activity: float
    h3po4_activity: float


def orthophosphate_speciation(
    total_phosphate_molal: float, ph: float, ionic_strength: float
) -> OrthophosphateSpeciation:
    """Distribute total uncomplexed orthophosphate among four protonation states.

    The calculation uses ``a_H = 10**(-pH)`` and the PHREEQC mass-action
    reactions ``PO4-3 + nH+ = H_nPO4``. Davies coefficients convert activity
    to molality. The declared domain is 0 <= ionic strength <= 0.1 mol/kgw;
    outside it, this reduced Davies model is deliberately rejected.
    """
    for name, value in (("total phosphate", total_phosphate_molal), ("pH", ph), ("ionic strength", ionic_strength)):
        if not math.isfinite(value):
            raise DeliveryError("invalid_value", f"{name} must be finite")
    if total_phosphate_molal < 0:
        raise DeliveryError("out_of_range", "total phosphate must be non-negative")
    if not 0.0 <= ph <= 14.0:
        raise DeliveryError("out_of_range", "pH must be in [0, 14]")
    if not 0.0 <= ionic_strength <= 0.1:
        raise DeliveryError("unsupported_ionic_strength", "phosphate kernel supports ionic strength in [0, 0.1]")

    a_h = 10.0 ** -ph
    gamma_1 = davies_gamma(1, ionic_strength)
    gamma_2 = davies_gamma(2, ionic_strength)
    gamma_3 = davies_gamma(3, ionic_strength)
    factors = {
        "po4": 1.0,
        "hpo4": 10.0 ** LOG_BETA_HPO4_25C * a_h,
        "h2po4": 10.0 ** LOG_BETA_H2PO4_25C * a_h * a_h,
        "h3po4": 10.0 ** LOG_BETA_H3PO4_25C * a_h * a_h * a_h,
    }
    denominator = factors["po4"] / gamma_3 + factors["hpo4"] / gamma_2 + factors["h2po4"] / gamma_1 + factors["h3po4"]
    po4_activity = total_phosphate_molal / denominator
    activities = {name: po4_activity * factor for name, factor in factors.items()}
    return OrthophosphateSpeciation(
        total_phosphate_molal=total_phosphate_molal,
        ph=ph,
        ionic_strength=ionic_strength,
        po4_molal=activities["po4"] / gamma_3,
        hpo4_molal=activities["hpo4"] / gamma_2,
        h2po4_molal=activities["h2po4"] / gamma_1,
        h3po4_molal=activities["h3po4"],
        po4_activity=activities["po4"],
        hpo4_activity=activities["hpo4"],
        h2po4_activity=activities["h2po4"],
        h3po4_activity=activities["h3po4"],
    )
