# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Condition-qualified saturation findings; thermodynamics is not precipitation rate.

REVIEW-named phases (HAP, MnHPO4, Goethite, Vivianite) are qualifications at the
assessed state (#78): they yield review findings, not hard blocks, unless the SI
sign is unresolved or allocation is positive. Other positive SI still blocks.
Caller evidence envelopes can demote a hard phase to review-only when they match;
mixing is never approved here. No kinetic envelopes ship with the package.
"""

from collections.abc import Mapping
import math

from .delivery_contracts import DeliveryError

# Existing numerical comparison guard, not a kinetic or agronomic allowance.
SI_THRESHOLD = 1e-7
REVIEW = {
    'Hydroxylapatite': (
        'Condition-specific precursor/kinetic evidence requires review.',
        'Nancollas, Tomazic & Tomson (1976), Croat. Chem. Acta 48, 431-438.',
    ),
    'Goethite': (
        'Condition-specific transformation kinetics require review.',
        'Schwertmann & Murad (1983), doi:10.1346/CCMN.1983.0310405.',
    ),
    'MnHPO4': (
        'The measurement/source chain and its applicability remain unverified here.',
        'Ball & Nordstrom (1991), USGS OFR 91-183; Plummer et al. (1976), WRI 76-13.',
    ),
    'Vivianite': (
        'Oxidation-state and redox applicability require explicit evidence.',
        'Metz et al. (2024), Environ. Sci. Technol. 58, 15321; Rothe et al. (2016), '
        'Earth-Sci. Rev. 158, 51.',
    ),
}
FERROUS_IRON_ADVISORY = (
    'Iron(II) is represented at a fixed oxidation state. Actual redox conditions and '
    'holding time are required to assess oxidation and subsequent solids; no rate '
    'or absence of precipitation is established by this calculation.'
)
_REQUIRED_CONDITIONS = frozenset(
    {
        'temperature_c',
        'ph',
        'ionic_strength',
        'holding_time_hours',
        'redox',
        'matrix_id',
    }
)


def _applicability(phase, conditions, evidence):
    record = evidence.get(phase)
    if not isinstance(record, Mapping):
        return 'missing_evidence', None
    if (
        record.get('phase') != phase
        or record.get('reviewed') is not True
        or not isinstance(record.get('source'), str)
        or not record['source'].strip()
        or not isinstance(record.get('review_id'), str)
        or not record['review_id'].strip()
        or record.get('decision') != 'review_only'
    ):
        return 'unreviewed_evidence', None
    envelope = record.get('conditions')
    if not isinstance(envelope, Mapping) or not _REQUIRED_CONDITIONS <= envelope.keys():
        return 'incomplete_evidence_conditions', None
    for name, constraint in envelope.items():
        if name in {
            'temperature_c',
            'ph',
            'ionic_strength',
            'holding_time_hours',
        } and not isinstance(constraint, (list, tuple)):
            return 'invalid_evidence_conditions', record['review_id']
        if name in {'redox', 'matrix_id'} and (
            not isinstance(constraint, str)
            or constraint.strip().lower() in {'', 'unknown', 'unspecified'}
        ):
            return 'invalid_evidence_conditions', record['review_id']
        value = conditions.get(name)
        if value is None:
            return 'missing_conditions', record['review_id']
        if isinstance(constraint, (list, tuple)):
            if (
                len(constraint) != 2
                or any(
                    isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                    for v in constraint
                )
                or constraint[0] > constraint[1]
            ):
                return 'invalid_evidence_conditions', record['review_id']
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                return 'invalid_conditions', record['review_id']
            if not constraint[0] <= value <= constraint[1]:
                return 'outside_evidence_conditions', record['review_id']
        elif not isinstance(constraint, str) or not constraint:
            return 'invalid_evidence_conditions', record['review_id']
        elif value != constraint:
            return 'outside_evidence_conditions', record['review_id']
    return 'applicable_for_review', record['review_id']


def assess_saturation(state, *, conditions=None, evidence=None, si_uncertainty=None):
    """Return separate thermodynamic, applicability and allocation findings.

    Assess the supplied state (coupled plans pass the **target** pH state). Positive
    SI on a non-REVIEW phase blocks unless a caller-reviewed envelope matches every
    condition (review only; never mixing approval). REVIEW-named phases stay
    qualifications (#78 / Task 6): they populate ``review`` without hard-blocking.
    Unresolved SI sign, invalid indices, and every positive allocated solid still
    block. No envelopes ship by default. State pH/ionic strength override caller
    values when available. SI uncertainty is a nonnegative half-width in log10 units.
    """
    for value in (conditions, evidence, si_uncertainty):
        if value is not None and not isinstance(value, Mapping):
            raise DeliveryError('invalid_phase_evidence', 'phase evidence inputs must be mappings')
    conditions, evidence = dict(conditions or {}), evidence or {}
    for key, attribute in (('ph', 'ph'), ('ionic_strength', 'ionic_strength')):
        if hasattr(state, attribute):
            conditions[key] = getattr(state, attribute)
    uncertainties = si_uncertainty or {}
    for phase, width in uncertainties.items():
        if (
            phase not in state.saturation_indices
            or isinstance(width, bool)
            or not isinstance(width, (int, float))
            or not math.isfinite(width)
            or width < 0
        ):
            raise DeliveryError(
                'invalid_si_uncertainty',
                'SI half-width must be finite and nonnegative for a reported phase',
            )
    blocking, review, thermodynamic, applicability = [], [], {}, {}
    for phase, si in sorted(state.saturation_indices.items(), key=lambda item: item[0]):
        width = max(SI_THRESHOLD, uncertainties.get(phase, 0.0))
        valid = isinstance(si, (int, float)) and not isinstance(si, bool)
        if valid and si == -math.inf:
            thermodynamic[phase] = {'status': 'absent_reactant', 'interval': None}
            continue
        if not valid or not math.isfinite(si):
            thermodynamic[phase] = {'status': 'invalid_index', 'interval': None}
            blocking.append((phase, si))
            continue
        low, high = si - width, si + width
        if not math.isfinite(low) or not math.isfinite(high):
            thermodynamic[phase] = {'status': 'invalid_interval', 'interval': None}
            blocking.append((phase, si))
            continue
        sign = 'supersaturated' if low > 0 else 'undersaturated' if high < 0 else 'uncertain_sign'
        thermodynamic[phase] = {'status': sign, 'interval': (low, high)}
        if sign == 'undersaturated':
            continue
        status, review_id = _applicability(phase, conditions, evidence)
        applicability[phase] = {'status': status, 'review_id': review_id}
        reason = (
            'SI sign is unresolved within the numerical/declared interval.'
            if sign == 'uncertain_sign'
            else 'Thermodynamic supersaturation; ' + status.replace('_', ' ') + '.'
        )
        sources = (
            evidence[phase]['source']
            if status == 'applicable_for_review'
            else REVIEW.get(phase, ('', ''))[1]
        )
        review.append((phase, si, reason, sources))
        # Unresolved sign always blocks. REVIEW-class supersaturation is review-only
        # (#78). Matching evidence demotes other phases to review-only; otherwise block.
        if sign == 'uncertain_sign':
            blocking.append((phase, si))
        elif status == 'applicable_for_review' or phase in REVIEW:
            continue
        else:
            blocking.append((phase, si))
    solids = {}
    invalid_solids = []
    for phase, amount in state.precipitated.items():
        if (
            isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or not math.isfinite(amount)
            or amount < 0
        ):
            invalid_solids.append(phase)
        elif amount > 0:
            solids[phase] = amount
    totals = getattr(state, 'totals', None)
    advisories = (
        [FERROUS_IRON_ADVISORY]
        if isinstance(totals, Mapping) and totals.get('Fe+2', 0) > 0
        else []
    )
    return {
        'blocking': blocking,
        'review': review,
        'advisories': advisories,
        'solids': solids,
        'blocks': bool(blocking or solids or invalid_solids),
        'thermodynamic': thermodynamic,
        'applicability': applicability,
        'invalid_solids': invalid_solids,
        'mixing_approved': False,
    }


def describe(assessment):
    """One line per finding, including unresolved allocation data."""
    lines = [f'{p} SI {si} (blocks)' for p, si in assessment['blocking']]
    lines += [f'solid {p} allocated' for p in assessment['solids']]
    lines += [f'{p} SI {si:.2f} (review: {reason})' for p, si, reason, _ in assessment['review']]
    lines += [f'invalid solid allocation: {p}' for p in assessment.get('invalid_solids', ())]
    return lines
