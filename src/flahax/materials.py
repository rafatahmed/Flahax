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
from functools import lru_cache
from importlib.resources import files

from .composition import theoretical_assay
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
