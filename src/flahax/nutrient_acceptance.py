# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Keep nutrient targets, incidental contributions and hard limits distinct."""

from .composition import validate_profile
from .requirement_fit import met


def assess_incidental(rows, maximum_concentrations=None):
    """Untargeted nutrients present in the solution and the limits exceeded; an incidental nutrient
    without a limit requires review. Explicit zero targets are hard zero limits,
    not incidental nutrients, met within 1e-6 mg/L (requirement_fit.met, G25). Declared maxima
    are compared directly without an absolute slack.
    """
    maximums = validate_profile(
        {} if maximum_concentrations is None else maximum_concentrations, 'maximum_concentrations'
    )
    zeros = {row['symbol'] for row in rows if row['target'] == 0}
    maximums.update({symbol: 0.0 for symbol in zeros})
    final = {row['symbol']: row['final'] for row in rows}
    violations = [
        {'symbol': ion, 'ppm': final.get(ion, 0.0), 'maximumPpm': limit}
        for ion, limit in maximums.items()
        if (not met(0.0, final.get(ion, 0.0)) if ion in zeros else final.get(ion, 0.0) > limit)
    ]
    incidental = []
    for row in rows:
        if row['target'] is not None or row['final'] <= 0:
            continue
        limit = maximums.get(row['symbol'])
        incidental.append(
            {
                'symbol': row['symbol'],
                'ppm': row['final'],
                'target': row['target'],
                'maximumPpm': limit,
                'assessment': 'requires_review'
                if limit is None
                else ('within_limit' if row['final'] <= limit else 'exceeds_limit'),
            }
        )
    return {
        'incidentalContributions': incidental,
        'limitViolations': violations,
        'requiresReview': any(row['assessment'] == 'requires_review' for row in incidental),
    }


def assessed_limits(maximum_concentrations, recommendation):
    """The user's maxima plus the N_NH4 allowance ``recommend`` applied when none was declared."""
    limits = dict(maximum_concentrations or {})
    allowance = recommendation.get('ammoniumLimit')
    if allowance and 'N_NH4' not in limits:
        limits['N_NH4'] = allowance['mgPerL']
    return limits


def name_sources(assessment, dosed, library, water=None):
    """Add ``source`` to each incidental row: the dosed products (and the water) that supply that
    nutrient.

    ``dosed`` is a recipe's ``salts`` ({id, name, gramsPerLitre}); ``library`` the product records.
    Formula counterion sodium (chelates, #84) names the product that carries it.
    """
    from .product_conversion import material_inventory

    records = {record.get('id'): record for record in library}
    for row in assessment['incidentalContributions']:
        names = []
        for item in dosed:
            record = records.get(item['id'])
            if record is None:
                continue
            if material_inventory(record)['nutrient_percent'].get(row['symbol'], 0) > 0:
                names.append(item['name'])
        if (water or {}).get(row['symbol'], 0) > 0:
            names.append('water')
        row['source'] = names
    return assessment


def assess_water_basis(rows, maximum_concentrations, analytical_ppm, modelled_ppm):
    """Limits whose decision the charge balancing alone would change (#84).

    ``rows`` are final concentrations on the laboratory basis (water analysis +
    products + reagent at the final volume). The modelled value swaps only the
    water's contribution for the charge-balanced one: same recipe, dose and
    volume. The decision stays on the laboratory basis; a disagreement is
    returned for review, never used to pass or fail a plan.
    """
    maximums = validate_profile(
        {} if maximum_concentrations is None else maximum_concentrations, 'maximum_concentrations'
    )
    final = {row['symbol']: row['final'] for row in rows}
    findings = []
    for ion, limit in sorted(maximums.items()):
        measured = final.get(ion, 0.0)
        modelled = measured - analytical_ppm.get(ion, 0.0) + modelled_ppm.get(ion, 0.0)
        if (measured > limit) != (modelled > limit):
            exceeds = measured > limit
            findings.append(
                {
                    'symbol': ion,
                    'maximumPpm': limit,
                    'analyticalPpm': measured,
                    'modelledPpm': modelled,
                    'decision': 'exceeds_limit' if exceeds else 'within_limit',
                    'message': (
                        f'{ion}: {measured:.4g} mg/L on the laboratory analysis is '
                        f'{"above" if exceeds else "within"} the {limit:g} mg/L maximum; the '
                        f'charge-balanced '
                        f'model gives {modelled:.4g} mg/L. The decision uses the laboratory '
                        f'value; '
                        'check the analysis.'
                    ),
                }
            )
    return findings
