"""Conversion of a stated catalogue dose into analytical equilibrium totals.

The conversion is deliberately a data boundary: the caller supplies a
``ProductChemistry`` profile, not a string which is interpreted by a solver.
The catalogue adapter merely resolves that profile once.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from .catalogue_chemistry import ProductChemistry, chemistry_for_product
from .delivery_contracts import DeliveryError

MOLAR_MASS = {"N": 14.0067, "P": 30.973762, "K": 39.0983, "Ca": 40.078,
              "Mg": 24.305, "S": 32.06, "Fe": 55.845, "Mn": 54.938044,
              "Zn": 65.38, "Cu": 63.546, "B": 10.81, "Mo": 95.95,
              "Na": 22.989769}

@dataclass(frozen=True, slots=True)
class ProductAnalyticalTotals:
    """Molal analytical components arising from a stated g/kg-water dose."""
    chemistry: ProductChemistry
    dose_g_per_kg_water: float
    totals: Mapping[str, float]
    counterions: Mapping[str, float]
    ligands: Mapping[str, float]
    inert_mass_fraction: float

def _finite_dose(value: float) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise DeliveryError("out_of_range", "product dose must be finite and non-negative g/kg water")
    return float(value)

def convert_product_dose(product: Mapping[str, object], chemistry: ProductChemistry,
                         dose_g_per_kg_water: float) -> ProductAnalyticalTotals:
    """Convert a library assay using an explicit chemistry profile.

    Assays are elemental mass fractions.  Counterions/ligands are declared by
    the chemical family; unassayed remainder is retained as inert carrier.
    """
    dose = _finite_dose(dose_g_per_kg_water)
    if str(product.get("name", "")) != chemistry.name:
        raise DeliveryError("product_chemistry_mismatch", "product and explicit chemistry profile do not match")
    assay = product.get("elements")
    if not isinstance(assay, Mapping):
        raise DeliveryError("missing_field", "product assay is required")
    totals = {key: dose * float(percent) / 100.0 / MOLAR_MASS[key.split("_")[0]]
              for key, percent in assay.items() if key.split("_")[0] in MOLAR_MASS}
    # Normalize nitrogen form to the analytical species vocabulary.
    if "N_NO3" in totals: totals["nitrate"] = totals.pop("N_NO3")
    if "N_NH4" in totals: totals["ammonium"] = totals.pop("N_NH4")
    if "N_UREA" in totals: totals["urea"] = totals.pop("N_UREA")
    if "P" in totals: totals["phosphate"] = totals.pop("P")
    if "S" in totals: totals["sulfate"] = totals.pop("S")
    if "B" in totals: totals["boron"] = totals.pop("B")
    if "Mo" in totals: totals["molybdate"] = totals.pop("Mo")
    counterions: dict[str, float] = {}
    ligands: dict[str, float] = {}
    family = chemistry.family
    # These relations follow the stated dissolved formula/profile, not label
    # text. Assay values remain the authoritative analytical metal totals.
    if family == "edta_chelate":
        ligands["EDTA"] = sum(totals.get(k, 0.0) for k in ("Fe", "Mn", "Zn", "Cu"))
    elif family == "dtpa_chelate": ligands["DTPA"] = totals.get("Fe", 0.0)
    elif family == "eddha_chelate": ligands["o,o-EDDHA"] = totals.get("Fe", 0.0)
    elif family == "citrate_salt":
        ligands["citrate"] = totals.get("K", 0.0) / 3.0
    elif family == "edta_borax_molybdate_blend":
        ligands["EDTA"] = sum(totals.get(k, 0.0) for k in ("Fe", "Mn", "Zn", "Cu"))
        counterions["sodium"] = 0.5 * totals.get("boron", 0.0) + 2 * totals.get("molybdate", 0.0)
    elif family == "boron" and "borax" in chemistry.components:
        counterions["sodium"] = 0.5 * totals.get("boron", 0.0)
    elif family == "molybdate": counterions["sodium"] = 2 * totals.get("molybdate", 0.0)
    elif family == "free_metal_sulfate": counterions["sulfate"] = sum(totals.get(k, 0.0) for k in ("Fe", "Mn", "Zn", "Cu"))
    # Explicit profile components also catch macro formula counterions where
    # the assay omits their analytical total (for example Ca(NO3)2).
    if family == "macro_salt":
        if "Ca+2" in chemistry.components: counterions["nitrate"] = 2 * totals.get("Ca", 0.0)
        elif "Mg+2" in chemistry.components and "NO3-" in chemistry.components: counterions["nitrate"] = 2 * totals.get("Mg", 0.0)
        elif "SO4-2" in chemistry.components:
            counterions["sulfate"] = (totals.get("Mg", 0.0) + totals.get("Fe", 0.0) + totals.get("Zn", 0.0)
                                          + 0.5 * totals.get("ammonium", 0.0))
    inert = max(0.0, 1.0 - sum(float(v) for v in assay.values()) / 100.0)
    return ProductAnalyticalTotals(chemistry, dose, totals, counterions, ligands, inert)

def convert_catalogue_product_dose(product: Mapping[str, object], dose_g_per_kg_water: float) -> ProductAnalyticalTotals:
    """Catalogue adapter. Equilibrium callers should retain the returned profile."""
    return convert_product_dose(product, chemistry_for_product(str(product.get("name", ""))), dose_g_per_kg_water)
