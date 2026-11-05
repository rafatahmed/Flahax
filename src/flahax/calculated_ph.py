# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Charge-balanced pH from analytical totals, not nutrient ppm.

The caller supplies the closed-carbon/fixed-valence inventory. No missing ion,
alkalinity, CO2 reservoir or balancing salt is invented. The inner mass-action
model and phase policy are identical to the fixed-pH solver.
"""

import math
from collections.abc import Mapping, Sequence

from .aqueous_model import solve
from .delivery_contracts import DeliveryError


def calculate_equilibrium_ph(
    totals, *, phases, temperature_c=25.0, carbon_boundary='closed', residual_charge=0.0
):
    """Return AqueousResult at the net charge ``residual_charge`` within the Davies domain.

    ``residual_charge`` (eq/kg water) is the charge the measured water carried that no ion
    accounts for: the solve reproduces it instead of forcing zero, so a measured imbalance is
    neither hidden nor corrected with an invented ion (decision G11). Zero means a balanced
    solution. A nutrient table alone gives no carbon: the caller supplies the carbon inventory
    (``CO3-2``, zero for measured carbon-free water). Charge adjustment changes only pH.
    """
    if carbon_boundary != 'closed':
        raise DeliveryError(
            'unsupported_carbon_boundary',
            'calculated pH requires closed analytical inorganic carbon',
        )
    if not isinstance(totals, Mapping):
        raise DeliveryError('invalid_totals', 'analytical totals must be a mapping')
    if isinstance(temperature_c, bool) or temperature_c != 25:
        raise DeliveryError(
            'temperature_out_of_range', 'calculated pH requires the 25 C reaction set'
        )
    if (
        isinstance(residual_charge, bool)
        or not isinstance(residual_charge, (int, float))
        or not math.isfinite(residual_charge)
    ):
        raise DeliveryError('invalid_value', 'residual_charge must be finite (signed eq/kg water)')
    if isinstance(phases, (str, bytes)) or not isinstance(phases, Sequence):
        raise DeliveryError(
            'invalid_type', 'supply an explicit phase sequence, or [] for aqueous-only'
        )
    phases = tuple(phases)
    for value in totals.values():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise DeliveryError(
                'invalid_totals', 'analytical totals must be finite nonnegative numbers'
            )

    last = []

    def at(ph):
        # Warm-start from the previous pH step (#61); the bracket sequence is unchanged.
        last[:] = [
            solve(
                dict(totals),
                ph,
                phases=phases,
                temperature_c=temperature_c,
                start=last[0] if last else None,
            )
        ]
        return last[0]

    # Start near neutral to avoid unnecessarily evaluating extreme acidic/basic
    # states outside the Davies range. No out-of-domain solve is extrapolated.
    def off(result):
        return result.charge_balance - residual_charge

    middle = at(7.0)
    if off(middle) == 0:
        return middle
    direction = 1 if off(middle) > 0 else -1
    previous = middle
    bracket = None
    for index in range(1, 15):
        ph = 7.0 + direction * 0.5 * index
        current = at(ph)
        if off(current) == 0:
            return current
        if (off(previous) > 0) != (off(current) > 0):
            bracket = sorted((previous, current), key=lambda result: result.ph)
            break
        previous = current
    if bracket is None:
        raise DeliveryError(
            'ph_not_bracketed', 'no charge-balanced pH in the supported [0,14] interval'
        )
    low, high = bracket
    for _ in range(60):
        current = at((low.ph + high.ph) / 2)
        if abs(off(current)) <= 1e-12 and high.ph - low.ph <= 1e-7:
            return current
        if (off(current) > 0) == (off(low) > 0):
            low = current
        else:
            high = current
    raise DeliveryError('nonconvergent', 'calculated pH did not close charge balance')
