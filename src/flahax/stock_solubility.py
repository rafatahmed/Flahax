# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Source-qualified single-product screening, never mixed-stock dissolution approval.

Historical density-one values are conditional screening floors, not measured
limits. Exceeding a floor is inconclusive. No source value is silently converted,
interpolated or applied to a different grade.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path

from .delivery_contracts import DeliveryError

TABLE_PATH = Path(__file__).with_name('data') / 'solubility.json'
_HISTORICAL_SHA256 = '857c6f7b4aa7c73209b25b8848b5da4f66436c8b22814d650fd64a52cb0bf001'
SINGLE_SALT = (
    'single-product screening only; mixture solubility, common-ion effects, '
    'grade equivalence and preparation conditions require separate evidence'
)


@dataclass(frozen=True)
class SolubilityRow:
    """Reference comparison with explicit qualification; no mixture approval."""

    tank: str
    product: str
    stock_g_per_l: float
    limit_g_per_l: float | None
    status: str
    source: str | None
    screening_g_per_l: float | None = None
    reason: str | None = None
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
    """Load records; annotate only the byte-pinned historical table as assumed floors.

    Historical numeric values stay unchanged. The CALCINIT source supplies 20 C
    only; the earlier 20-to-40 C extension does not establish applicability.
    """
    path = Path(path)
    if not path.is_file():
        return []
    raw = path.read_bytes()
    records = json.loads(raw.decode('utf-8'))
    if hashlib.sha256(raw).hexdigest() == _HISTORICAL_SHA256:
        for record in records:
            record['qualification'] = {
                'kind': 'assumed_density_floor',
                'basis': 'g_product_per_l_solution',
                'interpolation': 'none',
                'reviewed': False,
                'reason': (
                    'historical_density_one_assumption; ' 'grade/density applicability unverified'
                ),
            }
            if record['product'] == 'Calcium Nitrate (ag grade)':
                record['qualification']['source_temperatures_c'] = [20.0]
    return records


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
    """Algebraic linear interpolation only; physical applicability must be checked separately."""
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


def _reference(record, temperature, grade):
    points = _points(record.get('points'))
    q = record.get('qualification')
    if not isinstance(q, Mapping) or q.get('basis') != 'g_product_per_l_solution':
        return None, 'missing_or_unsupported_basis', {}
    q = dict(q)
    kind = q.get('kind')
    if kind not in ('limit', 'lower_bound', 'assumed_density_floor'):
        return None, 'unknown_qualification', q
    if kind != 'assumed_density_floor':
        if (
            q.get('reviewed') is not True
            or not isinstance(q.get('review_id'), str)
            or not q['review_id'].strip()
        ):
            return None, 'unreviewed_source', q
        if (
            not isinstance(q.get('grade_id'), str)
            or not q['grade_id'].strip()
            or grade != q['grade_id']
        ):
            return None, 'grade_not_matched', q
    allowed = q.get('source_temperatures_c')
    if allowed is not None:
        if not isinstance(allowed, (list, tuple)):
            raise DeliveryError(
                'invalid_solubility_table', 'source temperatures must be a sequence'
            )
        allowed = [_number(t, 'source temperature') for t in allowed]
        if temperature not in allowed:
            return None, 'temperature_not_qualified', q
    exact = next((g for t, g in points if t == temperature), None)
    if exact is not None:
        return exact, None, q
    if (
        q.get('interpolation') != 'linear'
        or not isinstance(q.get('interpolation_review_id'), str)
        or not q['interpolation_review_id'].strip()
    ):
        return None, 'interpolation_not_qualified', q
    value = limit_at(points, temperature)
    return value, None if value is not None else 'temperature_outside_source', q


def check_stock_solubility(tanks, ratio, temperature_c, *, table=None, product_grades=None):
    """Compare each product with a qualified limit or a conditional screening value.

    Caller-reviewed limit/lower-bound records require matching product_grades.
    Source and grade review metadata are supplied by the caller, not authenticated
    here. Interpolation requires an explicit review ID; extrapolation is refused.
    Assumed floors never produce ok/exceeds. No row approves a mixed stock.
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
        _points(record.get('points'))
        records[record['product']] = record
    found = []
    for tank in tanks:
        for product in tank.products:
            dose = _number(product.grams_per_litre, 'product dose')
            if dose < 0:
                raise DeliveryError('invalid_solubility_input', 'product dose must be nonnegative')
            stock = _number(dose * ratio, 'stock concentration')
            record = records.get(product.name)
            value, reason, q = (
                (None, 'missing_source', {})
                if record is None
                else _reference(record, temperature, grades.get(product.name))
            )
            limit = screening = None
            if value is None:
                status = 'not_checked'
            elif q['kind'] == 'limit':
                limit = value
                status = 'exceeds' if stock > value else 'ok'
                reason = (
                    'above_single_product_limit'
                    if stock > value
                    else 'within_single_product_limit'
                )
            else:
                screening = value
                status = 'inconclusive' if stock > value else 'screening_only'
                reason = (
                    'above_floor_not_proven_failure'
                    if stock > value
                    else 'within_floor_not_mixture_approval'
                )
            found.append(
                SolubilityRow(
                    tank.name,
                    product.name,
                    stock,
                    limit,
                    status,
                    record['source'] if record else None,
                    screening,
                    reason,
                    q,
                )
            )
    return found


def exceeds_message(row, temperature_c):
    """Describe only a qualified limit exceedance, without claiming mixture dissolution failure."""
    if row.status != 'exceeds' or row.limit_g_per_l is None:
        raise DeliveryError(
            'unqualified_solubility_limit', 'only qualified limit exceedances have this message'
        )
    return (
        f'{row.product} exceeds the recorded single-product limit in tank {row.tank}: '
        f'{row.stock_g_per_l:.4g} g/L needed, '
        f'{row.limit_g_per_l:.4g} g/L at {temperature_c:g} °C; '
        'mixture solubility is not established'
    )
