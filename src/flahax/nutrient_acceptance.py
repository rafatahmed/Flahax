"""Keep nutrient targets, incidental contributions and hard limits distinct."""
from .composition import validate_profile


def assess_incidental(rows, maximum_concentrations=None):
    maximums = validate_profile({} if maximum_concentrations is None else maximum_concentrations,
                                'maximum_concentrations')
    final = {row['symbol']: row['final'] for row in rows}
    violations = [{'symbol': ion, 'ppm': final.get(ion, 0.), 'maximumPpm': limit}
                  for ion, limit in maximums.items() if final.get(ion, 0.) > limit + 1e-12]
    incidental = []
    for row in rows:
        if row['target'] not in (None, 0) or row['final'] <= 1e-12:
            continue
        limit = maximums.get(row['symbol'])
        incidental.append({'symbol': row['symbol'], 'ppm': row['final'],
                           'target': row['target'], 'maximumPpm': limit,
                           'assessment': 'requires_review' if limit is None else
                           ('within_limit' if row['final'] <= limit + 1e-12 else 'exceeds_limit')})
    return {'incidentalContributions': incidental, 'limitViolations': violations,
            'requiresReview': any(row['assessment'] == 'requires_review' for row in incidental)}


def assess_water_basis(rows, maximum_concentrations, analytical_ppm, modelled_ppm):
    """Limits whose decision the charge balancing alone would change (#84).

    ``rows`` are final concentrations on the laboratory basis (water analysis +
    products + reagent at the final volume). The modelled value swaps only the
    water's contribution for the charge-balanced one: same recipe, dose and
    volume. The decision stays on the laboratory basis; a disagreement is
    returned for review, never used to pass or fail a plan.
    """
    maximums = validate_profile({} if maximum_concentrations is None else maximum_concentrations,
                                'maximum_concentrations')
    final = {row['symbol']: row['final'] for row in rows}
    findings = []
    for ion, limit in sorted(maximums.items()):
        measured = final.get(ion, 0.)
        modelled = measured - analytical_ppm.get(ion, 0.) + modelled_ppm.get(ion, 0.)
        if (measured > limit + 1e-12) != (modelled > limit + 1e-12):
            exceeds = measured > limit + 1e-12
            findings.append({
                'symbol': ion, 'maximumPpm': limit, 'analyticalPpm': measured, 'modelledPpm': modelled,
                'decision': 'exceeds_limit' if exceeds else 'within_limit',
                'message': (f'{ion}: {measured:.4g} mg/L on the laboratory analysis is '
                            f'{"above" if exceeds else "within"} the {limit:g} mg/L maximum; the charge-balanced '
                            f'model gives {modelled:.4g} mg/L. The decision uses the laboratory value; '
                            'check the analysis.')})
    return findings
