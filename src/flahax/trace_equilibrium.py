"""Source-versioned CH-micro EDTA, borax, and molybdate equilibrium model.

The model deliberately represents the declared product components rather than
turning a trace blend into unchelated free metals.  Constants are from the
``minteq.v4.dat`` database distributed with USGS PHREEQC 3.8.6.  It is a
25 C, Davies-domain calculation (``I <= 0.1 mol/kgw``).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from .delivery_contracts import DeliveryError
from .equilibrium import davies_gamma
from .catalogue_chemistry import LIGAND_PROFILES


# molar masses, g mol-1; used only to convert the declared elemental assay.
MOLAR_MASS = {"Fe": 55.845, "Mn": 54.938_044, "Zn": 65.38, "Cu": 63.546, "B": 10.81, "Mo": 95.95}
EDTA_LOG_BETA = LIGAND_PROFILES["EDTA"]["metal_log_beta"]
EDTA_COMPLEX_CHARGE = {"Fe+3": -1, "Mn+2": -2, "Zn+2": -2, "Cu+2": -2, "Ca+2": -2, "Mg+2": -2}
EDTA_METAL_CHARGE = {"Fe+3": 3, "Mn+2": 2, "Zn+2": 2, "Cu+2": 2, "Ca+2": 2, "Mg+2": 2}
# H_n(EDTA)^(n-4), written from Edta-4 in minteq.v4.dat.
EDTA_PROTONATION_LOG_BETA = LIGAND_PROFILES["EDTA"]["protonation_log_k"]
LOG_BETA_MOLYBDATE_H = 4.2988
LOG_BETA_MOLYBDATE_H2 = 8.1636
# B(OH)3 + H2O = B(OH)4- + H+; phreeqc.dat at 25 C.
LOG_K_BORIC_ACID = -9.24


def _nonnegative(**values: float) -> None:
    for name, value in values.items():
        if not math.isfinite(value) or value < 0:
            raise DeliveryError("out_of_range", f"{name} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ChMicroTotals:
    """Analytical molal totals for the declared CH-micro components."""

    iron: float = 0.0
    manganese: float = 0.0
    zinc: float = 0.0
    copper: float = 0.0
    edta: float = 0.0
    boron: float = 0.0
    molybdate: float = 0.0
    calcium: float = 0.0
    magnesium: float = 0.0

    def __post_init__(self) -> None:
        _nonnegative(**{name: getattr(self, name) for name in self.__dataclass_fields__})


@dataclass(frozen=True, slots=True)
class ChMicroProductDose:
    """Declared CH-micro assay converted from g product per kg water.

    Product identity (declared by the project owner): Fe-EDTA, Mn-EDTA,
    Zn-EDTA, Cu-EDTA, borax, and sodium molybdate.  One EDTA ligand per
    chelated metal is an exact stoichiometric consequence of those names.
    """

    product_g_per_kg_water: float

    def __post_init__(self) -> None:
        _nonnegative(product_g_per_kg_water=self.product_g_per_kg_water)

    def totals(self, *, calcium: float = 0.0, magnesium: float = 0.0) -> ChMicroTotals:
        _nonnegative(calcium=calcium, magnesium=magnesium)
        grams = self.product_g_per_kg_water
        values = {
            "iron": grams * .0700 / MOLAR_MASS["Fe"],
            "manganese": grams * .0200 / MOLAR_MASS["Mn"],
            "zinc": grams * .0040 / MOLAR_MASS["Zn"],
            "copper": grams * .0011 / MOLAR_MASS["Cu"],
            "boron": grams * .0130 / MOLAR_MASS["B"],
            "molybdate": grams * .0005 / MOLAR_MASS["Mo"],
        }
        values["edta"] = values["iron"] + values["manganese"] + values["zinc"] + values["copper"]
        values["calcium"] = calcium
        values["magnesium"] = magnesium
        return ChMicroTotals(**values)


@dataclass(frozen=True, slots=True)
class TraceEquilibrium:
    """Mass-balanced EDTA competition and B/Mo acid-base species at fixed pH."""

    totals: ChMicroTotals
    ph: float
    ionic_strength: float
    species: Mapping[str, float]
    activities: Mapping[str, float]


def _valid_ph_and_i(ph: float, ionic_strength: float) -> None:
    if not math.isfinite(ph) or not 0 <= ph <= 14:
        raise DeliveryError("out_of_range", "pH must be finite and in [0, 14]")
    if not math.isfinite(ionic_strength) or not 0 <= ionic_strength <= .1:
        raise DeliveryError("activity_model_out_of_range", "trace model requires 0 <= I <= 0.1 mol/kgw")


def solve_ch_micro_equilibrium(totals: ChMicroTotals, ph: float, ionic_strength: float) -> TraceEquilibrium:
    """Solve the declared CH-micro chemistry at fixed pH and ionic strength.

    The one-dimensional EDTA mass balance is solved by bisection.  It includes
    competition from supplied Ca and Mg, which is essential in hard water or a
    calcium-nitrate fertilizer mixture.  Redox is deliberately fixed as Fe(III)
    because the declared component is Fe-EDTA; no unsupported redox conversion
    is inferred.
    """
    if not isinstance(totals, ChMicroTotals):
        raise DeliveryError("invalid_type", "totals must be ChMicroTotals")
    _valid_ph_and_i(ph, ionic_strength)
    h = 10.0 ** -ph
    gamma = {charge: davies_gamma(charge, ionic_strength) for charge in (1, 2, 3, 4)}
    metals = {
        "Fe+3": totals.iron, "Mn+2": totals.manganese, "Zn+2": totals.zinc,
        "Cu+2": totals.copper, "Ca+2": totals.calcium, "Mg+2": totals.magnesium,
    }

    def distribution(edta_activity: float) -> tuple[dict[str, float], float]:
        complexes: dict[str, float] = {}
        for metal, total in metals.items():
            z_metal = EDTA_METAL_CHARGE[metal]
            z_complex = abs(EDTA_COMPLEX_CHARGE[metal])
            multiplier = 10.0 ** EDTA_LOG_BETA[metal] * gamma[z_metal] * edta_activity / gamma[z_complex]
            free = total / (1.0 + multiplier)
            complexes[metal] = total - free
            complexes[f"free:{metal}"] = free
        ligand = edta_activity / gamma[4]
        for count, log_beta in enumerate(EDTA_PROTONATION_LOG_BETA, 1):
            charge = abs(4 - count)
            ligand += 10.0 ** log_beta * edta_activity * h**count / (gamma[charge] if charge else 1.0)
        return complexes, ligand + sum(complexes[metal] for metal in metals)

    if totals.edta == 0:
        complexes = {metal: 0.0 for metal in metals}
        complexes.update({f"free:{metal}": total for metal, total in metals.items()})
        edta_activity = 0.0
    else:
        low, high = 0.0, max(totals.edta * gamma[4], 1e-30)
        while distribution(high)[1] < totals.edta:
            high *= 2.0
        for _ in range(100):
            middle = (low + high) / 2.0
            if distribution(middle)[1] < totals.edta:
                low = middle
            else:
                high = middle
        edta_activity = (low + high) / 2.0
        complexes, _ = distribution(edta_activity)

    borate_ratio = 10.0 ** LOG_K_BORIC_ACID / h / gamma[1]
    boric = totals.boron / (1.0 + borate_ratio)
    molybdate_factor = 1.0 + 10.0 ** LOG_BETA_MOLYBDATE_H * h / gamma[1] + 10.0 ** LOG_BETA_MOLYBDATE_H2 * h * h
    mo4 = totals.molybdate / molybdate_factor
    species = {
        "EDTA-4": edta_activity / gamma[4],
        "Fe(III)-EDTA": complexes["Fe+3"], "Mn-EDTA": complexes["Mn+2"],
        "Zn-EDTA": complexes["Zn+2"], "Cu-EDTA": complexes["Cu+2"],
        "Ca-EDTA": complexes["Ca+2"], "Mg-EDTA": complexes["Mg+2"],
        "Fe+3": complexes["free:Fe+3"], "Mn+2": complexes["free:Mn+2"],
        "Zn+2": complexes["free:Zn+2"], "Cu+2": complexes["free:Cu+2"],
        "Ca+2": complexes["free:Ca+2"], "Mg+2": complexes["free:Mg+2"],
        "B(OH)3": boric, "B(OH)4-": boric * borate_ratio,
        "MoO4-2": mo4, "HMoO4-": 10.0 ** LOG_BETA_MOLYBDATE_H * mo4 * h / gamma[1],
        "H2MoO4": 10.0 ** LOG_BETA_MOLYBDATE_H2 * mo4 * h * h,
    }
    activities = {name: amount for name, amount in species.items()}
    for name, z in {"EDTA-4": 4, "Fe+3": 3, "Mn+2": 2, "Zn+2": 2, "Cu+2": 2, "Ca+2": 2, "Mg+2": 2, "B(OH)4-": 1, "MoO4-2": 2, "HMoO4-": 1}.items():
        activities[name] *= gamma[z]
    activities["H+"] = h
    return TraceEquilibrium(totals, ph, ionic_strength, species, activities)
