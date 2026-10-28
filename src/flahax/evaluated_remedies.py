# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Bounded, explicit scenario re-evaluation; no invented treatment or equipment performance."""

from copy import deepcopy
from collections.abc import Mapping

from .canonical_result import _digest
from .composition import InputError
from .delivery_contracts import DeliveryError


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


def unresolved_requirements(workflow):
    """Return next actions for every unmet nutrient, hard limit and unfinished workflow stage."""
    stage = workflow.stages.get('ph_adjustment')
    plan = stage.value if stage is not None else None
    chosen = getattr(plan, 'selected', None)
    recipe = (
        chosen.recommendation
        if chosen is not None
        else (getattr(plan, 'unadjusted_recommendation', None) or workflow.recommendation)
    )
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


def evaluate_remedies(workflow, request, options=(), max_evaluations=20):
    """Re-run declared alternatives without adopting them or expanding the search implicitly.

    Options have unique id, kind (catalogue/treatment/equipment), and changes.
    Catalogue bundles require available=True; treatment requires evidence source/revision.
    The budget counts attempted workflow evaluations, not unqualified suggestions.
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
    baseline = unresolved_requirements(workflow)
    baseline_ids = {r['id'] for r in baseline}
    results, evaluations, skipped = [], 0, False
    for option in options:
        changes, needed = _changes(option, request)
        result = dict(
            id=option['id'],
            kind=option['kind'],
            option_sha256=_digest(option),
            resolved_requirements=[],
            introduced_requirements=[],
            remaining_requirements=deepcopy(baseline),
        )
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
            evaluations += 1
            try:
                candidate = plan_fertilizer_workflow(**candidate_request)
            except InputError as exc:
                result.update(
                    status='evaluation_failed',
                    next_action='Correct the scenario inputs or evaluate another alternative.',
                    error_code=getattr(exc, 'code', 'invalid_input'),
                    message=str(exc),
                )
            else:
                remaining = unresolved_requirements(candidate)
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
        results.append(result)
    return dict(
        status='search_incomplete'
        if skipped or any(r['status'] == 'potential_remedy' for r in results)
        else 'declared_options_evaluated'
        if evaluations
        else 'needs_input',
        scope='Supplied alternatives only; no global proof or automatic adoption.',
        evaluations=evaluations,
        max_evaluations=max_evaluations,
        requirements=baseline,
        options=results,
    )
