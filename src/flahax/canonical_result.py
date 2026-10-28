# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Immutable calculation snapshots and content-bound export copies.

Hashes identify content, not authenticity, scientific validity or authorization.
"""

from dataclasses import dataclass, fields, is_dataclass
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from collections.abc import Mapping

from .delivery_contracts import DeliveryError


def _plain(value):
    if is_dataclass(value):
        return {
            f.name: _plain(getattr(value, f.name))
            for f in fields(value)
            if f.name != 'canonical_result'
        }
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(v) for v in value), key=repr)
    if isinstance(value, float) and not math.isfinite(value):
        return {'nonfinite': str(value)}
    if callable(value):
        return {
            'callback': getattr(value, '__module__', type(value).__module__)
            + '.'
            + getattr(value, '__qualname__', type(value).__qualname__),
            'qualification': 'identity only; applicability requires result evidence',
        }
    return value


def _json(value):
    return json.dumps(_plain(value), sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def _sources():
    root = Path(__file__).parent
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob('*'))
        if p.is_file() and p.suffix in ('.py', '.json')
    }


@dataclass(frozen=True, slots=True)
class CanonicalResult:
    """Immutable JSON snapshot of inputs, source fingerprints and completed workflow state."""

    payload: str

    @property
    def result_id(self):
        """SHA-256 of this exact snapshot, independent of dictionary insertion order."""
        return hashlib.sha256(self.payload.encode('utf-8')).hexdigest()

    def to_dict(self):
        """Return a detached export copy; modifying it cannot change the snapshot."""
        return json.loads(self.payload)

    @classmethod
    def capture(cls, workflow, inputs):
        """Capture completed stage values, selected candidates and original supplied inputs."""
        from . import __version__

        return cls(
            _json(
                dict(
                    schema_version=1,
                    package_version=__version__,
                    inputs=inputs,
                    sources=_sources(),
                    workflow=workflow,
                )
            )
        )

    def verify(self, workflow, products):
        """Reject changed calculation state or changed records for supplied product IDs."""
        record = self.to_dict()
        if _json(workflow) != _json(record['workflow']):
            raise DeliveryError('canonical_result_mismatch', 'workflow changed after calculation')
        supplied = {p['id']: p for p in products}
        if len(supplied) != len(products):
            raise DeliveryError('canonical_result_mismatch', 'duplicate report product IDs')
        for product in record['inputs']['salts']:
            if _json(supplied.get(product['id'])) != _json(product):
                raise DeliveryError('canonical_result_mismatch', 'report product record changed')
        if _sources() != record['sources']:
            raise DeliveryError(
                'canonical_result_mismatch', 'model sources changed after calculation'
            )


def _export_value(value):
    # Match the existing public JSON convention while retaining Python tuple types.
    if isinstance(value, dict):
        return {k: _export_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_export_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_export_value(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def seal_summary(summary):
    """Bind a final export copy to its content; return a detached JSON-compatible mapping."""
    result = _export_value(deepcopy({k: v for k, v in summary.items() if k != 'export_identity'}))
    result['export_identity'] = dict(schema_version=1, sha256=_digest(result))
    return result


def verify_summary(summary):
    """Reject changed bound exports; legacy unbound dictionaries have no identity claim."""
    identity = summary.get('export_identity')
    if identity is None and (summary.get('calculation_identity') or {}).get('status') == 'bound':
        raise DeliveryError('canonical_result_mismatch', 'bound export identity is missing')
    if identity is not None and identity != dict(
        schema_version=1,
        sha256=_digest({k: v for k, v in summary.items() if k != 'export_identity'}),
    ):
        raise DeliveryError('canonical_result_mismatch', 'export changed after finalization')


STATUS_VOCABULARY = frozenset(
    {
        'ready',
        'requires_review',
        'blocked',
        'not_supported',
        'needs_input',
        'not_validated',
    }
)

# Legacy / stage-local tokens mapped onto the grower status contract.
_STATUS_ALIASES = {
    'calculated': 'ready',
    'feasible': 'ready',
    'infeasible': 'blocked',
    'assessed': 'ready',
    'not_assessed': 'needs_input',
    'not_reported': 'not_validated',
}


def contract_status(raw):
    """Map a stage or legacy token onto STATUS_VOCABULARY.

    Unknown tokens become ``not_validated`` so callers cannot invent out-of-contract statuses.
    """
    if raw in STATUS_VOCABULARY:
        return raw
    return _STATUS_ALIASES.get(raw, 'not_validated')


def result_statuses(summary):
    """Expose independent qualifications in the unified status vocabulary."""
    stages = summary['stages']
    chemistry = summary.get('chemistry')
    stocks = summary['tanks']
    if not summary['formulation']['feasible']:
        formulation = 'blocked'
    else:
        formulation = contract_status(
            stages.get('formulation', {}).get('status', 'ready')
        )
    phase = (
        'blocked'
        if chemistry and chemistry['phase_assessment']['blocks']
        else 'requires_review'
        if chemistry and chemistry['phase_assessment']['review']
        else 'ready'
        if chemistry
        else 'needs_input'
    )
    return dict(
        numerical='not_validated',
        formulation=formulation,
        chemistry=contract_status(stages.get('chemistry', {}).get('status', 'needs_input')),
        phase=phase,
        ph=contract_status((summary.get('ph') or {}).get('status', 'needs_input')),
        ec=contract_status((summary.get('ec') or {}).get('status', 'needs_input')),
        stock='blocked'
        if stocks['required_tanks'] > stocks['available_tanks']
        or any(row['status'] == 'exceeds' for row in summary['solubility'])
        else 'requires_review',
        delivery='not_validated',
        physical='not_validated',
        overall=contract_status(summary['status']),
    )
