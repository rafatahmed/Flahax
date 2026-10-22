"""Traceable material catalogue: the shipped chemical-identity layer.

An identity is what a material *is* (formula, hydration, molecular weight,
CAS, dissolved ion forms, theoretical analysis), with the reference material
that evidences it. It is not a supplier grade or a batch lot. Evidence:
docs/audit/2026-10-18-materials-identity; owner decisions D1 (Mg nitrate
hexahydrate) and D2 (chelates as their sodium salts).

Records are shipped in data/material_identities.json, pinned by SHA-256.
The loader fails closed if a record is malformed or if a stored theoretical
analysis disagrees with composition.theoretical_assay for a parseable formula.
"""
import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import date
from functools import lru_cache
from importlib.resources import files
from typing import Any

from .composition import ATOMIC, theoretical_assay
from .delivery_contracts import DeliveryError

_RESOURCE = 'data/material_identities.json'
_RAW = files('flahax').joinpath(_RESOURCE).read_bytes()
IDENTITIES_SHA256 = hashlib.sha256(_RAW).hexdigest()

IDENTITY_STATUSES = frozenset({'identity_consistent', 'chelate_salt_defined', 'commercial_double_salt',
                               'aqueous_solution', 'assumed_blend'})
_REQUIRED = ('id', 'products', 'name', 'formula', 'hydration', 'molecular_weight', 'cas',
             'ion_forms', 'theoretical_analysis', 'comparator', 'status', 'notes')
_THEORY_TOLERANCE = 1e-9


def _invalid(identity_id: str, message: str) -> None:
    raise DeliveryError('invalid_identity_record', f'{identity_id}: {message}')


def _check(record: dict) -> None:
    identity_id = str(record.get('id'))
    missing = [key for key in _REQUIRED if key not in record]
    if missing:
        _invalid(identity_id, f'missing keys {missing}')
    if not identity_id.startswith('idn-'):
        _invalid(identity_id, "id must start with 'idn-'")
    if record['status'] not in IDENTITY_STATUSES:
        _invalid(identity_id, f"unknown status {record['status']!r}")
    if not record['products'] or not all(isinstance(p, str) and p for p in record['products']):
        _invalid(identity_id, 'products must be a non-empty list of names')
    if not isinstance(record['ion_forms'], dict) or not record['ion_forms']:
        _invalid(identity_id, 'ion_forms must be a non-empty mapping')
    for value in record['ion_forms'].values():
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            _invalid(identity_id, 'ion_forms stoichiometry must be positive numbers')
    if set(record['comparator']) != {'product', 'url', 'accessed'}:
        _invalid(identity_id, 'comparator needs product, url, accessed')
    formula = record['formula']
    computed = theoretical_assay(formula) if formula else None
    if computed:
        stored = record['theoretical_analysis']
        if set(stored) != set(computed) or any(abs(stored[k] - computed[k]) > _THEORY_TOLERANCE for k in computed):
            _invalid(identity_id, 'theoretical_analysis disagrees with composition.theoretical_assay')


@lru_cache(maxsize=1)
def _load() -> tuple[dict, dict]:
    records = json.loads(_RAW.decode('utf-8'))['identities']
    identities, by_product = {}, {}
    for record in records:
        _check(record)
        if record['id'] in identities:
            _invalid(record['id'], 'duplicate id')
        identities[record['id']] = record
        for product in record['products']:
            if product in by_product:
                _invalid(record['id'], f'product {product!r} already mapped to {by_product[product]}')
            by_product[product] = record['id']
    return identities, by_product


def load_identities() -> dict:
    """Return the cached identity records keyed by id (treat as read-only)."""
    return _load()[0]


def identity_for_product(name: str) -> dict:
    """Return the identity record of a catalogue product name, or fail closed."""
    identities, by_product = _load()
    try:
        return identities[by_product[name]]
    except KeyError as exc:
        raise DeliveryError('unknown_product', f'no identity record for {name!r}') from exc


# --- Grades (technical data sheets) and lots (certificates of analysis) ---------------------

NUTRIENT_FORMS = ('N_NO3', 'N_NH4', 'N_UREA', 'P', 'K', 'Ca', 'Mg', 'S',
                  'Fe', 'Mn', 'Zn', 'Cu', 'B', 'Mo', 'Na')


def _oxide_factor(element: str, count: int, oxygens: int) -> float:
    mass = count * ATOMIC[element]
    return mass / (mass + oxygens * ATOMIC['O'])


# Oxide -> (element, factor); elemental % = oxide % x factor, from composition.ATOMIC.
OXIDE_FACTORS = {
    'P2O5': ('P', _oxide_factor('P', 2, 5)),
    'K2O': ('K', _oxide_factor('K', 2, 1)),
    'CaO': ('Ca', _oxide_factor('Ca', 1, 1)),
    'MgO': ('Mg', _oxide_factor('Mg', 1, 1)),
    'SO3': ('S', _oxide_factor('S', 1, 3)),
}
COMPOSITIONS = frozenset({'single', 'disclosed', 'undisclosed', 'declared_ions'})
CHELATING_AGENTS = ('EDTA', 'DTPA', 'o,o-EDDHA', None)
N_FORMS = ('N_NO3', 'N_NH4', 'N_UREA')
_BANDS = ('typical', 'minimum', 'maximum')
_CHARGE_RESIDUAL_LIMIT_PERCENT = 0.1
# Theory is the pure compound, not the commercial solution or the chelate product as sold,
# so a grade range of these identities is not compared with it (the charge test still applies).
_RANGE_TEST_EXEMPT = frozenset({'aqueous_solution', 'chelate_salt_defined'})
# Disclosed blend: declared vs component-implied analysis, relative and absolute (% points).
_BLEND_RELATIVE_TOLERANCE = 0.05
_BLEND_ABSOLUTE_TOLERANCE = 0.05
_FRACTION_TOLERANCE = 1e-9

# Dissolved ion form -> (nutrient form it carries, charge per nutrient atom). Each listed
# form carries one atom of its nutrient. Forms without a nutrient (CO3-2, citrate) are absent.
_ION_NUTRIENT_CHARGE = {
    'NO3-': ('N_NO3', -1), 'NH4+': ('N_NH4', 1), 'CO(NH2)2': ('N_UREA', 0),
    'K+': ('K', 1), 'Na+': ('Na', 1), 'Ca+2': ('Ca', 2), 'Mg+2': ('Mg', 2),
    'Fe+2': ('Fe', 2), 'Cu+2': ('Cu', 2), 'Zn+2': ('Zn', 2),
    'SO4-2': ('S', -2), 'H2PO4-': ('P', -1), 'HPO4-2': ('P', -2), 'H3PO4': ('P', 0),
    'MoO4-2': ('Mo', -2), 'B(OH)4-': ('B', -1), 'B(OH)3': ('B', 0),
    'Fe(III)-EDTA': ('Fe', -1), 'Mn-EDTA': ('Mn', -2), 'Zn-EDTA': ('Zn', -2), 'Cu-EDTA': ('Cu', -2),
    'Fe(III)-DTPA': ('Fe', -2), 'Fe(III)-o,o-EDDHA': ('Fe', -1),
}


@dataclass(frozen=True)
class DocumentReference:
    supplier: str
    title: str
    issued: str
    entered: str
    url: str | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class Grade:
    grade_id: str
    identity_id: str | None
    supplier: str
    product: str
    typical: dict
    minimum: dict
    maximum: dict
    impurity_limits: dict
    composition: str
    components: tuple
    oxide_conversions: dict
    document: DocumentReference
    flags: tuple = ()
    form_split: dict = field(default_factory=dict)
    charge_residual_percent: float | None = None
    chelating_agent: str | None = None
    chelating_agent_stated: bool = False


@dataclass(frozen=True)
class DeclaredCheck:
    modellable: bool
    protons_per_phosphate: float | None
    residual_percent: float | None
    reason: str | None


@dataclass(frozen=True)
class Lot:
    lot_id: str
    grade_id: str | None
    identity_id: str | None
    measured: dict
    uncertainty: dict
    document: DocumentReference
    oxide_conversions: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedMaterial:
    name: str
    identity_id: str
    record: dict
    basis: dict
    band_minimum: dict
    band_maximum: dict
    composition: str
    provenance: dict
    flags: tuple = ()
    components: tuple = ()  # disclosed blend: (identity_id, mass_fraction) pairs
    chelating_agent: str | None = None  # declared_ions compound only
    declared_check: DeclaredCheck | None = None  # declared_ions compound only


def _text(record: Mapping, key: str, label: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DeliveryError('invalid_value', f'{label}: {key} must be a non-empty string')
    return value


def _number(value: Any, label: str, *, ceiling: float | None = 100.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DeliveryError('invalid_value', f'{label}: {value!r} is not a number')
    number = float(value)
    if not math.isfinite(number) or number < 0 or (ceiling is not None and number > ceiling):
        bound = f'within 0..{ceiling:g} %' if ceiling is not None else 'finite and non-negative'
        raise DeliveryError('invalid_value', f'{label}: {value!r} must be {bound}')
    return number


def _document(record: Mapping, label: str) -> DocumentReference:
    raw = record.get('document')
    if not isinstance(raw, Mapping):
        raise DeliveryError('missing_document_reference', f'{label}: a document reference is required')
    for key in ('supplier', 'title', 'issued', 'entered'):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise DeliveryError('missing_document_reference', f'{label}: document needs {key}')
    for key in ('issued', 'entered'):
        try:
            date.fromisoformat(raw[key])
        except ValueError as exc:
            raise DeliveryError('invalid_value', f'{label}: document {key} must be an ISO date') from exc
    for key in ('url', 'sha256'):
        if raw.get(key) is not None and not isinstance(raw[key], str):
            raise DeliveryError('invalid_value', f'{label}: document {key} must be a string')
    sha = raw.get('sha256')
    if sha is not None and (len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha.lower())):
        raise DeliveryError('invalid_value', f'{label}: document sha256 must be 64 hex characters')
    return DocumentReference(supplier=raw['supplier'], title=raw['title'], issued=raw['issued'],
                             entered=raw['entered'], url=raw.get('url'), sha256=sha)


def _nutrient_key(key: Any, label: str, conversions: dict) -> tuple[str, float]:
    """Map an analysis key to its elemental form and the factor that converts its value."""
    if key in OXIDE_FACTORS:
        element, factor = OXIDE_FACTORS[key]
        conversions[key] = {'element': element, 'factor': factor}
        return element, factor
    if key in NUTRIENT_FORMS:
        return key, 1.0
    raise DeliveryError('invalid_value', f'{label}: unknown analysis key {key!r}')


def _elemental(values: Any, label: str, conversions: dict) -> dict:
    """Validate a nutrient -> % mapping, converting oxide keys to elemental forms."""
    if not isinstance(values, Mapping):
        raise DeliveryError('invalid_value', f'{label}: expected a mapping of nutrient to %')
    out = {}
    for key, raw in values.items():
        element, factor = _nutrient_key(key, label, conversions)
        if element in out:
            raise DeliveryError('invalid_value', f'{label}: {element} stated twice (elemental and oxide)')
        out[element] = _number(raw, f'{label} {key}') * factor
    return out


def _known_identity(identity_id: Any, label: str) -> str:
    if not isinstance(identity_id, str) or identity_id not in load_identities():
        raise DeliveryError('unknown_identity', f'{label}: unknown identity {identity_id!r}')
    return identity_id


def _components(raw: Any, composition: str, label: str) -> tuple:
    raw = [] if raw is None else raw
    if not isinstance(raw, (list, tuple)):
        raise DeliveryError('invalid_composition', f'{label}: components must be a list')
    if composition != 'disclosed':
        if raw:
            raise DeliveryError('invalid_composition', f'{label}: a {composition} grade has no components')
        return ()
    if not raw:
        raise DeliveryError('invalid_composition', f'{label}: a disclosed blend must list its components')
    pairs = []
    for item in raw:
        if isinstance(item, Mapping):
            identity_id, fraction = item.get('identity_id'), item.get('mass_fraction')
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            identity_id, fraction = item
        else:
            raise DeliveryError('invalid_composition', f'{label}: component {item!r} is malformed')
        _known_identity(identity_id, label)
        if (isinstance(fraction, bool) or not isinstance(fraction, (int, float))
                or not math.isfinite(fraction) or not 0 < fraction <= 1):
            raise DeliveryError('invalid_composition', f'{label}: mass fraction {fraction!r} must be in (0, 1]')
        pairs.append((identity_id, float(fraction)))
    if len({identity_id for identity_id, _ in pairs}) != len(pairs):
        raise DeliveryError('invalid_composition', f'{label}: a component identity is listed twice')
    if sum(fraction for _, fraction in pairs) > 1 + _FRACTION_TOLERANCE:
        raise DeliveryError('invalid_composition', f'{label}: component mass fractions sum above 1')
    return tuple(pairs)


def _nutrient_charges(identity: dict) -> dict:
    """Mean charge per nutrient atom, from the identity's dissolved ion forms."""
    totals: dict = {}
    for ion, count in identity['ion_forms'].items():
        if ion in _ION_NUTRIENT_CHARGE:
            nutrient, charge = _ION_NUTRIENT_CHARGE[ion]
            weighted, atoms = totals.get(nutrient, (0.0, 0.0))
            totals[nutrient] = (weighted + charge * count, atoms + count)
    return {nutrient: weighted / atoms for nutrient, (weighted, atoms) in totals.items()}


def _charge_residual_percent(identity: dict, declared: dict) -> float | None:
    """100 * sum(z n) / sum(|z| n) over declared forms; None without a cation and an anion."""
    charges = _nutrient_charges(identity)
    signed = absolute = 0.0
    has_cation = has_anion = False
    for nutrient, percent in declared.items():
        charge = charges.get(nutrient, 0.0)
        if charge == 0:
            continue
        has_cation, has_anion = has_cation or charge > 0, has_anion or charge < 0
        moles = percent / ATOMIC['N' if nutrient in N_FORMS else nutrient]
        signed += charge * moles
        absolute += abs(charge) * moles
    if not (has_cation and has_anion) or absolute <= 0:
        return None
    return 100.0 * signed / absolute


def _range_excludes_theory(identity: dict, minimum: dict, maximum: dict) -> bool:
    theory = identity['theoretical_analysis']
    if not theory:
        return False
    return any(not minimum[key] <= theory.get(key, 0.0) <= maximum[key]
               for key in set(minimum) & set(maximum))


def _analysis_targets(key: Any, label: str, identity_id: str | None, conversions: dict,
                      split: dict) -> list:
    """Elemental forms an analysis key feeds, each with its multiplier."""
    if key != 'N':
        return [_nutrient_key(key, label, conversions)]
    theory = load_identities()[identity_id]['theoretical_analysis'] if identity_id else {}
    forms = {form: theory[form] for form in N_FORMS if theory.get(form, 0) > 0}
    if not forms:
        raise DeliveryError('invalid_value', f'{label}: total N needs an identity whose theory states N forms')
    total = sum(forms.values())
    split['N'] = {form: value / total for form, value in forms.items()}
    return list(split['N'].items())


def make_grade(record: Mapping) -> Grade:
    """Validate a technical-data-sheet grade; oxide inputs are converted to elemental %."""
    if not isinstance(record, Mapping):
        raise DeliveryError('invalid_value', 'a grade must be a mapping')
    label = f"grade {record.get('grade_id')!r}"
    document = _document(record, label)
    grade_id = _text(record, 'grade_id', label)
    supplier = _text(record, 'supplier', label)
    product = _text(record, 'product', label)
    composition = record.get('composition', 'single')
    if composition not in COMPOSITIONS:
        raise DeliveryError('invalid_composition', f'{label}: composition must be one of {sorted(COMPOSITIONS)}')
    chelating_agent = record.get('chelating_agent')
    if chelating_agent not in CHELATING_AGENTS:
        raise DeliveryError('invalid_value', f'{label}: chelating_agent must be one of {list(CHELATING_AGENTS)}')
    identity_id = record.get('identity_id')
    if composition == 'declared_ions' and identity_id is not None:
        raise DeliveryError('invalid_composition', f'{label}: a declared-ions compound has no single identity')
    if identity_id is None:
        if composition == 'single':
            raise DeliveryError('invalid_composition', f'{label}: a single-material grade must name its identity')
    else:
        _known_identity(identity_id, label)
    components = _components(record.get('components'), composition, label)

    analysis = record.get('analysis')
    if not isinstance(analysis, Mapping) or not analysis:
        raise DeliveryError('invalid_value', f'{label}: analysis must be a non-empty mapping')
    if 'N' in analysis and set(analysis) & set(N_FORMS):
        raise DeliveryError('invalid_value', f'{label}: state total N or its forms, not both')
    conversions: dict = {}
    split: dict = {}
    bands: dict = {band: {} for band in _BANDS}
    for key, stated in analysis.items():
        targets = _analysis_targets(key, label, identity_id, conversions, split)
        if not isinstance(stated, Mapping) or set(stated) - set(_BANDS) or not set(stated) & {'typical', 'minimum'}:
            raise DeliveryError('invalid_value', f'{label} {key}: state a typical or minimum value '
                                '(a maximum alone is not an assay)')
        for element, factor in targets:
            if any(element in bands[band] for band in _BANDS):
                raise DeliveryError('invalid_value', f'{label}: {element} stated twice')
            for band, raw in stated.items():
                bands[band][element] = _number(raw, f'{label} {key} {band}') * factor
            ordered = [bands[band][element] for band in ('minimum', 'typical', 'maximum')
                       if element in bands[band]]
            if ordered != sorted(ordered):
                raise DeliveryError('invalid_value', f'{label} {key}: needs minimum <= typical <= maximum')

    impurities = record.get('impurity_limits') or {}
    if not isinstance(impurities, Mapping):
        raise DeliveryError('invalid_value', f'{label}: impurity_limits must be a mapping')
    impurity_limits = {str(key): _number(value, f'{label} impurity {key}', ceiling=None)
                       for key, value in impurities.items()}

    flags, residual = (), None
    if composition == 'single':
        identity = load_identities()[identity_id]
        # Declared forms only: typical, else minimum; forms split from total N are inferred, not declared.
        inferred = set(split.get('N', ()))
        declared = {key: value for key, value in {**bands['minimum'], **bands['typical']}.items()
                    if key not in inferred}
        residual = _charge_residual_percent(identity, declared)
        if ((residual is not None and abs(residual) > _CHARGE_RESIDUAL_LIMIT_PERCENT)
                or (identity['status'] not in _RANGE_TEST_EXEMPT
                    and _range_excludes_theory(identity, bands['minimum'], bands['maximum']))):
            flags = ('identity_inconsistent',)
    return Grade(grade_id=grade_id, identity_id=identity_id, supplier=supplier, product=product,
                 typical=bands['typical'], minimum=bands['minimum'], maximum=bands['maximum'],
                 impurity_limits=impurity_limits, composition=composition, components=components,
                 oxide_conversions=conversions, document=document, flags=flags, form_split=split,
                 charge_residual_percent=residual, chelating_agent=chelating_agent,
                 chelating_agent_stated='chelating_agent' in record)


_MICRONUTRIENTS = ('Fe', 'Mn', 'Zn', 'Cu', 'B', 'Mo')
_PROTONS_PER_PHOSPHATE = (1.0, 2.0)  # HPO4-2 .. H2PO4-, the forms in fertilizer salts
# Labels and catalogue assays are rounded: 1 g KNO3 + 1 g KH2PO4 from the catalogue assays
# implies 2.0001 H+ per P. A hidden acid moves it by tenths (K2O 10 instead of 20: 2.75).
_PROTONS_ROUNDING = 0.01
_DECLARED_RESIDUAL_LIMIT_PERCENT = 5.0


def declared_ions_check(grade: Grade) -> DeclaredCheck:
    """Whether a data-sheet compound's declared ions can be modelled.

    Charges are those of the declared-ions conversion (phosphate as PO4-3, chelates as
    their D2 sodium salts); implied protons per P = (anion charge - cation charge) / mol P.
    """
    from .product_conversion import declared_ion_charges  # deferred: product_conversion imports this module
    declared = {**grade.minimum, **grade.typical}
    missing = [form for form in N_FORMS if form not in declared]
    if missing:
        return DeclaredCheck(False, None, None, f'the label does not state {", ".join(missing)} '
                             '(state every nitrogen form, 0 when absent)')
    if any(declared.get(key, 0) > 0 for key in _MICRONUTRIENTS) and not grade.chelating_agent_stated:
        return DeclaredCheck(False, None, None, 'the label states micronutrients but not whether they are '
                             'chelated (chelating_agent)')
    if grade.chelating_agent in ('DTPA', 'o,o-EDDHA') and any(declared.get(k, 0) > 0 for k in ('Mn', 'Zn', 'Cu')):
        return DeclaredCheck(False, None, None, f'{grade.chelating_agent} sodium salts are defined for iron only (D2)')
    phosphate, cations, anions = declared_ion_charges(declared, grade.chelating_agent)
    if phosphate > 0:
        protons = (anions + 3 * phosphate - cations) / phosphate
        low, high = _PROTONS_PER_PHOSPHATE
        if not low - _PROTONS_ROUNDING <= protons <= high + _PROTONS_ROUNDING:
            return DeclaredCheck(False, protons, None, f'phosphate balance: the declared ions imply {protons:.2f} H+ '
                                 f'per phosphate, outside {low:g}-{high:g} (HPO4-2 to H2PO4-)')
        return DeclaredCheck(True, protons, None, None)
    residual = 100.0 * (cations - anions) / (cations + anions) if cations + anions > 0 else 0.0
    if abs(residual) > _DECLARED_RESIDUAL_LIMIT_PERCENT:
        return DeclaredCheck(False, None, residual, f'charge balance: the declared ions leave a {residual:+.1f} % '
                             f'residual (limit {_DECLARED_RESIDUAL_LIMIT_PERCENT:g} %)')
    return DeclaredCheck(True, None, residual, None)


def _resolve_declared(product_name: str, grade: Grade, lot: Lot | None) -> ResolvedMaterial:
    """A data-sheet compound: elements are the label's, chemistry its declared ions."""
    if lot is not None:
        raise DeliveryError('material_mismatch', f'{product_name}: lots of a declared-ions compound are not supported')
    elements, basis = {}, {}
    for key in _unique([*grade.typical, *grade.minimum]):
        in_typical = key in grade.typical
        elements[key] = grade.typical[key] if in_typical else grade.minimum[key]
        basis[key] = 'grade_typical' if in_typical else 'grade_minimum'
    check = declared_ions_check(grade)
    lower_bound = ('lower_bound_grade_assay',) if 'grade_minimum' in basis.values() else ()
    # Na, Cl and S the label does not state are taken as zero.
    unstated = () if all(k in elements for k in ('Na', 'Cl', 'S')) else ('unstated_Na_Cl_S',)
    flags = _unique([*grade.flags, *lower_bound, *unstated, *(() if check.modellable else ('not_modellable',))])
    provenance = {
        'identityId': None, 'gradeId': grade.grade_id, 'lotId': None,
        'documents': {'grade': asdict(grade.document), 'lot': None}, 'source': None,
        'oxideConversions': {'grade': dict(grade.oxide_conversions), 'lot': {}}, 'assumed': False,
        'identitiesSha256': IDENTITIES_SHA256, 'chelatingAgent': grade.chelating_agent,
        'declaredCheck': asdict(check),
    }
    record = {'id': grade.grade_id, 'name': product_name, 'formula': None, 'elements': elements,
              'provenance': {**provenance, 'recordId': grade.grade_id, 'analysisBasis': dict(basis),
                             'flags': list(flags)}}
    return ResolvedMaterial(name=product_name, identity_id=None, record=record, basis=basis,
                            band_minimum={k: grade.minimum.get(k) for k in elements},
                            band_maximum={k: grade.maximum.get(k) for k in elements},
                            composition='declared_ions', provenance=provenance, flags=flags,
                            chelating_agent=grade.chelating_agent, declared_check=check)


def make_lot(record: Mapping) -> Lot:
    """Validate a certificate-of-analysis lot linked to exactly one grade or one identity."""
    if not isinstance(record, Mapping):
        raise DeliveryError('invalid_value', 'a lot must be a mapping')
    label = f"lot {record.get('lot_id')!r}"
    document = _document(record, label)
    lot_id = _text(record, 'lot_id', label)
    grade_id, identity_id = record.get('grade_id'), record.get('identity_id')
    if (grade_id is None) == (identity_id is None):
        raise DeliveryError('material_mismatch', f'{label}: name exactly one of grade_id or identity_id')
    if grade_id is not None:
        grade_id = _text(record, 'grade_id', label)
    else:
        _known_identity(identity_id, label)
    conversions: dict = {}
    measured = _elemental(record.get('measured'), f'{label} measured', conversions)
    if not measured:
        raise DeliveryError('invalid_value', f'{label}: measured must state at least one nutrient')
    uncertainty = _elemental(record.get('uncertainty') or {}, f'{label} uncertainty', conversions)
    extra = set(uncertainty) - set(measured)
    if extra:
        raise DeliveryError('invalid_value', f'{label}: uncertainty given for unmeasured {sorted(extra)}')
    return Lot(lot_id=lot_id, grade_id=grade_id, identity_id=identity_id, measured=measured,
               uncertainty=uncertainty, document=document, oxide_conversions=conversions)


def _shipped_salt(name: str) -> dict:
    from .engine import load_library  # deferred: the engine may later import this module
    for salt in load_library()['salts']:
        if salt['name'] == name:
            return salt
    raise DeliveryError('unknown_product', f'no catalogue record for {name!r}')


def _unique(items) -> tuple:
    return tuple(dict.fromkeys(items))


def _blend_implied(grade: Grade) -> tuple[dict, bool]:
    """Component-implied % of each declared nutrient, and whether any disagrees with the declaration.

    Implied = sum(mass fraction x component's shipped catalogue assay). A difference above
    max(5 % of declared, 0.05 % points) is unreconciled; it is reported, never rejected.
    """
    declared = {**grade.minimum, **grade.typical}
    assays = [(_shipped_salt(load_identities()[identity_id]['products'][0])['elements'], fraction)
              for identity_id, fraction in grade.components]
    implied = {key: sum(fraction * elements.get(key, 0.0) for elements, fraction in assays)
               for key in declared}
    unreconciled = any(abs(implied[key] - value) > max(_BLEND_RELATIVE_TOLERANCE * value,
                                                        _BLEND_ABSOLUTE_TOLERANCE)
                       for key, value in declared.items())
    return implied, unreconciled


def _check_linkage(product_name: str, identity_id: str, grade: Grade | None, lot: Lot | None) -> None:
    if grade is not None and grade.identity_id is not None and grade.identity_id != identity_id:
        raise DeliveryError('material_mismatch',
                            f'grade {grade.grade_id!r} is {grade.identity_id}, not {identity_id} ({product_name})')
    if lot is None:
        return
    if grade is not None:
        if lot.grade_id != grade.grade_id:
            raise DeliveryError('material_mismatch', f'lot {lot.lot_id!r} belongs to '
                                f'{lot.grade_id or lot.identity_id}, not grade {grade.grade_id!r}')
    elif lot.grade_id is not None:
        raise DeliveryError('material_mismatch', f'lot {lot.lot_id!r} names grade {lot.grade_id!r}; pass that grade')
    elif lot.identity_id != identity_id:
        raise DeliveryError('material_mismatch',
                            f'lot {lot.lot_id!r} is {lot.identity_id}, not {identity_id} ({product_name})')


def resolve_material(product_name: str, *, grade: Grade | None = None, lot: Lot | None = None) -> ResolvedMaterial:
    """Pick each nutrient's assay: lot measured > grade typical > grade minimum > identity theory.

    With neither grade nor lot, the shipped catalogue record is used with its declared basis.
    With a grade or lot, ``record['id']`` is the catalogue id suffixed with the grade and lot
    ids, so a resolved record is never mistaken for the shipped product; ``record['name']``
    stays the product name. A ``declared_ions`` grade (a compound entered from its data
    sheet) names the product itself; its record id is the grade id.
    """
    if grade is not None and grade.composition == 'declared_ions':
        return _resolve_declared(product_name, grade, lot)
    identity = identity_for_product(product_name)
    identity_id = identity['id']
    salt = _shipped_salt(product_name)
    _check_linkage(product_name, identity_id, grade, lot)

    if grade is None and lot is None:
        elements = dict(salt['elements'])
        declared = salt.get('analysisBasis', 'declared_catalogue')
        basis = {key: declared for key in elements}
        band_minimum = {key: None for key in elements}
        band_maximum = {key: None for key in elements}
        composition = salt.get('composition') or (
            'disclosed' if identity['status'] == 'assumed_blend' else 'single')
        flags: tuple = ()
        components: tuple = ()  # the shipped assumed blend keeps its own chemistry profile
        source = salt.get('source')
        implied = None
    else:
        theory = {}
        if grade is None or grade.identity_id == identity_id:
            theory = dict(identity['theoretical_analysis'])
            if identity['status'] == 'chelate_salt_defined':
                theory.pop('Na', None)  # D2: chelate sodium is a counterion, never a formulation element
        measured = lot.measured if lot is not None else {}
        uncertainty = lot.uncertainty if lot is not None else {}
        typical = grade.typical if grade is not None else {}
        minimum = grade.minimum if grade is not None else {}
        maximum = grade.maximum if grade is not None else {}
        elements, basis, band_minimum, band_maximum = {}, {}, {}, {}
        outside = False
        for key in _unique([*measured, *typical, *minimum, *theory]):
            low = high = None
            if key in measured:
                value, basis[key] = measured[key], 'lot_measured'
                if key in uncertainty:
                    low = max(0.0, value - uncertainty[key])
                    high = min(100.0, value + uncertainty[key])
                else:
                    low, high = minimum.get(key), maximum.get(key)
                    # The certificate outranks the data sheet: widen the band to include it.
                    if low is not None and value < low:
                        low, outside = value, True
                    if high is not None and value > high:
                        high, outside = value, True
            elif key in typical:
                value, basis[key] = typical[key], 'grade_typical'
                low, high = minimum.get(key), maximum.get(key)
            elif key in minimum:
                value, basis[key] = minimum[key], 'grade_minimum'
                low, high = minimum[key], maximum.get(key)
            else:
                value, basis[key] = theory[key], 'identity_theoretical'
            elements[key], band_minimum[key], band_maximum[key] = value, low, high
        composition = grade.composition if grade is not None else 'single'
        components = grade.components if grade is not None else ()
        implied = None
        source = None  # the catalogue document does not describe a user grade or lot
        lower_bound = ('lower_bound_grade_assay',) if 'grade_minimum' in basis.values() else ()
        flags = _unique([*(grade.flags if grade is not None else ()), *lower_bound,
                         *(('lot_outside_grade_range',) if outside else ())])
        if grade is not None and grade.components:
            implied, unreconciled = _blend_implied(grade)
            if unreconciled:
                flags = _unique([*flags, 'blend_analysis_unreconciled'])
    assumed = identity['status'] == 'assumed_blend'
    if assumed:
        flags = _unique([*flags, 'assumed_composition'])

    # A grade or lot is not the shipped product: it gets its own record id. The name stays the
    # shipped product's, which chemistry and materials= keying rely on.
    record_id = salt['id']
    if grade is not None:
        record_id += f'+{grade.grade_id}' + (f'+{lot.lot_id}' if lot is not None else '')
    elif lot is not None:
        record_id += f'+lot:{lot.lot_id}'
    blend = grade is not None and grade.identity_id is None
    provenance = {
        'identityId': None if blend else identity_id,
        'gradeId': grade.grade_id if grade is not None else None,
        'lotId': lot.lot_id if lot is not None else None,
        'documents': {'grade': asdict(grade.document) if grade is not None else None,
                      'lot': asdict(lot.document) if lot is not None else None},
        'source': dict(source) if source is not None else None,
        'oxideConversions': {'grade': dict(grade.oxide_conversions) if grade is not None else {},
                             'lot': dict(lot.oxide_conversions) if lot is not None else {}},
        'assumed': assumed,
        'identitiesSha256': IDENTITIES_SHA256,
    }
    if blend:
        provenance['hostProduct'] = product_name  # the catalogue name the blend is dosed under
    if implied is not None:
        provenance['blendImpliedAnalysis'] = implied
    # A blend has no single formula; the host's would make assay checks compare the wrong compound.
    formula = None if blend else identity['formula'] or salt.get('formula')
    record = {'id': record_id, 'name': salt['name'], 'formula': formula, 'elements': elements,
              'provenance': {**provenance, 'recordId': record_id, 'analysisBasis': dict(basis),
                             'flags': list(flags)}}
    return ResolvedMaterial(name=product_name, identity_id=identity_id, record=record, basis=basis,
                            band_minimum=band_minimum, band_maximum=band_maximum,
                            composition=composition, provenance=provenance, flags=flags,
                            components=components)


def material_audit_entry(material: ResolvedMaterial) -> dict:
    """Audit record of one dosed material: provenance plus per-nutrient basis.

    ``analysisBasis`` is the basis shared by every nutrient (always one for a shipped
    product), else None.
    """
    bases = set(material.basis.values())
    return {**material.provenance, 'basis': dict(material.basis),
            'analysisBasis': bases.pop() if len(bases) == 1 else None,
            'composition': material.composition, 'flags': list(material.flags),
            'components': [list(pair) for pair in material.components]}


BAND_NOTE = 'Band applies to nutrient amounts only; chemistry is reported at the nominal assay.'


def nutrient_band(doses_g_per_litre: Mapping[str, float], *,
                  materials: Mapping[str, ResolvedMaterial] | None = None) -> dict:
    """Delivered nutrient (mg/L) at nominal and band-end assays for the same doses.

    Linear re-evaluation (mg/L = g/L x % x 10); the solver is never called. A nutrient
    whose contributor has an open band end gets ``None`` for that end of the total.
    Products without a resolved material use the shipped record with no band.
    """
    from .product_conversion import _check_materials  # deferred: avoids a circular import with product_conversion
    resolved = _check_materials(doses_g_per_litre, materials, allow_undisclosed=True)
    nutrients: dict = {}
    basis: dict = {}
    for name, dose in doses_g_per_litre.items():
        material = resolved.get(name) or resolve_material(name)
        basis[name] = dict(material.basis)
        for key, percent in material.record['elements'].items():
            entry = nutrients.setdefault(key, {'nominal_mg_per_l': 0.0, 'minimum_mg_per_l': 0.0,
                                               'maximum_mg_per_l': 0.0})
            entry['nominal_mg_per_l'] += dose * percent * 10
            for end, edge in (('minimum_mg_per_l', material.band_minimum),
                              ('maximum_mg_per_l', material.band_maximum)):
                bound = edge.get(key)
                if entry[end] is not None:
                    entry[end] = None if bound is None else entry[end] + dose * bound * 10
    return {'nutrients': nutrients, 'basis': basis, 'note': BAND_NOTE}
