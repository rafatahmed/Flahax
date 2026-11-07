# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Stock volumes for the two interactive-mix fill modes.

``fill``: the smaller nutrient tank sets the irrigation volume. The separate reagent
container is refilled as needed at the same injection ratio. ``once``: the grower gives
the irrigation volume; nutrient stocks must fit their tanks, while reagent refills are allowed.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass

from .delivery_contracts import DeliveryError

CONTAINERS = ('A', 'B', 'acid')
MODES = ('fill', 'once')


@dataclass(frozen=True)
class StockVolumes:
    """The irrigation supplied, nutrient stock volumes, first reagent fill and tank capacities.

    The reagent container can require subsequent fills at the same injection ratio.
    """

    irrigation_litres: float
    prepared_litres: dict
    capacity_litres: dict


def _positive(value, label):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise DeliveryError(
            'invalid_value', f'{label} must be a positive finite number, got {value!r}'
        )
    return float(value)


def prepare_stocks(
    *, tank_litres: Mapping, ratio: float, mode: str, irrigation_litres: float | None = None
) -> StockVolumes:
    """Nutrient stock litres and first reagent fill for full tanks or one irrigation.

    A smaller reagent container is refilled; only nutrient tanks constrain batch capacity.
    """
    if not isinstance(tank_litres, Mapping):
        raise DeliveryError("invalid_type", "tank_litres must be a mapping")
    if set(tank_litres) != set(CONTAINERS):
        raise DeliveryError(
            'invalid_value',
            f'tank_litres must have exactly the keys {CONTAINERS}, ' f'got {tuple(tank_litres)}',
        )
    capacity = {name: _positive(tank_litres[name], f'{name} capacity') for name in CONTAINERS}
    ratio = _positive(ratio, 'injection ratio')
    if ratio <= len(CONTAINERS):
        raise DeliveryError('invalid_ratio', 'three stock channels require positive carrier water')
    if mode not in MODES:
        raise DeliveryError('invalid_value', f'mode must be one of {MODES}, got {mode!r}')

    if mode == 'fill':
        # Assumption: irrigation_litres is ignored in fill mode. Nutrient tanks are prepared to the
        # smallest capacity directly: (x * ratio) / ratio can round 1 ulp above x.
        prepared_each = min(capacity['A'], capacity['B'])
        irrigation = _positive(prepared_each * ratio, 'derived irrigation litres')
    else:
        if irrigation_litres is None:
            raise DeliveryError('invalid_value', 'one-irrigation mode needs irrigation_litres')
        irrigation = _positive(irrigation_litres, 'irrigation_litres')
        prepared_each = _positive(irrigation / ratio, 'derived prepared litres')
        too_small = [name for name in ('A', 'B') if prepared_each > capacity[name]]
        if too_small:
            raise DeliveryError(
                'tank_too_small',
                f'{", ".join(too_small)} cannot hold {prepared_each:g} L each '
                f'for {irrigation:g} L of irrigation at 1:{ratio:g}; use a smaller irrigation '
                'or larger containers',
            )
    prepared = dict(A=prepared_each, B=prepared_each, acid=min(prepared_each, capacity['acid']))
    return StockVolumes(
        irrigation_litres=irrigation, prepared_litres=prepared, capacity_litres=capacity
    )
