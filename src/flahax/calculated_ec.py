# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Manufacturer-anchor screening, not a concentrated-electrolyte model.

Source: SQM Ultrasol Macronutrients brochure, 165357805552.pdf, page 2.
Values are EC at 1 g/L and 25 C. Exact commercial names are intentional:
these coefficients must not silently replace generic catalogue identities.
"""

from collections.abc import Mapping

from .conductivity import _number, water_ec25
from .delivery_contracts import DeliveryError


SOURCE = {
    'file': 'docs/sources/165357805552.pdf',
    'page': 2,
    'sha256': '28a15230851581f66255fe45f67f6e3b580d88f5cfbbc65a7cb97a9c5171ad48',
    'reference_g_per_litre': 1.0,
    'reference_temperature_c': 25.0,
}
# The brochure prints 1.2 for Magsul, but this conflicts with the ion calculation.
# Retain that evidence without treating it as a usable or corrected anchor.
_DISPUTED = {
    'Ultrasol Magsul': {
        'status': 'disputed',
        'published_ec_ms_cm': 1.2,
        'reason': 'Published brochure value conflicts with chemistry calculations; unresolved.',
        'review': 'docs/site/evidence/source-sheet-review.md',
    },
}
_ANCHORS = {
    'Ultrasol K Plus': 1.3,
    'Ultrasol SOP': 1.5,
    'Ultrasol MKP': 0.7,
    'Ultrasol MAP': 0.9,
    'Ultrasol Calcium': 1.2,
    'Ultrasol Magnit': 0.9,
}


def estimate_manufacturer_ec(
    doses_g_per_litre,
    *,
    water_ec_ms_cm=None,
    water_tds_ppm=None,
    tds_factor=None,
    temperature_c=25,
    channel='irrigation',
    acid_added=False,
):
    """Approximate EC25 = source-water EC25 + sum(dose * brochure anchor).

    A no-new-measurements, pre-acid screening estimate. Linearity/additivity
    are assumptions, not manufacturer validation. A total fertilizer loading
    cap of 1 g/L is a conservative software policy, NOT a validated range.
    No uncertainty bound or model for concentrated A/B stocks is asserted.
    Unknown or disputed products never disappear into a falsely complete total.
    Positive Magsul doses return disputed_product_ec_evidence; its published
    value is retained as disputed evidence, not replaced by a model prediction.
    """
    if not isinstance(doses_g_per_litre, Mapping):
        raise DeliveryError('invalid_type', 'doses must map exact commercial product names to g/L')
    if any(not isinstance(k, str) or not k.strip() for k in doses_g_per_litre):
        raise DeliveryError('invalid_value', 'product names must be nonempty strings')
    doses = {k: _number(v, 'product g/L') for k, v in doses_g_per_litre.items()}
    water = water_ec25(ec_ms_cm=water_ec_ms_cm, tds_ppm=water_tds_ppm, tds_factor=tds_factor)
    _number(temperature_c, 'temperature')
    if not isinstance(acid_added, bool):
        raise DeliveryError('invalid_type', 'acid_added must be boolean')
    if channel != 'irrigation' and not (
        isinstance(channel, str) and channel.startswith('tank:') and len(channel) > 5
    ):
        raise DeliveryError('unknown_channel', 'expected irrigation or tank:<id>')
    disputed = {k: dict(_DISPUTED[k]) for k, v in doses.items() if v > 0 and k in _DISPUTED}
    missing = sorted(
        k for k, v in doses.items() if v > 0 and k not in _ANCHORS and k not in _DISPUTED
    )
    result = dict(
        status='screening_estimate',
        ec_ms_cm=None,
        uncertainty_ms_cm=None,
        uncertainty_components={
            'numerical': {'status': 'not_quantified', 'bound_ms_cm': None},
            'input': {'status': 'not_propagated', 'bound_ms_cm': None},
            'model': {'status': 'unvalidated_additivity', 'bound_ms_cm': None},
        },
        water_ec_ms_cm=water,
        channel=channel,
        source=dict(SOURCE),
        model='manufacturer-anchor-additive-screening-v1',
        doses_g_per_litre=doses,
        missing_products=missing,
        disputed_products=disputed,
        assumptions=[
            'Pre-acid; no precipitation or speciation corrections.',
            'Linear dose scaling and additive EC; unvalidated mixture approximation.',
            'Water EC represents this source at 25 C; its composition is not inferred.',
            'No numerical accuracy guarantee; not an equipment-control setpoint.',
        ],
    )
    reason = None
    if disputed:
        reason = 'disputed_product_ec_evidence'
    elif temperature_c != 25:
        reason = 'temperature_outside_reference'
    elif channel != 'irrigation':
        reason = 'concentrated_stock_model_unavailable'
    elif acid_added:
        reason = 'acid_reaction_model_unavailable'
    elif missing:
        reason = 'missing_product_ec_evidence'
    elif sum(doses.values()) > 1:
        reason = 'loading_outside_screening_policy'
    if reason:
        result.update(status='not_supported', error_code=reason)
        return result
    result['contributions_ms_cm'] = {k: v * _ANCHORS[k] for k, v in doses.items() if v > 0}
    result['ec_ms_cm'] = _number(
        water + sum(result['contributions_ms_cm'].values()), 'estimated EC'
    )
    return result
