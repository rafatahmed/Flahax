"""The explicit aqueous-chemistry identity of every shipped fertilizer.

This is the input boundary for the unified P2/P3 equilibrium system.  A product
may not enter an equilibrium calculation by its display name alone: it has a
declared dissolved-component family, source profile, and temperature domain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .delivery_contracts import DeliveryError


@dataclass(frozen=True, slots=True)
class ProductChemistry:
    """Source-versioned chemical identity; not a nutrient-assay replacement."""

    name: str
    family: str
    components: tuple[str, ...]
    source_profile: str
    temperature_c: float = 25.0

    def __post_init__(self) -> None:
        if not self.name or not self.family or not self.components or not self.source_profile:
            raise DeliveryError("missing_field", "product chemistry requires name, family, components, and source profile")


PHREEQC_MINTEQ_V4 = "USGS PHREEQC 3.8.6 minteq.v4.dat, 25 C"

# The canonical, fully deprotonated ligand forms used by the unified solver.
# EDDHA is explicitly the o,o form selected for the otherwise unspecific
# catalogue product; it is not interchangeable with o,p-EDDHA.
LIGAND_PROFILES = {
    "EDTA": {"charge": -4, "protonation_log_k": (10.948, 17.221, 20.34, 22.5, 24.0), "metal_log_beta": {"Fe+3": 27.7, "Mn+2": 15.6, "Zn+2": 18.0, "Cu+2": 20.5, "Ca+2": 12.42, "Mg+2": 10.57}, "source": PHREEQC_MINTEQ_V4},
    "DTPA": {"charge": -5, "protonation_log_k": (10.48, 19.08, 23.36, 25.96, 27.96), "metal_log_beta": {"Fe+3": 28.6, "Mn+2": 15.6, "Zn+2": 18.4, "Cu+2": 21.4, "Ca+2": 10.7, "Mg+2": 9.3}, "source": "Martell and Smith stability constants, 25 C"},
    "o,o-EDDHA": {"charge": -4, "protonation_log_k": (11.88, 22.68, 31.35, 37.63), "metal_log_beta": {"Fe+3": 35.1, "Ca+2": 7.99, "Mg+2": 10.13}, "source": "Yunta et al. 2003 / o,o-EDDHA profile, 25 C"},
}
PRODUCT_CHEMISTRY: Mapping[str, ProductChemistry] = {
    "Ammonium Dibasic Phosphate": ProductChemistry("Ammonium Dibasic Phosphate", "macro_salt", ("NH4+", "HPO4-2"), PHREEQC_MINTEQ_V4),
    "Ammonium Monobasic Phosphate": ProductChemistry("Ammonium Monobasic Phosphate", "macro_salt", ("NH4+", "H2PO4-"), PHREEQC_MINTEQ_V4),
    "Ammonium Nitrate": ProductChemistry("Ammonium Nitrate", "macro_salt", ("NH4+", "NO3-"), PHREEQC_MINTEQ_V4),
    "Ammonium Sulfate": ProductChemistry("Ammonium Sulfate", "macro_salt", ("NH4+", "SO4-2"), PHREEQC_MINTEQ_V4),
    "Boric Acid": ProductChemistry("Boric Acid", "boron", ("B(OH)3",), PHREEQC_MINTEQ_V4),
    "CH - micro": ProductChemistry("CH - micro", "edta_borax_molybdate_blend", ("Fe(III)-EDTA", "Mn-EDTA", "Zn-EDTA", "Cu-EDTA", "borax", "sodium molybdate"), "project-declared CH-micro composition, 2026-09-26; " + PHREEQC_MINTEQ_V4),
    "Calcium Nitrate (ag grade)": ProductChemistry("Calcium Nitrate (ag grade)", "macro_salt", ("Ca+2", "NO3-", "NH4+"), PHREEQC_MINTEQ_V4),
    "Copper EDTA": ProductChemistry("Copper EDTA", "edta_chelate", ("Cu-EDTA",), PHREEQC_MINTEQ_V4),
    "Copper Sulfate (pentahydrate)": ProductChemistry("Copper Sulfate (pentahydrate)", "free_metal_sulfate", ("Cu+2", "SO4-2"), PHREEQC_MINTEQ_V4),
    "Iron DTPA": ProductChemistry("Iron DTPA", "dtpa_chelate", ("Fe(III)-DTPA",), "Martell/Smith stability profile; Fe(III)-DTPA log beta 28.6 at 25 C"),
    "Iron EDDHA": ProductChemistry("Iron EDDHA", "eddha_chelate", ("Fe(III)-o,o-EDDHA",), "Yunta et al. 2003 o,o-EDDHA profile; Fe(III) log beta 35.1 at 25 C"),
    "Iron EDTA": ProductChemistry("Iron EDTA", "edta_chelate", ("Fe(III)-EDTA",), PHREEQC_MINTEQ_V4),
    "Iron II Sulfate (Hepahydrate)": ProductChemistry("Iron II Sulfate (Hepahydrate)", "free_metal_sulfate", ("Fe+2", "SO4-2"), PHREEQC_MINTEQ_V4),
    "Magnesium Sulfate (Heptahydrate)": ProductChemistry("Magnesium Sulfate (Heptahydrate)", "macro_salt", ("Mg+2", "SO4-2"), PHREEQC_MINTEQ_V4),
    "Mg Nitrate": ProductChemistry("Mg Nitrate", "macro_salt", ("Mg+2", "NO3-"), PHREEQC_MINTEQ_V4),
    "Mn EDTA": ProductChemistry("Mn EDTA", "edta_chelate", ("Mn-EDTA",), PHREEQC_MINTEQ_V4),
    "Phosphoric Acid (75%)": ProductChemistry("Phosphoric Acid (75%)", "macro_acid", ("H3PO4",), PHREEQC_MINTEQ_V4),
    "Potassium Carbonate": ProductChemistry("Potassium Carbonate", "macro_salt", ("K+", "CO3-2"), PHREEQC_MINTEQ_V4),
    "Potassium Citrate": ProductChemistry("Potassium Citrate", "citrate_salt", ("K+", "citrate"), PHREEQC_MINTEQ_V4),
    "Potassium Dibasic Phosphate": ProductChemistry("Potassium Dibasic Phosphate", "macro_salt", ("K+", "HPO4-2"), PHREEQC_MINTEQ_V4),
    "Potassium Monobasic Phosphate": ProductChemistry("Potassium Monobasic Phosphate", "macro_salt", ("K+", "H2PO4-"), PHREEQC_MINTEQ_V4),
    "Potassium Nitrate": ProductChemistry("Potassium Nitrate", "macro_salt", ("K+", "NO3-"), PHREEQC_MINTEQ_V4),
    "Potassium Sulfate": ProductChemistry("Potassium Sulfate", "macro_salt", ("K+", "SO4-2"), PHREEQC_MINTEQ_V4),
    "Sodium Borate (Decahydrate) (borax)": ProductChemistry("Sodium Borate (Decahydrate) (borax)", "boron", ("Na+", "B(OH)3"), PHREEQC_MINTEQ_V4),
    "Sodium Molybdate (Dihydrate)": ProductChemistry("Sodium Molybdate (Dihydrate)", "molybdate", ("Na+", "MoO4-2"), PHREEQC_MINTEQ_V4),
    "Urea": ProductChemistry("Urea", "neutral_urea", ("CO(NH2)2"), "analytical urea; hydrolysis is kinetic and excluded from 25 C instantaneous equilibrium"),
    "Zinc Sulfate (Monohydrate)": ProductChemistry("Zinc Sulfate (Monohydrate)", "free_metal_sulfate", ("Zn+2", "SO4-2"), PHREEQC_MINTEQ_V4),
    "Zn EDTA": ProductChemistry("Zn EDTA", "edta_chelate", ("Zn-EDTA",), PHREEQC_MINTEQ_V4),
}


def chemistry_for_product(name: str) -> ProductChemistry:
    """Return a product's explicit equilibrium identity or fail closed."""
    try:
        return PRODUCT_CHEMISTRY[name]
    except KeyError as exc:
        raise DeliveryError("unsupported_product_chemistry", f"no chemistry record for {name!r}") from exc


def assert_catalogue_coverage(products: list[Mapping[str, object]]) -> None:
    """Require exact one-to-one coverage of the package fertilizer catalogue."""
    names = {str(product.get("name", "")) for product in products}
    mapped = set(PRODUCT_CHEMISTRY)
    if names != mapped:
        missing, stale = sorted(names - mapped), sorted(mapped - names)
        raise DeliveryError("catalogue_chemistry_mismatch", f"missing={missing}; stale={stale}")
