"""Charge-balanced pH from declared complete analytical totals, not nutrient ppm.

The caller supplies the closed-carbon/fixed-valence inventory. No missing ion,
alkalinity, CO2 reservoir or balancing salt is invented. The inner mass-action
model and phase policy are identical to the fixed-pH solver.
"""
import math
from collections.abc import Mapping, Sequence

from .aqueous_model import solve
from .delivery_contracts import DeliveryError


def calculate_equilibrium_ph(totals, *, complete_analysis, carbon_boundary,
                             phases, temperature_c=25.):
    """Return AqueousResult at zero net charge within the existing Davies domain.

    Completeness is a caller declaration of analytical coverage, not a claim
    that the software can identify absent laboratory measurements. A nutrient
    table alone is not a complete analysis. Charge adjustment changes only pH.
    """
    if complete_analysis is not True:
        raise DeliveryError('incomplete_water_analysis', 'complete analytical totals must be explicitly declared')
    if carbon_boundary != 'closed':
        raise DeliveryError('unsupported_carbon_boundary', 'calculated pH requires closed analytical inorganic carbon')
    if not isinstance(totals, Mapping):
        raise DeliveryError('invalid_totals', 'analytical totals must be a mapping')
    if isinstance(temperature_c, bool) or temperature_c != 25:
        raise DeliveryError('temperature_out_of_range', 'calculated pH requires the 25 C reaction set')
    if isinstance(phases, (str, bytes)) or not isinstance(phases, Sequence):
        raise DeliveryError('invalid_type', 'supply an explicit phase sequence, or [] for aqueous-only')
    phases = tuple(phases)
    for value in totals.values():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise DeliveryError('invalid_totals', 'analytical totals must be finite nonnegative numbers')

    def at(ph):
        return solve(dict(totals), ph, phases=phases, temperature_c=temperature_c)

    # Start near neutral to avoid unnecessarily evaluating extreme acidic/basic
    # states outside the Davies range. No out-of-domain solve is extrapolated.
    middle = at(7.)
    if abs(middle.charge_balance) <= 1e-12:
        return middle
    direction = 1 if middle.charge_balance > 0 else -1
    previous = middle
    bracket = None
    for index in range(1, 15):
        ph = 7. + direction * .5 * index
        current = at(ph)
        if abs(current.charge_balance) <= 1e-12:
            return current
        if previous.charge_balance * current.charge_balance < 0:
            bracket = sorted((previous, current), key=lambda result: result.ph)
            break
        previous = current
    if bracket is None:
        raise DeliveryError('ph_not_bracketed', 'no charge-balanced pH in the supported [0,14] interval')
    low, high = bracket
    for _ in range(60):
        current = at((low.ph + high.ph) / 2)
        if abs(current.charge_balance) <= 1e-12 and high.ph - low.ph <= 1e-7:
            return current
        if current.charge_balance * low.charge_balance > 0:
            low = current
        else:
            high = current
    raise DeliveryError('nonconvergent', 'calculated pH did not close charge balance')
