# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Whether a calculated result meets a declared requirement, under the numerical tolerance (G25).

A requirement is met only within the precision of the calculation: 1e-5 relative for a positive
nutrient target, 1e-6 mg/L for a declared zero, 1e-4 pH units. These are numerical tolerances,
validated against an exact reference on 2026-10-24 (decision G25); they are never agronomic
ranges and never widened to absorb a result. Anything beyond them is a deviation, and it is
reported. They replace the former 1 % band.
"""

RELATIVE_TOLERANCE = 1e-5
ZERO_TARGET_TOLERANCE_MG_PER_L = 1e-6
PH_TOLERANCE = 1e-4


def met(target: float, final: float) -> bool:
    """True when ``final`` meets ``target`` (mg/L) within the numerical tolerance: relative for a
    positive target, absolute for a declared zero."""
    if target > 0:
        return abs(final - target) <= RELATIVE_TOLERANCE * target
    return abs(final - target) <= ZERO_TARGET_TOLERANCE_MG_PER_L
