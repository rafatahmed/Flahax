# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Assess and locally refit rounded batch preparation quantities."""

from itertools import product
import math

from .aqueous_model import solve
from .calculated_ph import calculate_equilibrium_ph
from .composition import fitted_targets
from .delivery_contracts import DeliveryError
from .irrigation_ec import calculate_ec_from_totals
from .measured_water import nutrient_mg_per_litre
from .nutrient_acceptance import assessed_limits
from .ph_adjustment import REAGENTS
from .product_conversion import catalogue_dose_totals
from .ratio_product_stocks import prepare_product_stocks, validate_product_stocks
from .requirement_fit import met
from .saturation_policy import assess_saturation


def _number(value, field, maximum=math.inf):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise DeliveryError('invalid_stock_dosing', f'Invalid value for {field}')
    return value


def _interval(values, nominal, field, maximum=math.inf):
    if not isinstance(values, (list, tuple)) or len(values) != 2:
        raise DeliveryError('invalid_stock_dosing', f'Supply two endpoints for {field}')
    low, high = (_number(value, field, maximum=maximum) for value in values)
    if not low <= nominal <= high:
        raise DeliveryError('invalid_stock_dosing', f'{field} must contain the selected value')
    return low, high


def _uncertainty(config, dry_names, reagent, liquid):
    uncertainty = config.get('uncertainty', {})
    allowed = {
        'dry_product_error_g',
        'dry_product_assay_relative_error',
        'reagent_mass_fraction_bounds',
    }
    allowed |= (
        {'reagent_volume_error_ml', 'reagent_density_kg_l_bounds'}
        if liquid
        else {'reagent_mass_error_g'}
    )
    if not isinstance(uncertainty, dict) or not uncertainty.keys() <= allowed:
        raise DeliveryError('invalid_stock_dosing', 'Invalid uncertainty for batch preparation')

    def dry_errors(field, maximum):
        errors = uncertainty.get(field, {})
        if not isinstance(errors, dict) or not errors.keys() <= set(dry_names):
            raise DeliveryError(
                'invalid_stock_dosing', 'Specify dry errors by dosed dry product name'
            )
        return {name: _number(error, field, maximum) for name, error in errors.items()}

    field = 'reagent_volume_error_ml' if liquid else 'reagent_mass_error_g'
    assay = reagent['massFraction']
    density = reagent['densityKgPerL'] if liquid else 1
    assay_bounds = _interval(
        uncertainty.get('reagent_mass_fraction_bounds', (assay, assay)),
        assay,
        'reagent_mass_fraction_bounds',
        maximum=1,
    )
    density_bounds = _interval(
        uncertainty.get('reagent_density_kg_l_bounds', (density, density)),
        density,
        'reagent_density_kg_l_bounds',
    )
    if density_bounds[0] == 0:
        raise DeliveryError('invalid_stock_dosing', 'Reagent density must be positive')
    return (
        dry_errors('dry_product_error_g', math.inf),
        dry_errors('dry_product_assay_relative_error', 1),
        _number(uncertainty.get(field, 0), field),
        assay_bounds,
        density_bounds,
    )


def _adjacent(ideal, decimals):
    nearest = round(ideal, decimals)
    increment = 10.0**-decimals
    return tuple(
        dict.fromkeys(
            (
                nearest,
                round(nearest + increment, decimals),
                max(0.0, round(nearest - increment, decimals)),
            )
        )
    )


def _measure_bounds(dose, error):
    # A zero dose is an omitted operation. A positive dose must fit the measuring range.
    error = error if dose else 0
    if dose < error:
        raise DeliveryError('rounded_dose_infeasible', 'Dose is smaller than its declared error')
    return dose - error, dose + error


def verify_batch_stock_delivery(
    chosen,
    chemistry,
    equilibrium,
    litres,
    targets,
    ph,
    maxima,
    config,
    *,
    reagent_maximum=math.inf,
):
    """Check delivery and try nearby discrete doses when the nearest recipe fails."""
    targets = fitted_targets(targets)
    required = {
        'stock',
        'dry_mass_decimals',
        'reagent_volume_decimals',
        'nutrient_tolerance_percent',
        'ph_tolerance',
    }
    optional = {'alternative_stock_concentrations_g_l', 'nutrient_ceiling_reserve', 'uncertainty'}
    if not isinstance(config, dict) or not required <= config.keys() <= required | optional:
        raise DeliveryError(
            'invalid_stock_dosing', 'Supply stock, both resolutions and both tolerances'
        )
    for field in ('dry_mass_decimals', 'reagent_volume_decimals'):
        if type(config[field]) is not int or not 0 <= config[field] <= 6:
            raise DeliveryError('invalid_stock_dosing', f'{field} must be an integer from 0 to 6')
    for field in ('nutrient_tolerance_percent', 'ph_tolerance'):
        if _number(config[field], field) == 0:
            raise DeliveryError('invalid_stock_dosing', f'{field} must be positive')
    stock = config['stock']
    if not isinstance(stock, dict) or not isinstance(stock.get('concentrations_g_l'), dict):
        raise DeliveryError('invalid_stock_dosing', 'Supply stock concentrations by product name')
    grams = {
        salt['name']: salt['gramsPerLitre'] * litres for salt in chosen.recommendation['salts']
    }
    concentrations = stock['concentrations_g_l']
    if not concentrations or not concentrations.keys() <= grams.keys():
        raise DeliveryError('invalid_stock_dosing', 'Stock names must identify dosed fertilizers')
    stock_bounds = dict(
        mode='water_product_elemental',
        water_mass_model='closed_batch_mass_balance',
        weighing_error_g=0,
        volume_error_litres=0,
    )
    ingredients = [dict(name=name, grams=grams[name]) for name in concentrations]
    validate_product_stocks(stock, ingredients, stock_bounds)
    alternatives = config.get('alternative_stock_concentrations_g_l', {})
    if not isinstance(alternatives, dict) or not alternatives.keys() <= concentrations.keys():
        raise DeliveryError('invalid_stock_dosing', 'Specify alternative strengths by stock name')
    for name, strengths in alternatives.items():
        if not isinstance(strengths, (list, tuple)) or not strengths:
            raise DeliveryError(
                'invalid_stock_dosing', 'Supply a nonempty list of stock strengths'
            )
        for strength in strengths:
            replacement = stock | {'concentrations_g_l': concentrations | {name: strength}}
            validate_product_stocks(replacement, ingredients, stock_bounds)

    reserve = _number(config.get('nutrient_ceiling_reserve', 0), 'nutrient_ceiling_reserve')
    if reserve >= 1 or (reserve and not maxima):
        raise DeliveryError(
            'invalid_stock_dosing', 'Reserve must be below one and requires declared ceilings'
        )
    limits = assessed_limits(maxima, chosen.recommendation)
    limits.update({key: value * (1 - reserve) for key, value in (maxima or {}).items()})
    liquid = chosen.reagent_volume_litres is not None
    reagent = chosen.product_record
    stock_names = list(concentrations)
    dry_names = [name for name in grams if name not in concentrations]
    dry_errors, dry_assay_errors, reagent_error, assay_bounds, density_bounds = _uncertainty(
        config, dry_names, reagent, liquid
    )
    ideal_reagent = 1000 * chosen.reagent_volume_litres if liquid else chosen.reagent_mass_g
    reagent_decimals = config['reagent_volume_decimals' if liquid else 'dry_mass_decimals']
    choices = [
        tuple(
            dict.fromkeys(
                (strength, dose)
                for strength in (concentrations[name], *alternatives.get(name, ()))
                for dose in _adjacent(1000 * grams[name] / strength, stock['dose_decimals'])
            )
        )
        for name in stock_names
    ]
    choices.extend(_adjacent(grams[name], config['dry_mass_decimals']) for name in dry_names)
    choices.append(_adjacent(ideal_reagent, reagent_decimals))

    _, reagent_basis, molar_mass, _ = REAGENTS[chosen.formula]
    solvent = equilibrium['water_mass_kg']
    # The disclosed fertilizer analyses give linear conserved amounts per gram.
    unit_totals = {
        name: catalogue_dose_totals(
            {name: 1 / solvent},
            materials={name: chemistry['materials'][name]}
            if name in chemistry['materials']
            else {},
            products=chemistry['products'],
        )
        for name in grams
    }

    def inventories(product_grams, carrier_ml, active_reagent_g):
        source_fraction = 1 - carrier_ml / (1000 * litres)
        additions = {
            basis: active_reagent_g / molar_mass / solvent * count
            for basis, count in reagent_basis.items()
        }
        for name, amount in product_grams.items():
            for basis, per_gram in unit_totals[name].items():
                additions[basis] = additions.get(basis, 0) + amount * per_gram

        def combine(water):
            return {
                basis: water.get(basis, 0) * source_fraction + additions.get(basis, 0)
                for basis in water.keys() | additions.keys()
            }

        return (
            nutrient_mg_per_litre(combine(chemistry['analytical_water_totals']), solvent, litres),
            combine(chemistry['water_totals']),
            chemistry['residual_charge_eq'] * source_fraction,
        )

    def evaluate(candidate, *, diagnostic=False):
        nstocks = len(stock_names)
        stocked = dict(zip(stock_names, candidate[:nstocks]))
        dry = dict(zip(dry_names, candidate[nstocks:-1]))
        dose = candidate[-1]
        delivered = prepare_product_stocks(
            dict(
                volume_litres=litres,
                ingredients=[
                    dict(name=name, grams=strength * volume / 1000)
                    for name, (strength, volume) in stocked.items()
                ],
            ),
            stock
            | {'concentrations_g_l': {name: strength for name, (strength, _) in stocked.items()}},
            stock_bounds,
        )
        rows = delivered['stocks']
        dry_bounds = {name: _measure_bounds(g, dry_errors.get(name, 0)) for name, g in dry.items()}
        effective_dry_bounds = {
            name: (low * (1 - error), high * (1 + error))
            for name, (low, high) in dry_bounds.items()
            for error in [dry_assay_errors.get(name, 0)]
        }
        steps = _measure_bounds(dose, reagent_error)
        density = reagent['densityKgPerL'] if liquid else 1
        reagent_grams = dose * density
        mass_bounds = tuple(volume * rho for volume, rho in zip(steps, density_bounds))
        active_bounds = tuple(g * assay for g, assay in zip(mass_bounds, assay_bounds))

        nominal, solution, residual = inventories(
            dry | {row['name']: row['effective_grams'] for row in rows},
            delivered['total_dose_ml'],
            reagent_grams * reagent['massFraction'],
        )
        extrema = [
            {row['name']: row['effective_grams_bounds'][side] for row in rows}
            | {name: bounds[side] for name, bounds in effective_dry_bounds.items()}
            for side in (0, -1)
        ]
        volumes = [
            sum(row['dose_ml'] + sign * row['dose_error_ml'] for row in rows) for sign in (-1, 1)
        ]
        endpoints = [
            inventories(masses, volume, active)
            for masses, volume, active in product(
                extrema, sorted(set(volumes)), sorted(set(active_bounds))
            )
        ]
        nutrient_bounds = {
            key: [min(values), max(values)]
            for key in sorted(nominal.keys() | targets.keys() | limits.keys())
            for values in [[inventory.get(key, 0) for inventory, _, _ in endpoints]]
        }
        missed = [
            key
            for key, target in targets.items()
            if any(
                abs(value - target) > target * config['nutrient_tolerance_percent'] / 100
                if target > 0
                else not met(0, value)
                for value in nutrient_bounds[key]
            )
        ]
        exceeded = [key for key, limit in limits.items() if nutrient_bounds[key][1] > limit]
        reagent_exceeded = steps[1] > reagent_maximum
        score = sum(
            max(abs(value - target) for value in nutrient_bounds[key]) / max(target, 1e-6)
            for key, target in targets.items()
        )
        score += sum(
            max(0, nutrient_bounds[key][1] - limit) / max(limit, 1e-6)
            for key, limit in limits.items()
        )
        failures = len(missed) + len(exceeded) + reagent_exceeded
        if failures and not diagnostic:
            return (failures, score), None
        ec = calculate_ec_from_totals(
            solution,
            solution_id='rounded-batch',
            ph_mode='calculated',
            phase_policy='dissolved',
            residual_charge_eq_per_kgw=residual,
        )
        if ec.ph is None:
            raise DeliveryError(
                'rounded_chemistry_incomplete', 'Could not solve rounded-batch chemistry'
            )
        ph_samples = [ec.ph]
        sampled = {(tuple(sorted(solution.items())), residual)}
        for _, totals, charge in endpoints:
            fingerprint = (tuple(sorted(totals.items())), charge)
            if fingerprint not in sampled:
                sample = calculate_equilibrium_ph(totals, phases=(), residual_charge=charge)
                ph_samples.append(sample.ph)
                sampled.add(fingerprint)
        ph_error = max(abs(value - ph) for value in ph_samples)
        ph_pass = ph_error <= config['ph_tolerance']
        rank = (failures + (not ph_pass), score + ph_error / config['ph_tolerance'])
        if rank[0] and not diagnostic:
            return rank, None
        return rank, dict(
            stocks=rows,
            stock_preparation=(
                'One separate stock per declared fertilizer product. The pH reagent is measured '
                'separately. Concentrated mixtures and physical stability require qualification.'
            ),
            dry_product_grams=dry,
            dry_product_grams_bounds=dry_bounds,
            dry_product_assay_adjusted_grams_bounds=effective_dry_bounds,
            reagent=dict(
                formula=chosen.formula,
                grams=reagent_grams,
                grams_bounds=mass_bounds,
                volume_ml=dose if liquid else None,
                volume_ml_bounds=steps if liquid else None,
                active_grams_bounds=active_bounds,
            ),
            reagent_limit_exceeded=reagent_exceeded,
            nutrient_mg_l=nominal,
            nutrient_bounds_mg_l=nutrient_bounds,
            nutrient_ceiling_reserve=reserve,
            effective_maximum_concentrations=limits,
            missed_targets=sorted(missed),
            limit_violations=sorted(exceeded),
            ph=ec.ph,
            sampled_ph_range=[min(ph_samples), max(ph_samples)],
            ph_within_tolerance=ph_pass,
            ec25_ms_cm=ec.ec25_ms_cm,
            ec25_range_ms_cm=ec.ec25_range_ms_cm,
            saturation=assess_saturation(solve(solution, ec.ph, phases=())),
            assumptions=(
                'Fixed final solvent mass, equal-volume source-water displacement by stock '
                'doses, closed carbon and aqueous-only chemistry. Analytical bounds enclose '
                'declared delivery, uniform dry-product assay scaling and reagent uncertainty. '
                'pH samples use common low/high fertilizer mass, independent carrier volume '
                'and independent reagent potency endpoints. Stock physical preparation, '
                'assay and stability require separate evidence.'
            ),
        )

    return _search(choices, evaluate)


def _search(choices, evaluate):
    """Bound the refit to the nearest and adjacent increments per declared strength."""
    nearest = tuple(options[0] for options in choices)
    try:
        rank, original = evaluate(nearest, diagnostic=True)
    except DeliveryError as exc:
        original, original_error = None, exc
    else:
        if rank[0] == 0:
            original['rounding_search'] = dict(attempts=1, status='nearest_passed')
            return original

    # Keep a small frontier so a second dose change can compensate for the first.
    frontier = [nearest]
    tried = {nearest}
    budget = 128
    while frontier and len(tried) < budget:
        ranked = []
        for current in frontier:
            for index, options in enumerate(choices):
                for option in options:
                    candidate = current[:index] + (option,) + current[index + 1 :]
                    if candidate in tried or len(tried) >= budget:
                        continue
                    tried.add(candidate)
                    try:
                        rank, result = evaluate(candidate)
                    except DeliveryError:
                        continue
                    if result is not None:
                        result['rounding_search'] = dict(attempts=len(tried), status='refitted')
                        return result
                    ranked.append((rank, candidate))
        frontier = [candidate for _, candidate in sorted(ranked)[:4]]
    if original is None:
        raise original_error
    original['rounding_search'] = dict(
        attempts=len(tried), status='no_passing_candidate', budget=budget
    )
    return original
