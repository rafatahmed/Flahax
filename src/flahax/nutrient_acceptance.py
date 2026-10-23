# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Keep nutrient targets, incidental contributions and hard limits distinct."""

from .composition import validate_profile


def assess_incidental(rows, maximum_concentrations=None):
    maximums = validate_profile(
        {} if maximum_concentrations is None else maximum_concentrations, 'maximum_concentrations'
    )
    final = {row['symbol']: row['final'] for row in rows}
    violations = [
        {'symbol': ion, 'ppm': final.get(ion, 0.0), 'maximumPpm': limit}
        for ion, limit in maximums.items()
        if final.get(ion, 0.0) > limit + 1e-12
    ]
    incidental = []
    for row in rows:
        if row['target'] not in (None, 0) or row['final'] <= 1e-12:
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
                else ('within_limit' if row['final'] <= limit + 1e-12 else 'exceeds_limit'),
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
    """Add ``source`` to each incidental row: the dosed products (and the water) that supply that nutrient.

    ``dosed`` is a recipe's ``salts`` ({id, name, gramsPerLitre}); ``library`` the product records.
    Formula counterion sodium (chelates, #84) names the product that carries it.
    """
    from .product_conversion import counterion_sodium_mg_per_l

    records = {record.get('id'): record for record in library}
    for row in assessment['incidentalContributions']:
        names = []
        for item in dosed:
            record = records.get(item['id'])
            if record is None:
                continue
            if row['symbol'] in record.get('elements', {}) or (
                row['symbol'] == 'Na'
                and counterion_sodium_mg_per_l([(record, item['gramsPerLitre'])]) > 0
            ):
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
        if (measured > limit + 1e-12) != (modelled > limit + 1e-12):
            exceeds = measured > limit + 1e-12
            findings.append(
                {
                    'symbol': ion,
                    'maximumPpm': limit,
                    'analyticalPpm': measured,
                    'modelledPpm': modelled,
                    'decision': 'exceeds_limit' if exceeds else 'within_limit',
                    'message': (
                        f'{ion}: {measured:.4g} mg/L on the laboratory analysis is '
                        f'{"above" if exceeds else "within"} the {limit:g} mg/L maximum; the charge-balanced '
                        f'model gives {modelled:.4g} mg/L. The decision uses the laboratory value; '
                        'check the analysis.'
                    ),
                }
            )
    return findings
