"""No-new-measurements EC screening and equipment requirement arithmetic."""
from flahax import estimate_manufacturer_ec, size_injection_requirements
from .common import show


def run():
    doses = {'Ultrasol K Plus': .5, 'Ultrasol Calcium': .25, 'Ultrasol MKP': .1}
    return dict(assumptions=[
        'Separate illustrative SQM product mixture, NOT the pepper catalogue recipe.',
        'Manufacturer single-salt EC anchors, linear/additive pre-acid approximation; error unknown.',
        'Water EC25 0.5 mS/cm is an example user input, not standard water.',
        'No new EC measurements or fitted calibration profiles used.',
        'Injector flow requirement only; no model selection or physical stock compatibility approval.'],
        irrigation=estimate_manufacturer_ec(doses, water_ec_ms_cm=.5),
        stock_a=estimate_manufacturer_ec({'Ultrasol Calcium': 25}, water_ec_ms_cm=.5, channel='tank:A'),
        stock_b=estimate_manufacturer_ec({'Ultrasol K Plus': 50, 'Ultrasol MKP': 10},
                                        water_ec_ms_cm=.5, channel='tank:B'),
        sizing=size_injection_requirements(active_area_m2=2000, gross_depth_mm=5,
            duration_hours=2, equipment_type='dosatron',
            channels={n:dict(final_litres_per_stock_litre=100, available_stock_litres=100) for n in ('A','B')}))


if __name__ == '__main__':
    show(run())
