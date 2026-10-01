"""Explicit, inspectable water-to-recipe-to-chemistry planning orchestration."""
from dataclasses import dataclass, field
import math
from collections.abc import Mapping

from .calculated_ph import calculate_equilibrium_ph
from .composition import validate_profile
from .delivery_contracts import DeliveryError
from .delivery_quantities import VolumeLitres, final_solution_recipe
from .engine import recommend, gap_for, load_library
from .equilibrium_delivery import plan_equilibrium_delivery
from .ph_planning import plan_ph
from .product_conversion import catalogue_dose_totals, MOLAR_MASS
from .stock_planning import plan_stocks
from .acid_selection import plan_acid_options
from .nutrient_acceptance import assess_incidental


@dataclass
class WorkflowStage:
    status: str
    value: object = None
    required_inputs: tuple = ()
    error_code: str | None = None
    message: str | None = None


@dataclass
class FertilizerWorkflow:
    recommendation: dict
    water: dict
    nutrient_gap: dict
    target_ph: float
    stages: dict = field(default_factory=dict)
    post_mix_measurement_required: bool = True


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise DeliveryError('invalid_value', f'{name} must be finite and positive')
    return float(value)


def _water_ppm(totals, mass, volume):
    mapping = {'Ca+2':'Ca', 'Mg+2':'Mg', 'K+':'K', 'Na+':'Na', 'Cl-':'Cl',
               'NO3-':'N_NO3', 'NH4+':'N_NH4', 'PO4-3':'P', 'SO4-2':'S',
               'Fe+3':'Fe', 'Fe+2':'Fe', 'Mn+2':'Mn', 'Zn+2':'Zn', 'Cu+2':'Cu',
               'H3BO3':'B', 'MoO4-2':'Mo', 'Ure':'N_UREA'}
    ppm = {}
    for basis, ion in mapping.items():
        molar = 35.453 if ion == 'Cl' else MOLAR_MASS[ion.split('_')[0]]
        value = totals.get(basis, 0) * molar * mass * 1000 / volume
        ppm[ion] = ppm.get(ion, 0) + value * (2 if basis == 'Ure' else 1)
    return ppm


def plan_fertilizer_workflow(salts, targets, water, target_ph, *, final_volume=None,
                             equilibrium=None, nitric=None, titration=None, stocks=None, acids=None,
                             maximum_concentrations=None):
    """Run available stages; expose missing inputs and rejected stages separately.

    Water nutrient mg/L is mandatory ({} explicitly denotes zero nutrients).
    It is never silently promoted to a complete acid/base analysis. Optional
    configurations are mappings documented in docs/water-to-delivery.md.
    No stage performs external writes, mixing or equipment operation.
    """
    if not isinstance(water, Mapping):
        raise DeliveryError('missing_field', 'explicit water nutrient concentrations are required')
    if isinstance(target_ph, bool) or not isinstance(target_ph, (int, float)) or not math.isfinite(target_ph) or not 0 <= target_ph <= 14:
        raise DeliveryError('out_of_range', 'target_ph must be finite in [0,14]')
    for config in (equilibrium, nitric, titration, stocks, acids):
        if config is not None and not isinstance(config, Mapping):
            raise DeliveryError('invalid_type', 'stage configurations must be mappings')
    targets = validate_profile(dict(targets), 'targets')
    water = validate_profile(dict(water), 'water')
    recommendation = recommend(salts, targets, water)
    recommendation.update(assess_incidental(recommendation['rows'], maximum_concentrations))
    if recommendation['limitViolations']:
        recommendation['feasible'] = False
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
        absent = tuple(key for key in required if config is None or key not in config or config[key] is None)
        if absent:
            stages[name] = WorkflowStage('needs_input', required_inputs=absent)
        return bool(absent)

    stages['formulation'] = WorkflowStage('calculated' if recommendation['feasible'] else 'blocked',
                                        value=recommendation, error_code=None if recommendation['feasible'] else 'infeasible_recipe')
    if recommendation['feasible'] and recommendation['requiresReview']:
        stages['formulation'].status = 'requires_review'
    recipe = None
    if final_volume is None:
        stages['batch'] = WorkflowStage('needs_input', required_inputs=('final_volume',))
    elif not isinstance(final_volume, VolumeLitres):
        raise DeliveryError('invalid_type', 'final_volume must be VolumeLitres')
    else:
        recipe = final_solution_recipe(recommendation, final_volume)
        stages['batch'] = WorkflowStage('calculated', value=recipe)

    required = ('water_totals', 'water_mass_kg', 'water_analysis_id', 'complete_analysis',
                'carbon_boundary', 'temperature_c', 'phases')
    if not missing('chemistry', equilibrium, required):
        if recipe is None:
            stages['chemistry'] = WorkflowStage('needs_input', required_inputs=('final_volume',))
        else:
            def chemical_states():
                config = equilibrium
                mass = _positive(config['water_mass_kg'], 'water_mass_kg')
                if not isinstance(config['water_analysis_id'], str) or not config['water_analysis_id'].strip():
                    raise DeliveryError('missing_field', 'water_analysis_id is required')
                kwargs = {key: config[key] for key in ('complete_analysis', 'carbon_boundary', 'temperature_c', 'phases')}
                water_state = calculate_equilibrium_ph(config['water_totals'], **kwargs)
                expected = _water_ppm(config['water_totals'], mass, final_volume.value)
                for ion in set(expected) | set(water):
                    if not math.isclose(expected.get(ion, 0), water.get(ion, 0), rel_tol=1e-6, abs_tol=1e-6):
                        raise DeliveryError('inconsistent_water_analysis', f'nutrient ppm and molal water disagree for {ion}')
                library = {p['id']: p for p in load_library()['salts']}
                for supplied in salts:
                    reference = library.get(supplied.get('id'))
                    if reference is None or any(supplied.get(key) != reference.get(key)
                                                for key in ('name', 'formula', 'elements')):
                        raise DeliveryError('product_chemistry_mismatch',
                                            'supplied products must retain catalogue identity and assay')
                doses = {}
                for salt in recipe.salts:
                    product = library.get(salt.salt_id)
                    if product is None or product['name'] != salt.name:
                        raise DeliveryError('product_chemistry_mismatch', 'chemistry requires exact catalogue identities')
                    doses[salt.name] = doses.get(salt.name, 0) + salt.mass.value / mass
                totals = dict(config['water_totals'])
                for basis, amount in catalogue_dose_totals(doses).items():
                    totals[basis] = totals.get(basis, 0) + amount
                mixed = calculate_equilibrium_ph(totals, **kwargs)
                return {'water': water_state, 'mixed': mixed, 'product_doses_g_per_kg_water': doses,
                        'water_analysis_id': config['water_analysis_id'], 'carbon_boundary': config['carbon_boundary']}
            run('chemistry', chemical_states)

    if not missing('nitric', nitric, ('reagent', 'reagent_channel_id', 'maximum_reagent_volume', 'maximum_nutrient_error_percent')):
        if stages['chemistry'].status != 'calculated':
            stages['nitric'] = WorkflowStage('blocked', error_code='chemistry_required', message='complete calculated chemistry is required')
        else:
            run('nitric', lambda: plan_equilibrium_delivery(
                recipe, water_mass_kg=equilibrium['water_mass_kg'], water_totals=equilibrium['water_totals'],
                water_analysis_id=equilibrium['water_analysis_id'], initial_ph=stages['chemistry'].value['mixed'].ph,
                target_ph=target_ph, targets=targets, temperature_c=equilibrium['temperature_c'], phases=equilibrium['phases'],
                maximum_concentrations=maximum_concentrations,
                **{key: nitric[key] for key in ('reagent', 'reagent_channel_id', 'maximum_reagent_volume', 'maximum_nutrient_error_percent')}))
            if stages['nitric'].value is not None and stages['nitric'].value.incidental_assessment['requiresReview']:
                stages['nitric'].status = 'requires_review'

    if not missing('titration', titration, ('water_analysis', 'curve', 'reagent', 'maximum_reagent_volume')):
        if recipe is None:
            stages['titration'] = WorkflowStage('needs_input', required_inputs=('final_volume',))
        elif not recommendation['feasible']:
            stages['titration'] = WorkflowStage('blocked', error_code='infeasible_recipe')
        else:
            def titration_plan():
                if not isinstance(titration['water_analysis'], Mapping):
                    raise DeliveryError('invalid_type', 'titration water_analysis must be a mapping')
                if titration['water_analysis'].get('ions') != water:
                    raise DeliveryError('inconsistent_water_analysis', 'titration water ions must match formulation water')
                plan = plan_ph(titration['water_analysis'], titration['curve'], titration['reagent'], target_ph,
                               final_volume, titration['maximum_reagent_volume'],
                               {row['symbol']: row['final'] for row in recommendation['rows']}, targets)
                tolerance = _positive(titration.get('maximum_nutrient_error_percent', 1),
                                      'maximum_nutrient_error_percent')
                if any(row['deltaPct'] is not None and abs(row['deltaPct']) > tolerance for row in plan.rows):
                    raise DeliveryError('nutrient_tolerance_exceeded', 'titration dose violates a positive nutrient target')
                if assess_incidental(plan.rows, maximum_concentrations)['limitViolations']:
                    raise DeliveryError('nutrient_limit_exceeded', 'titration dose exceeds an explicit nutrient maximum')
                return plan
            plan = run('titration', titration_plan)
            if plan is not None and assess_incidental(plan.rows, maximum_concentrations)['requiresReview']:
                stages['titration'].status = 'requires_review'

    if not missing('acid_selection', acids, ('products', 'maximum_nutrient_error_percent', 'maximum_reagent_volume_litres')):
        if (not isinstance(acids['products'], (list, tuple)) or not acids['products'] or
                any(not isinstance(p, Mapping) or p.get('chemicalFormula') not in ('HNO3', 'H3PO4')
                    for p in acids['products'])):
            stages['acid_selection'] = WorkflowStage('blocked', error_code='unsupported_standard_acid',
                message='Standard fertigation workflow accepts only nitric (HNO3) and phosphoric (H3PO4) products.')
        elif stages['chemistry'].status != 'calculated':
            stages['acid_selection'] = WorkflowStage('blocked', error_code='chemistry_required')
        elif not recommendation['feasible']:
            stages['acid_selection'] = WorkflowStage('blocked', error_code='infeasible_recipe')
        else:
            state = stages['chemistry'].value['mixed']
            selection = run('acid_selection', lambda: plan_acid_options(
                state.totals, state.ph, target_ph, products=acids['products'],
                water_mass_kg=equilibrium['water_mass_kg'], final_volume_litres=final_volume.value,
                achieved={row['symbol']: row['final'] for row in recommendation['rows']}, targets=targets,
                maximum_nutrient_error_percent=acids['maximum_nutrient_error_percent'],
                maximum_reagent_volume_litres=acids['maximum_reagent_volume_litres'],
                preferred_product_id=acids.get('preferred_product_id'), phases=equilibrium['phases'],
                maximum_concentrations=maximum_concentrations))
            if selection is not None and selection.selected_product_id is None:
                stages['acid_selection'] = WorkflowStage('blocked', value=selection, error_code='no_acceptable_acid')

    if not missing('stocks', stocks, ('injection_ratio', 'tanks', 'compatibility_rules', 'solubility_limits', 'temperature')):
        if recipe is None:
            stages['stocks'] = WorkflowStage('needs_input', required_inputs=('final_volume',))
        else:
            run('stocks', lambda: plan_stocks(recipe, stocks['injection_ratio'], stocks['tanks'],
                                            stocks['compatibility_rules'], stocks['solubility_limits'], stocks['temperature']))
    return output
