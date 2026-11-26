# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""A water analysis as the batch commands read it: the JSON file, its units and keys,
the solvent basis, and the blend with a second water."""

import math
from pathlib import Path

from .delivery_contracts import DeliveryError
from .delivery_quantities import SolventBasis
from .inputs import number, read_json
from .measured_water import balance_water_analysis
from .product_conversion import MOLAR_MASS


# Water analysis key -> (basis, grams per mole of the reported
# quantity).
WATER_KEYS = {
    'Ca': ('Ca+2', MOLAR_MASS['Ca']),
    'Mg': ('Mg+2', MOLAR_MASS['Mg']),
    'K': ('K+', MOLAR_MASS['K']),
    'Na': ('Na+', MOLAR_MASS['Na']),
    'Cl': ('Cl-', MOLAR_MASS['Cl']),
    'S': ('SO4-2', MOLAR_MASS['S']),
    'P': ('PO4-3', MOLAR_MASS['P']),
    'N_NO3': ('NO3-', MOLAR_MASS['N']),
    'N_NH4': ('NH4+', MOLAR_MASS['N']),
    'Fe': ('Fe+3', MOLAR_MASS['Fe']),
    'Mn': ('Mn+2', MOLAR_MASS['Mn']),
    'Zn': ('Zn+2', MOLAR_MASS['Zn']),
    'Cu': ('Cu+2', MOLAR_MASS['Cu']),
    'B': ('H3BO3', MOLAR_MASS['B']),
    'Mo': ('MoO4-2', MOLAR_MASS['Mo']),
    'HCO3': ('CO3-2', 61.0168),
}


def _mg(key, value, what='water value'):
    """A water concentration in mg/L: a finite, non-negative number."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise DeliveryError('invalid_value', f'{what} {key} = {value!r} is not a number of mg/L')
    try:
        amount = float(value)
    except ValueError:
        raise DeliveryError(
            'invalid_value', f'{what} {key} = {value!r} is not a number of mg/L'
        ) from None
    if not math.isfinite(amount) or amount < 0:
        raise DeliveryError('invalid_value', f'{what} {key} = {value!r} must be zero or more mg/L')
    return amount


def water_basis(data):
    """Return a final solvent basis and its disclosed input/uncertainty
    status.
    """
    keys = {'water_mass_kg', 'final_volume_litres', 'density_kg_per_litre', 'nonwater_mass_kg'}
    present = keys.intersection(data)
    if not present:
        return SolventBasis(1, 1), {
            'status': 'assumed',
            'water_kg_per_litre': 1.0,
            'uncertainty': 'not quantified',
            'note': 'Assumes 1 kg final solvent water per litre; '
            'carrier/hydrate water and nonwater mass are not independently quantified.',
        }
    if 'final_volume_litres' not in present:
        raise DeliveryError('missing_field', 'solvent basis requires final_volume_litres')
    if 'water_mass_kg' in present:
        if present != {'water_mass_kg', 'final_volume_litres'}:
            raise DeliveryError(
                'contradictory_water_inputs', 'supply solvent mass or density basis, not both'
            )
        basis = SolventBasis(data['final_volume_litres'], data['water_mass_kg'])
        source = 'declared final solvent mass including carrier and dissolved hydrate water'
    else:
        if present != {'final_volume_litres', 'density_kg_per_litre', 'nonwater_mass_kg'}:
            raise DeliveryError(
                'missing_field', 'density basis requires complete nonwater_mass_kg'
            )
        basis = SolventBasis.from_solution_mass(
            data['final_volume_litres'], data['density_kg_per_litre'], data['nonwater_mass_kg']
        )
        source = 'declared final solution density minus complete nonwater mass'
    return basis, {
        'status': 'declared',
        'water_kg_per_litre': basis.water_mass_kg / basis.final_volume_litres,
        'uncertainty': 'not supplied; not inferred from input precision',
        'note': source,
    }


def read_water(spec):
    """(label, nutrient mg/L, equilibrium configuration) from ``ro`` or
    a JSON file.
    """
    if spec.lower() == 'ro':
        return (
            'RO water, no ions',
            {},
            dict(water_totals={}, water_analysis_id='RO', concentration_basis=water_basis({})[1]),
        )
    data = read_json(spec, 'water')
    if not isinstance(data, dict) or not isinstance(data.get('mg_per_litre'), dict):
        raise DeliveryError('invalid_type', 'water JSON needs an "mg_per_litre" object')
    for key, value in data['mg_per_litre'].items():
        if key in WATER_KEYS:
            _mg(key, value)
    if 'measured_ph' not in data:
        raise DeliveryError(
            'missing_field', 'water JSON needs "measured_ph" to close the analysis'
        )
    unknown = set(data['mg_per_litre']) - set(WATER_KEYS)
    if unknown:
        raise DeliveryError(
            'unknown_field',
            'unsupported water keys: '
            + ', '.join(sorted(unknown))
            + '; use '
            + ', '.join(WATER_KEYS),
        )
    closing = sorted({'balance_ion', 'balance_ion_uncertainty_percent'} & set(data))
    if closing:
        raise DeliveryError(
            'unknown_field',
            f'{", ".join(closing)} is no longer used: the analysis is taken as measured, its '
            'charge imbalance is reported, and no ion is adjusted to close it',
        )
    below = data.get('below_detection') or {}
    if not isinstance(below, dict) or set(below) - set(WATER_KEYS):
        raise DeliveryError(
            'unknown_field', '"below_detection" maps water keys to detection limits in mg/L'
        )
    if isinstance(data['measured_ph'], bool) or not isinstance(data['measured_ph'], (int, float)):
        raise DeliveryError(
            'invalid_value', f'"measured_ph" = {data["measured_ph"]!r} is not a number'
        )
    solvent, basis_audit = water_basis(data)
    alkalinity = data.get('alkalinity_meq_per_litre')
    if 'alkalinity_below_detection_meq_per_litre' in data:
        raise DeliveryError(
            'unsupported_alkalinity',
            'below-detection alkalinity is an interval, not measured zero; '
            'supply a resolved analysis',
        )
    if 'alkalinity_meq_per_litre' in data:
        if 'HCO3' in data['mg_per_litre'] or 'HCO3' in below:
            raise DeliveryError(
                'ambiguous_carbon', 'supply HCO3 carbon or total alkalinity, not both'
            )
        number(alkalinity, 'alkalinity_meq_per_litre', minimum=None)
    totals = {}
    for key, mg in data['mg_per_litre'].items():
        basis, grams = WATER_KEYS[key]
        totals[basis] = totals.get(basis, 0) + solvent.mg_per_litre_to_molality(mg, grams)
    # Nutrients straight from the laboratory analysis; the workflow
    # balances it for chemistry only.
    nutrients = {key: float(mg) for key, mg in data['mg_per_litre'].items() if key != 'HCO3'}
    analysis_id = str(data.get('id', Path(spec).stem))
    label = f'{analysis_id}: laboratory analysis, measured pH {data["measured_ph"]}'
    config = dict(
        water_totals=totals,
        measured_ph=data['measured_ph'],
        water_analysis_id=analysis_id,
        concentration_basis=basis_audit,
        below_detection={
            WATER_KEYS[k][0]: solvent.mg_per_litre_to_molality(
                _mg(k, v, 'detection limit'), WATER_KEYS[k][1]
            )
            for k, v in below.items()
        },
    )
    if alkalinity is not None:
        config['alkalinity_eq_per_kg'] = alkalinity / 1000 / basis_audit['water_kg_per_litre']
    if 'HCO3' in data['mg_per_litre']:
        config['water_input_notes'] = [
            'Legacy HCO3 is treated as equivalent total inorganic carbon. '
            'This is not a bicarbonate speciation measurement or a titration; '
            'use alkalinity_meq_per_litre for measured total alkalinity.'
        ]
    return label, nutrients, config


def blend(label, water, chemistry, percent):
    """The analysed water as ``percent`` of the batch water, the rest
    ion-free (desalinated or RO).

    Nutrients and limits scale the laboratory analysis; the chemistry
    dilutes its measured-pH record (#84). If the analysis cannot be
    closed, the chemistry is left out with the reason, and nutrient
    accounting goes on.
    """
    if chemistry.get('measured_ph') is None:
        raise DeliveryError(
            'invalid_value', '--water-share needs a measured water analysis file, not ro'
        )
    if not 0 < percent <= 100:
        raise DeliveryError('invalid_value', '--water-share must be a percentage in (0, 100]')
    fraction = percent / 100
    source_basis = chemistry.get('concentration_basis', water_basis({})[1])
    source_ratio = source_basis['water_kg_per_litre']
    mixed_ratio = fraction * source_ratio + (1 - fraction)
    # The share is volumetric; the molal dilution is the source solvent
    # mass share.
    molal_fraction = fraction * source_ratio / mixed_ratio
    basis_audit = dict(source_basis, water_kg_per_litre=mixed_ratio)
    if percent != 100:
        basis_audit.update(
            status='assumed',
            uncertainty='not quantified',
            note='Blend assumes additive solution volumes and 1 kg solvent/L '
            'for ion-free water; ' + source_basis['note'],
        )
    options = {
        key: chemistry[key]
        for key in ('below_detection', 'alkalinity_eq_per_kg')
        if key in chemistry
    }
    label = f'{percent:g}% {label}, {100 - percent:g}% ion-free water'
    water = {key: value * fraction for key, value in water.items()}
    try:
        balanced = balance_water_analysis(
            chemistry['water_totals'],
            measured_ph=chemistry['measured_ph'],
            analysis_id=chemistry['water_analysis_id'],
            **options,
        )
    except DeliveryError as exc:
        return f'{label}. Chemistry not calculated: {exc}', water, None
    return (
        label,
        water,
        dict(
            water_balance=balanced.diluted(molal_fraction),
            water_analysis_id=f'{chemistry["water_analysis_id"]}-{percent:g}pct',
            concentration_basis=basis_audit,
            water_input_notes=chemistry.get('water_input_notes', []),
        ),
    )
