# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The precipitation screen: risk by evidence, information otherwise (decisions G12-G14).

A supersaturated phase is not a predicted precipitate: thermodynamics says nothing of rate.
The phases known to form readily mark the recipe with a precipitation risk. Every other
supersaturated phase is reported as information with the basis of its constant. Nothing
here refuses a candidate or a plan.
"""

from collections.abc import Mapping
import math

# Numerical comparison guard, not a kinetic or agronomic allowance.
SI_THRESHOLD = 1e-7
# Known to form readily in a feed. Gypsum is here only to detect the by-product of bad mixing
# in the final solution; it is never an input, a product, a reference value or a remedy.
RISK_PHASES = ('CaHPO4:2H2O', 'Gypsum', 'Calcite')
DATABASE_BASIS = 'database constant (minteq.v4), not individually reviewed'
CONSTANT_BASIS = {'MnHPO4': 'unmeasured constant (Plummer et al. 1976 program data)'}
FERROUS_IRON_ADVISORY = (
    'Iron(II) is held at a fixed oxidation state; in an aerated tank it oxidizes.'
)


def _is_real_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def assess_saturation(state):
    """The precipitation screen of one solved state.

    ``risk``: (phase, SI) of each readily forming phase above saturation, and of each allocated
    solid. ``information``: (phase, SI, basis of its constant) of every other supersaturated
    phase. ``advisories``: notes on the model's fixed redox state. ``solids``: the allocated
    solids by amount. There is no blocking: a risk is a label and a warning.
    """
    risk, information = [], []
    for phase, si in sorted(state.saturation_indices.items(), key=lambda item: item[0]):
        if not _is_real_number(si) or not math.isfinite(si) or si <= SI_THRESHOLD:
            continue
        if phase in RISK_PHASES:
            risk.append((phase, si))
        else:
            information.append((phase, si, CONSTANT_BASIS.get(phase, DATABASE_BASIS)))
    solids = {
        phase: amount
        for phase, amount in state.precipitated.items()
        if _is_real_number(amount) and math.isfinite(amount) and amount > 0
    }
    risk += [(phase, 0.0) for phase in solids if phase not in dict(risk)]
    totals = getattr(state, 'totals', None)
    advisories = (
        [FERROUS_IRON_ADVISORY]
        if isinstance(totals, Mapping) and totals.get('Fe+2', 0) > 0
        else []
    )
    return {'risk': risk, 'information': information, 'advisories': advisories, 'solids': solids}


def risk_warnings(assessment):
    """The warning sentence of each risk, as a recipe's label reads."""
    return [f'The recipe carries a {line}.' for line in describe(assessment)]


def describe(assessment):
    """One line per risk: a readily forming phase above saturation, or an allocated solid."""
    solids = assessment['solids']
    lines = [
        f'precipitation risk: {p} SI {si:.2f}' for p, si in assessment['risk'] if p not in solids
    ]
    return lines + [f'precipitation risk: solid {p} allocated' for p in solids]
