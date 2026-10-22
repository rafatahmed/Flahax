"""A material is what it puts in the water: its dissolved ions.

A compound has a fixed structure, so its formula or its stated ions define it (MKP is
KH2PO4, Fe-EDTA is Na+ and the Fe(III)-EDTA complex). A blend has none, so its analysis by
nutrient form defines it (a declared-ions grade, materials.py). The catalogue's products are
pre-filled materials: their ions are their identities' ``ion_forms``. Nothing here reads a
product name (owner decision 2026-10-22).
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from functools import lru_cache

from .catalogue_chemistry import PHREEQC_MINTEQ_V4, ProductChemistry
from .composition import parse_formula
from .delivery_contracts import DeliveryError
from .materials import _CHARGE_RESIDUAL_LIMIT_PERCENT

UNDEFINED = 'give its formula, its ions, or its analysis by nutrient form'

# Fertilizer ions: atoms, charge, and the nutrient form (assay key) each carries one atom of.
ION_TABLE = {
    'NH4+': ({'N': 1, 'H': 4}, 1, 'N_NH4'), 'K+': ({'K': 1}, 1, 'K'), 'Na+': ({'Na': 1}, 1, 'Na'),
    'Ca+2': ({'Ca': 1}, 2, 'Ca'), 'Mg+2': ({'Mg': 1}, 2, 'Mg'), 'Fe+2': ({'Fe': 1}, 2, 'Fe'),
    'Fe+3': ({'Fe': 1}, 3, 'Fe'), 'Mn+2': ({'Mn': 1}, 2, 'Mn'), 'Zn+2': ({'Zn': 1}, 2, 'Zn'),
    'Cu+2': ({'Cu': 1}, 2, 'Cu'),
    'NO3-': ({'N': 1, 'O': 3}, -1, 'N_NO3'), 'H2PO4-': ({'H': 2, 'P': 1, 'O': 4}, -1, 'P'),
    'HPO4-2': ({'H': 1, 'P': 1, 'O': 4}, -2, 'P'), 'PO4-3': ({'P': 1, 'O': 4}, -3, 'P'),
    'SO4-2': ({'S': 1, 'O': 4}, -2, 'S'), 'Cl-': ({'Cl': 1}, -1, 'Cl'),
    'CO3-2': ({'C': 1, 'O': 3}, -2, None), 'HCO3-': ({'H': 1, 'C': 1, 'O': 3}, -1, None),
    'OH-': ({'O': 1, 'H': 1}, -1, None), 'MoO4-2': ({'Mo': 1, 'O': 4}, -2, 'Mo'),
    'B(OH)4-': ({'B': 1, 'O': 4, 'H': 4}, -1, 'B'), 'B(OH)3': ({'B': 1, 'O': 3, 'H': 3}, 0, 'B'),
    'H3PO4': ({'H': 3, 'P': 1, 'O': 4}, 0, 'P'), 'CO(NH2)2': ({'C': 1, 'O': 1, 'N': 2, 'H': 4}, 0, 'N_UREA'),
    'citrate': ({'C': 6, 'H': 5, 'O': 7}, -3, None),
}
# Chelating ligands, fully deprotonated, as a formula carries them.
LIGANDS = {'EDTA': ({'C': 10, 'H': 12, 'N': 2, 'O': 8}, -4), 'DTPA': ({'C': 14, 'H': 18, 'N': 3, 'O': 10}, -5),
           'o,o-EDDHA': ({'C': 18, 'H': 16, 'N': 2, 'O': 6}, -4)}
# Chelate complexes: agent, chelated metal, charge. D2: DTPA and o,o-EDDHA are defined for iron only.
COMPLEXES = {'Fe(III)-EDTA': ('EDTA', 'Fe', -1), 'Mn-EDTA': ('EDTA', 'Mn', -2), 'Zn-EDTA': ('EDTA', 'Zn', -2),
             'Cu-EDTA': ('EDTA', 'Cu', -2), 'Fe(III)-DTPA': ('DTPA', 'Fe', -2),
             'Fe(III)-o,o-EDDHA': ('o,o-EDDHA', 'Fe', -1)}
_CHELATED = {('EDTA', 'Fe+3'): 'Fe(III)-EDTA', ('EDTA', 'Mn+2'): 'Mn-EDTA', ('EDTA', 'Zn+2'): 'Zn-EDTA',
             ('EDTA', 'Cu+2'): 'Cu-EDTA', ('DTPA', 'Fe+3'): 'Fe(III)-DTPA',
             ('o,o-EDDHA', 'Fe+3'): 'Fe(III)-o,o-EDDHA'}
# Charge per nutrient atom, for the charge-residual check (materials._charge_residual_percent).
NUTRIENT_CHARGES = {**{ion: (n, z) for ion, (_, z, n) in ION_TABLE.items() if n},
                    **{ion: (metal, z) for ion, (_, metal, z) in COMPLEXES.items()}}
# Converted-totals key of each nutrient form (product_conversion.convert_product_dose).
_TOTALS_KEY = {'N_NO3': 'nitrate', 'N_NH4': 'ammonium', 'N_UREA': 'urea', 'P': 'phosphate', 'S': 'sulfate',
               'B': 'boron', 'Mo': 'molybdate'}
# Ions without a nutrient of their own, when the analysis leaves them to the charge balance.
_UNSTATED_KEY = {'Na+': 'sodium', 'CO3-2': 'carbonate', 'HCO3-': 'carbonate', 'citrate': 'citrate'}
_LIGAND_IONS = frozenset({'citrate'})
# Hydroxide is the proton deficit the charge balance closes, as the implicit protons of acids are (#75).
_IMPLICIT = frozenset({'OH-'})
_MICRO_CATIONS = frozenset({'Fe+2', 'Fe+3', 'Mn+2', 'Zn+2', 'Cu+2'})
_CHELATE_FAMILY = {'EDTA': 'edta_chelate', 'DTPA': 'dtpa_chelate', 'o,o-EDDHA': 'eddha_chelate'}
# A chelate blend names the sodium salts beside its complexes (D2: borax, sodium molybdate).
_BLEND_SALTS = {'B(OH)4-': ('borax', 'borax'), 'MoO4-2': ('molybdate', 'sodium molybdate')}
_AGENT_SOURCE = {'DTPA': 'Martell/Smith stability profile; Fe(III)-DTPA log beta 28.6 at 25 C',
                 'o,o-EDDHA': 'Yunta et al. 2003 o,o-EDDHA profile; Fe(III) log beta 35.1 at 25 C'}
_UREA_SOURCE = 'analytical urea; hydrolysis is kinetic and excluded from 25 C instantaneous equilibrium'
_BALANCE_TOLERANCE = 1e-6


def _charge(ion: str) -> float:
    return COMPLEXES[ion][2] if ion in COMPLEXES else ION_TABLE[ion][1]


def chelate(ions: Mapping, agent: str) -> dict:
    """Ions with every metal ``agent`` chelates replaced by its complex, in place."""
    if agent not in LIGANDS:
        raise DeliveryError('invalid_value', f'chelating agent must be one of {list(LIGANDS)}')
    if not any((agent, ion) in _CHELATED or COMPLEXES.get(ion, ('',))[0] == agent for ion in ions):
        raise DeliveryError('invalid_composition', f'no metal in {list(ions)} is chelated by {agent}')
    return {_CHELATED.get((agent, ion), ion): count for ion, count in ions.items()}


def _pair_ligands(ions: dict) -> dict | None:
    """A formula's ligands bound to its metals (one metal per ligand); None if they do not pair."""
    for agent in LIGANDS:
        ligands = ions.pop(agent, 0)
        if not ligands:
            continue
        if sum(count for ion, count in ions.items() if (agent, ion) in _CHELATED) != ligands:
            return None
        ions = chelate(ions, agent)
    return ions


def _decompose(atoms: dict) -> list[dict]:
    """Every way to write ``atoms`` as table ions, ligands and water with zero net charge."""
    pool = [(ion, need, z) for ion, (need, z, _) in ION_TABLE.items()]
    pool += [(agent, need, z) for agent, (need, z) in LIGANDS.items()]
    candidates = [c for c in pool if set(c[1]) <= set(atoms)] + [('H2O', {'H': 2, 'O': 1}, 0)]
    covered = [set().union(*(set(c[1]) for c in candidates[i:])) for i in range(len(candidates))] + [set()]
    found: list[dict] = []

    def search(i, remaining, charge, chosen):
        if any(n and e not in covered[i] for e, n in remaining.items()):
            return
        if i == len(candidates):
            if charge == 0:
                found.append(dict(chosen))
            return
        ion, need, z = candidates[i]
        for n in range(min(remaining.get(e, 0) // k for e, k in need.items()), -1, -1):
            if n:
                chosen[ion] = n
            search(i + 1, {e: v - n * need.get(e, 0) for e, v in remaining.items()}, charge + n * z, chosen)
            chosen.pop(ion, None)

    search(0, dict(atoms), 0, {})
    return found


@lru_cache(maxsize=256)
def _formula_ions(text: str) -> tuple | None:
    parsed = parse_formula(text.replace('·', '.'))
    if parsed is None or not all(float(n).is_integer() for n in parsed['atoms'].values()):
        return None
    solutions = _decompose({e: int(n) for e, n in parsed['atoms'].items()})
    if not solutions:
        return None
    # Hydroxide only where nothing else balances (KOH), not borax as 2 NaOH + 4 H3BO3.
    fewest = min(s.get('OH-', 0) for s in solutions)
    solutions = [s for s in solutions if s.get('OH-', 0) == fewest]
    ions = [{k: v for k, v in s.items() if k != 'H2O'} for s in solutions]
    if any(i != ions[0] for i in ions):
        return None
    paired = _pair_ligands(ions[0])
    return tuple(paired.items()) if paired else None


def ions_from_formula(formula) -> dict | None:
    """Ions per formula unit of a compound's formula (hydrate water dropped), or None.

    None when the text is not a formula, or cannot be written as fertilizer ions in one way.
    """
    if not isinstance(formula, str) or not formula.strip():
        return None
    ions = _formula_ions(formula.strip())
    return dict(ions) if ions is not None else None


def _checked_ions(name: str, ions, agent: str | None = None) -> dict:
    """Known ions with positive counts (metals of ``agent`` chelated) that balance."""
    if not isinstance(ions, Mapping) or not ions:
        raise DeliveryError('invalid_composition', f'{name}: ions must map ion to count per formula unit')
    for ion, count in ions.items():
        if ion not in ION_TABLE and ion not in COMPLEXES:
            raise DeliveryError('invalid_composition', f'{name}: unknown ion {ion!r} (known: '
                                f'{", ".join([*ION_TABLE, *COMPLEXES])})')
        if isinstance(count, bool) or not isinstance(count, (int, float)) or not math.isfinite(count) or count <= 0:
            raise DeliveryError('invalid_composition', f'{name}: {ion} count must be a positive number')
    if agent is not None:
        ions = chelate(ions, agent)
    net = sum(_charge(ion) * count for ion, count in ions.items())
    if abs(net) > _BALANCE_TOLERANCE * sum(abs(_charge(ion)) * count for ion, count in ions.items()):
        raise DeliveryError('invalid_composition', f'{name}: its ions do not balance (net charge {net:+g})')
    return dict(ions)


def _profile(name: str, ions: dict, status: str | None) -> ProductChemistry:
    """Family, components and source profile, read from the ions."""
    complexes = [ion for ion in ions if ion in COMPLEXES]
    agents = list(dict.fromkeys(COMPLEXES[ion][0] for ion in complexes))
    if complexes:
        others = [ion for ion in ions if ion not in COMPLEXES and ion != 'Na+' and ion != 'B(OH)3']
        if others or len(agents) > 1:
            parts = [_BLEND_SALTS.get(ion, (ion, ion)) for ion in others]
            family = '_'.join([*(a.replace('o,o-', '').lower() for a in agents), *(p[0] for p in parts), 'blend'])
            components = (*complexes, *(p[1] for p in parts))
        else:
            family, components = _CHELATE_FAMILY[agents[0]], tuple(ions)
    else:
        components = tuple(ions)
        if 'CO(NH2)2' in ions:
            family = 'neutral_urea'
        elif 'citrate' in ions:
            family = 'citrate_salt'
        elif 'H3PO4' in ions:
            family = 'macro_acid'
        elif 'OH-' in ions:
            family = 'strong_base'
        elif 'B(OH)3' in ions or 'B(OH)4-' in ions:
            family = 'boron'
        elif 'MoO4-2' in ions:
            family = 'molybdate'
        elif 'SO4-2' in ions and _MICRO_CATIONS & set(ions):
            family = 'free_metal_sulfate'
        else:
            family = 'macro_salt'
    source = next((_AGENT_SOURCE[a] for a in agents if a in _AGENT_SOURCE), None)
    if source is None:
        source = (_UREA_SOURCE if 'CO(NH2)2' in ions else
                  f'project-declared composition of {name}; {PHREEQC_MINTEQ_V4}' if status == 'assumed_blend' else
                  PHREEQC_MINTEQ_V4)
    return ProductChemistry(name, family, components, source, ions=tuple(ions.items()))


def _check_analysis(name: str, ions: dict, elements) -> None:
    """One rule for every material: its analysis agrees with its ions."""
    from .materials import _charge_residual_percent  # deferred: materials imports product_conversion lazily
    if not isinstance(elements, Mapping):
        return
    carried = {NUTRIENT_CHARGES[ion][0] for ion in ions if ion in NUTRIENT_CHARGES}
    carried |= {ION_TABLE[ion][2] for ion in ions if ion in ION_TABLE and ION_TABLE[ion][2]}
    foreign = [key for key, value in elements.items() if value and key not in carried]
    if foreign:
        raise DeliveryError('identity_inconsistent', f'{name}: the analysis states {", ".join(foreign)}, '
                            f'which its ions ({", ".join(ions)}) do not carry')
    residual = _charge_residual_percent({'ion_forms': ions}, dict(elements), NUTRIENT_CHARGES)
    if residual is not None and abs(residual) > _CHARGE_RESIDUAL_LIMIT_PERCENT:
        raise DeliveryError('identity_inconsistent', f'{name}: the analysis does not fit its ions '
                            f'(charge residual {residual:.2f} %, limit {_CHARGE_RESIDUAL_LIMIT_PERCENT:g} %)')
    stated = set(elements)
    unstated = [ion for ion in ions if _unstated(ion, stated)]
    if len(unstated) > 1:
        raise DeliveryError('material_undefined', f'{name}: the analysis must state all but one of its charged '
                            f'ions; {", ".join(unstated)} are not stated')


def _unstated(ion: str, stated) -> bool:
    if ion in COMPLEXES or ion in _IMPLICIT or ION_TABLE[ion][1] == 0:
        return False
    return ION_TABLE[ion][2] is None or ION_TABLE[ion][2] not in stated


@lru_cache(maxsize=1024)
def _resolve(key: str) -> ProductChemistry:
    name, ions, agent, identity_id, formula, elements = json.loads(key)
    status = None
    if ions is not None:
        ions = _checked_ions(name, ions, agent)
    elif identity_id is not None:
        from .materials import load_identities
        identity = load_identities().get(identity_id)
        if identity is None:
            raise DeliveryError('unknown_identity', f'{name}: unknown identity {identity_id!r}')
        ions, status = _checked_ions(name, identity['ion_forms']), identity['status']
    else:
        ions = ions_from_formula(formula)
        if ions is None:
            raise DeliveryError('material_undefined', f'{name}: {UNDEFINED}')
        ions = _checked_ions(name, ions)
    _check_analysis(name, ions, elements)
    return _profile(name, ions, status)


def _declared(name: str, record: Mapping, grade: Mapping) -> ProductChemistry:
    """A blend defined by its analysis: the declared-ions path (interactive mix Task 4)."""
    from .materials import declared_ions_check, make_grade
    from .product_conversion import declared_ion_totals
    made = make_grade(grade)
    check = declared_ions_check(made)
    if not check.modellable:
        raise DeliveryError('ph_not_planned_for_product', f'pH cannot be planned with {name}: {check.reason}')
    totals = declared_ion_totals(record['elements'], made.chelating_agent, 100.0)
    return ProductChemistry(name, 'declared_ions', tuple(sorted(totals)), 'supplier data sheet (declared ions)')


def material_chemistry(record: Mapping, *, check: bool = True) -> ProductChemistry:
    """The chemistry of a material record, from what it puts in the water.

    In order: (1) a ``declared_ions`` grade: its analysis (Task 4); (2) ``ions``, a mapping of
    ion to count per formula unit (e.g. ``{"K+": 1, "H2PO4-": 1}``), with an optional
    ``chelating_agent`` that turns its metals into their complexes; (2b) the ``ion_forms`` of
    its identity (``identityId``, or a single grade's ``identity_id``): the catalogue's data;
    (3) ``formula``, parsed into fertilizer ions plus hydrate water; otherwise
    ``material_undefined``. With ``check``, the ``elements`` of a record that is not a grade
    must fit its ions (the grade's own analysis is checked by ``make_grade``).
    """
    if not isinstance(record, Mapping):
        raise DeliveryError('invalid_type', 'a material must be a mapping')
    name = record.get('name')
    if not isinstance(name, str) or not name.strip():
        raise DeliveryError('missing_field', 'a material needs a name')
    grade = record.get('grade')
    if isinstance(grade, Mapping) and grade.get('composition') == 'declared_ions':
        return _declared(name, record, grade)
    identity_id = (grade.get('identity_id') if isinstance(grade, Mapping) else None) or record.get('identityId')
    elements = record.get('elements') if check and grade is None else None
    try:
        key = json.dumps([name, record.get('ions'), record.get('chelating_agent'), identity_id,
                          record.get('formula'), elements])
    except (TypeError, ValueError) as exc:
        raise DeliveryError('invalid_value', f'{name}: material fields must be plain data') from exc
    return _resolve(key)


def chemistry_ions(chemistry: ProductChemistry) -> dict:
    """A chemistry profile's ions; a profile built without them falls back to its components."""
    if chemistry.ions:
        return dict(chemistry.ions)
    components = (chemistry.components,) if isinstance(chemistry.components, str) else chemistry.components
    unknown = [c for c in components if c not in ION_TABLE and c not in COMPLEXES]
    if unknown:
        raise DeliveryError('unsupported_product_chemistry', f'{chemistry.name}: no ions for {unknown}')
    return {c: 1 for c in components}


def unstated_amounts(ions: Mapping, totals: Mapping) -> tuple[dict, dict]:
    """(counterions, ligands) in mol/kg water that the analysis leaves to the ions.

    ``totals`` are the stated amounts by converted key (convert_product_dose). A complex
    brings its ligand, one per chelated metal. The one charged ion the analysis does not
    state closes the charge balance; chelated metals are summed per complex charge first,
    then the other ions follow in order. Hydroxide stays implicit, like an acid's protons.
    """
    ligands: dict = {}
    by_charge: dict = {}
    for ion in ions:
        if ion in COMPLEXES:
            agent, metal, z = COMPLEXES[ion]
            ligands[agent] = ligands.get(agent, 0.0) + totals.get(metal, 0.0)
            if metal in totals:
                by_charge.setdefault(z, []).append(totals[metal])
    stated = {nutrient for nutrient in {*_TOTALS_KEY, *(v[2] for v in ION_TABLE.values() if v[2])}
              if _TOTALS_KEY.get(nutrient, nutrient) in totals}
    unstated = [ion for ion in ions if _unstated(ion, stated)]
    counterions: dict = {}
    if not unstated:
        return counterions, ligands
    if len(unstated) > 1:
        raise DeliveryError('material_undefined', f'the analysis must state all but one of the charged ions; '
                            f'{", ".join(unstated)} are not stated')
    charge = sum(z * sum(amounts) for z, amounts in by_charge.items())
    shares: dict = {}
    for ion, count in ions.items():
        if ion in ION_TABLE and ION_TABLE[ion][2]:
            shares[ION_TABLE[ion][2]] = shares.get(ION_TABLE[ion][2], 0) + count
    for ion, count in ions.items():
        if ion in COMPLEXES or ion in unstated or ion in _IMPLICIT or ION_TABLE[ion][1] == 0:
            continue
        nutrient = ION_TABLE[ion][2]
        charge += (ION_TABLE[ion][1] * (count / shares[nutrient])) * totals[_TOTALS_KEY.get(nutrient, nutrient)]
    ion = unstated[0]
    nutrient = ION_TABLE[ion][2]
    target = ligands if ion in _LIGAND_IONS else counterions
    target[_UNSTATED_KEY.get(ion) or _TOTALS_KEY.get(nutrient, nutrient)] = -charge / ION_TABLE[ion][1]
    return counterions, ligands
