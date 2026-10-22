"""Conversion of a stated catalogue dose into analytical equilibrium totals.

The conversion is deliberately a data boundary: the caller supplies a
``ProductChemistry`` profile, not a string which is interpreted by a solver.
The profile comes from what the material puts in the water (material_chemistry):
its formula, its ions, or its analysis. Catalogue products are pre-filled materials.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from .catalogue_chemistry import ProductChemistry, chemistry_for_product
from .delivery_contracts import DeliveryError
from .material_chemistry import chemistry_ions, material_chemistry, unstated_amounts

MOLAR_MASS = {"N": 14.0067, "P": 30.973762, "K": 39.0983, "Ca": 40.078,
              "Mg": 24.305, "S": 32.06, "Fe": 55.845, "Mn": 54.938044,
              "Zn": 65.38, "Cu": 63.546, "B": 10.81, "Mo": 95.95,
              "Na": 22.989769, "Cl": 35.45}

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

    Assays are elemental mass fractions. Counterions and ligands the assay does not
    state follow from the profile's ions (``unstated_amounts``): chelate ligands and
    D2 sodium, carbonate, citrate, a salt's missing counterion. Unassayed remainder
    is retained as inert carrier.
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
    # Assayed totals are authoritative; the ions fill only what the assay leaves out.
    # Hydroxide (potassium hydroxide) stays implicit, like the protons of the acids (#75).
    counterions, ligands = unstated_amounts(chemistry_ions(chemistry), totals)
    inert = max(0.0, 1.0 - sum(float(v) for v in assay.values()) / 100.0)
    return ProductAnalyticalTotals(chemistry, dose, totals, counterions, ligands, inert)

def convert_catalogue_product_dose(product: Mapping[str, object], dose_g_per_kg_water: float) -> ProductAnalyticalTotals:
    """Catalogue adapter (the ``PRODUCT_CHEMISTRY`` view). Any material: ``convert_material_dose``."""
    return convert_product_dose(product, chemistry_for_product(str(product.get("name", ""))), dose_g_per_kg_water)


def convert_material_dose(product: Mapping[str, object], dose_g_per_kg_water: float) -> ProductAnalyticalTotals:
    """Convert any material record through its own chemistry (``material_chemistry``)."""
    return convert_product_dose(product, material_chemistry(product), dose_g_per_kg_water)


_BASIS = {'Ca': 'Ca+2', 'Mg': 'Mg+2', 'K': 'K+', 'Na': 'Na+', 'sodium': 'Na+', 'Cl': 'Cl-',
          'Fe': 'Fe+3', 'Mn': 'Mn+2', 'Zn': 'Zn+2', 'Cu': 'Cu+2', 'boron': 'H3BO3',
          'molybdate': 'MoO4-2', 'phosphate': 'PO4-3', 'sulfate': 'SO4-2',
          'nitrate': 'NO3-', 'ammonium': 'NH4+', 'carbonate': 'CO3-2', 'urea': 'Ure',
          'EDTA': 'Edta-4', 'DTPA': 'Dtp-5', 'o,o-EDDHA': 'Edd-4', 'citrate': 'Citrate-3'}


# Declared-ions compounds (a data sheet, no catalogue identity): label form -> equilibrium basis.
_DECLARED_BASIS = {'N_NO3': 'NO3-', 'N_NH4': 'NH4+', 'N_UREA': 'Ure', 'P': 'PO4-3', 'S': 'SO4-2', 'B': 'H3BO3',
                   'Mo': 'MoO4-2', 'K': 'K+', 'Ca': 'Ca+2', 'Mg': 'Mg+2', 'Na': 'Na+', 'Cl': 'Cl-',
                   'Fe': 'Fe+3', 'Mn': 'Mn+2', 'Zn': 'Zn+2', 'Cu': 'Cu+2'}
_DECLARED_CHARGE = {'NO3-': -1, 'NH4+': 1, 'Ure': 0, 'PO4-3': -3, 'SO4-2': -2, 'H3BO3': 0, 'MoO4-2': -2,
                    'K+': 1, 'Ca+2': 2, 'Mg+2': 2, 'Na+': 1, 'Cl-': -1, 'Fe+3': 3, 'Mn+2': 2, 'Zn+2': 2,
                    'Cu+2': 2, 'Edta-4': -4, 'Dtp-5': -5, 'Edd-4': -4}
# D2 sodium salts: ligand basis and Na+ per chelated metal (NaFe(III)EDTA, Na2M(II)EDTA,
# Na2Fe(III)DTPA, NaFe(III)-o,o-EDDHA). DTPA and o,o-EDDHA are defined for iron only.
_DECLARED_CHELATES = {'EDTA': ('Edta-4', {'Fe': 1, 'Mn': 2, 'Zn': 2, 'Cu': 2}),
                      'DTPA': ('Dtp-5', {'Fe': 2}), 'o,o-EDDHA': ('Edd-4', {'Fe': 1})}


def declared_ion_totals(elements: Mapping[str, float], chelating_agent, dose_g_per_kg_water: float) -> dict:
    """Equilibrium basis (mol/kg water) of a declared-ions compound, from its elemental label.

    Totals follow the elemental basis as ``convert_product_dose`` does; urea counts per molecule.
    Chelated metals bring their ligand and D2 sodium counterions, unless the label states Na.
    Na, Cl and S the label does not state are zero; protons are implicit (charge balance).
    """
    dose = _finite_dose(dose_g_per_kg_water)
    totals: dict = {}
    for key, percent in elements.items():
        if key not in _DECLARED_BASIS:
            raise DeliveryError('unsupported_product_chemistry', f'no declared-ions basis for {key!r}')
        moles = dose * float(percent) / 100.0 / MOLAR_MASS[key.split('_')[0]]
        basis = _DECLARED_BASIS[key]
        totals[basis] = totals.get(basis, 0.0) + (moles / 2.0 if key == 'N_UREA' else moles)
    if chelating_agent is not None:
        ligand, sodium = _DECLARED_CHELATES[chelating_agent]
        chelated = {metal: totals.get(_DECLARED_BASIS[metal], 0.0) for metal in sodium}
        totals[ligand] = sum(chelated.values())
        if 'Na' not in elements:
            totals['Na+'] = sum(count * chelated[metal] for metal, count in sodium.items())
    return {basis: amount for basis, amount in totals.items() if amount}


def declared_ion_charges(elements: Mapping[str, float], chelating_agent) -> tuple:
    """(mol P, cation eq, anion eq without phosphate) per 100 g of a declared-ions compound."""
    totals = declared_ion_totals(elements, chelating_agent, 100.0)
    cations = sum(_DECLARED_CHARGE[b] * v for b, v in totals.items() if _DECLARED_CHARGE[b] > 0)
    anions = -sum(_DECLARED_CHARGE[b] * v for b, v in totals.items() if _DECLARED_CHARGE[b] < 0 and b != 'PO4-3')
    return totals.get('PO4-3', 0.0), cations, anions


def _declared_unit(name: str, material, dose: float):
    check = material.declared_check
    if not check.modellable:
        raise DeliveryError('ph_not_planned_for_product', f'pH cannot be planned with {name}: {check.reason}')
    totals = declared_ion_totals(material.record['elements'], material.chelating_agent, dose)
    chemistry = ProductChemistry(name, 'declared_ions', tuple(sorted(totals)), 'supplier data sheet (declared ions)')
    return name, chemistry, totals


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


def _named(products) -> dict:
    """Product records by name, from a mapping or a sequence of records."""
    if products is None:
        return {}
    records = products.values() if isinstance(products, Mapping) else products
    named = {}
    for record in records:
        if not isinstance(record, Mapping) or not isinstance(record.get('name'), str):
            raise DeliveryError('invalid_type', 'products must be material records with a name')
        named[record['name']] = record
    return named


def _catalogue_product(identity_id: str, library: Mapping[str, Mapping]) -> Mapping:
    """The catalogue product an identity covers, as shipped (grade-free)."""
    from .materials import load_identities
    return library[load_identities()[identity_id]['products'][0]]


def catalogue_dose_contributions(doses: Mapping[str, float], *, materials=None, products=None):
    """Per conversion unit: (dosed product name, ProductChemistry, {basis: mol/kg water}).

    Each dosed name is a material record: from ``products`` (records, or a mapping of name to
    record), else the catalogue's pre-filled record of that name. Its chemistry is what it
    puts in the water (``material_chemistry``), never its name. A product in ``materials`` is
    converted from its resolved record through its identity's ions. A disclosed blend
    contributes one unit per component identity: that identity's shipped catalogue record,
    at dose x mass fraction. A declared-ions compound is converted from its label
    (``declared_ion_totals``); one that cannot be modelled raises ``ph_not_planned_for_product``.
    An undisclosed blend raises ``composition_undisclosed``; nothing is computed for the rest.
    """
    from .engine import load_library
    catalogue = {str(item["name"]): item for item in load_library()["salts"]}
    library = {**catalogue, **_named(products)}
    resolved = _check_materials(doses, materials)
    units = []
    for name, dose in doses.items():
        material = resolved.get(name)
        if material is not None and material.composition == 'declared_ions':
            units.append(_declared_unit(name, material, dose))
            continue
        if name not in library:
            raise DeliveryError("unknown_product", f"product {name!r} is not available")
        if material is None:
            parts = [(library[name], dose, None)]
        elif material.components:
            parts = [(_catalogue_product(identity_id, catalogue), _finite_dose(dose) * fraction, None)
                     for identity_id, fraction in material.components]
        else:
            parts = [(material.record, dose, material.identity_id)]
        for product, amount, identity_id in parts:
            # A resolved grade or lot takes its identity's ions; its analysis was checked when graded.
            chemistry = (material_chemistry({**product, 'identityId': identity_id}, check=False)
                         if identity_id else material_chemistry(product))
            converted = convert_product_dose(product, chemistry, amount)
            ferrous = 'Fe+2' in chemistry_ions(chemistry)
            totals: dict = {}
            for source in (converted.totals, converted.counterions, converted.ligands):
                for key, value in source.items():
                    basis = 'Fe+2' if key == 'Fe' and ferrous else _BASIS[key]
                    totals[basis] = totals.get(basis, 0.) + value
            units.append((name, converted.chemistry, totals))
    return units


_NA_MG_PER_MOL = 22.98977 * 1000.0


def counterion_sodium_mg_per_l(salts_with_doses) -> float:
    """Formula counterion sodium in mg/L for ``[(product record, g/L), ...]``.

    Doses in g/L are treated as g/kg water. Sums the counterion sodium that
    ``convert_catalogue_product_dose`` reports for every dosed product: the chelate
    sodium (D2) of the EDTA, DTPA and EDDHA products and all of CH - micro's
    sodium (chelate share plus its borax and molybdate), and the chelate sodium of a
    declared-ions compound (``declared_ion_totals``). Sodium already assayed as
    elemental Na (standalone borax, sodium molybdate) is not a counterion there and
    contributes nothing. Every record is read through ``material_chemistry``; one that
    does not define its chemistry contributes nothing.
    """
    moles = 0.0
    for product, dose in salts_with_doses:
        if dose <= 0:
            continue
        grade = product.get('grade')
        if isinstance(grade, Mapping) and grade.get('composition') == 'declared_ions':
            # A data-sheet compound: its D2 chelate sodium, as its chemistry counts it; stated Na is elemental.
            if 'Na' not in product['elements']:
                moles += declared_ion_totals(product['elements'], grade.get('chelating_agent'), dose).get('Na+', 0.0)
            continue
        try:
            converted = convert_product_dose(product, material_chemistry(product, check=False), dose)
        except DeliveryError:
            continue
        moles += converted.counterions.get("sodium", 0.0)
    return moles * _NA_MG_PER_MOL


def catalogue_dose_totals(doses: Mapping[str, float], *, materials=None, products=None):
    """Convert every assayed catalogue element into one conserved basis.

    Hydration water/inert carrier is outside mol/kg *water* totals. Iron sulfate
    retains Fe(II); declared iron chelates retain Fe(III). Urea stays neutral and
    unhydrolysed. Rounded product assays do not establish unassayed counterions.
    ``materials`` optionally maps dosed product names to ``ResolvedMaterial``
    (user grade or lot); ``products`` supplies material records by name, for
    materials the catalogue does not hold; see ``catalogue_dose_contributions``.
    """
    result = {}
    for _, _, totals in catalogue_dose_contributions(doses, materials=materials, products=products):
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
