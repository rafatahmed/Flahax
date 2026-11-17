# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Reconstruct a batch from its rounded dry, volumetric and reagent doses."""

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


def verify_batch_stock_delivery(
    chosen, chemistry, equilibrium, litres, targets, ph, maxima, config
):
    """Check delivered analytical totals and sample chemistry with aqueous-only speciation."""
    targets = fitted_targets(targets)
    fields = {
        'stock',
        'dry_mass_decimals',
        'reagent_volume_decimals',
        'nutrient_tolerance_percent',
        'ph_tolerance',
    }
    if not isinstance(config, dict) or set(config) != fields:
        raise DeliveryError(
            'invalid_stock_dosing', 'Supply stock, both resolutions and both tolerances'
        )
    for field in ('dry_mass_decimals', 'reagent_volume_decimals'):
        if type(config[field]) is not int or not 0 <= config[field] <= 6:
            raise DeliveryError('invalid_stock_dosing', f'{field} must be an integer from 0 to 6')
    for field in ('nutrient_tolerance_percent', 'ph_tolerance'):
        value = config[field]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise DeliveryError('invalid_stock_dosing', f'{field} must be finite and positive')
    stock = config['stock']
    if not isinstance(stock, dict) or not isinstance(stock.get('concentrations_g_l'), dict):
        raise DeliveryError('invalid_stock_dosing', 'Supply stock concentrations by product name')
    grams = {
        salt['name']: salt['gramsPerLitre'] * litres for salt in chosen.recommendation['salts']
    }
    names = stock['concentrations_g_l']
    if not names or not names.keys() <= grams.keys():
        raise DeliveryError('invalid_stock_dosing', 'Stock names must identify dosed fertilizers')
    bounds = dict(
        mode='water_product_elemental',
        water_mass_model='closed_batch_mass_balance',
        weighing_error_g=0,
        volume_error_litres=0,
    )
    ingredients = [dict(name=name, grams=grams[name]) for name in names]
    validate_product_stocks(stock, ingredients, bounds)
    delivery = prepare_product_stocks(
        dict(volume_litres=litres, ingredients=ingredients), stock, bounds
    )
    dry = {
        name: round(amount, config['dry_mass_decimals'])
        for name, amount in grams.items()
        if name not in names
    }

    reagent_ml = chosen.reagent_volume_litres
    reagent = chosen.product_record
    if reagent_ml is None:
        reagent_grams = round(chosen.reagent_mass_g, config['dry_mass_decimals'])
    else:
        reagent_ml = round(1000 * reagent_ml, config['reagent_volume_decimals'])
        reagent_grams = reagent_ml * reagent['densityKgPerL']
    _, reagent_basis, molar_mass, _ = REAGENTS[chosen.formula]
    solvent = equilibrium['water_mass_kg']
    reagent_molal = reagent_grams * reagent['massFraction'] / molar_mass / solvent

    def inventories(product_grams, carrier_ml):
        # Preserve the stated final solvent mass. Pure carrier replaces an equal
        # volume of the otherwise supplied source-water share.
        source_fraction = 1 - carrier_ml / (1000 * litres)
        doses = {name: amount / solvent for name, amount in (dry | product_grams).items()}
        additions = catalogue_dose_totals(
            doses,
            materials={
                name: grade for name, grade in chemistry['materials'].items() if name in doses
            },
            products=chemistry['products'],
        )
        for basis, count in reagent_basis.items():
            additions[basis] = additions.get(basis, 0) + reagent_molal * count

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

    rows = delivery['stocks']
    nominal_grams = {row['name']: row['effective_grams'] for row in rows}
    dose_ml = delivery['total_dose_ml']
    error_ml = sum(row['dose_error_ml'] for row in rows)
    extremes = [
        {row['name']: row['effective_grams_bounds'][side] for row in rows} for side in (0, -1)
    ]
    nominal, solution, residual = inventories(nominal_grams, dose_ml)
    endpoint_inventories = [
        inventories(doses, volume)
        for doses, volume in product(extremes, (dose_ml - error_ml, dose_ml + error_ml))
    ]
    limits = assessed_limits(maxima, chosen.recommendation)
    nutrient_bounds = {
        key: [min(values), max(values)]
        for key in nominal.keys() | targets.keys() | limits.keys()
        for values in [[inventory.get(key, 0) for inventory, _, _ in endpoint_inventories]]
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
    exceeded = [key for key, max_mg_l in limits.items() if nutrient_bounds[key][1] > max_mg_l]
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
    for _, totals, charge in endpoint_inventories:
        ph_samples.append(calculate_equilibrium_ph(totals, phases=(), residual_charge=charge).ph)
    return dict(
        stocks=rows,
        dry_product_grams=dry,
        reagent=dict(formula=chosen.formula, grams=reagent_grams, volume_ml=reagent_ml),
        nutrient_mg_l=nominal,
        nutrient_bounds_mg_l=nutrient_bounds,
        missed_targets=sorted(missed),
        limit_violations=sorted(exceeded),
        ph=ec.ph,
        sampled_ph_range=[min(ph_samples), max(ph_samples)],
        ph_within_tolerance=all(abs(value - ph) <= config['ph_tolerance'] for value in ph_samples),
        ec25_ms_cm=ec.ec25_ms_cm,
        ec25_range_ms_cm=ec.ec25_range_ms_cm,
        saturation=assess_saturation(solve(solution, ec.ph, phases=())),
        assumptions=(
            'Declared stock concentration and dispensing errors only. Fixed final solvent mass, '
            'equal-volume source-water displacement, closed carbon and aqueous-only chemistry. '
            'Analytical bounds enclose the stock inputs; pH endpoints are sampled. '
            'Dry-scale and reagent assay uncertainty and stock stability require '
            'separate evidence.'
        ),
    )
