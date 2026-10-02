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
