# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Bounded, explicit scenario re-evaluation; no invented treatment or
equipment performance.
"""

from copy import deepcopy
from collections.abc import Mapping
from math import fsum, isclose, isfinite

from .canonical_result import _digest
from .composition import InputError, validate_profile
from .delivery_contracts import DeliveryError
from .nutrient_acceptance import assess_incidental, assessed_limits
from .product_conversion import material_inventory
from .requirement_fit import met


ACTIONS = {
    'no_source': 'Supply available nutrient-source records and re-evaluate the bundle.',
    'water_exceeds_target': (
        'Supply treated-water analysis; ' 'fertilizer cannot subtract water nutrients.'
    ),
    'target_above_maximum': (
        'Resolve the conflicting target and ' 'maximum explicitly; never relax them silently.'
    ),
    'prohibited_by_zero_requirement': (
        'Supply a product without this ' 'component; preserve the zero requirement.'
    ),
}

RANKING_PREFERENCES = ('relative_residual', 'incidental_mg_l', 'product_count')


def _recommendation(workflow):
    stage = workflow.stages.get('ph_adjustment')
    plan = stage.value if stage is not None else None
    chosen = getattr(plan, 'selected', None)
    return (
        chosen.recommendation
        if chosen is not None
        else (getattr(plan, 'unadjusted_recommendation', None) or workflow.recommendation)
    )


def unresolved_requirements(workflow):
    """Return next actions for every unmet nutrient, hard limit and
    unfinished workflow stage.
    """
    recipe = _recommendation(workflow)
    requirements = []
    for row in recipe.get('unmetTargets', []):
        requirements.append(
            dict(
                id='nutrient:' + row['symbol'],
                status=row.get('status', 'search_incomplete'),
                evidence=deepcopy(row),
                next_action=ACTIONS.get(
                    row.get('reason'),
                    (
                        'Evaluate permitted bundles; preserve '
                        'targets and limits. Search failure is not proof.'
                    ),
                ),
            )
        )
    for row in recipe.get('limitViolations', []):
        requirements.append(
            dict(
                id='limit:' + row['symbol'],
                status='blocked',
                evidence=deepcopy(row),
                next_action=(
                    'Evaluate lower-contribution products '
                    'or treated water; preserve the maximum.'
                ),
            )
        )
    if equipment_unfit(workflow):
        stage = workflow.stages['stocks']
        requirements.append(
            dict(
                id='equipment:fit',
                status='blocked',
                evidence=dict(error_code=stage.error_code, message=stage.message),
                next_action=(
                    'Search other product combinations for the declared equipment, or declare '
                    'different equipment; no separation rule is waived.'
                ),
            )
        )
    for name, stage in workflow.stages.items():
        if stage.status != 'calculated':
            action = (
                'Supply ' + ', '.join(stage.required_inputs) + ' and re-evaluate.'
                if stage.required_inputs
                else 'Provide qualified mixture evidence and sufficient equipment; re-evaluate.'
                if name == 'stocks'
                else 'Resolve the recorded stage diagnosis with qualified inputs and re-evaluate.'
            )
            requirements.append(
                dict(
                    id='stage:' + name,
                    status=stage.status,
                    evidence=dict(error_code=stage.error_code, message=stage.message),
                    next_action=action,
                )
            )
    return requirements


def equipment_unfit(workflow):
    """True when the declared equipment cannot hold the recipe: the
    stocks stage failed with an error, not merely lacking mixture
    evidence.
    """
    stage = workflow.stages.get('stocks')
    return stage is not None and stage.error_code is not None


def declared_equipment(request):
    """The equipment the scenario declared, as saved plain data (Q27);
    None when no stock equipment was declared.
    """
    stocks = request.get('stocks')
    if not isinstance(stocks, Mapping):
        return None
    tanks = [
        dict(
            tank_id=getattr(t, 'tank_id', None), capacity_litres=getattr(t.capacity, 'value', None)
        )
        for t in stocks.get('tanks') or ()
        if hasattr(t, 'capacity')
    ]
    return dict(
        tanks=tanks,
        injection_ratio=getattr(stocks.get('injection_ratio'), 'value', None),
        temperature_c=getattr(stocks.get('temperature'), 'value', None),
        compatibility_rule_count=len(stocks.get('compatibility_rules') or ()),
        solubility_limit_count=len(stocks.get('solubility_limits') or ()),
        mixture_model_supplied=stocks.get('mixture_model') is not None,
    )


def _changes(option, request):
    kind = option['kind']
    changes = option.get('changes')
    if not isinstance(changes, Mapping):
        return None, 'Supply explicit scenario changes.'
    allowed = {
        'catalogue': {'products'},
        'treatment': {'water', 'equilibrium'},
        'equipment': {'stocks'},
    }[kind]
    if set(changes) - allowed:
        raise DeliveryError(
            'invalid_remedy', 'remedies cannot change targets, limits or other scenario fields'
        )
    if kind == 'catalogue':
        if option.get('available') is not True:
            return None, 'Confirm availability of every product in this bundle.'
        products = changes.get('products')
        if not isinstance(products, list) or not products:
            return None, 'Supply explicit product records for the bundle.'
        pool = {p['id']: deepcopy(p) for p in request['salts']}
        seen = set()
        for product in products:
            if (
                not isinstance(product, dict)
                or not isinstance(product.get('id'), str)
                or not product['id'].strip()
                or not isinstance(product.get('name'), str)
                or not isinstance(product.get('elements'), Mapping)
                or product['id'] in seen
            ):
                raise DeliveryError('invalid_remedy', 'product IDs must be present and unique')
            seen.add(product['id'])
            if product['id'] in pool and product != pool[product['id']]:
                raise DeliveryError(
                    'invalid_remedy', 'changed assays require distinct product record IDs'
                )
            pool[product['id']] = deepcopy(product)
        return {'salts': list(pool.values())}, None
    if kind == 'treatment':
        evidence = option.get('evidence')
        if not isinstance(evidence, Mapping) or not all(
            isinstance(evidence.get(k), str) and evidence[k].strip()
            for k in ('source', 'revision')
        ):
            return (
                None,
                'Supply analysis source and revision; no removal efficiency is inferred.',
            )
        if not isinstance(changes.get('water'), Mapping) or not isinstance(
            changes.get('equilibrium'), Mapping
        ):
            return None, 'Supply treated-water nutrient and complete equilibrium analysis inputs.'
        return deepcopy(dict(changes)), None
    if not isinstance(changes.get('stocks'), Mapping):
        return None, 'Supply stock ratios, tanks, limits, temperature and model evidence.'
    return deepcopy(dict(changes)), None


def available_product_search(
    products, *, preferences=('relative_residual',), on_equipment_miss=False
):
    """Try a confirmed expanded pool, then individual additions within
    the scenario budget.

    The search runs on a nutrient miss. With ``on_equipment_miss`` it
    also runs when the declared equipment cannot hold the recipe (the
    stocks stage failed with an error); every candidate keeps that
    equipment and every separation rule, and only the products change.

    Preferences apply in the supplied order after tolerance attainment.
    Supported metrics are relative_residual, incidental_mg_l and
    product_count.
    """
    return dict(
        id='catalogue:available-product-search',
        kind='catalogue',
        available=True,
        on_nutrient_miss=True,
        on_equipment_miss=on_equipment_miss,
        source_search=True,
        preferences=preferences,
        changes={'products': products},
    )


def _preferences(options):
    requested = [option['preferences'] for option in options if 'preferences' in option]
    for value in requested:
        if (
            not isinstance(value, (list, tuple))
            or any(not isinstance(p, str) or p not in RANKING_PREFERENCES for p in value)
            or len(set(value)) != len(value)
        ):
            raise DeliveryError(
                'invalid_remedy', 'rank preferences must be unique supported metrics'
            )
    distinct = {tuple(value) for value in requested}
    if len(distinct) > 1:
        raise DeliveryError('invalid_remedy', 'remedies must agree on the ranking preferences')
    return next(iter(distinct), ('relative_residual',))


def _candidate_score(candidate, request, preferences):
    recipe = _recommendation(candidate)
    rows = recipe['rows']
    assessment = assess_incidental(
        rows, assessed_limits(request['maximum_concentrations'], recipe)
    )
    if assessment['limitViolations'] or recipe.get('requirementConflicts'):
        return None
    if request['ph_adjustment'] is not None and candidate.stages['ph_adjustment'].status not in (
        'calculated',
        'requires_review',
    ):
        return None
    if (
        request.get('volumetric_stocks') is not None
        and candidate.stages['volumetric_stocks'].status == 'blocked'
    ):
        return None
    targets = [row for row in rows if row['target'] is not None]
    missed = sum(not met(r['target'], r['final']) for r in targets)
    requested_stages = (
        ('equilibrium', 'chemistry'),
        ('nitric', 'nitric'),
        ('titration', 'titration'),
        ('stocks', 'stocks'),
        ('acids', 'acid_selection'),
        ('ph_adjustment', 'ph_adjustment'),
        ('volumetric_stocks', 'volumetric_stocks'),
    )
    incomplete = sum(
        candidate.stages[stage].status != 'calculated'
        for key, stage in requested_stages
        if request.get(key) is not None
    )
    review = assessment['requiresReview']
    metrics = {
        'relative_residual': fsum(
            ((r['final'] - r['target']) / r['target']) ** 2 for r in targets if r['target']
        ),
        'incidental_mg_l': fsum(r['ppm'] for r in assessment['incidentalContributions']),
        'product_count': len(recipe['salts']),
    }
    score = (missed, incomplete, review, *(metrics[p] for p in preferences))
    return score, recipe['feasible'] and not (missed or incomplete or review)


def _source_gain(recipe, maxima, assay):
    # Estimate improvement from the best permitted incremental dose. The
    # full workflow can also trade existing doses against the additional
    # product.
    rows = recipe['rows']
    final = {r['symbol']: r['final'] for r in rows}
    limits = assessed_limits(maxima, recipe)
    limits.update({r['symbol']: 0.0 for r in rows if r['target'] == 0})
    wanted = [r for r in rows if r['target']]
    residuals = [(r['target'] - r['final']) / r['target'] for r in wanted]
    slopes = [assay.get(r['symbol'], 0.0) * 10 / r['target'] for r in wanted]
    numerator = fsum(a * b for a, b in zip(slopes, residuals))
    denominator = fsum(a * a for a in slopes)
    dose = max(0.0, numerator / denominator) if denominator else 0.0
    caps = [
        max(0.0, limit - final.get(symbol, 0.0)) / (assay[symbol] * 10)
        for symbol, limit in limits.items()
        if assay.get(symbol, 0.0) > 0
    ]
    permitted = min([dose, *caps])
    return permitted * (2 * numerator - permitted * denominator), 0.0 in caps


def _source_retries(option, request, workflow, expanded, seen):
    existing = {p['id'] for p in request['salts']}
    products = [p for p in option['changes']['products'] if p['id'] not in existing]
    if len(products) < 2:
        return []
    original = _recommendation(workflow)
    current = _recommendation(expanded) if expanded is not None else original
    maxima = request['maximum_concentrations']

    def source_score(product):
        try:
            validate_profile(dict(product['elements']), 'source assay')
            assay = material_inventory(product)['nutrient_percent']
        except InputError:
            return (float('inf'), True, 0.0, product['id'])
        gain, binding = _source_gain(current, maxima, assay)
        original_gain, _ = _source_gain(original, maxima, assay)
        return (-gain, binding, -original_gain, product['id'])

    retries = []
    for product in sorted(products, key=source_score):
        id_ = _retry_id(option['id'] + ':source:' + product['id'], seen)
        retries.append(
            dict(
                id=id_,
                kind='catalogue',
                available=True,
                changes={'products': [product]},
                source_product_id=product['id'],
            )
        )
    return retries


def _retry_id(id_, seen):
    while id_ in seen:
        id_ += ':retry'
    seen.add(id_)
    return id_


def _doses(recipe):
    return {salt['id']: salt['gramsPerLitre'] for salt in recipe['salts']}


def _joint_start_retry(option, request, workflow, expanded, seen):
    adjustment = request['ph_adjustment']
    if adjustment is None or not isinstance(adjustment.get('joint'), Mapping):
        return None
    joint = adjustment['joint']
    original_stage = workflow.stages['ph_adjustment']
    selected = getattr(original_stage.value, 'selected', None)
    if selected is None or original_stage.status not in ('calculated', 'requires_review'):
        return None
    result = selected.joint_result or {}
    if result.get('status') not in ('numerical_candidate', 'bounded_best_fit', 'stationary_point'):
        return None
    if _candidate_score(workflow, request, ()) is None:
        return None
    doses = result.get('fertilizerDoses')
    reagent = result.get('reagentDose')
    if not isinstance(doses, Mapping) or not all(
        type(dose) in (int, float) and isfinite(dose) and dose >= 0
        for dose in (*doses.values(), reagent)
    ):
        return None
    reagent_id = selected.product_id
    expanded_plan = expanded.stages['ph_adjustment'].value
    if expanded_plan is None or (
        adjustment.get('correct_mixed_ph')
        and (
            expanded_plan.direction != selected.direction
            or reagent_id in joint.get('sequential_fallbacks', {})
        )
    ):
        return None
    starts = dict(joint.get('starting_points', {}))
    fitted = getattr(expanded_plan, 'unadjusted_recommendation', None) or expanded.recommendation
    default = dict(fertilizer_doses=_doses(fitted), reagent_dose=0)
    current = starts.get(reagent_id, default)
    proposed = dict(
        fertilizer_doses={key: dose for key, dose in doses.items() if dose}, reagent_dose=reagent
    )
    current_doses = current['fertilizer_doses']
    if isclose(reagent, current['reagent_dose'], rel_tol=1e-12, abs_tol=1e-15) and all(
        isclose(doses.get(key, 0.0), current_doses.get(key, 0.0), rel_tol=1e-12, abs_tol=1e-15)
        for key in doses.keys() | current_doses.keys()
    ):
        return None
    starts[reagent_id] = proposed
    retry = dict(
        option,
        id=_retry_id(option['id'] + ':joint-start:' + reagent_id, seen),
        source_search=False,
        joint_start_reagent_id=reagent_id,
        starting_point=proposed,
    )
    return retry, dict(adjustment, joint=dict(joint, starting_points=starts))


def evaluate_remedies(workflow, request, options=(), max_evaluations=20):
    """Re-run declared alternatives and rank checked results within the
    scenario budget.

    Options have unique id, kind (catalogue/treatment/equipment), and
    changes. Catalogue bundles require available=True; treatment
    requires evidence source/revision. Options from
    available_product_search can also try individual source additions.
    Only attempted workflow evaluations count against the budget.
    """
    if (
        not isinstance(options, (list, tuple))
        or type(max_evaluations) is not int
        or max_evaluations < 0
    ):
        raise DeliveryError(
            'invalid_remedy', 'options must be a sequence and budget a nonnegative integer'
        )
    seen = set()
    for option in options:
        if (
            not isinstance(option, Mapping)
            or not isinstance(option.get('id'), str)
            or not option['id'].strip()
        ):
            raise DeliveryError('invalid_remedy', 'each remedy needs a nonempty ID')
        if option['id'] in seen or option.get('kind') not in (
            'catalogue',
            'treatment',
            'equipment',
        ):
            raise DeliveryError('invalid_remedy', 'remedy IDs must be unique and kinds supported')
        seen.add(option['id'])
    preferences = _preferences(options)
    baseline = unresolved_requirements(workflow)
    nutrient_miss = any(r["id"].startswith("nutrient:") for r in baseline)
    equipment_miss = equipment_unfit(workflow)
    baseline_ids = {r['id'] for r in baseline}
    results, evaluations, skipped = [], 0, False
    scored = {}
    queue = [(option, None) for option in options]
    for option, adjustment in queue:
        gated = [
            flag
            for flag, miss in (
                ('on_nutrient_miss', nutrient_miss),
                ('on_equipment_miss', equipment_miss),
            )
            if option.get(flag) is True
        ]
        if gated and not any(
            (nutrient_miss if flag == 'on_nutrient_miss' else equipment_miss) for flag in gated
        ):
            continue
        changes, needed = _changes(option, request)
        result = dict(
            id=option['id'],
            kind=option['kind'],
            option_sha256=_digest(option),
            resolved_requirements=[],
            introduced_requirements=[],
            remaining_requirements=deepcopy(baseline),
        )
        if 'source_product_id' in option:
            result['source_product_id'] = option['source_product_id']
        if adjustment is not None:
            result['joint_start_reagent_id'] = option['joint_start_reagent_id']
        if needed:
            result.update(status='potential_remedy', next_action=needed)
        elif evaluations >= max_evaluations:
            skipped = True
            result.update(
                status='not_evaluated',
                next_action='Increase the evaluation budget; this scenario has no result.',
            )
        else:
            from .fertilizer_workflow import plan_fertilizer_workflow

            candidate_request = deepcopy(request)
            candidate_request.update(changes)
            if adjustment is not None:
                candidate_request['ph_adjustment'] = adjustment
            evaluations += 1
            try:
                candidate = plan_fertilizer_workflow(**candidate_request)
            except InputError as exc:
                candidate = None
                result.update(
                    status='evaluation_failed',
                    next_action='Correct the scenario inputs or evaluate another alternative.',
                    error_code=getattr(exc, 'code', 'invalid_input'),
                    message=str(exc),
                )
                retry_sources = True
            else:
                remaining = unresolved_requirements(candidate)
                retry_sources = any(r['id'].startswith('nutrient:') for r in remaining)
                resolved = sorted(baseline_ids - {r['id'] for r in remaining})
                result.update(
                    status='evaluated_candidate' if resolved else 'evaluated_no_resolution',
                    resolved_requirements=resolved,
                    remaining_requirements=remaining,
                    introduced_requirements=sorted({r["id"] for r in remaining} - baseline_ids),
                    calculation_id=candidate.canonical_result.result_id,
                    snapshot=candidate.canonical_result.payload,
                    next_action=(
                        'Review remaining requirements before '
                        'adoption; no delivery or physical approval.'
                    ),
                )
                score = _candidate_score(candidate, candidate_request, preferences)
                if score is not None:
                    scored[option['id']] = score
            if (
                retry_sources
                and option.get('source_search') is True
                and option['kind'] == 'catalogue'
            ):
                if candidate is not None:
                    repeat = _joint_start_retry(option, request, workflow, candidate, seen)
                    if repeat is not None:
                        queue.append(repeat)
                queue.extend(
                    (retry, None)
                    for retry in _source_retries(option, request, workflow, candidate, seen)
                )
        results.append(result)
    report = dict(
        status='search_incomplete'
        if skipped
        or any(r['status'] in ('potential_remedy', 'evaluation_failed') for r in results)
        else 'declared_options_evaluated'
        if evaluations
        else 'needs_input',
        scope='Supplied alternatives only; no global proof or automatic adoption.',
        mode='find_suitable_doses' if evaluations else 'analyze_supplied_doses',
        declared_equipment=declared_equipment(request),
        evaluations=evaluations,
        max_evaluations=max_evaluations,
        requirements=baseline,
        options=results,
    )
    if results:
        ranking = sorted(scored, key=lambda id_: (scored[id_][0], id_))
        verified = [id_ for id_ in ranking if scored[id_][1]]
        report.update(
            ranking_preferences=list(preferences),
            ranked_candidate_ids=ranking,
            verified_candidate_ids=verified,
            best_candidate_id=ranking[0] if ranking else None,
            best_verified_candidate_id=verified[0] if verified else None,
        )
    return report
