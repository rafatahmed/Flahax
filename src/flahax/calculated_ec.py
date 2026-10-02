"""Manufacturer-anchor screening, not a concentrated-electrolyte model.

Source: SQM Ultrasol Macronutrients brochure, 165357805552.pdf, page 2.
Values are EC at 1 g/L and 25 C. Exact commercial names are intentional:
these coefficients must not silently replace generic catalogue identities.
"""
from collections.abc import Mapping

from .conductivity import _number, water_ec25
from .delivery_contracts import DeliveryError


SOURCE = {
    'file': 'docs/sources/165357805552.pdf', 'page': 2,
    'sha256': '28a15230851581f66255fe45f67f6e3b580d88f5cfbbc65a7cb97a9c5171ad48',
    'reference_g_per_litre': 1.0, 'reference_temperature_c': 25.0,
}
# Reviewed against the rendered table, not OCR. Magsul is 1.2, not 0.9.
_ANCHORS = {'Ultrasol K Plus': 1.3, 'Ultrasol SOP': 1.5,
            'Ultrasol MKP': .7, 'Ultrasol MAP': .9,
            'Ultrasol Calcium': 1.2, 'Ultrasol Magsul': 1.2,
            'Ultrasol Magnit': .9}


def estimate_manufacturer_ec(doses_g_per_litre, *, water_ec_ms_cm=None,
                             water_tds_ppm=None, tds_factor=None,
                             temperature_c=25, channel='irrigation',
                             acid_added=False):
    """Approximate EC25 = source-water EC25 + sum(dose * brochure anchor).

    A no-new-measurements, pre-acid screening estimate. Linearity/additivity
    are assumptions, not manufacturer validation. A total fertilizer loading
    cap of 1 g/L is a conservative software policy, NOT a validated range.
    No uncertainty bound or model for concentrated A/B stocks is asserted.
    Unknown products never disappear into a falsely complete total.
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
    if channel != 'irrigation' and not (isinstance(channel, str) and channel.startswith('tank:') and len(channel) > 5):
        raise DeliveryError('unknown_channel', 'expected irrigation or tank:<id>')
    missing = sorted(k for k, v in doses.items() if v > 0 and k not in _ANCHORS)
    result = dict(status='screening_estimate', ec_ms_cm=None, uncertainty_ms_cm=None,
                  water_ec_ms_cm=water, channel=channel, source=dict(SOURCE),
                  model='manufacturer-anchor-additive-screening-v1',
                  doses_g_per_litre=doses, missing_products=missing,
                  assumptions=['Pre-acid; no precipitation or speciation corrections.',
                               'Linear dose scaling and additive EC; unvalidated mixture approximation.',
                               'Water EC represents this source at 25 C; its composition is not inferred.',
                               'No numerical accuracy guarantee; not an equipment-control setpoint.'])
    reason = None
    if temperature_c != 25:
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
    result['ec_ms_cm'] = _number(water + sum(result['contributions_ms_cm'].values()), 'estimated EC')
    return result
