# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Public candidate reconstruction and acceptance for explicitly joint calculations."""

from collections.abc import Mapping
from .delivery_contracts import DeliveryError
from .joint_solver import solve_joint_problem
from .calculated_ph import calculate_equilibrium_ph
from .engine import _provenance


def zero_reagent_controls(problem):
    """Bounded zero-dose recovery policy; no best-fit or stationarity acceptance."""
    return dict(
        dose_steps={s.product_id: 1e-4 for s in (*problem.fertilizers, problem.reagent)},
        charge_scale=0.001,
        charge_tolerance=2e-12,
        loss_tolerance=1e-16,
        sensitivity_tolerance=0.01,
        trust_radius=10000,
        max_iterations=20,
        max_backtracks=20,
    )


def joint_candidate(
    pool,
    targets,
    water,
    target_ph,
    product,
    initial,
    mix,
    mass,
    volume,
    cap,
    phases,
    maxima,
    water_components,
    config=None,
):
    """Run a joint candidate, or the strictly zero-reagent legacy recovery.

    No assay remainder is assigned to solvent. A zero-dose recovery fixes the
    reagent mass to zero, so its solvent coefficient has no material effect.
    """
    from .ph_adjustment import (
        make_joint_problem,
        PhCandidate,
        REAGENTS,
        PH_TOLERANCE,
        _blend_recipe,
        _judge,
    )

    if water_components is None:
        raise DeliveryError('missing_chemistry', 'joint fitting requires water components')
    if config is not None:
        if not isinstance(config, Mapping):
            raise DeliveryError('invalid_type', 'joint configuration must be a mapping')
        required = {
            'controls',
            'solvent_mass_kg',
            'reagent_solvent_fractions',
            'maximum_reagent_mass_g',
        }
        if not required <= set(config) or set(config) - required - {'starting_points'}:
            raise DeliveryError(
                'missing_field', 'joint configuration requires ' + ', '.join(sorted(required))
            )
        if isinstance(config['solvent_mass_kg'], bool) or config['solvent_mass_kg'] != mass:
            raise DeliveryError(
                'inconsistent_basis', 'joint and workflow final solvent mass must agree'
            )
        if not isinstance(config['controls'], Mapping):
            raise DeliveryError('invalid_type', 'joint controls must be a mapping')
        for key in ('reagent_solvent_fractions', 'maximum_reagent_mass_g'):
            if not isinstance(config[key], Mapping) or product['id'] not in config[key]:
                raise DeliveryError('missing_field', key + ' must name the offered reagent')
        solvent = config['reagent_solvent_fractions'][product['id']]
        maximum_mass = config['maximum_reagent_mass_g'][product['id']]
    else:
        solvent, maximum_mass = 0, 0
    problem = make_joint_problem(
        pool,
        product,
        targets,
        water,
        reagent_solvent_fraction=solvent,
        water_components=water_components,
        final_volume_litres=volume,
        solvent_mass_kg=mass,
        target_ph=target_ph,
        reference_charge_mol_per_kg=0,
        maximum_reagent_mass_g=maximum_mass,
        maximum_reagent_volume_litres=cap,
        maximum_concentrations=maxima or {},
        phases=phases,
    )
    if config is None:
        controls = zero_reagent_controls(problem)
    else:
        selected_controls = config['controls']
        if 'dose_steps' not in selected_controls and product['id'] in selected_controls:
            selected_controls = selected_controls[product['id']]
        if not isinstance(selected_controls, Mapping):
            raise DeliveryError('invalid_type', 'joint controls must be a mapping')
        controls = dict(selected_controls)
    doses = {s['id']: s['gramsPerLitre'] for s in initial['salts']}
    initial_reagent = 0
    if config is not None and 'starting_points' in config:
        points = config['starting_points']
        if not isinstance(points, Mapping):
            raise DeliveryError('invalid_type', 'starting_points must map reagent IDs to starts')
        if product['id'] in points:
            start = points[product['id']]
            if not isinstance(start, Mapping) or set(start) != {
                'fertilizer_doses',
                'reagent_dose',
            }:
                raise DeliveryError(
                    'invalid_value', 'a starting point requires fertilizer_doses and reagent_dose'
                )
            doses, initial_reagent = start['fertilizer_doses'], start['reagent_dose']
    try:
        result = solve_joint_problem(problem, doses, initial_reagent, **controls)
    except TypeError as exc:
        raise DeliveryError(
            'invalid_value', 'joint numerical controls are incomplete or unknown'
        ) from exc
    if result['status'] not in ('numerical_candidate', 'bounded_best_fit', 'stationary_point'):
        raise DeliveryError('joint_search_incomplete', result['reason'])
    doses, reagent = result['fertilizerDoses'], result['reagentDose']
    state = problem.evaluate(doses, reagent)
    if state['violations'] or abs(state['chargeResidual']) > controls['charge_tolerance']:
        raise DeliveryError(
            'joint_verification_failed', 'fresh joint constraints or charge failed'
        )
    target = calculate_equilibrium_ph(
        state['componentsMolPerKg'],
        complete_analysis=True,
        carbon_boundary='closed',
        phases=phases,
    )
    if abs(target.ph - target_ph) > PH_TOLERANCE:
        raise DeliveryError('joint_verification_failed', 'independent final pH misses the target')
    contribution = {k: 1000 * reagent * v for k, v in problem.reagent.nutrients.items()}
    supply = dict(water)
    for key, value in contribution.items():
        supply[key] = supply.get(key, 0) + value
    endpoint = dict(
        initial,
        salts=[
            dict(
                id=p['id'],
                name=p['name'],
                gramsPerLitre=doses.get(p['id'], 0),
                provenance=_provenance(p),
            )
            for p in pool
            if doses.get(p['id'], 0) > 0
        ],
    )
    recommendation = _blend_recipe(pool, targets, supply, [endpoint, endpoint], 0, maxima)
    recommendation['substitutionSearch'] = dict(
        status='candidate_found' if recommendation['feasible'] else 'search_incomplete',
        method='joint fertilizer and reagent search; no global optimality claim',
        attemptedProductIds=[[p['id'] for p in pool]],
    )
    status, code, message, saturation = _judge(
        recommendation,
        target,
        maxima,
        accepted='not_needed' if reagent == 0 else 'accepted',
    )
    if not recommendation['feasible'] and status in ('accepted', 'not_needed'):
        status, message = 'requires_review', 'joint candidate misses nutrient targets'
    formula = product['chemicalFormula']
    return PhCandidate(
        product['id'],
        formula,
        REAGENTS[formula][0],
        status,
        reagent * volume * product['massFraction'] / (mass * REAGENTS[formula][2]),
        state['reagentMassGrams'],
        state['reagentVolumeLitres'],
        contribution,
        recommendation,
        mix(recommendation),
        target,
        result['diagnostics']['iterations'],
        recommendation['loss'],
        code,
        message,
        dict(product),
        saturation,
        joint_result=dict(
            status=result['status'],
            accepted=False,
            globalOptimalityProven=False,
            reason=result['reason'],
            fertilizerDoses=dict(doses),
            reagentDose=reagent,
            controls=controls,
            chargeResidual=state['chargeResidual'],
        ),
    )
