# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""One batch from its options to the summary: the target source, the water, the pH
reagents and joint configuration, the remedies and the ranges. The commands
``flahax batch`` and ``flahax mix`` both call ``run_batch``."""

from dataclasses import asdict, dataclass, field
import math
from pathlib import Path

from .batch_summary import EquipmentCheck, summarize_batch
from .canonical_result import seal_summary
from .delivery_contracts import DeliveryError
from .delivery_quantities import VolumeLitres
from .engine import load_library
from .fertilizer_workflow import plan_fertilizer_workflow
from .inputs import number, read_json
from .ph_adjustment import REAGENTS
from .ph_adjustment import catalogue_ph_reagents, nutrient_salts
from .result_wording import reagent_preparation
from .sonneveld import design_targets
from .stock_volumes import prepare_stocks
from .water_input import blend, read_water


ACID_FORMULAS = {f.upper(): f for f, (direction, *_) in REAGENTS.items() if direction == 'acid'}


def acid_record(spec):
    """Parse a supplier certificate, optionally including its declared
    solvent mass fraction.
    """
    parts = spec.split(':')
    if len(parts) not in (3, 4, 5):
        raise DeliveryError(
            'invalid_value',
            f'--acid {spec}: expected FORMULA:MASS_FRACTION:DENSITY[:NAME[:SOLVENT_FRACTION]]',
        )
    numbers = []
    for label, text in (('assay (mass fraction)', parts[1]), ('density (kg/L)', parts[2])):
        try:
            numbers.append(float(text))
        except ValueError:
            raise DeliveryError(
                'invalid_value', f'--acid {spec}: the {label} {text!r} is not a number'
            ) from None
    formula, (fraction, density) = parts[0].strip(), numbers
    formula = ACID_FORMULAS.get(formula.upper())
    if formula is None:
        raise DeliveryError(
            'invalid_value',
            f'--acid {spec}: the acid must be one of {", ".join(ACID_FORMULAS.values())}',
        )
    if not (0 < fraction <= 1 and math.isfinite(density) and density > 0):
        raise DeliveryError(
            'invalid_value',
            f'--acid {spec}: the assay is a fraction in (0, 1] and the density in kg/L',
        )
    name = parts[3].strip() if len(parts) >= 4 else f'{formula} {fraction:.0%}'
    solvent = None
    if len(parts) == 5:
        try:
            solvent = float(parts[4])
        except ValueError as error:
            raise DeliveryError(
                'invalid_value', 'invalid declared reagent solvent fraction'
            ) from error
        if not (math.isfinite(solvent) and 0 <= solvent <= 1 and fraction + solvent <= 1):
            raise DeliveryError(
                'invalid_value', 'solvent and active fractions must fit in one gram'
            )
    return dict(
        id=f'{formula}-{fraction:g}-{density:g}',
        name=name,
        source='user certificate (flahax batch --acid)',
        revision='1',
        recordedAt='2026-01-01T00:00:00Z',
        chemicalFormula=formula,
        massFraction=fraction,
        solventMassFraction=solvent,
        densityKgPerL=density,
    )


def choose_formula(library, formula, crop):
    """The packaged formula name chosen by ``--formula`` (exact) or
    ``--crop`` (must match one name); raises DeliveryError otherwise.
    """
    names = [f['name'] for f in library['formulas']]
    if formula:
        if formula not in names:
            raise DeliveryError(
                'unknown_formula', f'no formula named {formula!r}; see --list-formulas'
            )
        return formula
    matches = [n for n in names if crop.lower() in n.lower()]
    if len(matches) != 1:
        raise DeliveryError(
            'ambiguous_formula',
            f'--crop {crop!r} matches {len(matches)} formulas; choose one with '
            '--formula:\n  ' + '\n  '.join(matches or names),
        )
    return matches[0]


@dataclass
class BatchOptions:
    """The ``flahax batch`` flags, plus the interactive mix's tanks,
    fill mode, temperature and depth.

    With ``tank_litres`` (keys A, B and acid) the batch volume is the
    irrigation the stocks supply (``stock_volumes.prepare_stocks``) and
    ``volume`` is not used.
    """

    water: str
    formula: str | None = None
    crop: str | None = None
    targets: str | None = None
    water_share: float | None = None
    volume: float = 1000
    ph: float = 5.8
    ph_min: float | None = None
    ph_max: float | None = None
    range_percent: float | None = None
    ranges: list = field(default_factory=list)
    require_ranges: bool = False
    ratio: float = 100
    acid: list = field(default_factory=list)
    limit: list = field(default_factory=list)
    max_reagent_litres: float | None = None
    ec: float | None = None
    products: str | None = None
    rules: str | None = None
    tank_litres: dict | None = None
    available_tanks: int | None = None
    tank_capacities: list | None = None
    fit_equipment: bool = False
    mode: str = 'fill'
    irrigation_litres: float | None = None
    temperature_c: float = 25
    depth: int = 3
    title: str | None = None
    max_solid_reagent_grams: float | None = None
    confirmed_products: list[str] = field(default_factory=list)
    alternative_products: str | None = None
    alternative_search_preferences: tuple[str, ...] = ('relative_residual',)
    alternative_search_budget: int = 4
    volumetric_stocks: str | None = None
    sonneveld_targets: str | None = None
    reagents: str | None = None


# Batch search controls. The loss threshold is an exact-fit shortcut. A
# constrained local solution can finish by stationarity even when
# nutrient targets are missed.
JOINT_CONTROLS = dict(
    charge_scale=0.001,
    charge_tolerance=2e-12,
    loss_tolerance=1e-16,
    sensitivity_tolerance=0.01,
    trust_radius=10000,
    sensitivity_method='equilibrium',
    curvature_block=True,
    whole_mix=True,
    stationarity_tolerance=1e-6,
    active_bound_tolerance=1e-8,
    max_iterations=60,
    max_backtracks=20,
)


JOINT_DOSE_STEP_G_PER_L = 1e-4


def joint_configuration(products, reagents, solvent_mass_kg, cap_litres, solid_cap=None):
    """The explicit joint-fit configuration for every offered reagent.

    Only declared solvent fractions enter the joint problem. Liquid mass
    caps use their recorded densities. Dry solids use a separately
    declared mass cap.
    """
    if solid_cap is not None:
        number(solid_cap, 'solid reagent mass cap')
    pool_ids = [p['id'] for p in nutrient_salts(products)]
    solvents, masses, fallbacks, solids = {}, {}, {}, []
    for reagent in reagents:
        identity = reagent['id']
        if reagent.get('solventMassFraction') is not None:
            solvents[identity] = reagent['solventMassFraction']
        if reagent.get('physicalForm') == 'solid':
            solids.append(identity)
            if solid_cap is not None:
                masses[identity] = solid_cap
        elif reagent.get('densityKgPerL') is not None:
            density = reagent['densityKgPerL']
            number(density, f'{identity}: densityKgPerL', positive=True)
            masses[identity] = 1000 * cap_litres * density
        else:
            # Neither a known solid nor a liquid with a verifiable
            # volume cap.
            continue
        if identity not in solvents:
            fallbacks[identity] = 'joint fit needs a declared solvent fraction'
        elif identity not in masses and identity in solids:
            fallbacks[identity] = 'joint fit needs a declared solid reagent mass cap'
    return dict(
        controls={
            r['id']: dict(
                JOINT_CONTROLS,
                dose_steps={i: JOINT_DOSE_STEP_G_PER_L for i in [*pool_ids, r['id']]},
            )
            for r in reagents
        },
        solvent_mass_kg=solvent_mass_kg,
        reagent_solvent_fractions=solvents,
        maximum_reagent_mass_g=masses,
        sequential_fallbacks=fallbacks,
        solid_reagent_ids=solids,
    )


def left_out_products(library, products, confirmed_products=()):
    """One declared remedy per catalogue fertilizer the grower's product
    list leaves out.

    Only excluded catalogue IDs explicitly confirmed by the grower are
    rerun.
    """
    present = {p['id'] for p in products}
    extras = [p for p in nutrient_salts(library['salts']) if p['id'] not in present]
    if not isinstance(confirmed_products, (list, tuple)) or not all(
        isinstance(i, str) for i in confirmed_products
    ):
        raise DeliveryError('invalid_remedy', 'confirmed products must be a list of catalogue IDs')
    confirmed = set(confirmed_products)
    invalid = confirmed - {p['id'] for p in extras}
    if invalid or len(confirmed) != len(confirmed_products):
        raise DeliveryError(
            'invalid_remedy',
            'confirmed IDs must be unique excluded catalogue fertilizers'
            + (': ' + ', '.join(sorted(invalid)) if invalid else ''),
        )
    return [
        dict(
            id='catalogue:' + p['name'],
            kind='catalogue',
            available=p['id'] in confirmed,
            changes=dict(products=[p]),
        )
        for p in extras
    ]


def _product_records(records, label):
    if not isinstance(records, list):
        raise DeliveryError('invalid_value', f'{label} must be a JSON array of product records')
    names = set()
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            raise DeliveryError(
                'invalid_value',
                f'{label} must be a JSON array of product records; '
                f'{label} entry {index} must be a product record',
            )
        identity = record.get('id')
        if not isinstance(identity, str) or not identity.strip():
            raise DeliveryError(
                'invalid_value', f'{label} entry {index} needs a nonempty string id'
            )
        name = record.get('name')
        if not isinstance(name, str) or not name.strip():
            raise DeliveryError(
                'invalid_value', f'{label} entry {index} needs a nonempty string name'
            )
        if name in names:
            raise DeliveryError(
                'invalid_value', f'{label} need distinct names; {name!r} is repeated'
            )
        names.add(name)
    return records


def _target_ph(options):
    """The pH the batch aims at: ``ph``, or the interval ``(ph_min, ph_max)`` when given."""
    if options.ph_min is None and options.ph_max is None:
        return options.ph
    if options.ph_min is None or options.ph_max is None:
        raise DeliveryError('invalid_value', 'a pH interval needs both ph_min and ph_max')
    return (options.ph_min, options.ph_max)


def parse_range(text):
    """``SYMBOL=SHORTAGE:EXCESS`` to ``(symbol, override)``. Each side is ``5%`` or ``3mg``
    (mg/L); an empty side keeps the symmetric percentage, if any.
    """
    symbol, _, sides = str(text).partition('=')
    shortage, colon, excess = sides.partition(':')
    if not symbol.strip() or not colon:
        raise DeliveryError('invalid_value', f'range {text!r} must look like K=2%:5% or Ca=:4mg')
    override = {}
    for side, token in (('shortage', shortage), ('excess', excess)):
        token = token.strip()
        if not token:
            continue
        unit, digits = ('percent', token[:-1]) if token.endswith('%') else (None, token)
        if token.endswith('mg'):
            unit, digits = 'mg_per_l', token[:-2]
        if unit is None:
            raise DeliveryError('invalid_value', f'range side {token!r} needs % or mg')
        try:
            override[f'{side}_{unit}'] = float(digits)
        except ValueError:
            raise DeliveryError('invalid_value', f'range side {token!r} is not a number') from None
    return symbol.strip(), override


def _deviation_ranges(options):
    """The ``deviation_ranges`` setting the options ask for, or None."""
    if options.range_percent is None and not options.ranges:
        return None
    return dict(
        percent=options.range_percent,
        overrides=dict(parse_range(item) for item in options.ranges),
        mode='require' if options.require_ranges else 'assess',
    )


def run_batch(options):
    """The batch summary (``summarize_batch``); with tanks,
    ``summary['volumes']`` gives the stock volumes.
    """
    volumes = None
    if options.tank_litres is not None:
        volumes = prepare_stocks(
            tank_litres=options.tank_litres,
            ratio=options.ratio,
            mode=options.mode,
            irrigation_litres=options.irrigation_litres,
        )
    volume = options.volume if volumes is None else volumes.irrigation_litres
    library = load_library()
    products = _product_records(
        read_json(options.products, 'products') if options.products else library['salts'],
        'products',
    )
    target_design = None
    if options.sonneveld_targets is not None:
        if any(value is not None for value in (options.targets, options.formula, options.crop)):
            raise DeliveryError('invalid_value', 'Choose a single source of batch targets')
        target_design = design_targets(
            read_json(options.sonneveld_targets, 'Sonneveld targets'), require_approval=True
        )
        targets = target_design['targets_mg_l']
        title = options.title or Path(options.sonneveld_targets).stem
    elif options.targets:
        targets = read_json(options.targets, 'targets')
        title = options.title or Path(options.targets).stem
    else:
        title = choose_formula(library, options.formula, options.crop)
        targets = next(f['targets'] for f in library['formulas'] if f['name'] == title)
    label, water, chemistry = read_water(options.water)
    if options.water_share is not None:
        label, water, chemistry = blend(label, water, chemistry, options.water_share)
    rules = read_json(options.rules, 'rules') if options.rules else ()
    reagents = (
        read_json(options.reagents, 'pH reagents')
        if options.reagents is not None
        else catalogue_ph_reagents()
    )
    reagents = _product_records(reagents, 'pH reagents')
    reagents = _product_records(reagents + [acid_record(a) for a in options.acid], 'pH reagents')
    limits = dict(options.limit)
    cap_litres = options.max_reagent_litres or volume / 200
    joint = (
        None
        if chemistry is None
        else joint_configuration(
            products,
            reagents,
            volume * chemistry['concentration_basis']['water_kg_per_litre'],
            cap_litres,
            options.max_solid_reagent_grams,
        )
    )
    remedies = left_out_products(library, products, options.confirmed_products)
    alternative_products = (
        _product_records(
            read_json(options.alternative_products, 'alternative products'), 'alternative products'
        )
        if options.alternative_products is not None
        else []
    )
    if options.fit_equipment and not alternative_products:
        raise DeliveryError(
            'invalid_value', '--fit-equipment searches the --alternative-products; supply them'
        )
    equipment_check = (
        EquipmentCheck(
            products,
            rules=rules,
            injection_ratio=options.ratio,
            temperature_c=options.temperature_c,
            available_tanks=options.available_tanks,
            tank_capacities_litres=options.tank_capacities,
            batch_litres=volume,
        )
        if options.fit_equipment
        else None
    )
    if alternative_products:
        from .evaluated_remedies import available_product_search

        if joint is not None:
            joint['check_inventory_relaxation'] = True
        if (
            type(options.alternative_search_budget) is not int
            or options.alternative_search_budget < 1
        ):
            raise DeliveryError('invalid_remedy', 'The alternative search budget must be positive')
        remedies.insert(
            0,
            available_product_search(
                alternative_products,
                preferences=options.alternative_search_preferences,
                on_equipment_miss=options.fit_equipment,
            ),
        )
    additional_ids = [*options.confirmed_products, *(p['id'] for p in alternative_products)]
    if joint is not None and additional_ids:
        joint['additional_product_steps'] = dict.fromkeys(additional_ids, JOINT_DOSE_STEP_G_PER_L)
    workflow = plan_fertilizer_workflow(
        products,
        targets,
        water,
        _target_ph(options),
        final_volume=VolumeLitres(volume),
        equilibrium=None
        if chemistry is None
        else dict(
            chemistry,
            water_mass_kg=volume * chemistry['concentration_basis']['water_kg_per_litre'],
            carbon_boundary='closed',
            temperature_c=25,
            phases=[],
        ),
        ph_adjustment=dict(
            products=reagents,
            correct_mixed_ph=True,
            maximum_reagent_volume_litres=cap_litres,
            **({} if joint is None else {'joint': joint}),
        ),
        maximum_concentrations=limits or None,
        volumetric_stocks=(
            read_json(options.volumetric_stocks, 'volumetric stocks')
            if options.volumetric_stocks is not None
            else None
        ),
        remedy_options=remedies,
        equipment_check=equipment_check,
        deviation_ranges=_deviation_ranges(options),
        max_remedy_evaluations=len(options.confirmed_products)
        + (options.alternative_search_budget if alternative_products else 0),
    )
    summary = summarize_batch(
        workflow,
        products,
        title=title,
        water_label=label,
        injection_ratio=options.ratio,
        rules=rules,
        temperature_c=options.temperature_c,
        available_tanks=options.available_tanks,
        tank_capacities_litres=options.tank_capacities,
        requested_ec_ms_cm=options.ec,
    )
    if target_design is not None:
        summary['sonneveld_target_design'] = target_design
    if chemistry is not None:
        for note in chemistry.get('water_input_notes', []):
            if note not in summary['warnings']:
                summary['warnings'].append(note)
        summary['concentration_basis'] = dict(
            chemistry['concentration_basis'],
            final_volume_litres=volume,
            water_mass_kg=volume * chemistry['concentration_basis']['water_kg_per_litre'],
        )
        warning = (
            'Concentration basis: '
            + chemistry['concentration_basis']['note']
            + ' Uncertainty: '
            + chemistry['concentration_basis']['uncertainty']
            + '.'
        )
        if warning not in summary['warnings']:
            summary['warnings'].append(warning)

    if volumes is not None:
        summary['volumes'] = dict(asdict(volumes), mode=options.mode)
        summary['reagent_preparation'] = reagent_preparation(summary)
        preparation = summary['reagent_preparation']
        if preparation and preparation['status'] == 'blocked':
            summary['status'] = 'blocked'
            summary['statuses'].update(overall='blocked', delivery='blocked')
            summary['stages']['reagent_preparation'] = dict(
                status='blocked',
                error_code=None,
                message=preparation['message'],
                required_inputs=[],
            )
            summary['warnings'].append('reagent_preparation: ' + preparation['message'])
    weighed = {p['name'] for t in summary['tanks']['tanks'] for p in t['products']}
    summary['product_notes'] = {
        r['name']: list(
            r.get('compatibility_notes') or (r.get('grade') or {}).get('compatibility_notes') or []
        )
        for r in products
        if r.get('name') in weighed
    }
    summary['product_notes'] = {k: v for k, v in summary['product_notes'].items() if v}
    return seal_summary(summary)
