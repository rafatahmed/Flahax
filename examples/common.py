"""Example records are fictional, never manufacturer or laboratory evidence."""
from dataclasses import asdict, is_dataclass
import json
import math

from flahax import DeliveryError, load_library


def catalogue():
    return {product['name']: product for product in load_library()['salts']}


def record(identity, **fields):
    return dict(schemaVersion='0.1', id=identity, source='SYNTHETIC EXAMPLE ONLY',
                revision='1', recordedAt='2026-09-28T00:00:00Z', **fields)


def rejection(action):
    try:
        action()
    except DeliveryError as error:
        return {'error_code': error.code, 'message': str(error)}
    raise AssertionError('example rejection unexpectedly succeeded')


def serializable(value):
    """Presentation format only, not a versioned FlahaX persistence contract.

    Negative infinite SI means an absent phase component. Represent it as text
    rather than emitting invalid JSON Infinity tokens.
    """
    if is_dataclass(value):
        return serializable(asdict(value))
    if isinstance(value, dict):
        return {str(key): serializable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [serializable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def show(value):
    print(json.dumps(serializable(value), indent=2, allow_nan=False))
