"""Recipe-matched empirical EC at 25 C; no universal concentrated-stock law.

Calibration surfaces contain measured TOTAL EC, not additive ion contributions.
Interpolation is bounded in water EC and recipe strength. A missing profile
never becomes a fabricated prediction. No device I/O or EC-driven reformulation.
"""
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import math

from .delivery_contracts import DeliveryError
from .stock_planning import StockPlan
from .delivery_quantities import VolumeLitres
from .pump_planning import plan_pump_command
from .engine import load_library


def _number(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DeliveryError('invalid_value', f'{name} must be a finite number')
    if value < 0 or (positive and value == 0):
        raise DeliveryError('out_of_range', f'{name} must be nonnegative (positive where required)')
    return float(value)


def water_ec25(*, ec_ms_cm=None, tds_ppm=None, tds_factor=None):
    """TDS is a meter-equivalent value: ppm = factor * EC in microS/cm.

    No conversion of gravimetrically measured dissolved-solids mass is implied.
    """
    if (ec_ms_cm is None) == (tds_ppm is None):
        raise DeliveryError('ambiguous_ec_input', 'supply exactly one water EC or meter TDS reading')
    if ec_ms_cm is not None:
        if tds_factor is not None:
            raise DeliveryError('ambiguous_ec_input', 'TDS factor applies only to TDS input')
        return _number(ec_ms_cm, 'water EC mS/cm')
    factor = _number(tds_factor, 'explicit meter TDS factor', positive=True)
    return _number(_number(tds_ppm, 'meter TDS ppm') / factor / 1000, 'converted EC')


def _recipe(stocks, channel):
    if not isinstance(stocks, StockPlan):
        raise DeliveryError('invalid_type', 'stocks must be a StockPlan')
    doses = {salt.salt_id: dict(name=salt.name, grams_per_litre=salt.dose.value)
             for salt in stocks.recipe.salts}
    if len(doses) != len(stocks.recipe.salts):
        raise DeliveryError('inconsistent_recipe', 'duplicate recipe product IDs')
    if channel != 'irrigation':
        tanks = [tank for tank in stocks.tanks if 'tank:' + tank.tank.tank_id == channel]
        if len(tanks) != 1:
            raise DeliveryError('unknown_channel', 'expected irrigation or tank:<id>')
        if any(salt.salt_id not in doses for salt in tanks[0].salts):
            raise DeliveryError('inconsistent_recipe', 'stock references a product absent from the recipe')
        doses = {salt.salt_id: doses[salt.salt_id] for salt in tanks[0].salts}
    return doses


def ec_recipe_key(stocks, channel='irrigation', *, reagent_doses_g_per_l=None):
    """Bind calibration to dose, identity, shipped assays and separate reagents.

    Changing a product, dose or included reagent requires a new profile. Caller
    provenance must additionally identify commercial grades/lots and protocol.
    """
    reagents = {} if reagent_doses_g_per_l is None else reagent_doses_g_per_l
    if not isinstance(reagents, dict) or any(not isinstance(k, str) or not k.strip() for k in reagents):
        raise DeliveryError('invalid_type', 'reagent doses must map nonempty record IDs to g/L')
    reagents = {key: _number(value, 'reagent g/L') for key, value in reagents.items()}
    payload = dict(recipe=_recipe(stocks, channel), catalogue=load_library()['salts'],
                   reagents=reagents if channel == 'irrigation' else {})
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class ECPrediction:
    status: str
    ec_ms_cm: float | None = None
    profile_id: str | None = None
    profile_sha256: str | None = None
    error_code: str | None = None
    message: str | None = None
    uncertainty_ms_cm: float | None = None


@dataclass(frozen=True)
class ECDeliveryPlan:
    water_ec_ms_cm: float
    predictions: dict
    injections: dict
    pump_commands: tuple
    audit: dict
    warnings: tuple = field(default_factory=lambda: (
        'Empirical interpolation only; verify stock and final EC with suitable calibrated meters.',
        'EC does not establish nutrient balance, solubility, pH or safety.',
        'Injection volumes preserve the existing recipe; no autonomous EC correction or dosing.',
        'Separate acid/reagent additions are excluded unless explicitly included in the matched irrigation profile.',
    ))
    post_mix_measurement_required: bool = True


def _bracket(axis, value):
    if value < axis[0] or value > axis[-1]:
        raise DeliveryError('outside_ec_calibration', 'requested water EC or strength is outside calibration')
    if value in axis:
        return value, value, 0.
    for low, high in zip(axis, axis[1:]):
        if low < value < high:
            return low, high, (value-low)/(high-low)
    raise DeliveryError('invalid_ec_profile', 'calibration axis cannot bracket request')


def _predict(profile, water, strength, key, channel, source_id):
    for field_name in ('id', 'source', 'revision', 'recordedAt', 'protocol'):
        if not isinstance(profile.get(field_name), str) or not profile[field_name].strip():
            raise DeliveryError('invalid_ec_profile', f'{field_name} is required')
    try:
        recorded = datetime.fromisoformat(profile['recordedAt'].replace('Z', '+00:00'))
        if recorded.tzinfo is None:
            raise ValueError('timezone missing')
    except ValueError as exc:
        raise DeliveryError('invalid_ec_profile', 'recordedAt requires an ISO timestamp with timezone') from exc
    if profile.get('schemaVersion') != '1' or profile.get('reference_temperature_c') != 25:
        raise DeliveryError('invalid_ec_profile', 'expected schema 1 and EC referenced to 25 C')
    if profile.get('recipe_key') != key or profile.get('channel') != channel or profile.get('water_source_id') != source_id:
        raise DeliveryError('mismatched_ec_profile', 'recipe, channel or configured water source differs')
    points = profile.get('points')
    if not isinstance(points, list) or not points:
        raise DeliveryError('invalid_ec_profile', 'nonempty measured EC grid is required')
    grid = {}
    for point in points:
        if not isinstance(point, dict):
            raise DeliveryError('invalid_ec_profile', 'points must be objects')
        x = _number(point.get('water_ec_ms_cm'), 'calibration water EC')
        y = _number(point.get('strength'), 'calibration strength')
        ec = _number(point.get('ec_ms_cm'), 'calibration total EC')
        if (x, y) in grid:
            raise DeliveryError('invalid_ec_profile', 'duplicate calibration point')
        grid[x, y] = ec
    xs, ys = sorted({x for x, y in grid}), sorted({y for x, y in grid})
    if len(grid) != len(xs) * len(ys):
        raise DeliveryError('invalid_ec_profile', 'calibration must be a complete rectangular grid')
    x0, x1, tx = _bracket(xs, water)
    y0, y1, ty = _bracket(ys, strength)
    lower = grid[x0, y0]*(1-tx) + grid[x1, y0]*tx
    upper = grid[x0, y1]*(1-tx) + grid[x1, y1]*tx
    uncertainty = profile.get('validated_max_error_ms_cm')
    if uncertainty is not None:
        uncertainty = _number(uncertainty, 'validated maximum EC error')
    try:
        digest = hashlib.sha256(json.dumps(profile, sort_keys=True, allow_nan=False).encode()).hexdigest()
    except (TypeError, ValueError) as exc:
        raise DeliveryError('invalid_ec_profile', 'profile must contain finite JSON-serializable evidence') from exc
    return ECPrediction('estimated', lower*(1-ty)+upper*ty, profile['id'], digest,
                        uncertainty_ms_cm=uncertainty)


def plan_ec_delivery(stocks, *, profiles, water_source_id, water_ec_ms_cm=None,
                     water_tds_ppm=None, tds_factor=None, reference_temperature_c=25,
                     reagent_doses_g_per_l=None, pump_calibrations=None,
                     available_volumes=None, as_of=None):
    """Estimate each stock and the combined final solution independently.

    The configured source must be represented by the profiles, even if another
    source has the same EC. Calibration strength 1 is the stock-plan recipe in
    g/L of final solution; stock strength is the physical injection ratio.
    Pump plans are optional and require all used tank calibrations/inventories.
    """
    if not isinstance(stocks, StockPlan):
        raise DeliveryError('invalid_type', 'stocks must be a StockPlan')
    if reference_temperature_c != 25 or stocks.temperature.value != 25:
        raise DeliveryError('temperature_out_of_range', 'this EC model requires 25 C preparation and EC25 readings')
    if not isinstance(water_source_id, str) or not water_source_id.strip():
        raise DeliveryError('missing_field', 'configured water source identity is required')
    water = water_ec25(ec_ms_cm=water_ec_ms_cm, tds_ppm=water_tds_ppm, tds_factor=tds_factor)
    if not isinstance(profiles, (list, tuple)) or any(not isinstance(p, dict) for p in profiles):
        raise DeliveryError('invalid_ec_profile', 'profiles must be a sequence of records')
    channels = [p.get('channel') for p in profiles]
    if any(not isinstance(c, str) for c in channels) or len(channels) != len(set(channels)):
        raise DeliveryError('invalid_ec_profile', 'each profile must name one unique channel')
    lookup = dict(zip(channels, profiles))
    ratio = stocks.injection_ratio.value
    volume = stocks.recipe.final_volume.value
    predictions, injections, keys = {}, {}, {}
    assigned = set()
    base = _recipe(stocks, 'irrigation')
    for tank in stocks.tanks:
        identity = tank.tank.tank_id
        if identity in injections:
            raise DeliveryError('inconsistent_recipe', 'duplicate tank ID')
        for salt in tank.salts:
            if salt.salt_id not in base or salt.salt_id in assigned:
                raise DeliveryError('inconsistent_recipe', 'stock assignment must cover each recipe product once')
            assigned.add(salt.salt_id)
            expected = base[salt.salt_id]['grams_per_litre'] * ratio
            if not math.isclose(salt.concentration.value, expected, rel_tol=1e-10, abs_tol=1e-12):
                raise DeliveryError('inconsistent_recipe', 'stock concentration differs from the recipe and ratio')
        injected = volume / ratio
        if injected > tank.stock_volume.value + 1e-12 or tank.stock_volume.value > tank.tank.capacity.value + 1e-12:
            raise DeliveryError('dry_tank_risk', 'prepared stock/capacity does not support planned injection')
        injections[identity] = dict(volume_litres=injected, final_litres_per_stock_litre=ratio,
                                    ml_per_litre_final=1000/ratio)
    if assigned != set(base) or sum(i['volume_litres'] for i in injections.values()) > volume:
        raise DeliveryError('inconsistent_recipe', 'stock coverage or combined injected volume is invalid')
    expected_channels = ['irrigation'] + ['tank:'+tank_id for tank_id in injections]
    if set(lookup) - set(expected_channels):
        raise DeliveryError('unknown_channel', 'profile references an unused stock channel')
    for channel in expected_channels:
        key = ec_recipe_key(stocks, channel, reagent_doses_g_per_l=reagent_doses_g_per_l)
        keys[channel] = key
        if channel not in lookup:
            predictions[channel] = ECPrediction('needs_input', error_code='missing_ec_profile',
                                                message='recipe-matched measured calibration is required')
            continue
        try:
            predictions[channel] = _predict(lookup[channel], water, 1. if channel == 'irrigation' else ratio,
                                            key, channel, water_source_id)
        except DeliveryError as exc:
            predictions[channel] = ECPrediction('blocked', error_code=exc.code, message=str(exc))
    commands = []
    if pump_calibrations is not None or available_volumes is not None:
        if not isinstance(pump_calibrations, dict) or not isinstance(available_volumes, dict):
            raise DeliveryError('missing_field', 'pump calibrations and available volumes are both required')
        for identity, injection in injections.items():
            calibration = pump_calibrations.get(identity)
            if not isinstance(calibration, dict) or calibration.get('channelId') != identity or identity not in available_volumes:
                raise DeliveryError('mismatched_record', 'each stock needs a matching pump channel and inventory')
            commands.append(plan_pump_command(calibration, VolumeLitres(injection['volume_litres']),
                                              available_volumes[identity], as_of=as_of))
    audit = dict(model='recipe-calibrated-ec25-v1', recipe_keys=keys, water_source_id=water_source_id,
                 reference_temperature_c=25, water_ec_ms_cm=water_ec_ms_cm,
                 water_tds_ppm=water_tds_ppm, tds_factor=tds_factor,
                 reagent_doses_g_per_l=dict(reagent_doses_g_per_l or {}),
                 final_volume_litres=volume, includes_separate_reagents=bool(reagent_doses_g_per_l))
    return ECDeliveryPlan(water, predictions, injections, tuple(commands), audit)
