# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The batch summary: what is weighed, the pH, chemistry, EC, tank and status
record that every report, sheet and command line reads."""

from copy import deepcopy
from dataclasses import asdict
import math

from . import __version__
from .canonical_result import result_statuses, seal_summary
from .delivery_contracts import DeliveryError
from .deviation_ranges import assessment as range_assessment
from .fertilizer_workflow import PH_NOT_PLANNED, missed_message, unreviewed_reason
from .irrigation_ec import QUALIFIER, calculate_ec_from_totals
from .requirement_fit import RELATIVE_TOLERANCE, ZERO_TARGET_TOLERANCE_MG_PER_L, met
from .result_wording import extra_tank_note, requested_ec_note, status_explanations
from .saturation_policy import assess_saturation, risk_warnings
from .stock_solubility import (
    SINGLE_SALT,
    check_stock_solubility,
    exceeds_message,
    load_solubility_table,
    unverified_temperature_note,
)
from .tank_grouping import group_tanks


def _interval_record(interval, plan=None):
    """The summary's account of an acceptable pH interval, or None for a point target."""
    if not interval:
        return None
    return dict(
        low=interval[0],
        high=interval[1],
        aimed_at=None if plan is None else plan.target_ph,
        reagent_needed=None if plan is None else plan.direction != 'none',
        rule='Nearest bound, never a midpoint; a mix already inside needs no reagent.',
    )


def _stage(stage):
    return dict(
        status=stage.status,
        error_code=stage.error_code,
        message=stage.message,
        required_inputs=list(stage.required_inputs),
    )


def _water_and_limits(workflow, recipe):
    """Laboratory and modelled water side by side, and every declared
    limit decided on the laboratory basis.
    """
    basis = getattr(workflow, 'water_basis', None)
    water = dict(
        decision_basis='laboratory analysis',
        analysis_mg_per_litre=dict(basis['analyticalPpm'] if basis else workflow.water),
        modelled_mg_per_litre=dict(basis['modelledPpm']) if basis else None,
        adjustment_mg_per_litre=dict(basis['adjustmentPpm']) if basis else {},
        balance_ion=basis['balanceIon'] if basis else None,
        reconciliation=basis['reconciliation'] if basis else None,
        balance_ion_uncertainty_percent=basis['balanceIonUncertaintyPercent'] if basis else None,
        below_detection=sorted(basis['belowDetectionMolal']) if basis else [],
        imbalance_percent=basis['imbalancePercent'] if basis else None,
        measured_ph=basis['measuredPh'] if basis else None,
        dilution_fraction=basis['dilutionFraction'] if basis else None,
    )
    finals = {row['symbol']: row['final'] for row in recipe['rows']}
    limits = []
    for ion, limit in sorted((getattr(workflow, 'maximum_concentrations', None) or {}).items()):
        lab = finals.get(ion, 0.0)
        model = (
            lab - basis['analyticalPpm'].get(ion, 0.0) + basis['modelledPpm'].get(ion, 0.0)
            if basis
            else None
        )
        exceeds = lab > limit + 1e-12
        flips = model is not None and (model > limit + 1e-12) != exceeds
        limits.append(
            dict(
                symbol=ion,
                maximumPpm=limit,
                analyticalPpm=lab,
                modelledPpm=model,
                decision='exceeds_limit' if exceeds else 'within_limit',
                basis='laboratory analysis',
                balancingChangesDecision=flips,
                note=(
                    f'{ion}: {lab:.4g} mg/L on the laboratory analysis is '
                    f'{"above" if exceeds else "within"} the '
                    f'{limit:g} mg/L maximum; the charge-balanced model gives {model:.4g} mg/L. '
                    f'The decision uses the '
                    'laboratory value; check the analysis.'
                )
                if flips
                else None,
            )
        )
    return water, limits


def declared_tanks(available_tanks, tank_capacities_litres):
    """``(available tanks, capacities in litres, declared)``: the tanks a
    grower states, validated; two tanks are assumed, and ``declared`` is
    false, when none are stated (D3).
    """
    capacities = _tank_capacities(tank_capacities_litres)
    declared = available_tanks is not None or bool(capacities)
    if available_tanks is None:
        available_tanks = len(capacities) or 2
    if type(available_tanks) is not int or available_tanks < 1:
        raise DeliveryError('invalid_value', 'available_tanks must be a positive integer')
    if capacities and len(capacities) != available_tanks:
        raise DeliveryError(
            'invalid_value',
            f'{len(capacities)} tank capacities were given for {available_tanks} available tanks',
        )
    return available_tanks, capacities, declared


class EquipmentCheck:
    """Judge a workflow's recipe against the declared equipment, as the
    batch report does, so the equipment search can see a miss (D4).

    Called with a workflow, it returns None when the recipe fits or
    ``{error_code, message}`` for the first problem: too many tanks, a
    tank too small for its stock, or a stock above its recorded
    solubility. ``declaration`` is the saved record of the equipment.
    """

    def __init__(
        self,
        products,
        *,
        rules,
        injection_ratio,
        temperature_c,
        available_tanks,
        tank_capacities_litres,
        batch_litres,
    ):
        tanks, capacities, declared = declared_tanks(available_tanks, tank_capacities_litres)
        self._products = products
        self._rules = rules
        self._ratio = injection_ratio
        self._temperature = temperature_c
        self._tanks = tanks
        self._capacities = capacities
        self._litres = batch_litres
        self.declaration = dict(
            available_tanks=tanks,
            available_tanks_declared=declared,
            tank_capacities_litres=capacities,
            injection_ratio=injection_ratio,
            temperature_c=temperature_c,
            batch_litres=batch_litres,
        )

    def __call__(self, workflow):
        """None when the workflow's recipe fits the equipment, else the first problem."""
        from .evaluated_remedies import _recommendation

        try:
            salts = _recommendation(workflow)['salts']
            grouping = group_tanks(salts, self._products, rules=self._rules)
        except DeliveryError as exc:
            return dict(error_code=exc.code, message=str(exc))
        if len(grouping.tanks) > self._tanks:
            return dict(
                error_code='too_many_tanks', message=extra_tank_note(grouping, self._tanks)
            )
        stock_litres = self._litres / self._ratio
        for tank, capacity in zip(grouping.tanks, self._capacities):
            if stock_litres > capacity:
                return dict(
                    error_code='tank_too_small',
                    message=f'Tank {tank.name} cannot hold {stock_litres:g} L of stock.',
                )
        rows = check_stock_solubility(
            grouping.tanks,
            self._ratio,
            self._temperature,
            table=load_solubility_table(),
            products=self._products,
        )
        for row in rows:
            if row.status == 'exceeds':
                return dict(
                    error_code='solubility_exceeded',
                    message=exceeds_message(row, self._temperature),
                )
        return None


def _tank_capacities(values):
    """The declared tank capacities in litres, validated, as floats."""
    if values is None:
        return []
    if isinstance(values, (str, bytes)) or not hasattr(values, '__iter__'):
        raise DeliveryError('invalid_type', 'tank capacities must be a list of litres')
    capacities = []
    for value in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise DeliveryError(
                'invalid_value', f'a tank capacity must be a positive finite number, got {value!r}'
            )
        capacities.append(float(value))
    return capacities


def _joint_record(result):
    """The joint fit of one reagent, without its dose maps: status,
    caveats and charge residual.
    """
    if result is None:
        return None
    return {
        key: result[key]
        for key in (
            'status',
            'accepted',
            'globalOptimalityProven',
            'reason',
            'chargeResidual',
            'chargeTolerance',
            'finalPh',
            'stationarityResidual',
            'iterations',
            'evaluations',
        )
        if key in result
    }


def _ph_record(workflow, ph_stage, plan, chosen):
    """The pH section of the summary: the plan, its candidates and the skipped products."""
    ph = None
    if plan is not None:

        def candidate(c):
            name = (c.product_record or {}).get('name') or c.product_id
            return dict(
                product_id=c.product_id,
                product=name,
                formula=c.formula,
                direction=c.direction,
                status=c.status,
                volume_ml_per_batch=None
                if c.reagent_volume_litres is None
                or (c.product_record or {}).get('physicalForm') == 'solid'
                else 1000 * c.reagent_volume_litres,
                mass_g_per_batch=c.reagent_mass_g,
                nutrient_contribution=c.nutrient_contribution,
                message=c.message,
                joint=_joint_record(c.joint_result),
            )

        # mixed_ph: the weighed recipe without its reagent (the refit
        # when a reagent is chosen, #107).
        weighed = (
            chosen.mixed.ph
            if chosen is not None and chosen.mixed is not None
            else plan.unadjusted_ph
        )
        ph = dict(
            status=ph_stage.status,
            message=ph_stage.message,
            direction=plan.direction,
            unadjusted_ph=plan.unadjusted_ph,
            mixed_ph=weighed,
            target_ph=plan.target_ph,
            interval=_interval_record(plan.interval, plan),
            selected=candidate(chosen) if chosen is not None else None,
            candidates=[candidate(c) for c in plan.candidates if c.status != 'not_applicable'],
            skipped=[candidate(c) for c in plan.candidates if c.status == 'not_applicable'],
        )
    elif ph_stage is not None and ph_stage.error_code in PH_NOT_PLANNED:
        # A product that cannot be modelled: the nutrients stand, no
        # reagent is planned; the sheet names it.
        ph = dict(
            status=ph_stage.status,
            direction=None,
            unadjusted_ph=None,
            mixed_ph=None,
            target_ph=workflow.target_ph,
            interval=_interval_record(workflow.ph_interval),
            selected=None,
            candidates=[],
            message=ph_stage.message,
        )
    return ph


def _chemistry_and_ec(workflow, plan, chosen, rejected):
    """The weighed recipe state, its chemistry and the EC estimate; never a rejected candidate."""
    state = None
    chemistry = ec = None
    chem = workflow.stages.get('chemistry')
    unadjusted_state = getattr(plan, 'unadjusted_state', None)
    state_available = (
        plan is None
        or (chosen is not None and chosen.mixed is not None and chosen.target is not None)
        or (chosen is None and unadjusted_state is not None)
    )
    if not state_available:
        ec = dict(
            status='not_supported',
            ec25_ms_cm=None,
            reason='weighed_recipe_state_unavailable',
            qualifier=(
                'Weighed recipe chemistry is unavailable; '
                'rejected candidates are not substitutes.'
            ),
        )
    if chem is not None and chem.status in ('calculated', 'requires_review') and state_available:
        mixed = (
            chosen.mixed
            if chosen is not None and chosen.mixed is not None
            else unadjusted_state
            if unadjusted_state is not None
            else chem.value['mixed']
        )
        state = chosen.target if chosen is not None else mixed
        assessment = assess_saturation(state)
        chemistry = dict(
            state_basis=(
                'selected_recipe'
                if chosen is not None
                else 'unadjusted_recipe'
                if unadjusted_state is not None
                else 'initial_workflow'
            ),
            rejected_candidate_diagnostics=(
                dict(
                    product_id=rejected.product_id,
                    mixed_ph=rejected.mixed.ph if rejected.mixed is not None else None,
                    target_ph=rejected.target.ph,
                    phase_assessment=assess_saturation(rejected.target),
                    state_basis='rejected_candidate_not_weighed',
                )
                if rejected is not None
                else None
            ),
            water_ph=chem.value['water'].ph,
            mixed_ph=mixed.ph,
            final_ph=state.ph,
            phase_assessment=assessment,
            ionic_strength=state.ionic_strength,
            # Dissolved species and predicted precipitate, apart from the nutrient totals (Q12).
            species_mol_per_kg=dict(
                sorted(
                    ((name, amount) for name, amount in state.species.items() if amount > 1e-12),
                    key=lambda item: -item[1],
                )
            ),
            precipitated_mol_per_kg={
                name: amount for name, amount in state.precipitated.items() if amount > 0
            },
            risk=[dict(phase=p, si=si) for p, si in assessment['risk']],
            information=[
                dict(phase=p, si=si, basis=basis) for p, si, basis in assessment['information']
            ],
            advisories=assessment['advisories'],
            solids=assessment['solids'],
            indices=sorted(
                (
                    [p, si]
                    for p, si in state.saturation_indices.items()
                    if isinstance(si, float) and si > -1
                ),
                key=lambda item: -item[1],
            ),
        )
        try:
            result = calculate_ec_from_totals(
                state.totals,
                solution_id='batch',
                ph_mode='supplied',
                ph=state.ph,
                phase_policy='dissolved',
            )
            ec = asdict(result)
        except DeliveryError as exc:
            ec = dict(status='not_supported', ec25_ms_cm=None, ph=state.ph, message=str(exc))
    return state, chemistry, ec


def _tank_plan(
    recipe,
    products,
    rules,
    injection_ratio,
    temperature_c,
    available_tanks,
    tank_capacities_litres,
    litres,
):
    """The stock tank assignment, its single-product solubility and the declared equipment."""
    available_tanks, capacities, declared = declared_tanks(available_tanks, tank_capacities_litres)
    grouping = group_tanks(recipe['salts'], products, rules=rules)
    solubility = check_stock_solubility(
        grouping.tanks,
        injection_ratio,
        temperature_c,
        table=load_solubility_table(),
        products=products,
    )
    tanks = dict(
        source=grouping.source,
        required_tanks=len(grouping.tanks),
        available_tanks=available_tanks,
        available_tanks_declared=declared,
        equipment=dict(capacities_litres=capacities, fit=[]),
        mixture_approved=False,
        injection_ratio=injection_ratio,
        temperature_c=temperature_c,
        solubility_checked=bool(solubility)
        and all(r.status in {'ok', 'exceeds'} for r in solubility),
        reagent_channel=list(grouping.reagent_channel),
        separations=[list(s) for s in grouping.separations],
        waived=[list(w) for w in grouping.waived],
        tanks=[
            dict(
                name=t.name,
                acid_allowed=t.acid_allowed,
                notes=list(t.notes),
                stock_litres_per_batch=litres / injection_ratio,
                products=[
                    dict(
                        id=p.product_id,
                        name=p.name,
                        gramsPerLitre=p.grams_per_litre,
                        gramsPerBatch=p.grams_per_litre * litres,
                        stockGramsPerLitre=p.grams_per_litre * injection_ratio,
                        basis=p.basis,
                    )
                    for p in t.products
                ],
            )
            for t in grouping.tanks
        ],
    )
    return tanks, grouping, solubility, available_tanks, capacities


def _formulation_record(recipe, litres):
    """The formulation section: the salts, the target rows and what stayed unmet."""
    sources = {r['symbol']: r.get('source', []) for r in recipe['incidentalContributions']}
    return dict(
        feasible=recipe['feasible'],
        targets_met=all(
            met(r['target'], r['final']) for r in recipe['rows'] if r['target'] is not None
        ),
        match_criterion=dict(
            relative=RELATIVE_TOLERANCE, zero_target_mg_per_l=ZERO_TARGET_TOLERANCE_MG_PER_L
        ),
        salts=[
            dict(
                id=s['id'],
                name=s['name'],
                gramsPerLitre=s['gramsPerLitre'],
                gramsPerBatch=s['gramsPerLitre'] * litres,
            )
            for s in recipe['salts']
        ],
        rows=[
            dict(
                symbol=r['symbol'],
                target=r['target'],
                final=r['final'],
                deltaPct=r['deltaPct'],
                **({} if r['target'] else {'source': sources.get(r['symbol'], [])}),
            )
            for r in recipe['rows']
            if r['target'] is not None or r['final'] > 1e-6
        ],
        unmet=recipe['unmetTargets'],
        incidental_review=[
            r['symbol']
            for r in recipe['incidentalContributions']
            if r['assessment'] == 'requires_review'
        ],
        ion_balance=recipe['targetIonBalance'],
        # The ammonium allowance (G23), shown with its basis, and
        # total N as the sum of the three forms (D1, D2).
        ammonium_allowance=recipe.get('ammoniumLimit'),
        total_n=recipe.get('totalN'),
    )


def _assumptions(grouping, temperature_c):
    """The assumptions every report states beside the result."""
    return [
        'Planning calculation, not a dosing instruction: measure EC and pH after mixing.',
        'Product grades are the supplied records; confirm them against supplier certificates.',
        'EC is the experimental speciation estimate (McCleskey 2012), not a measurement.',
        'Tanks follow '
        + grouping.source
        + '; no equipment or small-dose separation waiver is applied. '
        f'Each stock is compared with its own product solubility value at {temperature_c:g} '
        '°C (basis and source temperature shown); a product without data is not checked '
        'and no comparison approves a mixed stock.',
        'A positive saturation index is a precipitation risk, not a predicted rate.',
        'Closed carbon: the mixed tank does not exchange CO2 with air.',
        'Chemistry at 25 °C only.',
        'No real-mixture predictive accuracy is claimed: results are calculations checked '
        'against reference models, and any accuracy claim needs measured evidence '
        '(issue #41).',
        'Meeting a nutrient target does not establish that nutrients remain dissolved or '
        'available; the dissolved-target calculation is not supported, so dissolved species '
        'and predicted precipitate are reported apart from the totals.',
        '1 L of solution is taken as 1 kg of water.',
    ]


def _apply_stage_evidence(summary, workflow, stages):
    """Make the stage evidence describe the same final recipe as the visible stage messages."""
    # Stage evidence must describe the same final recipe as the visible
    # stage messages. Keep alternative evaluations and the original
    # workflow evidence unchanged.
    volumetric = workflow.stages.get('volumetric_stocks')
    if volumetric is not None:
        summary['volumetric_stocks'] = deepcopy(volumetric.value)
        if volumetric.status == 'blocked':
            summary['status'] = 'blocked'
    for requirement in summary['remedies'].get('requirements', []):
        kind, _, name = requirement['id'].partition(':')
        if kind == 'stage' and name in stages:
            stage = stages[name]
            requirement['status'] = stage['status']
            requirement['evidence'] = dict(
                error_code=stage['error_code'], message=stage['message']
            )


def _bind_identity(summary, canonical, recipe, state):
    """Bind the summary to the canonical calculation it was drawn from."""
    summary['calculation_identity'] = dict(
        status='bound' if canonical is not None else 'legacy_unverified',
        result_id=canonical.result_id if canonical is not None else None,
        input_sha256=None,
        source_sha256=None,
        recipe_sha256=None,
        state_sha256=None,
    )
    if canonical is not None:
        from .canonical_result import _digest

        snapshot = canonical.to_dict()
        # The supplied inputs and product assays are saved with the result
        # and bound by input_sha256 (Q27).
        summary['supplied_inputs'] = snapshot['inputs']
        summary['calculation_identity'].update(
            input_sha256=_digest(snapshot['inputs']),
            source_sha256=_digest(snapshot['sources']),
            recipe_sha256=_digest(recipe),
            state_sha256=_digest(state) if state is not None else None,
        )


def summarize_batch(
    workflow,
    products,
    *,
    title,
    water_label,
    injection_ratio=100,
    rules=(),
    temperature_c=25,
    available_tanks=None,
    tank_capacities_litres=None,
    requested_ec_ms_cm=None,
):
    """Plain data for a grower report and batch sheet.

    ``workflow`` is a ``plan_fertilizer_workflow`` result with a final
    volume; ``products`` are the product records it was planned with
    (they give the tank grouping its chemistry); ``rules`` are extra
    ``compatibilityRule`` records. When a pH plan is selected its
    refitted recipe, which counts the reagent's nutrients, is the recipe
    to weigh. Each concentrate is compared with that product's own
    solubility value (catalogue data first, then the historical table),
    in the value's basis, and a product without data is not checked.

    ``available_tanks`` and ``tank_capacities_litres`` declare the
    equipment (D3). Undeclared, two tanks are assumed and the summary
    says so (``available_tanks_declared`` false). Capacities are listed
    in tank order, one per available tank; a tank that cannot hold its
    stock volume is reported and blocks, and the recipe and equipment
    are never changed to make it fit.
    """
    if requested_ec_ms_cm is not None and (
        isinstance(requested_ec_ms_cm, bool)
        or not isinstance(requested_ec_ms_cm, (int, float))
        or not math.isfinite(requested_ec_ms_cm)
        or requested_ec_ms_cm <= 0
    ):
        raise DeliveryError('invalid_value', 'requested_ec_ms_cm must be finite and positive')
    canonical = workflow.canonical_result
    if canonical is not None:
        canonical.verify(workflow, products)
    batch = workflow.stages.get('batch')
    if batch is None or batch.status != 'calculated':
        raise DeliveryError('missing_field', 'the workflow needs a final volume for a batch sheet')
    litres = batch.value.final_volume.value
    stages = {name: _stage(stage) for name, stage in workflow.stages.items()}
    ph_stage = workflow.stages.get('ph_adjustment')
    plan = ph_stage.value if ph_stage is not None else None
    chosen = plan.selected if plan is not None else None
    # Rejected-candidate diagnostics must never replace the weighed
    # recipe state.
    rejected = None
    if plan is not None and chosen is None:
        rejected = next(
            (c for c in plan.candidates if c.target is not None and c.direction == plan.direction),
            None,
        )
    if chosen is not None:
        recipe = chosen.recommendation
    elif plan is not None and plan.unadjusted_recommendation is not None:
        recipe = plan.unadjusted_recommendation
    else:
        recipe = workflow.recommendation
    # Report target misses and incidental contributions from the weighed
    # recipe. Preserve blocks.
    form = stages['formulation']
    if form['status'] in ('calculated', 'requires_review'):
        reason = (
            '; '.join(filter(None, (missed_message(recipe), unreviewed_reason(recipe)))) or None
        )
        form['status'], form['message'] = (
            ('requires_review', reason) if reason else ('calculated', None)
        )

    ph = _ph_record(workflow, ph_stage, plan, chosen)

    state, chemistry, ec = _chemistry_and_ec(workflow, plan, chosen, rejected)

    tanks, grouping, solubility, available_tanks, capacities = _tank_plan(
        recipe,
        products,
        rules,
        injection_ratio,
        temperature_c,
        available_tanks,
        tank_capacities_litres,
        litres,
    )

    warnings = list(recipe['warnings'])
    if ec:
        warnings.extend(ec.get('warnings', ()))
        if ec.get('reason'):
            warnings.append('EC: ' + ec['reason'].replace('_', ' ') + '.')
        note = requested_ec_note(requested_ec_ms_cm, ec)
        if note:
            warnings.append(note)
        warnings.append(ec.get('qualifier', QUALIFIER))
    chemistry_stage = workflow.stages.get('chemistry')
    concentration_basis = (
        chemistry_stage.value.get('concentration_basis')
        if chemistry_stage is not None and isinstance(chemistry_stage.value, dict)
        else None
    )
    if concentration_basis:
        warnings.append(
            'Concentration basis: '
            + concentration_basis['note']
            + ' Uncertainty: '
            + concentration_basis['uncertainty']
            + '.'
        )
    if chemistry_stage is not None and isinstance(chemistry_stage.value, dict):
        warnings.extend(chemistry_stage.value.get('water_input_notes', []))
    for name, stage in stages.items():
        message = stage['message']
        if (
            name == 'ph_adjustment'
            and chemistry
            and chosen is not None
            and chosen.message
            and message
            and message.startswith(chosen.message)
        ):
            message = message[len(chosen.message) :].lstrip(
                '; '
            )  # listed below as review rows and advisories
        if stage['status'] in ('blocked', 'requires_review') and message:
            warnings.append(f'{name}: {message}')
    if chemistry:

        def said(text):
            return any(text in w for w in warnings)

        warnings += risk_warnings(chemistry['phase_assessment'])
        warnings += [a for a in chemistry['advisories'] if not said(a)]
    warnings = list(dict.fromkeys(warnings))
    if ph_stage is not None and ph_stage.error_code in PH_NOT_PLANNED:
        status = (
            'blocked' if workflow.stages['formulation'].status == 'blocked' else 'requires_review'
        )
        warnings.append(
            f'{ph_stage.message}. pH was not planned: measure it after mixing and adjust before '
            f'use.'
        )
    elif ph_stage is not None:
        # These batches have a structural tank assignment only. A usable
        # pH plan therefore starts under review; actual hard-limit
        # failures below can still block it.
        status = (
            'requires_review'
            if ph_stage.status in ('calculated', 'requires_review')
            else 'blocked'
        )
    elif any(
        workflow.stages[n].status == 'blocked'
        for n in ('formulation', 'chemistry')
        if n in workflow.stages
    ):
        status = 'blocked'
    else:
        status = 'requires_review'  # pH not planned
        warnings.append('pH was not planned: measure it after mixing and adjust before use.')

    water, limits = _water_and_limits(workflow, recipe)
    # Final acceptance of the recipe to weigh, on the laboratory basis
    # (#84): a hard limit always blocks, and a decision the charge
    # balancing alone would change asks for review; review never
    # downgrades a block.
    if any(row['decision'] == 'exceeds_limit' for row in limits):
        status = 'blocked'
    for row in limits:
        if row['decision'] == 'exceeds_limit':
            warnings.append(
                f'{row["symbol"]} {row["analyticalPpm"]:.4g} mg/L exceeds the declared '
                f'{row["maximumPpm"]:g} mg/L maximum (laboratory analysis).'
            )
        if row['balancingChangesDecision'] and not any(row['note'] in w for w in warnings):
            warnings.append(row['note'])
    # A stock that does not dissolve at the entered temperature blocks;
    # nothing here lowers a block (#84).
    if len(grouping.tanks) > available_tanks:
        status = 'blocked'
        warnings.append(extra_tank_note(grouping, available_tanks))
    stock_litres = litres / injection_ratio
    for tank, capacity in zip(grouping.tanks, capacities):
        fits = stock_litres <= capacity
        tanks['equipment']['fit'].append(
            dict(
                tank=tank.name,
                stock_litres=stock_litres,
                capacity_litres=capacity,
                fits=fits,
            )
        )
        if not fits:
            status = 'blocked'
            warnings.append(
                f'Tank {tank.name} cannot hold {stock_litres:g} L of stock at '
                f'1:{injection_ratio:g}; its declared capacity is {capacity:g} L. The recipe '
                'is unchanged; use a larger tank or a different injection ratio.'
            )
    warnings.append('Tank separation is a structural assignment, not qualified mixture approval.')
    temperature_note = unverified_temperature_note(solubility, temperature_c)
    if temperature_note:
        warnings.append(temperature_note)
    for row in solubility:
        if row.status == 'exceeds':
            status = 'blocked'
            warnings.append(exceeds_message(row, temperature_c))
        elif row.status != 'ok':
            warnings.append(f'{row.product}: solubility not checked ({row.reason}).')
    deviation = range_assessment(
        workflow.deviation_ranges,
        {r['symbol']: r['target'] for r in recipe['rows'] if r['target'] is not None},
        {r['symbol']: r['final'] for r in recipe['rows']},
    )
    requirement = (deviation or {}).get('requirement')
    if requirement and requirement['status'] != 'met':
        # The final recipe, with the reagent, is judged against the required ranges.
        if status != 'blocked':
            status = 'requires_review'
        warnings.append(
            'A required deviation range is not met: '
            + ', '.join(
                f'{u["symbol"]} is {u["position"]} its range by {u["outsideBy"]:.3g} mg/L'
                for u in requirement['unmet']
            )
            + '. No range was widened.'
        )
    summary = dict(
        remedies=deepcopy(workflow.remedies),
        title=title,
        water_label=water_label,
        flahax_version=__version__,
        batch_litres=litres,
        target_ph=workflow.target_ph,
        target_ph_interval=list(workflow.ph_interval) if workflow.ph_interval else None,
        deviation_ranges=deviation,
        status=status,
        water=water,
        limits=limits,
        formulation=_formulation_record(recipe, litres),
        ph=ph,
        chemistry=chemistry,
        ec=ec,
        requested_ec=None
        if requested_ec_ms_cm is None
        else dict(
            requested_ms_cm=requested_ec_ms_cm, note=requested_ec_note(requested_ec_ms_cm, ec)
        ),
        tanks=tanks,
        stages=stages,
        warnings=warnings,
        concentration_basis=concentration_basis,
        solubility=[dict(**asdict(r), note=SINGLE_SALT) for r in solubility],
        assumptions=_assumptions(grouping, temperature_c),
    )

    _apply_stage_evidence(summary, workflow, stages)
    summary['statuses'] = result_statuses(summary)
    summary['status_explanations'] = status_explanations(summary)
    _bind_identity(summary, canonical, recipe, state)
    return seal_summary(summary)
