"""EXPERIMENTAL (M1): speciation-based irrigation EC from McCleskey et al. (2012).

Source: McCleskey, Nordstrom, Ryan, Ball (2012) Geochim. Cosmochim. Acta 77,
369-382, Table 1 (Eq. 8 parameters), shipped in
data/conductivity_mccleskey2012.json and pinned by SHA-256. This module holds
the coefficient loader and the ionic molal conductivity only. Units are
mS kg cm-1 mol-1. Not validated for concentrated nutrient solutions.
"""
import hashlib
import math
from functools import lru_cache
from importlib.resources import files

import json

from .delivery_contracts import DeliveryError

_RESOURCE = 'data/conductivity_mccleskey2012.json'
_RAW = files('flahax').joinpath(_RESOURCE).read_bytes()
COEFFICIENTS_SHA256 = hashlib.sha256(_RAW).hexdigest()


@lru_cache(maxsize=1)
def _load():
    return json.loads(_RAW.decode('utf-8'))


def load_conductivity_coefficients() -> dict:
    """Return the cached McCleskey 2012 Table 1 data (treat as read-only)."""
    return _load()


def covered_species() -> frozenset:
    """FlahaX aqueous species names that have a Table 1 coefficient."""
    return frozenset(_load()['species_map'])


def ionic_molal_conductivity(ion: str, ionic_strength: float,
                             temperature_c: float = 25.0) -> float:
    """Eq. 8: lambda = lambda0(T) - A(T)*sqrt(I)/(1 + B*sqrt(I)), T in C."""
    row = _load()['ions'].get(ion) if isinstance(ion, str) else None
    if row is None:
        raise DeliveryError('unknown_ion', f'no McCleskey 2012 Table 1 coefficient for {ion!r}')
    for name, v in (('ionic_strength', ionic_strength), ('temperature_c', temperature_c)):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise DeliveryError('invalid_value', f'{name} must be a finite number')
    if ionic_strength < 0:
        raise DeliveryError('invalid_value', 'ionic_strength must be >= 0')
    t = float(temperature_c)
    poly = lambda c: c[0] * t * t + c[1] * t + c[2]
    root = math.sqrt(ionic_strength)
    return poly(row['lambda0']) - poly(row['A']) * root / (1 + row['B'] * root)
