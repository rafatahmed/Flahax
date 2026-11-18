# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Observed boundary evidence, separate from the mineral with the
highest SI.
"""

from copy import deepcopy


def constraint_violations(recipe, required_records):
    """Read delivered-recipe checks without refitting or changing
    acceptance.
    """
    rounded = recipe['rounded_verification']
    check = recipe.get('uncertainty_verification', rounded)
    rows = []
    for name, limit in recipe.get('maximum_concentrations', {}).items():
        ranges = check.get('elemental_mg_l_ranges', {})
        value = ranges[name][1] if name in ranges else rounded.get('elemental_mg_l', {}).get(name)
        if value is not None and value > limit:
            rows.append(
                dict(
                    kind='nutrient_ceiling',
                    name=name,
                    value=value,
                    limit=limit,
                    units='mg/L',
                    required_comparison='<=',
                    basis='analytical_interval_upper' if name in ranges else 'rounded_inventory',
                    nutrient_reserve=deepcopy(recipe.get('nutrient_ceiling_reserve')),
                )
            )
    limit = check.get('si_required_below', rounded.get('si_required_below'))
    # An early nominal failure prevents uncertainty sampling; retain its
    # mineral evidence rather than replacing it with the generic
    # "nominal_recipe" flag.
    maxima = check.get('phase_maxima') or rounded.get('phase_maxima', {})
    for name, witness in maxima.items():
        if limit is not None and witness['si'] >= limit:
            rows.append(
                dict(
                    kind='mineral_saturation',
                    name=name,
                    value=witness['si'],
                    limit=limit,
                    units='SI',
                    required_comparison='<',
                    basis='sampled_phase_maximum',
                    witness=deepcopy(witness),
                )
            )
    assumptions = check.get('assumptions', {})
    for name, value_key, limit_key in (
        ('nutrient_ratios', 'worst_ratio_relative_error', 'ratio_relative_tolerance'),
        (
            'total_concentration',
            'worst_concentration_relative_error',
            'concentration_relative_tolerance',
        ),
    ):
        if name in check.get('failed_checks', []):
            rows.append(
                dict(
                    kind='inventory_tolerance',
                    name=name,
                    value=check.get(value_key),
                    limit=assumptions.get(limit_key),
                    units='relative deviation',
                    basis='analytical_interval_bound',
                    required_comparison='<=',
                    qualification='The underlying check retains its numerical guard.',
                )
            )
    represented = {
        'nutrient_limits',
        'sodium_chloride_limits',
        'saturation_margin',
        'nutrient_ratios',
        'total_concentration',
    }
    for name in check.get('failed_checks', []):
        if name not in represented:
            rows.append(
                dict(
                    kind='reported_check',
                    name=name,
                    value=False,
                    limit=True,
                    basis='recipe_verification',
                    witness=deepcopy(check.get('ph_failure_example')),
                )
            )
    if not rounded.get('rounding_within_tolerance', True):
        rows.append(
            dict(
                kind='rounding',
                name='rounding_within_tolerance',
                value=False,
                limit=True,
                basis='rounded_inventory',
                witness=deepcopy(rounded.get('nutrient_errors_mmol_l')),
            )
        )
    if not rounded.get('rounded_ph_in_range', True):
        rows.append(
            dict(
                kind='ph_interval',
                name='rounded_ph_in_range',
                value=rounded.get('rounded_ph'),
                limit=deepcopy(rounded.get('ph_range')),
                basis='source_relative_charge_bracket',
            )
        )
    for field, flag in required_records.items():
        if not recipe.get(flag, False):
            record = recipe.get(field, {})
            rows.append(
                dict(
                    kind='record_check',
                    name=field,
                    value=record.get('status', 'unverified'),
                    failures=deepcopy(record.get('failures', [])),
                    limit='passed',
                    basis='existing_record_assessment',
                )
            )
    return rows


def observed_limit(strength, cap, brackets, evaluated):
    """Explain only a sampled neighbouring failure, never infer global
    infeasibility.
    """
    scope = (
        'Violations at the adjacent evaluated failing candidate, not proof of a '
        'unique active constraint, global optimum or absence of alternative allocations.'
    )
    if strength == cap:
        return dict(status='search_cap', violations=[], qualification=scope)
    relevant = [b for b in brackets if b['passing_strength'] == strength]
    if not relevant:
        return dict(
            status='unknown',
            reason='no_refined_adjacent_failing_candidate',
            violations=[],
            qualification=scope,
        )
    bracket = min(relevant, key=lambda b: b['failing_strength'])
    row = evaluated[bracket['failing_strength']]
    violations = deepcopy(row.get('constraint_violations', []))
    return dict(
        status='identified' if violations else 'unknown',
        passing_strength=bracket['passing_strength'],
        failing_strength=bracket['failing_strength'],
        bracket_width=bracket['width'],
        violations=violations,
        reason=row.get('error_code') if not violations else None,
        qualification=scope,
    )
