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
    "DTPA": {"Fe+3": -2},
    "o,o-EDDHA": {"Fe+3": -1},
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
    """Fixed-I view of the same simultaneous aqueous mass-action model."""
    if not isinstance(totals, ChMicroTotals):
        raise DeliveryError("invalid_type", "totals must be ChMicroTotals")
    _valid_ph_and_i(ph, ionic_strength)
    from .aqueous_model import solve
    from .mixed_equilibrium import TRACE_BASIS, view
    result=solve({b:getattr(totals,n) for n,b in TRACE_BASIS.items()},ph,ionic_strength=ionic_strength)
    return TraceEquilibrium(totals,ph,ionic_strength,view(result.species),view(result.activities))
