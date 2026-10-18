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
COMPOSITIONS = frozenset({'single', 'disclosed', 'undisclosed'})
_BANDS = ('typical', 'minimum', 'maximum')
_RELATIVE_IDENTITY_TOLERANCE = 0.001
_FRACTION_TOLERANCE = 1e-9


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


def _identity_inconsistent(identity_id: str, typical: dict, minimum: dict, maximum: dict) -> bool:
    """A stated value off the theoretical by > 0.1 % relative, or a range that excludes it."""
    theory = load_identities()[identity_id]['theoretical_analysis']
    if not theory:
        return False
    for key in set(typical) | set(minimum) | set(maximum):
        expected = theory.get(key, 0.0)
        stated = typical.get(key, minimum.get(key))
        if stated is not None and abs(stated - expected) > _RELATIVE_IDENTITY_TOLERANCE * expected:
            return True
        if (key in minimum and minimum[key] > expected) or (key in maximum and maximum[key] < expected):
            return True
    return False


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
    identity_id = record.get('identity_id')
    if identity_id is None:
        if composition == 'single':
            raise DeliveryError('invalid_composition', f'{label}: a single-material grade must name its identity')
    else:
        _known_identity(identity_id, label)
    components = _components(record.get('components'), composition, label)

    analysis = record.get('analysis')
    if not isinstance(analysis, Mapping) or not analysis:
        raise DeliveryError('invalid_value', f'{label}: analysis must be a non-empty mapping')
    conversions: dict = {}
    bands: dict = {band: {} for band in _BANDS}
    for key, stated in analysis.items():
        element, factor = _nutrient_key(key, label, conversions)
        if not isinstance(stated, Mapping) or not stated or set(stated) - set(_BANDS):
            raise DeliveryError('invalid_value', f'{label} {key}: state typical, minimum and/or maximum')
        if any(element in bands[band] for band in _BANDS):
            raise DeliveryError('invalid_value', f'{label}: {element} stated twice (elemental and oxide)')
        for band, raw in stated.items():
            bands[band][element] = _number(raw, f'{label} {key} {band}') * factor
        ordered = [bands[band][element] for band in ('minimum', 'typical', 'maximum') if element in bands[band]]
        if ordered != sorted(ordered):
            raise DeliveryError('invalid_value', f'{label} {key}: needs minimum <= typical <= maximum')

    impurities = record.get('impurity_limits') or {}
    if not isinstance(impurities, Mapping):
        raise DeliveryError('invalid_value', f'{label}: impurity_limits must be a mapping')
    impurity_limits = {str(key): _number(value, f'{label} impurity {key}', ceiling=None)
                       for key, value in impurities.items()}

    flags = ()
    if composition == 'single' and _identity_inconsistent(identity_id, bands['typical'],
                                                          bands['minimum'], bands['maximum']):
        flags = ('identity_inconsistent',)
    return Grade(grade_id=grade_id, identity_id=identity_id, supplier=supplier, product=product,
                 typical=bands['typical'], minimum=bands['minimum'], maximum=bands['maximum'],
                 impurity_limits=impurity_limits, composition=composition, components=components,
                 oxide_conversions=conversions, document=document, flags=flags)


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
    """
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
        for key in _unique([*measured, *typical, *minimum, *theory]):
            low = high = None
            if key in measured:
                value, basis[key] = measured[key], 'lot_measured'
                if key in uncertainty:
                    low = max(0.0, value - uncertainty[key])
                    high = min(100.0, value + uncertainty[key])
                else:
                    low, high = minimum.get(key), maximum.get(key)
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
        lower_bound = ('lower_bound_grade_assay',) if 'grade_minimum' in basis.values() else ()
        flags = _unique([*(grade.flags if grade is not None else ()), *lower_bound])

    provenance = {
        'identityId': identity_id,
        'gradeId': grade.grade_id if grade is not None else None,
        'lotId': lot.lot_id if lot is not None else None,
        'documents': {'grade': asdict(grade.document) if grade is not None else None,
                      'lot': asdict(lot.document) if lot is not None else None},
        'oxideConversions': {'grade': dict(grade.oxide_conversions) if grade is not None else {},
                             'lot': dict(lot.oxide_conversions) if lot is not None else {}},
        'identitiesSha256': IDENTITIES_SHA256,
    }
    record = {'id': salt['id'], 'name': salt['name'], 'formula': identity['formula'] or salt.get('formula'),
              'elements': elements}
    return ResolvedMaterial(name=product_name, identity_id=identity_id, record=record, basis=basis,
                            band_minimum=band_minimum, band_maximum=band_maximum,
                            composition=composition, provenance=provenance, flags=flags)
