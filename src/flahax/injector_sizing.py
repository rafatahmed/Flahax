"""Volume/flow design requirements; no fabricated equipment curves or control."""
from collections.abc import Mapping

from .conductivity import _number
from .delivery_contracts import DeliveryError


def size_injection_requirements(*, duration_hours, channels, equipment_type,
                                final_volume_litres=None, active_area_m2=None,
                                gross_depth_mm=None):
    """Use final batch volume OR active irrigated area * gross depth.

    Channel fields: final_litres_per_stock_litre, available_stock_litres.
    Ratios use FINAL volume, not motive-water volume; output both definitions.
    One mm over one m2 is one litre. Area is the concurrently irrigated zone,
    not necessarily the whole farm. Gross depth already includes losses.
    """
    if equipment_type not in ('dosing_pump', 'venturi', 'dosatron'):
        raise DeliveryError('unknown_equipment_type', 'choose dosing_pump, venturi or dosatron')
    hours = _number(duration_hours, 'duration hours', positive=True)
    area_mode = active_area_m2 is not None or gross_depth_mm is not None
    if (final_volume_litres is not None) == area_mode:
        raise DeliveryError('ambiguous_volume', 'supply batch volume OR active area and gross depth')
    volume = (_number(active_area_m2, 'active area m2', positive=True) *
              _number(gross_depth_mm, 'gross depth mm', positive=True)) if area_mode else final_volume_litres
    volume = _number(volume, 'final volume L', positive=True)
    if not isinstance(channels, Mapping) or not channels:
        raise DeliveryError('missing_field', 'at least one channel is required')
    results = {}
    for name, spec in channels.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(spec, Mapping):
            raise DeliveryError('invalid_type', 'channels must map nonempty names to records')
        ratio = _number(spec.get('final_litres_per_stock_litre'), 'final L / stock L', positive=True)
        available = _number(spec.get('available_stock_litres'), 'available prepared stock L')
        dose = _number(volume / ratio, 'required stock L', positive=True)
        results[name] = dict(required_stock_litres=dose,
                             required_flow_litres_per_hour=_number(dose / hours, 'stock flow L/h', positive=True),
                             final_litres_per_stock_litre=ratio,
                             stock_percent_of_final=100 / ratio,
                             available_stock_litres=available,
                             inventory_sufficient=available >= dose)
    stock_volume = sum(r['required_stock_litres'] for r in results.values())
    if stock_volume >= volume:
        raise DeliveryError('invalid_ratio', 'combined injected stock must be less than final volume')
    carrier = volume - stock_volume
    for record in results.values():
        record['stock_percent_of_common_carrier'] = record['required_stock_litres'] / carrier * 100
    return dict(status='sized' if all(r['inventory_sufficient'] for r in results.values()) else 'insufficient_stock',
                equipment_type=equipment_type, final_volume_litres=volume,
                duration_hours=hours,
                final_flow_litres_per_hour=_number(volume / hours, 'final flow L/h', positive=True),
                carrier_water_litres=carrier, channels=results,
                model_selection_status='needs_manufacturer_operating_point', selected_model=None,
                required_for_model_selection=['inlet and downstream pressure; available pressure differential',
                    'minimum/maximum operating flow, bypass layout and injection locations',
                    'stock density, viscosity, temperature, suction lift and chemical compatibility',
                    'manufacturer liquid performance curves, turndown and operating limits'],
                assumptions=['Constant flow during the stated irrigation period; no automatic device operation.',
                    'Prepared stock inventory is not tank nominal capacity.',
                    'Common-carrier ratio is not a setting for serial injectors; their local flows differ.'])
