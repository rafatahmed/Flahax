# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Sonneveld et al. (1999) A–D target design for soilless irrigation
feed.
"""

from datetime import date
import math

from .canonical_result import digest
from .composition import ATOMIC
from .delivery_contracts import DeliveryError

# Charge magnitudes on the paper's analytical basis. P represents H2PO4.
CATIONS = {'N_NH4': 1, 'K': 1, 'Ca': 2, 'Mg': 2}
ANIONS = {'P': 1, 'N_NO3': 1, 'S': 2}
MACROS = CATIONS.keys() | ANIONS.keys()
NUTRIENTS = MACROS | {'Fe', 'Mn', 'Zn', 'B', 'Cu', 'Mo'}


def _profile(values, label, *, signed=False, keys=NUTRIENTS):
    if not isinstance(values, dict) or not values.keys() <= keys:
        raise DeliveryError('invalid_value', f'{label} must map supported nutrients to mmol/L')
    for name, amount in values.items():
        if (
            type(amount) not in (int, float)
            or not math.isfinite(amount)
            or (not signed and amount < 0)
        ):
            raise DeliveryError('invalid_value', f'{label}.{name} has an invalid concentration')
    return dict(values)


def _charge(values, weights):
    return math.fsum(values[key] * valence for key, valence in weights.items())


def _rescale(values, weights, protected, target, stage):
    adjustable = {key: valence for key, valence in weights.items() if key != protected}
    remaining = target - values[protected]
    available = _charge(values, adjustable)
    if remaining < 0 or (available == 0 and remaining > 0):
        raise DeliveryError(
            'invalid_value', f'Column {stage} cannot balance {protected} with the requested charge'
        )
    factor = remaining / available if available else 0
    return {key: values[key] * factor for key in adjustable}


def _root_zone_feedback(sample, target_design, require_approval):
    required = {'sample_id', 'sampled_on', 'measured_mmol_l', 'guide_mmol_l'}
    if (
        not isinstance(sample, dict)
        or not required <= sample.keys()
        or sample.keys() - required - {'approval'}
        or not isinstance(sample['sample_id'], str)
        or not sample['sample_id'].strip()
    ):
        raise DeliveryError(
            'invalid_value', 'Supply a root-zone sample ID, date and nutrient profiles'
        )
    try:
        date.fromisoformat(sample['sampled_on'])
    except (ValueError, TypeError) as exc:
        raise DeliveryError('invalid_value', 'sampled_on must be an ISO calendar date') from exc
    measured = _profile(sample['measured_mmol_l'], 'measured_mmol_l')
    guides = _profile(sample['guide_mmol_l'], 'guide_mmol_l')
    paired = measured.keys() & guides.keys()
    if not paired:
        raise DeliveryError(
            'invalid_value', 'Supply at least one matching nutrient measurement and guide'
        )
    evidence = {
        'sample_id': sample['sample_id'],
        'sampled_on': sample['sampled_on'],
        'measured_mmol_l': measured,
        'guide_mmol_l': guides,
        'deviations_mmol_l': {key: measured[key] - guides[key] for key in sorted(paired)},
        'without_guide': sorted(measured.keys() - guides.keys()),
        'without_measurement': sorted(guides.keys() - measured.keys()),
    }
    fingerprint = digest({'sample': evidence, 'feed_design': target_design})
    evidence.update(design_sha256=fingerprint, status='awaiting_approval')
    if 'approval' not in sample:
        if require_approval:
            raise DeliveryError('invalid_value', 'Root-zone feedback requires grower approval')
        return evidence
    approval = sample['approval']
    fields = {'approved_by', 'reason', 'design_sha256'}
    if (
        not isinstance(approval, dict)
        or set(approval) != fields
        or any(not isinstance(approval[key], str) or not approval[key].strip() for key in fields)
    ):
        raise DeliveryError(
            'invalid_value', 'Approval must include a grower name, reason and design hash'
        )
    if approval['design_sha256'] != fingerprint:
        raise DeliveryError('invalid_value', 'Approval does not match this sample and feed design')
    return dict(evidence, status='approved', approval=dict(approval))


def design_targets(design, *, require_approval=False):
    """Return A–D in mmol/L and the full-precision finished-feed targets
    in elemental mg/L.

    Corrections are signed increments in mmol/L. Optional minimum_mmol_l
    values are enforced against D. The EC input sets the paper's
    empirical charge budget. Root-zone feedback is optional. Batch
    callers require its preview-bound approval.
    """
    required = {'baseline_mmol_l', 'adjustments_mmol_l', 'irrigation_ec_ds_m'}
    if (
        not isinstance(design, dict)
        or not required <= design.keys()
        or design.keys() - required - {'minimum_mmol_l', 'root_zone_feedback'}
    ):
        raise DeliveryError('invalid_value', 'Supply the Sonneveld baseline, corrections and EC')
    a = _profile(design['baseline_mmol_l'], 'baseline_mmol_l')
    if not MACROS <= a.keys():
        raise DeliveryError(
            'invalid_value', 'The baseline must declare all seven macronutrient ions'
        )
    b = _profile(design['adjustments_mmol_l'], 'adjustments_mmol_l', signed=True, keys=a.keys())
    minimum = _profile(design.get('minimum_mmol_l', {}), 'minimum_mmol_l', keys=a.keys())
    ec = design['irrigation_ec_ds_m']
    if type(ec) not in (int, float) or not math.isfinite(ec) or ec <= 0:
        raise DeliveryError('invalid_value', 'The irrigation EC must be finite and positive')

    a_cations, a_anions = _charge(a, CATIONS), _charge(a, ANIONS)
    if not math.isclose(a_cations, a_anions, rel_tol=0, abs_tol=1e-9):
        raise DeliveryError(
            'invalid_value', 'Column A requires equal positive and negative charge'
        )
    provisional = {key: amount + b.get(key, 0) for key, amount in a.items()}
    if any(value < 0 for value in provisional.values()):
        raise DeliveryError(
            'invalid_value', 'A requested correction gives a negative concentration'
        )

    c = provisional | _rescale(provisional, CATIONS, 'N_NH4', a_cations, 'C')
    c.update(_rescale(provisional, ANIONS, 'P', a_anions, 'C'))
    charge_target = 10 * ec
    d = c | _rescale(c, CATIONS, 'N_NH4', charge_target, 'D')
    d.update(_rescale(c, ANIONS, 'P', charge_target, 'D'))
    misses = sorted(key for key, value in minimum.items() if d[key] < value)
    if misses:
        raise DeliveryError(
            'invalid_value', 'Column D falls below the declared minimum for ' + ', '.join(misses)
        )
    result = {
        'columns_mmol_l': {'A': a, 'B': b, 'C': c, 'D': d},
        'charge_mmol_l': {
            name: {'cations': _charge(values, CATIONS), 'anions': _charge(values, ANIONS)}
            for name, values in (('A', a), ('C', c), ('D', d))
        },
        'minimum_mmol_l': minimum,
        'irrigation_ec_ds_m': ec,
        'targets_mg_l': {
            key: amount * ATOMIC['N' if key in ('N_NO3', 'N_NH4') else key]
            for key, amount in d.items()
        },
    }
    if 'root_zone_feedback' in design:
        result['root_zone_feedback'] = _root_zone_feedback(
            design['root_zone_feedback'], result, require_approval
        )
    return result
