"""Synthetic calibration demonstration, NOT a physical EC prediction dataset."""
from datetime import datetime, timezone

from flahax import VolumeLitres, ec_recipe_key, plan_ec_delivery
from .common import record, show
from .titration_and_stocks import run as stock_example


def inputs():
    stocks = stock_example()['stocks']
    profiles = []
    # Deliberately curved FICTIONAL data: do not reuse these numbers in a plant.
    for channel, slope, strengths in [('irrigation', 1.4, (0, .5, 1, 1.5)),
                                      ('tank:A', .35, (0, 50, 100, 150)),
                                      ('tank:B', .50, (0, 50, 100, 150))]:
        profiles.append(dict(schemaVersion='1', id='synthetic-'+channel,
            source='SYNTHETIC MATHEMATICAL TEST ONLY', revision='1',
            recordedAt='2026-09-28T00:00:00Z', protocol='Fictional rectangular grid; not measurements',
            channel=channel, water_source_id='synthetic-water', reference_temperature_c=25,
            recipe_key=ec_recipe_key(stocks, channel), points=[
                dict(water_ec_ms_cm=water, strength=strength,
                     ec_ms_cm=water+slope*strength/(1+.01*strength))
                for water in (.2, .8) for strength in strengths]))
    calibrations = {identity:record('pump-'+identity, channelId=identity,
        stockDensityKgPerL=1.1, testTemperatureC=25, flowLitresPerMinute=.1,
        standardDeviationLitresPerMinute=.001, validMinLitres=.01, validMaxLitres=2)
        for identity in ('A', 'B')}
    return stocks, profiles, calibrations


def run():
    stocks, profiles, pumps = inputs()
    plan = plan_ec_delivery(stocks, profiles=profiles, water_source_id='synthetic-water',
        water_ec_ms_cm=.5, pump_calibrations=pumps,
        available_volumes={'A':VolumeLitres(1), 'B':VolumeLitres(1)},
        as_of=datetime(2026, 9, 28, tzinfo=timezone.utc))
    tds = plan_ec_delivery(stocks, profiles=profiles, water_source_id='synthetic-water',
                           water_tds_ppm=250, tds_factor=.5)
    missing = plan_ec_delivery(stocks, profiles=[], water_source_id='synthetic-water', water_ec_ms_cm=.5)
    return dict(assumptions=['EC25 in mS/cm; TDS 250 ppm on factor 0.5 equals water EC 0.5 mS/cm.',
        'All EC grids, pump records and stock data are fictional demonstrations, NOT field predictions.',
        'Independent A/B and combined-mixture profiles; no linear EC concentration scaling.',
        'No separate acid addition is included in this EC recipe.',
        '100 L final batch; 1 L from each 100x tank. Injection ratio is per tank.',
        'Pump planning is not execution or approval; as_of date is fixed for reproducibility.'],
        stock_plan=stocks, calibration_profiles=profiles, pump_calibrations=pumps,
        ec_and_injection=plan, equivalent_tds_input=tds, missing_calibration=missing)


if __name__ == '__main__':
    show(run())
