# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Explicit, inspectable water-to-recipe-to-chemistry planning orchestration."""

from dataclasses import dataclass, field
import math
from collections.abc import Mapping

from .calculated_ph import calculate_equilibrium_ph
from .canonical_result import CanonicalResult
from .composition import validate_profile
from .delivery_contracts import DeliveryError
from .delivery_quantities import SolventBasis, VolumeLitres, final_solution_recipe
from .engine import recommend, gap_for, load_library
from .measured_water import (
    DEFAULT_MAXIMUM_IMBALANCE_PERCENT,
    BalancedWaterAnalysis,
    balance_water_analysis,
    nutrient_mg_per_litre,
)
from .equilibrium_delivery import plan_equilibrium_delivery
from .ph_planning import plan_ph
from .product_conversion import catalogue_dose_totals
from .material_chemistry import material_chemistry
from .materials import make_grade, resolve_material
from .stock_planning import plan_stocks
from .acid_selection import plan_acid_options
from .ph_adjustment import plan_coupled_ph
from .nutrient_acceptance import (
    assess_incidental,
    assess_water_basis,
    assessed_limits,
    name_sources,
)


# Feed-solution pH guidance (research report 2026-10-20): Dutch soilless practice feeds at
# about pH 5.3-5.8 (Van der Lugt et al.; Savvas); 5.0-7.0 is the acceptable outer band.
RECOMMENDED_FEED_PH = (5.3, 5.8)
ACCEPTABLE_FEED_PH = (5.0, 7.0)
# Chemistry a later stage may build on: calculated, or calculated on an assumed charge closure
# (review).
USABLE = ('calculated', 'requires_review')
ASSUMED_CLOSURE = (
    'the water analysis was closed on {ion} without a stated measurement uncertainty '
    '({change:+.2f}% {ion}); pH, saturation and dose rest on that assumption. Targets and limits '
    'use the laboratory values (#84).'
)


@dataclass
class WorkflowStage:
    """One workflow stage: its status, value, the inputs it still needs, or the error code and
    message that stopped it.
    """

    status: str
    value: object = None
    required_inputs: tuple = ()
    error_code: str | None = None
    message: str | None = None


@dataclass
class FertilizerWorkflow:
    """The recommendation, water, nutrient gap and pH target, with each stage's result; the pH must
    still be measured after mixing.
    """

    recommendation: dict
    water: dict
    nutrient_gap: dict
    target_ph: float
    stages: dict = field(default_factory=dict)
    post_mix_measurement_required: bool = True
    maximum_concentrations: dict | None = None
    # Laboratory and charge-balanced water at the final volume, and the limits whose decision
    # the balancing alone would change (#84). None when the water was not charge-balanced.
    water_basis: dict | None = None
    canonical_result: CanonicalResult | None = None
    remedies: dict = field(default_factory=dict)


def _positive(value, name):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise DeliveryError('invalid_value', f'{name} must be finite and positive')
    return float(value)


def _graded(supplied, library):
    """Catalogue record and resolved material of a product carrying a supplier label grade.

    The record keeps the catalogue name and formula, takes the resolved label assay as its
    elements and is identified by the catalogue id or the resolved id (<catalogue id>+<grade id>).
    A compound declared from its data sheet (composition ``declared_ions``) is its own record,
    identified by its grade id, which must not be a catalogue id.
    """
    name = supplied.get('name')
    if (
        isinstance(supplied['grade'], Mapping)
        and supplied['grade'].get('composition') == 'declared_ions'
    ):
        resolved = resolve_material(name, grade=make_grade(supplied['grade']))
        if (
            supplied.get('id') != resolved.record['id']
            or supplied['id'] in library
            or supplied.get('elements') != resolved.record['elements']
        ):
            raise DeliveryError(
                'product_chemistry_mismatch',
                f'{name}: a declared compound is identified by its '
                'grade id and takes the label assay',
            )
        return dict(supplied), resolved
    reference = next((p for p in library.values() if p['name'] == name), None)
    if reference is None:
        raise DeliveryError(
            'product_chemistry_mismatch', f'graded product {name!r} is not a catalogue product'
        )
    grade = make_grade(supplied['grade'])
    if 'identity_inconsistent' in grade.flags:
        raise DeliveryError(
            'identity_inconsistent',
            f'{name}: the analysis of grade {grade.grade_id!r} '
            f'does not fit the identity (charge residual {grade.charge_residual_percent:.2f} %)'
            if grade.charge_residual_percent is not None
            else f'{name}: the analysis range of grade {grade.grade_id!r} excludes the identity',
        )
    resolved = resolve_material(name, grade=grade)
    if (
        supplied.get('id') not in (reference['id'], resolved.record['id'])
        or supplied.get('formula') != reference.get('formula')
        or supplied.get('elements') != resolved.record['elements']
    ):
        raise DeliveryError(
            'product_chemistry_mismatch',
            f'{name}: a graded product keeps its catalogue identity and takes the label assay',
        )
    return reference, resolved


def _dose_totals(doses, materials, products):
    """Dose totals of the supplied records; graded products convert through their resolved
    material."""
    return catalogue_dose_totals(
        doses, materials={n: m for n, m in materials.items() if n in doses}, products=products
    )


# A dosed product whose declared ions cannot be modelled: nutrients stand, no pH is planned.
NOT_MODELLABLE = 'ph_not_planned_for_product'


def _not_planned(stage):
    """A stage stopped by a product that cannot be modelled needs input; it is not a block."""
    if stage.error_code == NOT_MODELLABLE:
        stage.status = 'needs_input'


def unreviewed_reason(recommendation):
    """Why a feasible formulation needs review: incidental nutrients with no declared maximum."""
    found = [
        f'{row["symbol"]} {row["ppm"]:.3g} mg/L'
        for row in recommendation['incidentalContributions']
        if row['assessment'] == 'requires_review'
    ]
    return (
        (
            'incidental nutrients with no declared maximum: '
            + ', '.join(found)
            + '; check them, or declare maximum concentrations'
        )
        if found
        else None
    )


def limit_message(recommendation):
    """Why a recipe is not feasible, in plain words: a declared maximum it breaks, else the
    targets it misses by >1 %."""
    broken = [
        f'{v["symbol"]} would be {v["ppm"]:.3g} mg/L, above the declared maximum '
        f'{v["maximumPpm"]:.3g} mg/L'
        for v in recommendation['limitViolations']
    ]
    if broken:
        return '; '.join(broken)
    missed = [
        f'{r["symbol"]} {r["deltaPct"]:+.1f} %'
        for r in recommendation['rows']
        if r['target'] and r['deltaPct'] is not None and abs(r['deltaPct']) > 1
    ]
    return (
        ('targets missed by more than 1 %: ' + ', '.join(missed))
        if missed
        else 'no recipe meets the targets'
    )


def no_reagent_message(plan):
    """Why no pH reagent was selected: none offered in the needed direction, or the reasons each
    one failed."""
    if any(c.joint_result is not None for c in plan.candidates):
        return 'no offered candidate has passed joint workflow acceptance: ' + '; '.join(
            f'{(c.product_record or {}).get("name") or c.product_id}: '
            f'{c.message or (c.joint_result or {}).get("reason") or c.error_code or c.status}'
            for c in plan.candidates
        )
    need = 'an acid' if plan.direction == 'acid' else 'a base'
    tried = [
        c
        for c in plan.candidates
        if c.direction == plan.direction and c.status != 'not_applicable'
    ]
    if not tried:
        return (
            f'the feed mixes at pH {plan.unadjusted_ph:.2f} and needs {need} to reach pH '
            f'{plan.target_ph:.2f}; '
            f'none was offered: add {need}'
        )
    return f'no {plan.direction} reaches pH {plan.target_ph:.2f} acceptably: ' + '; '.join(
        f'{(c.product_record or {}).get("name") or c.product_id}: '
        f'{c.message or c.error_code or c.status}'
        for c in tried
    )


def _water_ppm(totals, mass, volume):
    return nutrient_mg_per_litre(totals, mass, volume)


def plan_fertilizer_workflow(
    salts,
    targets,
    water,
    target_ph,
    *,
    final_volume=None,
    equilibrium=None,
    nitric=None,
    titration=None,
    stocks=None,
    acids=None,
    maximum_concentrations=None,
    ph_adjustment=None,
    remedy_options=(),
    max_remedy_evaluations=20,
):
    """Run available stages; expose missing inputs and rejected stages separately.

    Water nutrient mg/L is mandatory ({} explicitly denotes zero nutrients).
    It is never silently promoted to a complete acid/base analysis. Optional
    configurations are mappings documented in docs/water-to-delivery.md.
    No stage performs external writes, mixing or equipment operation.
    remedy_options declares catalogue bundles, treated-water analyses or stock
    equipment alternatives. Up to max_remedy_evaluations scenarios are re-run
    with unchanged targets/limits; no candidate is adopted automatically.

    ph_adjustment (products, maximum_reagent_volume_litres, optional
    preferred_product_id and joint) plans the recipe and its pH reagent together (#74):
    acids or bases, with the reagent's nutrients counted as supply. It needs the
    equilibrium configuration and final_volume; see ph_adjustment.plan_coupled_ph.
    joint requires explicit controls, solvent_mass_kg, reagent_solvent_fractions
    and maximum_reagent_mass_g. Its final solvent basis must match the equilibrium
    water_mass_kg. Optional starting_points are never accepted without verification.
    """
    if not isinstance(water, Mapping):
        raise DeliveryError('missing_field', 'explicit water nutrient concentrations are required')
    if (
        isinstance(target_ph, bool)
        or not isinstance(target_ph, (int, float))
        or not math.isfinite(target_ph)
        or not 0 <= target_ph <= 14
    ):
        raise DeliveryError('out_of_range', 'target_ph must be finite in [0,14]')
    for config in (equilibrium, nitric, titration, stocks, acids, ph_adjustment):
        if config is not None and not isinstance(config, Mapping):
            raise DeliveryError('invalid_type', 'stage configurations must be mappings')
    targets = validate_profile(dict(targets), 'targets')
    water = validate_profile(dict(water), 'water')
    recommendation = recommend(
        salts, targets, water, maximum_concentrations=maximum_concentrations
    )
    # One assessment: the user's limits plus the ammonium allowance recommend applied (#92).
    limits = assessed_limits(maximum_concentrations, recommendation)
    recommendation.update(
        name_sources(
            assess_incidental(recommendation['rows'], limits),
            recommendation['salts'],
            salts,
            water,
        )
    )
    if recommendation['limitViolations']:
        recommendation['feasible'] = False
    if not ACCEPTABLE_FEED_PH[0] <= target_ph <= ACCEPTABLE_FEED_PH[1]:
        recommendation['warnings'].append(
            f'Target pH {target_ph:g} is outside '
            f'{ACCEPTABLE_FEED_PH[0]:g}-{ACCEPTABLE_FEED_PH[1]:g}, the range '
            'acceptable for most soilless crops.'
        )
    elif not RECOMMENDED_FEED_PH[0] <= target_ph <= RECOMMENDED_FEED_PH[1]:
        recommendation['warnings'].append(
            f'Target pH {target_ph:g} is outside the '
            f'{RECOMMENDED_FEED_PH[0]:g}-{RECOMMENDED_FEED_PH[1]:g} feed range of '
            'Dutch soilless practice (root zone about 5.5-6.0).'
        )
    output = FertilizerWorkflow(recommendation, water, gap_for(targets, water), float(target_ph))
    stages = output.stages

    def run(name, action):
        try:
            value = action()
        except DeliveryError as exc:
            stages[name] = WorkflowStage('blocked', error_code=exc.code, message=str(exc))
            return None
        stages[name] = WorkflowStage('calculated', value=value)
        return value

    def missing(name, config, required):
        absent = tuple(
            key for key in required if config is None or key not in config or config[key] is None
        )
        if absent:
            stages[name] = WorkflowStage('needs_input', required_inputs=absent)
        return bool(absent)

    stages['formulation'] = WorkflowStage(
        'calculated' if recommendation['feasible'] else 'blocked',
        value=recommendation,
        error_code=None if recommendation['feasible'] else 'infeasible_recipe',
        message=None if recommendation['feasible'] else limit_message(recommendation),
    )
    if recommendation['feasible'] and recommendation['requiresReview']:
        stages['formulation'].status = 'requires_review'
        stages['formulation'].message = unreviewed_reason(recommendation)
    recipe = None
    if final_volume is None:
        stages['batch'] = WorkflowStage('needs_input', required_inputs=('final_volume',))
    elif not isinstance(final_volume, VolumeLitres):
        raise DeliveryError('invalid_type', 'final_volume must be VolumeLitres')
    else:
        recipe = final_solution_recipe(recommendation, final_volume)
        stages['batch'] = WorkflowStage('calculated', value=recipe)

    required = (
        'water_totals',
        'water_mass_kg',
        'water_analysis_id',
        'complete_analysis',
        'carbon_boundary',
        'temperature_c',
        'phases',
    )
    if equilibrium is not None and equilibrium.get('water_balance') is not None:
        required = required[1:]  # the balanced record carries its own analytical totals
    if not missing('chemistry', equilibrium, required):
        if recipe is None:
            stages['chemistry'] = WorkflowStage('needs_input', required_inputs=('final_volume',))
        else:

            def chemical_states():
                materials, records = {}, {}
                config = equilibrium
                mass = _positive(config['water_mass_kg'], 'water_mass_kg')
                solvent = SolventBasis(final_volume.value, mass)
                if (
                    not isinstance(config['water_analysis_id'], str)
                    or not config['water_analysis_id'].strip()
                ):
                    raise DeliveryError('missing_field', 'water_analysis_id is required')
                kwargs = {
                    key: config[key]
                    for key in ('complete_analysis', 'carbon_boundary', 'temperature_c', 'phases')
                }
                balance = config.get('water_balance')
                # Two inventories (#84): ``analytical`` is the laboratory analysis and decides
                # targets and limits; ``water_totals`` is what the chemistry uses (balanced when it
                # was closed).
                if balance is not None:
                    if not isinstance(balance, BalancedWaterAnalysis):
                        raise DeliveryError(
                            'invalid_type', 'water_balance must be a BalancedWaterAnalysis'
                        )
                    if config.get('measured_ph') is not None:
                        raise DeliveryError(
                            'contradictory_water_inputs',
                            'supply measured_ph or a prepared water_balance, not both',
                        )
                    if (
                        config.get('water_totals') is not None
                        and dict(config['water_totals']) != balance.analytical_totals
                    ):
                        raise DeliveryError(
                            'contradictory_water_inputs',
                            'water_totals differ from the water_balance analytical totals',
                        )
                    if (
                        config['complete_analysis'] is not True
                        or config['carbon_boundary'] != 'closed'
                    ):
                        raise DeliveryError(
                            'contradictory_water_inputs',
                            'a balanced analysis is complete with closed inorganic carbon',
                        )
                    analytical = dict(balance.analytical_totals)
                    water_state = balance.state
                    water_totals = dict(balance.totals)
                elif config.get('measured_ph') is None:
                    analytical = dict(config['water_totals'])
                    water_state = calculate_equilibrium_ph(config['water_totals'], **kwargs)
                    water_totals = dict(config['water_totals'])
                else:
                    analytical = dict(config['water_totals'])
                    # Speciate at the laboratory's measured pH and close the charge
                    # on a named ion, instead of letting analytical error set the pH.
                    if config['complete_analysis'] is not True:
                        raise DeliveryError(
                            'incomplete_water_analysis',
                            'complete analytical totals must be explicitly declared',
                        )
                    if config['carbon_boundary'] != 'closed':
                        raise DeliveryError(
                            'unsupported_carbon_boundary',
                            'calculated pH requires closed analytical inorganic carbon',
                        )
                    balance = balance_water_analysis(
                        config['water_totals'],
                        measured_ph=config['measured_ph'],
                        alkalinity_eq_per_kg=config.get('alkalinity_eq_per_kg'),
                        balance_ion=config.get('balance_ion', 'Cl-'),
                        maximum_imbalance_percent=config.get(
                            'maximum_imbalance_percent', DEFAULT_MAXIMUM_IMBALANCE_PERCENT
                        ),
                        phases=config['phases'],
                        temperature_c=config['temperature_c'],
                        analysis_id=config['water_analysis_id'],
                        balance_ion_uncertainty_percent=config.get(
                            'balance_ion_uncertainty_percent'
                        ),
                        fixed=tuple(config.get('fixed', ())),
                        below_detection=config.get('below_detection'),
                    )
                    water_state = balance.state
                    water_totals = dict(balance.totals)
                # The formulation's water mg/L must be the laboratory analysis, never the balanced
                # model.
                expected = _water_ppm(analytical, mass, final_volume.value)
                for ion in set(expected) | set(water):
                    if not math.isclose(
                        expected.get(ion, 0), water.get(ion, 0), rel_tol=1e-6, abs_tol=1e-6
                    ):
                        raise DeliveryError(
                            'inconsistent_water_analysis',
                            f'nutrient ppm and molal water disagree for {ion}',
                        )
                library = {p['id']: p for p in load_library()['salts']}
                for supplied in salts:
                    if 'grade' in supplied:
                        reference, resolved = _graded(supplied, library)
                        materials[supplied['name']] = resolved
                        library[supplied['id']] = reference
                        continue
                    reference = library.get(supplied.get('id'))
                    if reference is not None:
                        # A catalogue id is a claim to be that pre-filled material, unchanged.
                        if any(
                            supplied.get(key) != reference.get(key)
                            for key in ('name', 'formula', 'elements')
                        ):
                            raise DeliveryError(
                                'product_chemistry_mismatch',
                                'supplied products must retain catalogue identity and assay',
                            )
                    else:
                        # A material of its own: its formula, ions or analysis define it (Task 11).
                        material_chemistry(supplied)
                        library[supplied.get('id')] = supplied
                    records[supplied['name']] = supplied
                doses = {}
                for salt in recipe.salts:
                    product = library.get(salt.salt_id)
                    if product is None or product['name'] != salt.name:
                        raise DeliveryError(
                            'product_chemistry_mismatch',
                            'chemistry requires the supplied product records',
                        )
                    doses[salt.name] = doses.get(
                        salt.name, 0
                    ) + solvent.grams_per_litre_to_grams_per_kg_water(salt.dose.value)
                totals = dict(water_totals)
                for basis, amount in _dose_totals(doses, materials, records).items():
                    totals[basis] = totals.get(basis, 0) + amount
                mixed = calculate_equilibrium_ph(totals, **kwargs)
                return {
                    'water': water_state,
                    'mixed': mixed,
                    'product_doses_g_per_kg_water': doses,
                    'materials': materials,
                    'products': records,
                    'water_analysis_id': config['water_analysis_id'],
                    'carbon_boundary': config['carbon_boundary'],
                    'water_totals': water_totals,
                    'analytical_water_totals': analytical,
                    'water_balance': balance,
                    'water_input_notes': config.get('water_input_notes', []),
                    'concentration_basis': config.get(
                        'concentration_basis',
                        {
                            'status': 'declared',
                            'water_kg_per_litre': mass / final_volume.value,
                            'uncertainty': 'not supplied',
                            'note': 'Final solvent inventory includes carrier and '
                            'dissolved hydrate water.',
                        },
                    ),
                }

            value = run('chemistry', chemical_states)
            _not_planned(stages['chemistry'])
            balance = value and value['water_balance']
            if balance is not None and balance and balance.reconciliation == 'assumed':
                stages['chemistry'].status = 'requires_review'
                stages['chemistry'].message = ASSUMED_CLOSURE.format(
                    ion=balance.balance_ion,
                    change=100
                    * balance.balance_adjustment_molal
                    / balance.analysed_balance_ion_molal,
                )

    if not missing(
        'nitric',
        nitric,
        (
            'reagent',
            'reagent_channel_id',
            'maximum_reagent_volume',
            'maximum_nutrient_error_percent',
        ),
    ):
        if stages['chemistry'].status not in USABLE:
            stages['nitric'] = WorkflowStage(
                'blocked',
                error_code='chemistry_required',
                message='complete calculated chemistry is required',
            )
        else:
            run(
                'nitric',
                lambda: plan_equilibrium_delivery(
                    recipe,
                    water_mass_kg=equilibrium['water_mass_kg'],
                    water_totals=stages['chemistry'].value['water_totals'],
                    analytical_water_totals=stages['chemistry'].value['analytical_water_totals'],
                    water_analysis_id=equilibrium['water_analysis_id'],
                    initial_ph=stages['chemistry'].value['mixed'].ph,
                    target_ph=target_ph,
                    targets=targets,
                    temperature_c=equilibrium['temperature_c'],
                    phases=equilibrium['phases'],
                    maximum_concentrations=limits,
                    **{
                        key: nitric[key]
                        for key in (
                            'reagent',
                            'reagent_channel_id',
                            'maximum_reagent_volume',
                            'maximum_nutrient_error_percent',
                        )
                    },
                ),
            )
            if (
                stages['nitric'].value is not None
                and stages['nitric'].value.incidental_assessment['requiresReview']
            ):
                stages['nitric'].status = 'requires_review'

    if not missing(
        'titration', titration, ('water_analysis', 'curve', 'reagent', 'maximum_reagent_volume')
    ):
        if recipe is None:
            stages['titration'] = WorkflowStage('needs_input', required_inputs=('final_volume',))
        elif not recommendation['feasible']:
            stages['titration'] = WorkflowStage(
                'blocked', error_code='infeasible_recipe', message=limit_message(recommendation)
            )
        else:

            def titration_plan():
                if not isinstance(titration['water_analysis'], Mapping):
                    raise DeliveryError(
                        'invalid_type', 'titration water_analysis must be a mapping'
                    )
                if titration['water_analysis'].get('ions') != water:
                    raise DeliveryError(
                        'inconsistent_water_analysis',
                        'titration water ions must match formulation water',
                    )
                plan = plan_ph(
                    titration['water_analysis'],
                    titration['curve'],
                    titration['reagent'],
                    target_ph,
                    final_volume,
                    titration['maximum_reagent_volume'],
                    {row['symbol']: row['final'] for row in recommendation['rows']},
                    targets,
                )
                tolerance = _positive(
                    titration.get('maximum_nutrient_error_percent', 1),
                    'maximum_nutrient_error_percent',
                )
                if any(
                    row['deltaPct'] is not None and abs(row['deltaPct']) > tolerance
                    for row in plan.rows
                ):
                    raise DeliveryError(
                        'nutrient_tolerance_exceeded',
                        'titration dose violates a positive nutrient target',
                    )
                if assess_incidental(plan.rows, limits)['limitViolations']:
                    raise DeliveryError(
                        'nutrient_limit_exceeded',
                        'titration dose exceeds an explicit nutrient maximum',
                    )
                return plan

            plan = run('titration', titration_plan)
            if plan is not None and assess_incidental(plan.rows, limits)['requiresReview']:
                stages['titration'].status = 'requires_review'

    if not missing(
        'acid_selection',
        acids,
        ('products', 'maximum_nutrient_error_percent', 'maximum_reagent_volume_litres'),
    ):
        if (
            not isinstance(acids['products'], (list, tuple))
            or not acids['products']
            or any(
                not isinstance(p, Mapping) or p.get('chemicalFormula') not in ('HNO3', 'H3PO4')
                for p in acids['products']
            )
        ):
            stages['acid_selection'] = WorkflowStage(
                'blocked',
                error_code='unsupported_standard_acid',
                message='Standard fertigation workflow accepts only nitric (HNO3) and '
                'phosphoric (H3PO4) products.',
            )
        elif stages['chemistry'].status not in USABLE:
            stages['acid_selection'] = WorkflowStage('blocked', error_code='chemistry_required')
        elif not recommendation['feasible']:
            stages['acid_selection'] = WorkflowStage(
                'blocked', error_code='infeasible_recipe', message=limit_message(recommendation)
            )
        else:
            state = stages['chemistry'].value['mixed']
            selection = run(
                'acid_selection',
                lambda: plan_acid_options(
                    state.totals,
                    state.ph,
                    target_ph,
                    products=acids['products'],
                    water_mass_kg=equilibrium['water_mass_kg'],
                    final_volume_litres=final_volume.value,
                    achieved={row['symbol']: row['final'] for row in recommendation['rows']},
                    targets=targets,
                    maximum_nutrient_error_percent=acids['maximum_nutrient_error_percent'],
                    maximum_reagent_volume_litres=acids['maximum_reagent_volume_litres'],
                    preferred_product_id=acids.get('preferred_product_id'),
                    phases=equilibrium['phases'],
                    maximum_concentrations=limits,
                ),
            )
            if selection is not None and selection.selected_product_id is None:
                stages['acid_selection'] = WorkflowStage(
                    'blocked', value=selection, error_code='no_acceptable_acid'
                )

    if not missing('ph_adjustment', ph_adjustment, ('products', 'maximum_reagent_volume_litres')):
        if stages['chemistry'].error_code == NOT_MODELLABLE:
            stages['ph_adjustment'] = WorkflowStage(
                'needs_input', error_code=NOT_MODELLABLE, message=stages['chemistry'].message
            )
        elif stages['chemistry'].status not in USABLE:
            stages['ph_adjustment'] = WorkflowStage(
                'blocked',
                error_code='chemistry_required',
                message='complete calculated chemistry is required',
            )
        else:
            water_totals = stages['chemistry'].value['water_totals']
            mass = equilibrium['water_mass_kg']
            kwargs = {
                key: equilibrium[key]
                for key in ('complete_analysis', 'carbon_boundary', 'temperature_c', 'phases')
            }

            def mix(candidate):
                doses = {}
                for salt in final_solution_recipe(candidate, final_volume).salts:
                    doses[salt.name] = doses.get(salt.name, 0) + salt.mass.value / mass
                totals = dict(water_totals)
                for basis, amount in _dose_totals(
                    doses,
                    stages['chemistry'].value['materials'],
                    stages['chemistry'].value['products'],
                ).items():
                    totals[basis] = totals.get(basis, 0) + amount
                return calculate_equilibrium_ph(totals, **kwargs)

            plan = run(
                'ph_adjustment',
                lambda: plan_coupled_ph(
                    salts,
                    targets,
                    water,
                    target_ph,
                    products=ph_adjustment['products'],
                    mix=mix,
                    water_mass_kg=mass,
                    final_volume_litres=final_volume.value,
                    maximum_reagent_volume_litres=ph_adjustment['maximum_reagent_volume_litres'],
                    preferred_product_id=ph_adjustment.get('preferred_product_id'),
                    joint=ph_adjustment.get('joint'),
                    water_components=water_totals,
                    phases=equilibrium['phases'],
                    maximum_concentrations=maximum_concentrations,
                ),
            )
            _not_planned(stages['ph_adjustment'])
            if plan is not None:
                chosen = plan.selected
                if chosen is None:
                    stages['ph_adjustment'] = WorkflowStage(
                        'blocked',
                        value=plan,
                        error_code='no_acceptable_reagent',
                        message=no_reagent_message(plan),
                    )
                elif assess_incidental(
                    chosen.recommendation['rows'],
                    assessed_limits(maximum_concentrations, chosen.recommendation),
                )['limitViolations']:
                    # Final acceptance on the laboratory basis: a hard limit is never downgraded to
                    # review.
                    stages['ph_adjustment'] = WorkflowStage(
                        'blocked',
                        value=plan,
                        error_code='nutrient_limit_exceeded',
                        message='the selected plan exceeds an explicit nutrient maximum',
                    )
                elif not chosen.recommendation['feasible'] or chosen.status == 'requires_review':
                    stages['ph_adjustment'].status = 'requires_review'
                    missed = ', '.join(
                        f'{u["symbol"]} {u["deltaPct"]:+.1f}% ({u["reason"]})'
                        for u in chosen.recommendation.get('unmetTargets', [])
                    )
                    stages['ph_adjustment'].message = '; '.join(
                        filter(
                            None, [chosen.message, f'targets missed: {missed}' if missed else None]
                        )
                    )

    if not missing(
        'stocks',
        stocks,
        ('injection_ratio', 'tanks', 'compatibility_rules', 'solubility_limits', 'temperature'),
    ):
        if recipe is None:
            stages['stocks'] = WorkflowStage('needs_input', required_inputs=('final_volume',))
        else:
            run(
                'stocks',
                lambda: plan_stocks(
                    recipe,
                    stocks['injection_ratio'],
                    stocks['tanks'],
                    stocks['compatibility_rules'],
                    stocks['solubility_limits'],
                    stocks['temperature'],
                    mixture_model=stocks.get('mixture_model'),
                    max_assignments=stocks.get('max_assignments', 100000),
                ),
            )

    stock_stage = stages.get('stocks')
    if (
        stock_stage is not None
        and stock_stage.value is not None
        and stock_stage.status == 'calculated'
    ):
        if not stock_stage.value.mixture_approved:
            stock_stage.status = 'requires_review'
            stock_stage.message = (
                'Separation assignment only; stock mixture applicability is unqualified.'
            )

    output.maximum_concentrations = dict(maximum_concentrations or {})
    chemistry_stage = stages.get('chemistry')
    if chemistry_stage is not None and chemistry_stage.status == 'requires_review':
        # A plan built on an assumed charge closure is usable only after review; a block stays a
        # block.
        for name in ('nitric', 'acid_selection', 'ph_adjustment'):
            if name in stages and stages[name].status == 'calculated':
                stages[name].status = 'requires_review'
                stages[name].message = '; '.join(
                    filter(None, [stages[name].message, chemistry_stage.message])
                )
    if (
        chemistry_stage is not None
        and chemistry_stage.status in USABLE
        and chemistry_stage.value['water_balance']
    ):
        _review_water_basis(
            output, equilibrium['water_mass_kg'], final_volume.value, maximum_concentrations
        )
    request = dict(
        salts=salts,
        targets=targets,
        water=water,
        target_ph=target_ph,
        final_volume=final_volume,
        equilibrium=equilibrium,
        nitric=nitric,
        titration=titration,
        stocks=stocks,
        acids=acids,
        maximum_concentrations=maximum_concentrations,
        ph_adjustment=ph_adjustment,
    )
    from .evaluated_remedies import evaluate_remedies

    output.remedies = evaluate_remedies(output, request, remedy_options, max_remedy_evaluations)
    output.canonical_result = CanonicalResult.capture(
        output,
        dict(
            **request,
            remedy_options=remedy_options,
            max_remedy_evaluations=max_remedy_evaluations,
        ),
    )
    return output


def _review_water_basis(output, mass, volume, maximum_concentrations):
    """Record laboratory and balanced water side by side; flag limits the balancing alone would
    flip (#84)."""
    stages, chemistry = output.stages, output.stages['chemistry'].value
    balance = chemistry['water_balance']
    analytical = _water_ppm(chemistry['analytical_water_totals'], mass, volume)
    modelled = _water_ppm(chemistry['water_totals'], mass, volume)
    finals = {'formulation': output.recommendation['rows']}
    if stages.get('nitric') and stages['nitric'].value is not None:
        finals['nitric'] = stages['nitric'].value.rows
    if stages.get('titration') and stages['titration'].value is not None:
        finals['titration'] = stages['titration'].value.rows
    plan = stages['ph_adjustment'].value if stages.get('ph_adjustment') else None
    if plan is not None and plan.selected is not None:
        finals['ph_adjustment'] = plan.selected.recommendation['rows']
    findings = {}
    for name, rows in finals.items():
        found = assess_water_basis(rows, maximum_concentrations, analytical, modelled)
        if found:
            findings[name] = found
            stage = stages[name]
            # Review never downgrades a hard failure: only a passing stage moves to review.
            if stage.status == 'calculated':
                stage.status = 'requires_review'
            stage.message = '; '.join(
                filter(None, [stage.message] + [f['message'] for f in found])
            )
    output.water_basis = {
        'decisionBasis': 'laboratory analysis',
        'analysisId': chemistry['water_analysis_id'],
        'balanceIon': balance.balance_ion,
        'imbalancePercent': balance.imbalance_percent,
        'reconciliation': balance.reconciliation,
        'fixed': list(balance.fixed),
        'belowDetectionMolal': dict(balance.below_detection),
        'balanceIonUncertaintyPercent': balance.balance_ion_uncertainty_percent,
        'dilutionFraction': balance.dilution_fraction,
        'measuredPh': balance.measured_ph,
        'analyticalPpm': analytical,
        'modelledPpm': modelled,
        'adjustmentPpm': {
            ion: modelled.get(ion, 0.0) - analytical.get(ion, 0.0)
            for ion in set(analytical) | set(modelled)
            if abs(modelled.get(ion, 0.0) - analytical.get(ion, 0.0)) > 1e-9
        },
        'findings': findings,
    }
