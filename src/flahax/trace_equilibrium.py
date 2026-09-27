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
METAL_CHARGE = {"Fe+3": 3, "Mn+2": 2, "Zn+2": 2, "Cu+2": 2, "Ca+2": 2, "Mg+2": 2}
# Charges are derived directly from the reactions in minteq.v4.dat and the
# checked-in Dtp/Edd extension.  Citrate is native to minteq and is retained
# here because it is a catalogue ligand, not an invented generic organic ion.
COMPLEX_CHARGE = {
    "EDTA": {"Fe+3": -1, "Mn+2": -2, "Zn+2": -2, "Cu+2": -2, "Ca+2": -2, "Mg+2": -2},
    "DTPA": {"Fe+3": -2, "Mn+2": -3, "Zn+2": -3, "Cu+2": -3, "Ca+2": -3, "Mg+2": -3},
    "o,o-EDDHA": {"Fe+3": -1, "Ca+2": -2, "Mg+2": -2},
    "citrate": {"Fe+3": 0, "Mn+2": -1, "Zn+2": -1, "Cu+2": -1, "Ca+2": -1, "Mg+2": -1},
}
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
    dtpa: float = 0.0
    eddha: float = 0.0
    citrate: float = 0.0
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

    All declared ligand and metal balances are solved together.  This includes
    protonated free ligand forms and Ca/Mg competition, rather than applying
    DTPA or EDDHA as a post-processing removal from an EDTA result. Redox is
    deliberately fixed as Fe(III); no unsupported redox conversion is inferred.
    """
    if not isinstance(totals, ChMicroTotals):
        raise DeliveryError("invalid_type", "totals must be ChMicroTotals")
    _valid_ph_and_i(ph, ionic_strength)
    h = 10.0 ** -ph
    gamma = {charge: davies_gamma(charge, ionic_strength) for charge in range(1, 6)}
    metals = {
        "Fe+3": totals.iron, "Mn+2": totals.manganese, "Zn+2": totals.zinc,
        "Cu+2": totals.copper, "Ca+2": totals.calcium, "Mg+2": totals.magnesium,
    }

    ligand_totals = {"EDTA": totals.edta, "DTPA": totals.dtpa, "o,o-EDDHA": totals.eddha, "citrate": totals.citrate}
    def ligand_inventory(name: str, activity: float, available: Mapping[str, float]) -> tuple[float, dict[str, float]]:
        profile = LIGAND_PROFILES[name]
        charge = abs(int(profile["charge"]))
        inventory = activity / gamma[charge]
        for count, log_beta in enumerate(profile["protonation_log_k"], 1):
            protonated_charge = abs(charge - count)
            inventory += 10.0 ** log_beta * activity * h**count / (gamma[protonated_charge] if protonated_charge else 1.0)
        complexes = {}
        for metal, amount in available.items():
            log_beta = profile["metal_log_beta"].get(metal)
            if log_beta is not None:
                complex_charge = abs(COMPLEX_CHARGE[name][metal])
                multiplier = 10.0 ** log_beta * gamma[METAL_CHARGE[metal]] * activity / (gamma[complex_charge] if complex_charge else 1.0)
                complexes[metal] = amount * multiplier / (1.0 + multiplier)
        return inventory + sum(complexes.values()), complexes

    # Each ligand balance is monotonic.  The sequence is intentional: a
    # declared pre-chelate has its own analytical ligand inventory, and the
    # remaining dissolved-metal inventory is passed to the next declared
    # ligand. This keeps every analytical balance exact and lets the outer
    # macro/trace solver couple the resulting Ca/Mg removals.
    ligand_activities: dict[str, float] = {}
    ligand_complexes: dict[str, dict[str, float]] = {}
    available = dict(metals)
    for name in ("EDTA", "DTPA", "o,o-EDDHA", "citrate"):
        total = ligand_totals[name]
        if not total:
            ligand_activities[name], ligand_complexes[name] = 0.0, {}
            continue
        charge = abs(int(LIGAND_PROFILES[name]["charge"]))
        low, high = 0.0, max(total * gamma[charge], 1e-30)
        while ligand_inventory(name, high, available)[0] < total:
            high *= 2.0
        for _ in range(100):
            middle = (low + high) / 2.0
            if ligand_inventory(name, middle, available)[0] < total:
                low = middle
            else:
                high = middle
        ligand_activities[name] = (low + high) / 2.0
        ligand_complexes[name] = ligand_inventory(name, ligand_activities[name], available)[1]
        for metal, amount in ligand_complexes[name].items():
            available[metal] -= amount

    borate_ratio = 10.0 ** LOG_K_BORIC_ACID / h / gamma[1]
    boric = totals.boron / (1.0 + borate_ratio)
    molybdate_factor = 1.0 + 10.0 ** LOG_BETA_MOLYBDATE_H * h / gamma[1] + 10.0 ** LOG_BETA_MOLYBDATE_H2 * h * h
    mo4 = totals.molybdate / molybdate_factor
    species = {
        "EDTA-4": ligand_activities["EDTA"] / gamma[4],
        "Fe(III)-EDTA": ligand_complexes["EDTA"].get("Fe+3", 0.0), "Mn-EDTA": ligand_complexes["EDTA"].get("Mn+2", 0.0),
        "Zn-EDTA": ligand_complexes["EDTA"].get("Zn+2", 0.0), "Cu-EDTA": ligand_complexes["EDTA"].get("Cu+2", 0.0),
        "Ca-EDTA": ligand_complexes["EDTA"].get("Ca+2", 0.0), "Mg-EDTA": ligand_complexes["EDTA"].get("Mg+2", 0.0),
        **available,
        "B(OH)3": boric, "B(OH)4-": boric * borate_ratio,
        "MoO4-2": mo4, "HMoO4-": 10.0 ** LOG_BETA_MOLYBDATE_H * mo4 * h / gamma[1],
        "H2MoO4": 10.0 ** LOG_BETA_MOLYBDATE_H2 * mo4 * h * h,
    }
    for ligand in ("DTPA", "o,o-EDDHA", "citrate"):
        charge = abs(int(LIGAND_PROFILES[ligand]["charge"]))
        species[f"{ligand}-free"] = ligand_activities[ligand] / gamma[charge]
        for metal, amount in ligand_complexes[ligand].items():
            species[f"{metal}-{ligand}"] = amount
    activities = {name: amount for name, amount in species.items()}
    for name, z in {"EDTA-4": 4, "Fe+3": 3, "Mn+2": 2, "Zn+2": 2, "Cu+2": 2, "Ca+2": 2, "Mg+2": 2, "B(OH)4-": 1, "MoO4-2": 2, "HMoO4-": 1}.items():
        activities[name] *= gamma[z]
    activities["H+"] = h
    return TraceEquilibrium(totals, ph, ionic_strength, species, activities)
