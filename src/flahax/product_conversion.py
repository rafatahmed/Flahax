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
    if "N_UREA" in totals: totals["urea"] = totals.pop("N_UREA") / 2.0
    if "P" in totals: totals["phosphate"] = totals.pop("P")
    if "S" in totals: totals["sulfate"] = totals.pop("S")
    if "B" in totals: totals["boron"] = totals.pop("B")
    if "Mo" in totals: totals["molybdate"] = totals.pop("Mo")
    counterions: dict[str, float] = {}
    ligands: dict[str, float] = {}
    family = chemistry.family
    # These relations follow the stated dissolved formula/profile, not label
    # text. Assay values remain the authoritative analytical metal totals.
    # D2: chelate sodium counterions per formula unit (NaFe(III)EDTA,
    # Na2M(II)EDTA, Na2Fe(III)DTPA, NaFe(III)-o,o-EDDHA). They enter chemistry
    # totals only and are never added to the product assay ``elements``.
    edta_sodium = totals.get("Fe", 0.0) + 2 * sum(totals.get(k, 0.0) for k in ("Mn", "Zn", "Cu"))
    if family == "edta_chelate":
        ligands["EDTA"] = sum(totals.get(k, 0.0) for k in ("Fe", "Mn", "Zn", "Cu"))
        counterions["sodium"] = edta_sodium
    elif family == "dtpa_chelate":
        ligands["DTPA"] = totals.get("Fe", 0.0)
        counterions["sodium"] = 2 * totals.get("Fe", 0.0)
    elif family == "eddha_chelate":
        ligands["o,o-EDDHA"] = totals.get("Fe", 0.0)
        counterions["sodium"] = totals.get("Fe", 0.0)
    elif family == "citrate_salt":
        ligands["citrate"] = totals.get("K", 0.0) / 3.0
    elif family == "edta_borax_molybdate_blend":
        ligands["EDTA"] = sum(totals.get(k, 0.0) for k in ("Fe", "Mn", "Zn", "Cu"))
        counterions["sodium"] = (edta_sodium + 0.5 * totals.get("boron", 0.0)
                                 + 2 * totals.get("molybdate", 0.0))
    elif family == "boron" and "B(OH)4-" in chemistry.components:
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
    # Assayed totals are authoritative; formula-inferred counterions fill only
    # absent fields. They must never be added a second time to an assay total.
    counterions = {k:v for k,v in counterions.items() if k not in totals and not (k=='sodium' and 'Na' in totals)}
    if chemistry.name == 'Potassium Carbonate':
        counterions['carbonate'] = totals.get('K',0.0) / 2.0
    inert = max(0.0, 1.0 - sum(float(v) for v in assay.values()) / 100.0)
    return ProductAnalyticalTotals(chemistry, dose, totals, counterions, ligands, inert)

def convert_catalogue_product_dose(product: Mapping[str, object], dose_g_per_kg_water: float) -> ProductAnalyticalTotals:
    """Catalogue adapter. Equilibrium callers should retain the returned profile."""
    return convert_product_dose(product, chemistry_for_product(str(product.get("name", ""))), dose_g_per_kg_water)


_BASIS = {'Ca': 'Ca+2', 'Mg': 'Mg+2', 'K': 'K+', 'Na': 'Na+', 'sodium': 'Na+',
          'Fe': 'Fe+3', 'Mn': 'Mn+2', 'Zn': 'Zn+2', 'Cu': 'Cu+2', 'boron': 'H3BO3',
          'molybdate': 'MoO4-2', 'phosphate': 'PO4-3', 'sulfate': 'SO4-2',
          'nitrate': 'NO3-', 'ammonium': 'NH4+', 'carbonate': 'CO3-2', 'urea': 'Ure',
          'EDTA': 'Edta-4', 'DTPA': 'Dtp-5', 'o,o-EDDHA': 'Edd-4', 'citrate': 'Citrate-3'}


def _check_materials(doses: Mapping[str, float], materials, *, allow_undisclosed: bool = False) -> dict:
    """Validate the optional resolved-material mapping against the dosed products.

    Chemistry refuses an undisclosed blend; nutrient amounts (the band) may keep it.
    """
    from .materials import ResolvedMaterial
    if materials is None:
        return {}
    if not isinstance(materials, Mapping):
        raise DeliveryError("material_mismatch", "materials must map dosed product names to ResolvedMaterial")
    for name, material in materials.items():
        if name not in doses:
            raise DeliveryError("material_mismatch", f"material {name!r} is not a dosed product")
        if not isinstance(material, ResolvedMaterial) or material.name != name:
            raise DeliveryError("material_mismatch", f"materials[{name!r}] must be the ResolvedMaterial of {name!r}")
    for name, material in ({} if allow_undisclosed else materials).items():
        if material.composition == 'undisclosed':
            raise DeliveryError("composition_undisclosed",
                                f"{name!r} is a blend of undisclosed composition; chemistry is not supported")
    return dict(materials)


def _catalogue_product(identity_id: str, library: Mapping[str, Mapping]) -> Mapping:
    """The catalogue product an identity covers, as shipped (grade-free)."""
    from .materials import load_identities
    return library[load_identities()[identity_id]['products'][0]]


def catalogue_dose_contributions(doses: Mapping[str, float], *, materials=None):
    """Per conversion unit: (dosed product name, ProductChemistry, {basis: mol/kg water}).

    A product in ``materials`` is converted from its resolved record through the
    chemistry profile of its identity's catalogue product. A disclosed blend
    contributes one unit per component identity: that identity's shipped catalogue
    record and chemistry, at dose x mass fraction. An undisclosed blend raises
    ``composition_undisclosed``; nothing is computed for the rest of the mix.
    """
    from .engine import load_library
    from .materials import load_identities
    library = {str(item["name"]): item for item in load_library()["salts"]}
    resolved = _check_materials(doses, materials)
    units = []
    for name, dose in doses.items():
        if name not in library:
            raise DeliveryError("unknown_product", f"catalogue product {name!r} is not available")
        material = resolved.get(name)
        if material is None:
            parts = [(library[name], dose)]
        elif material.components:
            parts = [(_catalogue_product(identity_id, library), _finite_dose(dose) * fraction)
                     for identity_id, fraction in material.components]
        else:
            product_name = load_identities()[material.identity_id]['products'][0]
            parts = [({**material.record, 'name': product_name}, dose)]
        for product, amount in parts:
            converted = convert_catalogue_product_dose(product, amount)
            totals: dict = {}
            for source in (converted.totals, converted.counterions, converted.ligands):
                for key, value in source.items():
                    basis = 'Fe+2' if key == 'Fe' and product['name'] == 'Iron II Sulfate (Hepahydrate)' else _BASIS[key]
                    totals[basis] = totals.get(basis, 0.) + value
            units.append((name, converted.chemistry, totals))
    return units


_CHELATE_SODIUM_FAMILIES = ("edta_chelate", "dtpa_chelate", "eddha_chelate")
_NA_MG_PER_MOL = 22.98977 * 1000.0


def chelate_sodium_mg_per_l(salts_with_doses) -> float:
    """Chelate counterion sodium (D2) in mg/L for ``[(product record, g/L), ...]``.

    Doses in g/L are treated as g/kg water. Only the chelate counterion sodium of
    the EDTA, DTPA and EDDHA products and the chelate share of the CH - micro
    blend counts; borax and molybdate sodium are already elemental Na in the
    product assay. Records without catalogue chemistry contribute nothing.
    """
    moles = 0.0
    for product, dose in salts_with_doses:
        if dose <= 0:
            continue
        try:
            converted = convert_catalogue_product_dose(product, dose)
        except DeliveryError:
            continue
        family = converted.chemistry.family
        if family in _CHELATE_SODIUM_FAMILIES:
            moles += converted.counterions.get("sodium", 0.0)
        elif family == "edta_borax_molybdate_blend":
            t = converted.totals
            moles += t.get("Fe", 0.0) + 2 * sum(t.get(k, 0.0) for k in ("Mn", "Zn", "Cu"))
    return moles * _NA_MG_PER_MOL


def catalogue_dose_totals(doses: Mapping[str, float], *, materials=None):
    """Convert every assayed catalogue element into one conserved basis.

    Hydration water/inert carrier is outside mol/kg *water* totals. Iron sulfate
    retains Fe(II); declared iron chelates retain Fe(III). Urea stays neutral and
    unhydrolysed. Rounded product assays do not establish unassayed counterions.
    ``materials`` optionally maps dosed product names to ``ResolvedMaterial``
    (user grade or lot); see ``catalogue_dose_contributions``.
    """
    result = {}
    for _, _, totals in catalogue_dose_contributions(doses, materials=materials):
        for basis, amount in totals.items():
            result[basis] = result.get(basis, 0.) + amount
    return result


def solve_catalogue_product_doses(doses: Mapping[str, float], ph: float, *, water_totals=None, allow_precipitation=True):
    """Solve the actual catalogue doses and stated water through one model."""
    from .mixed_equilibrium import from_basis
    totals=dict(water_totals or {})
    for b,v in catalogue_dose_totals(doses).items():
        totals[b]=totals.get(b,0.)+v
    return from_basis(totals,ph,allow_precipitation=allow_precipitation)


def plan_catalogue_nitric_target(doses, initial_ph, target_ph, *, water_totals=None, phases=()):
    from .aqueous_model import nitric_target
    totals=dict(water_totals or {})
    for b,v in catalogue_dose_totals(doses).items():
        totals[b]=totals.get(b,0.)+v
    return nitric_target(totals,initial_ph,target_ph,phases=phases)
