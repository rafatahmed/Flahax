# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Explicit content-bound consent; never a scientific or operational
waiver.
"""

from copy import deepcopy
from datetime import datetime, timezone

from .canonical_result import _digest, verify_summary
from .delivery_contracts import DeliveryError


def _bound(summary):
    if not isinstance(summary, dict):
        raise DeliveryError('invalid_acceptance', 'result must be an object')
    identity = summary.get('calculation_identity') or {}
    if not isinstance(identity, dict):
        raise DeliveryError('invalid_acceptance', 'calculation identity must be an object')
    verify_summary(summary)
    if identity.get('status') != 'bound' or not identity.get('result_id'):
        raise DeliveryError('invalid_acceptance', 'legacy results cannot acquire acceptance')
    return summary['export_identity']['sha256']


def accept_result(summary, *, actor, reason):
    """Record explicit consent to this exact proposal, without changing
    any result status.

    Actor is caller-supplied attribution, not authenticated identity.
    Consent does not waive constraints, certify EC, or authorize
    physical delivery.
    """
    fingerprint = _bound(summary)
    if not all(isinstance(v, str) and v.strip() for v in (actor, reason)):
        raise DeliveryError('invalid_acceptance', 'actor and reason must be nonempty text')
    return dict(
        schema_version=1,
        scope='exact_result_proposal',
        actor=actor,
        reason=reason,
        recorded_at=datetime.now(timezone.utc).isoformat(),
        result_id=summary['calculation_identity']['result_id'],
        export_sha256=fingerprint,
    )


def verify_acceptance(summary, acceptance):
    """Reject stale or malformed consent. Success leaves every
    calculation guard intact.
    """
    fingerprint = _bound(summary)
    keys = {
        'schema_version',
        'scope',
        'actor',
        'reason',
        'recorded_at',
        'result_id',
        'export_sha256',
    }
    if not isinstance(acceptance, dict) or set(acceptance) != keys:
        raise DeliveryError('invalid_acceptance', 'malformed acceptance record')
    if (
        type(acceptance['schema_version']) is not int
        or acceptance['schema_version'] != 1
        or acceptance['scope'] != 'exact_result_proposal'
        or not all(
            isinstance(acceptance[k], str) and acceptance[k].strip()
            for k in ('actor', 'reason', 'recorded_at')
        )
    ):
        raise DeliveryError('invalid_acceptance', 'unsupported or incomplete acceptance')
    try:
        stamp = datetime.fromisoformat(acceptance['recorded_at'])
        if stamp.tzinfo is None:
            raise ValueError('timezone required')
    except ValueError as exc:
        raise DeliveryError('invalid_acceptance', 'invalid acceptance timestamp') from exc
    if (
        acceptance['export_sha256'] != fingerprint
        or acceptance['result_id'] != summary['calculation_identity']['result_id']
    ):
        raise DeliveryError('stale_acceptance', 'result changed; explicit acceptance is required')


def save_result(summary, acceptance=None):
    """Build a detached versioned archive; no acceptance is inferred by
    saving.
    """
    _bound(summary)
    if acceptance is not None:
        verify_acceptance(summary, acceptance)
    payload = dict(summary=deepcopy(summary), acceptance=deepcopy(acceptance))
    return dict(schema_version=1, payload=payload, sha256=_digest(payload))


def _flatten(value, prefix=''):
    """Leaf values of nested supplied inputs by dotted path; a list of
    records with ids is keyed by id.
    """
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _flatten(item, f'{prefix}.{key}' if prefix else str(key))
    elif (
        isinstance(value, list)
        and value
        and all(isinstance(item, dict) and 'id' in item for item in value)
    ):
        for item in value:
            yield from _flatten(item, f'{prefix}.{item["id"]}')
    else:
        yield prefix, value


def saved_input_differences(saved, recalculated):
    """What differs between the inputs of two results: a list of
    ``{path, saved, recalculated}`` sorted by path (Q27).

    Both results must carry their supplied inputs; an older saved result
    without them cannot be compared.
    """
    for name, result in (('saved', saved), ('recalculated', recalculated)):
        if not isinstance(result, dict) or 'supplied_inputs' not in result:
            raise DeliveryError('missing_field', f'the {name} result has no saved inputs')
    before = dict(_flatten(saved['supplied_inputs']))
    after = dict(_flatten(recalculated['supplied_inputs']))
    return [
        dict(path=path, saved=before.get(path), recalculated=after.get(path))
        for path in sorted(before.keys() | after.keys())
        if before.get(path) != after.get(path)
    ]


def load_result(record):
    """Validate a saved result and return its detached payload,
    preserving old provenance.
    """
    if (
        not isinstance(record, dict)
        or set(record) != {'schema_version', 'payload', 'sha256'}
        or type(record['schema_version']) is not int
        or record['schema_version'] != 1
    ):
        raise DeliveryError('invalid_saved_result', 'unsupported saved result schema')
    payload = record['payload']
    if (
        not isinstance(payload, dict)
        or set(payload) != {'summary', 'acceptance'}
        or record['sha256'] != _digest(payload)
    ):
        raise DeliveryError('invalid_saved_result', 'saved result content changed')
    summary = payload['summary']
    identity = summary.get('calculation_identity') if isinstance(summary, dict) else None
    if (
        isinstance(summary, dict)
        and 'supplied_inputs' in summary
        and isinstance(identity, dict)
        and identity.get('input_sha256') != _digest(summary['supplied_inputs'])
    ):
        raise DeliveryError('invalid_saved_result', 'saved inputs do not match their fingerprint')
    save_result(payload['summary'], payload['acceptance'])
    return deepcopy(payload)
