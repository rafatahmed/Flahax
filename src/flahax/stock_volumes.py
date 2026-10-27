# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Stock volumes for the two interactive-mix fill modes.

``fill``: the irrigation is set by the smallest container (tank A, tank B or the acid
container), and every container is prepared to that same irrigation divided by the
injection ratio; a larger tank is only part-filled. ``once``: the grower gives the
irrigation volume and each container gets its share, which must fit the tank.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass

from .delivery_contracts import DeliveryError

CONTAINERS = ('A', 'B', 'acid')
MODES = ('fill', 'once')


@dataclass(frozen=True)
class StockVolumes:
    """The irrigation the stocks supply and the litres prepared in each container, with each
    container's capacity.
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
    """Litres to prepare in tanks A and B and the acid container, filling them (``fill``) or for
    one irrigation (``once``).
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
        # Assumption: irrigation_litres is ignored in fill mode. Each container is prepared to the
        # smallest capacity directly: (x * ratio) / ratio can round 1 ulp above x.
        prepared_each = min(capacity.values())
        irrigation = _positive(prepared_each * ratio, 'derived irrigation litres')
    else:
        if irrigation_litres is None:
            raise DeliveryError('invalid_value', 'one-irrigation mode needs irrigation_litres')
        irrigation = _positive(irrigation_litres, 'irrigation_litres')
        prepared_each = _positive(irrigation / ratio, 'derived prepared litres')
        too_small = [name for name in CONTAINERS if prepared_each > capacity[name]]
        if too_small:
            raise DeliveryError(
                'tank_too_small',
                f'{", ".join(too_small)} cannot hold {prepared_each:g} L each '
                f'for {irrigation:g} L of irrigation at 1:{ratio:g}; use a smaller irrigation '
                'or larger containers',
            )
    prepared = {name: prepared_each for name in CONTAINERS}
    return StockVolumes(
        irrigation_litres=irrigation, prepared_litres=prepared, capacity_litres=capacity
    )
