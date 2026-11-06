# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Single-product stock solubility from measured data; never a mixed-stock approval.

A product's own catalogue ``physicalProperties.waterSolubility`` is the first source, the
historical table the second; a product with neither is ``not_checked``. Each source value is
used as measured: its basis and both temperatures are reported and nothing is interpolated or
converted. A value in a unit the check does not know is ``not_checked``.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
import math
from pathlib import Path

from .delivery_contracts import DeliveryError

TABLE_PATH = Path(__file__).with_name('data') / 'solubility.json'
SINGLE_SALT = 'single-product check; the mixed tank is not assessed'
SOLUTION_BASIS = (
    'g product/L solution (historical table value, converted at density 1 by its source)'
)
NO_DATA = 'no solubility data'


@dataclass(frozen=True)
class SolubilityRow:
    """One product against its source value: basis and both temperatures stated."""

    tank: str
    product: str
    stock_g_per_l: float
    limit_g_per_l: float | None
    status: str
    source: str | None
    reason: str | None = None
    basis: str | None = None
    source_temperature_c: float | None = None
    tank_temperature_c: float | None = None
    qualification: dict = field(default_factory=dict)
    mixture_approved: bool = False


def _number(value, name, *, positive=False):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or (positive and value <= 0)
    ):
        raise DeliveryError(
            'invalid_solubility_input',
            f'{name} must be finite' + (' and positive' if positive else ''),
        )
    return float(value)


def source_concentration_g_per_l(
    value,
    basis,
    *,
    solution_density_g_per_ml=None,
    water_density_g_per_ml=None,
    product_to_solute_mass_ratio=1.0,
):
    """Convert source concentration to product-equivalent g/L of final solution.

    Density is mandatory for mass/water bases; no density-one assumption is
    supplied. The explicit product/solute mass ratio handles hydrate equivalents.
    This arithmetic does not establish grade, temperature or density applicability.
    """
    value = _number(value, 'source concentration')
    ratio = _number(product_to_solute_mass_ratio, 'product/solute mass ratio', positive=True)
    if value < 0:
        raise DeliveryError('invalid_solubility_input', 'source concentration must be nonnegative')
    if basis == 'g_per_l_solution':
        result = value * ratio
    else:
        density = _number(solution_density_g_per_ml, 'solution density', positive=True)
        if basis == 'mass_percent':
            if value > 100:
                raise DeliveryError('invalid_solubility_input', 'mass percent cannot exceed 100')
            fraction = value / 100
        elif basis == 'g_per_100g_water':
            fraction = value / (100 + value)
        elif basis == 'g_per_l_water':
            water_density = _number(water_density_g_per_ml, 'water density', positive=True)
            denominator = _number(1000 * water_density + value, 'water-basis denominator')
            fraction = value / denominator
        else:
            raise DeliveryError(
                'invalid_solubility_basis', 'unsupported source concentration basis'
            )
        result = 1000 * density * fraction * ratio
    return _number(result, 'converted concentration')


def load_solubility_table(path=TABLE_PATH):
    """The historical records, unchanged: product, temperature points and source."""
    path = Path(path)
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding='utf-8'))


def _points(points):
    if not isinstance(points, (list, tuple)):
        raise DeliveryError('invalid_solubility_table', 'points must be a sequence')
    result = []
    for pair in points:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise DeliveryError(
                'invalid_solubility_table', 'each point must contain temperature and concentration'
            )
        t, g = (_number(pair[0], 'temperature'), _number(pair[1], 'concentration'))
        if g < 0 or any(t == old[0] for old in result):
            raise DeliveryError(
                'invalid_solubility_table', 'negative concentration or duplicate temperature'
            )
        result.append((t, g))
    return sorted(result)


def limit_at(points, temperature_c):
    """Algebraic linear interpolation of a point list; the stock check does not use it."""
    temperature_c = _number(temperature_c, 'temperature')
    points = _points(points)
    for temperature, concentration in points:
        if temperature_c == temperature:
            return concentration
    for (t0, g0), (t1, g1) in zip(points, points[1:]):
        if t0 < temperature_c < t1:
            weight = (temperature_c - t0) / (t1 - t0)
            return _number((1 - weight) * g0 + weight * g1, 'interpolated concentration')
    return None


def _catalogue_source(record):
    """(g/L, basis, source temperature, reason) from ``physicalProperties.waterSolubility``.

    ``None`` when the record holds no such value; a ``None`` g/L with a reason when it is unusable.
    """
    data = (record.get('physicalProperties') or {}).get('waterSolubility')
    if not isinstance(data, Mapping):
        return None
    value, unit, temperature = data.get('value'), data.get('unit'), data.get('temperatureC')
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not value >= 0:
        return None, None, None, 'unusable solubility value'
    basis = str(data.get('basis') or '')
    if unit == 'g/L':
        if 'water' not in basis:
            basis = 'g/L (volume basis unspecified by source)'
        return float(value), basis, temperature, None
    return None, None, None, 'unsupported solubility unit'


def _table_source(record, temperature_c):
    """The historical point nearest the tank temperature (the lower one on a tie); no blending."""
    t, g = min(_points(record.get('points')), key=lambda p: (abs(p[0] - temperature_c), p[0]))
    return g, SOLUTION_BASIS, t, None


def _catalogue_records(products):
    if products is None:
        return {}
    items = products.values() if isinstance(products, Mapping) else products
    return {str(p['name']): p for p in items if isinstance(p, Mapping) and 'name' in p}


def _source_label(record):
    source = (record.get('physicalProperties') or {}).get('source') or {}
    return f'{source.get("organization", "catalogue")}, {source.get("title", "catalogue data")}'


def check_stock_solubility(
    tanks, ratio, temperature_c, *, table=None, product_grades=None, products=None
):
    """Compare each product's stock with its own solubility value, in the value's own basis.

    ``products`` are catalogue records; their ``physicalProperties.waterSolubility`` is the
    first source, ``table`` (default: the historical table) the second. Status is ``ok``,
    ``exceeds`` (it blocks) or ``not_checked`` ("no solubility data"). ``product_grades`` is
    accepted for callers and does not select a value. No row approves a mixed stock.
    """
    ratio = _number(ratio, 'injection ratio', positive=True)
    temperature = _number(temperature_c, 'temperature')
    grades = {} if product_grades is None else product_grades
    if not isinstance(grades, Mapping):
        raise DeliveryError('invalid_solubility_input', 'product grades must be a mapping')
    rows = load_solubility_table() if table is None else table
    if not isinstance(rows, (list, tuple)):
        raise DeliveryError('invalid_solubility_table', 'table must be a sequence')
    records = {}
    for record in rows:
        if (
            not isinstance(record, Mapping)
            or not isinstance(record.get('product'), str)
            or not record['product'].strip()
            or record['product'] in records
            or not isinstance(record.get('source'), str)
            or not record['source'].strip()
        ):
            raise DeliveryError(
                'invalid_solubility_table', 'records need unique product names and sources'
            )
        if not _points(record.get('points')):
            raise DeliveryError('invalid_solubility_table', 'a record needs at least one point')
        records[record['product']] = record
    catalogue = _catalogue_records(products)
    found = []
    for tank in tanks:
        for product in tank.products:
            dose = _number(product.grams_per_litre, 'product dose')
            if dose < 0:
                raise DeliveryError('invalid_solubility_input', 'product dose must be nonnegative')
            stock = _number(dose * ratio, 'stock concentration')
            value = basis = source = source_t = None
            reason = NO_DATA
            own = catalogue.get(product.name)
            from_catalogue = _catalogue_source(own) if own else None
            if from_catalogue is not None:
                value, basis, source_t, why = from_catalogue
                source, reason = _source_label(own), f'{NO_DATA}: {why}' if why else reason
            if value is None and product.name in records:
                value, basis, source_t, why = _table_source(records[product.name], temperature)
                source, reason = records[product.name]['source'], why
            limit, status = None, 'not_checked'
            if value is not None:
                limit, status = value, 'exceeds' if stock > value else 'ok'
                reason = (
                    'above_single_product_limit'
                    if status == 'exceeds'
                    else 'within_single_product_limit'
                )
            found.append(
                SolubilityRow(
                    tank.name,
                    product.name,
                    stock,
                    limit,
                    status,
                    source,
                    reason,
                    basis,
                    source_t,
                    temperature,
                )
            )
    return found


def exceeds_message(row, temperature_c):
    """Describe a single-product exceedance, without claiming mixture dissolution failure."""
    if row.status != 'exceeds' or row.limit_g_per_l is None:
        raise DeliveryError(
            'unqualified_solubility_limit', 'only single-product exceedances have this message'
        )
    source_t = (
        'source temperature not stated'
        if row.source_temperature_c is None
        else f'{row.source_temperature_c:g} °C source'
    )
    return (
        f'{row.product} exceeds the recorded single-product limit in tank {row.tank}: '
        f'{row.stock_g_per_l:.4g} g/L needed, '
        f'{row.limit_g_per_l:.4g} g/L ({row.basis}; {source_t}, tank at {temperature_c:g} °C); '
        'mixture solubility is not established'
    )
