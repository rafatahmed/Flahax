# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""User-declared acceptable deviation ranges (contract Q24, Q26, Q28, Q30).

A range is a setting the user gives. No percentage is a default: with no setting there is
no range. A symmetric ``percent`` applies to every positive target; ``overrides`` set one
nutrient's shortage or excess side in percent or mg/L. A side nobody set is open. Ranges
exist only for positive targets: an explicit zero target is a hard zero and a range never
relaxes it, and a range never relaxes a declared maximum.

``mode`` is ``assess`` (classify the result against the ranges) or ``require`` (constrain
the search by them). The numerical criterion for being on a bound is the one used for a met
target, ``requirement_fit.RELATIVE_TOLERANCE``.
"""

import math
from collections.abc import Mapping

from .delivery_contracts import DeliveryError
from .requirement_fit import RELATIVE_TOLERANCE

MODES = ('assess', 'require')
SIDES = ('shortage', 'excess')
SIDE_FIELDS = {f'{side}_{unit}' for side in SIDES for unit in ('percent', 'mg_per_l')}
SETTING_FIELDS = {'percent', 'overrides', 'mode'}


def _amount(value, label):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise DeliveryError('invalid_value', f'{label} must be a finite number of at least 0')
    return float(value)


def normalize_ranges(spec):
    """The validated setting, or None when no range was asked for."""
    if spec is None:
        return None
    if not isinstance(spec, Mapping):
        raise DeliveryError('invalid_type', 'deviation_ranges must be a mapping')
    unknown = set(spec) - SETTING_FIELDS
    if unknown:
        raise DeliveryError(
            'unknown_field', f'deviation_ranges has unknown fields {sorted(unknown)}'
        )
    mode = spec.get('mode', 'assess')
    if mode not in MODES:
        raise DeliveryError('invalid_value', f'deviation_ranges mode must be one of {MODES}')
    percent = spec.get('percent')
    percent = None if percent is None else _amount(percent, 'percent')
    overrides = spec.get('overrides') or {}
    if not isinstance(overrides, Mapping):
        raise DeliveryError('invalid_type', 'overrides must map a nutrient to its sides')
    clean = {}
    for symbol, sides in overrides.items():
        if not isinstance(sides, Mapping):
            raise DeliveryError('invalid_type', f'the override for {symbol} must be a mapping')
        unknown = set(sides) - SIDE_FIELDS
        if unknown:
            raise DeliveryError(
                'unknown_field', f'the override for {symbol} has unknown fields {sorted(unknown)}'
            )
        for side in SIDES:
            if f'{side}_percent' in sides and f'{side}_mg_per_l' in sides:
                raise DeliveryError(
                    'invalid_value', f'{symbol} {side} is given in both percent and mg/L'
                )
        clean[symbol] = {k: _amount(v, f'{symbol} {k}') for k, v in sides.items()}
    return dict(percent=percent, overrides=clean, mode=mode)


def effective_ranges(spec, targets):
    """The range of each positive target the setting covers: ``symbol``, ``target``, ``low``,
    ``high`` (None for an open side) and how each side was set. Empty without a setting.
    """
    setting = normalize_ranges(spec)
    if setting is None:
        return []
    positive = {s: t for s, t in targets.items() if t > 0}
    for symbol in setting['overrides']:
        if symbol not in positive:
            raise DeliveryError(
                'range_without_positive_target',
                f'{symbol} has no positive target; a range never relaxes a zero target and '
                'cannot stand without one',
            )
    rows = []
    for symbol, target in positive.items():
        override = setting['overrides'].get(symbol, {})
        amounts, basis = {}, {}
        for side in SIDES:
            if f'{side}_percent' in override:
                amounts[side], basis[side] = (
                    target * override[f'{side}_percent'] / 100,
                    {'percent': override[f'{side}_percent']},
                )
            elif f'{side}_mg_per_l' in override:
                amounts[side], basis[side] = (
                    override[f'{side}_mg_per_l'],
                    {'mg_per_l': override[f'{side}_mg_per_l']},
                )
            elif setting['percent'] is not None:
                amounts[side], basis[side] = (
                    target * setting['percent'] / 100,
                    {'percent': setting['percent']},
                )
            else:
                amounts[side], basis[side] = None, None
        if amounts['shortage'] is None and amounts['excess'] is None:
            continue
        rows.append(
            dict(
                symbol=symbol,
                target=target,
                low=None
                if amounts['shortage'] is None
                else max(0.0, target - amounts['shortage']),
                high=None if amounts['excess'] is None else target + amounts['excess'],
                shortage=basis['shortage'],
                excess=basis['excess'],
            )
        )
    return rows


def classify(ranges, finals):
    """Where each final concentration sits against its range: ``inside``, ``below`` or
    ``above``, and by how many mg/L it is outside. A bound within the numerical criterion
    counts as inside.
    """
    rows = []
    for row in ranges:
        final = float(finals.get(row['symbol']) or 0.0)
        slack = RELATIVE_TOLERANCE * row['target']
        position, outside = 'inside', 0.0
        if row['low'] is not None and final < row['low'] - slack:
            position, outside = 'below', row['low'] - final
        elif row['high'] is not None and final > row['high'] + slack:
            position, outside = 'above', final - row['high']
        rows.append(
            dict(
                symbol=row['symbol'],
                target=row['target'],
                low=row['low'],
                high=row['high'],
                final=final,
                position=position,
                outsideBy=outside,
            )
        )
    return rows


REQUIRE_SCOPE = (
    'A candidate found by fitting with the upper bounds as hard maximums and extra weight on '
    'nutrients below their lower bound; not a proof that no recipe qualifies, and no range was '
    'widened.'
)


def assessment(spec, targets, finals):
    """The ``deviationRanges`` record for a result, or None without a setting."""
    setting = normalize_ranges(spec)
    if setting is None:
        return None
    ranges = effective_ranges(setting, targets)
    rows = classify(ranges, finals)
    outside = [r for r in rows if r['position'] != 'inside']
    return dict(
        mode=setting['mode'],
        percent=setting['percent'],
        effective=ranges,
        assessment=rows,
        allInside=not outside,
        requirement=None
        if setting['mode'] == 'assess'
        else dict(
            status='met' if not outside else 'search_incomplete',
            unmet=[
                dict(symbol=r['symbol'], position=r['position'], outsideBy=r['outsideBy'])
                for r in outside
            ],
            scope=REQUIRE_SCOPE,
        ),
    )
