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
    irrigation_litres: float
    prepared_litres: dict
    capacity_litres: dict


def _positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise DeliveryError('invalid_value', f'{label} must be a positive finite number, got {value!r}')
    return float(value)


def prepare_stocks(*, tank_litres: Mapping, ratio: float, mode: str,
                   irrigation_litres: float | None = None) -> StockVolumes:
    if set(tank_litres) != set(CONTAINERS):
        raise DeliveryError('invalid_value', f'tank_litres must have exactly the keys {CONTAINERS}, '
                            f'got {tuple(tank_litres)}')
    capacity = {name: _positive(tank_litres[name], f'{name} capacity') for name in CONTAINERS}
    ratio = _positive(ratio, 'injection ratio')
    if mode not in MODES:
        raise DeliveryError('invalid_value', f'mode must be one of {MODES}, got {mode!r}')

    if mode == 'fill':
        # Assumption: irrigation_litres is ignored in fill mode. Each container is prepared to the smallest
        # capacity directly: (x * ratio) / ratio can round 1 ulp above x.
        prepared_each = min(capacity.values())
        irrigation = prepared_each * ratio
    else:
        if irrigation_litres is None:
            raise DeliveryError('invalid_value', 'one-irrigation mode needs irrigation_litres')
        irrigation = _positive(irrigation_litres, 'irrigation_litres')
        prepared_each = irrigation / ratio
        too_small = [name for name in CONTAINERS if prepared_each > capacity[name]]
        if too_small:
            raise DeliveryError('tank_too_small', f'{", ".join(too_small)} cannot hold {prepared_each:g} L each '
                                f'for {irrigation:g} L of irrigation at 1:{ratio:g}; use a smaller irrigation '
                                'or larger containers')
    prepared = {name: prepared_each for name in CONTAINERS}
    return StockVolumes(irrigation_litres=irrigation, prepared_litres=prepared, capacity_litres=capacity)
