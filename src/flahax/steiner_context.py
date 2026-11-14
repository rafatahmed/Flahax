"""Historical source evidence and advisory coverage, separate from chemical acceptance."""

import copy
import json
import math
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def _article():
    return json.loads(
        files('flahax').joinpath('data/steiner_1961_evidence.json').read_text(encoding='utf-8')
    )


def article_evidence():
    """Return an independent copy of the cited source statements and ambiguities."""
    return copy.deepcopy(_article())


def historical_context(*, strength_range, ph_range, cation_shares, anion_shares):
    """Describe source coverage without fitting pH or changing a solver acceptance gate.

    Inputs are validated recipe/search quantities. Range warnings are conservative
    historical applicability notices, not a new validated chemistry domain.
    """
    low, high = strength_range
    ph_low, ph_high = ph_range
    warnings = []

    def warn(code, message):
        warnings.append({'code': code, 'message': message})

    def near(a, b):
        return math.isclose(a, b, rel_tol=0, abs_tol=1e-9)
    if low < 20 and not near(low, 20):
        warn(
            'below_historical_tested_strength',
            'This strength range extends below 20 mmol/L. Steiner reported no tests there; '
            'a FlahaX numerical pass is not validation by the historical curves.',
        )
    if low <= 20 <= high or near(low, 20) or near(high, 20):
        warn(
            'limited_20_mmol_l_evidence',
            'Only limited additional tests at 20 mmol/L were reported, with unspecified '
            'accuracy; this is not the main 30 mmol/L calibration.',
        )
    if high > 20 and low < 30 and not (near(high, 20) or near(low, 30)):
        warn(
            'untested_strength_interpolation',
            'The paper does not validate a continuous concentration domain between its '
            'limited 20 mmol/L tests and main 30 mmol/L study.',
        )
    if high > 30 and not near(high, 30):
        warn(
            'above_main_historical_strength',
            'Above 30 mmol/L the paper reports restricted feasibility. Its few possible '
            'mixtures around 42 mmol/L are not general higher-strength validation.',
        )
    if ph_low < 5:
        warn(
            'ph_below_investigated_curves',
            'Part of this pH interval is below 5.0, where Figure 6 relationships were '
            'not investigated; discussion of lower-pH behavior is not curve validation.',
        )
    if ph_high > 7:
        warn(
            'reduced_precision_above_ph_7',
            'Above pH 7 the author reports reduced precision, approximately ±0.20, only '
            'within feasible curve coverage. This does not validate the requested upper pH.',
        )
    if cation_shares[1] == 0 or anion_shares[1] == 0:
        warn(
            'historical_calcium_phosphate_exclusion',
            'Steiner explicitly excludes mixtures without calcium or phosphate from '
            'the empirical method, even if the separate numerical model returns a recipe.',
        )
    warn(
        'curve_specific_coverage_unverified',
        'Historical pH coverage depends on K:Ca and composition, with precipitation '
        'exclusions even inside the curves. No universal upper pH or numeric extreme-ratio '
        'cutoff is supplied; source applicability to this recipe is not certified.',
    )
    warn(
        'historical_precision_not_model_uncertainty',
        'The article precision bands are historical claims, not FlahaX error bounds, '
        'measurement uncertainty or a reason to relax the requested pH/saturation limits.',
    )
    return {
        'schema_version': 1,
        'article': article_evidence(),
        'assessed_strength_range_mmol_l': list(strength_range),
        'assessed_ph_range': list(ph_range),
        'establishes_experimental_validation': False,
        'affects_numerical_acceptance': False,
        'warnings': warnings,
    }


def recipe_historical_context(recipe):
    """Include ideal, rounded and available uncertainty strengths in source notices."""
    strengths = [recipe['counted_mmol_l']]
    rounded = recipe.get('rounded_verification', {})
    if rounded.get('counted_mmol_l') is not None:
        strengths.append(rounded['counted_mmol_l'])
    uncertainty = recipe.get('uncertainty_verification', {}).get('counted_mmol_l_range')
    if uncertainty is not None:
        strengths.extend(v for v in uncertainty if math.isfinite(v))
    return historical_context(
        strength_range=[min(strengths), max(strengths)],
        ph_range=rounded.get('ph_range', [recipe['target_ph'], recipe['target_ph']]),
        cation_shares=recipe['cation_percent'],
        anion_shares=recipe['anion_percent'],
    )
