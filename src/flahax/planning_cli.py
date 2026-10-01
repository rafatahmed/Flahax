"""JSON and interactive adapters; no standard water, acid grade or pump model."""
from dataclasses import asdict, is_dataclass
import json
import math
from pathlib import Path
import sys

from .delivery_contracts import DeliveryError
from .delivery_quantities import VolumeLitres, InjectionRatio, TemperatureCelsius
from .fertilizer_workflow import plan_fertilizer_workflow
from .stock_planning import StockTank
from .calculated_ec import estimate_manufacturer_ec
from .injector_sizing import size_injection_requirements


def serializable(value):
    if is_dataclass(value):
        return serializable(asdict(value))
    if isinstance(value, dict):
        return {k: serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def execute(command, payload):
    if not isinstance(payload, dict):
        raise DeliveryError('invalid_type', 'expected a JSON object')
    if command == 'ec':
        return estimate_manufacturer_ec(**payload)
    if command == 'size':
        return size_injection_requirements(**payload)
    if command != 'workflow':
        raise DeliveryError('unknown_command', 'expected workflow, ec or size')
    unknown = set(payload) - {'salts', 'targets', 'water', 'target_ph', 'final_volume_litres',
                              'stocks', 'equilibrium', 'acids', 'maximum_concentrations'}
    if unknown:
        raise DeliveryError('unknown_field', 'Unsupported workflow fields: ' + ', '.join(sorted(unknown)))
    required = ('salts', 'targets', 'water', 'target_ph', 'final_volume_litres')
    missing = [name for name in required if name not in payload]
    if missing:
        raise DeliveryError('missing_field', 'Required inputs: ' + ', '.join(missing))
    if not isinstance(payload['salts'], list) or not payload['salts']:
        raise DeliveryError('missing_field', 'salts must be a nonempty list of explicit product records')
    if not isinstance(payload['targets'], dict):
        raise DeliveryError('invalid_type', 'targets must be a nutrient mg/L map')
    stocks = payload.get('stocks')
    if stocks is not None:
        if not isinstance(stocks, dict):
            raise DeliveryError('invalid_type', 'stocks must be an object')
        stocks = dict(stocks)
        stocks['injection_ratio'] = InjectionRatio(stocks.pop('final_litres_per_stock_litre'))
        stocks['temperature'] = TemperatureCelsius(stocks.pop('temperature_c'))
        stocks['tanks'] = [StockTank(t['id'], VolumeLitres(t['capacity_litres'])) for t in stocks['tanks']]
    return plan_fertilizer_workflow(payload['salts'], payload['targets'], payload['water'],
        payload['target_ph'], final_volume=VolumeLitres(payload['final_volume_litres']),
        equilibrium=payload.get('equilibrium'), acids=payload.get('acids'), stocks=stocks,
        maximum_concentrations=payload.get('maximum_concentrations'))


def _ask(label, *, optional=False):
    print(label + (' [blank = unavailable/skip]' if optional else '') + ': ', end='', file=sys.stderr, flush=True)
    text = input().strip()
    if not text and not optional:
        raise DeliveryError('missing_field', label + ' is required; zero must be explicit')
    return text


def _json(label, *, optional=False):
    text = _ask(label + ' (JSON)', optional=optional)
    return json.loads(text) if text else None


def interactive(command):
    """Prompts go to stderr so stdout remains one machine-readable JSON result."""
    if command == 'workflow':
        path = _ask('Path to fertilizer JSON array (your actual product records)')
        payload = dict(salts=json.loads(Path(path).read_text(encoding='utf-8-sig')),
                       targets=_json('Crop targets in elemental mg/L; N_NO3 and N_NH4 as N'),
                       water=_json('YOUR water nutrients in mg/L; {} explicitly means all zero'),
                       target_ph=float(_ask('Target pH')),
                       final_volume_litres=float(_ask('Final irrigation solution volume L')))
        payload['maximum_concentrations'] = _json('Optional hard nutrient maxima mg/L', optional=True)
        payload['equilibrium'] = _json(
            'Complete water chemistry: water_totals mol/kg-water, water_mass_kg, water_analysis_id, '
            'complete_analysis, carbon_boundary, temperature_c, phases (see docs/site-planning.md)', optional=True)
        payload['acids'] = _json(
            'Acid selection: HNO3/H3PO4 products with assay/density/provenance and dose/nutrient limits '
            '(see docs/site-planning.md)', optional=True)
        payload['stocks'] = _json('Stock capacities, ratio, temperature and compatibility/solubility records '
                                '(see docs/site-planning.md)', optional=True)
        return payload
    if command == 'ec':
        payload = dict(doses_g_per_litre=_json('Exact SQM commercial product names mapped to FINAL g/L'))
        kind = _ask('Water input: ec or tds').lower()
        if kind == 'ec':
            payload['water_ec_ms_cm'] = float(_ask('Your source-water EC at 25 C, mS/cm'))
        elif kind == 'tds':
            payload['water_tds_ppm'] = float(_ask('Source-water meter TDS ppm'))
            payload['tds_factor'] = float(_ask('Meter TDS factor; no default'))
        else:
            raise DeliveryError('invalid_value', 'choose ec or tds')
        payload['temperature_c'] = float(_ask('Solution temperature C'))
        payload['channel'] = _ask('Location: irrigation or tank:<id>')
        payload['acid_added'] = _json('Has acid been added? true or false')
        return payload
    payload = dict(equipment_type=_ask('Equipment type: dosing_pump, venturi or dosatron'),
                   duration_hours=float(_ask('Irrigation duration hours')))
    mode = _ask('Volume basis: batch or area').lower()
    if mode == 'batch':
        payload['final_volume_litres'] = float(_ask('FINAL irrigation batch volume L (not stock tank capacity)'))
    elif mode == 'area':
        payload['active_area_m2'] = float(_ask('Concurrently irrigated area m2'))
        payload['gross_depth_mm'] = float(_ask('Gross applied irrigation depth mm'))
    else:
        raise DeliveryError('invalid_value', 'choose batch or area')
    payload['channels'] = _json('Channels A/B/acid: each has final_litres_per_stock_litre and available_stock_litres')
    return payload
