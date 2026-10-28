# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Grower outputs from a workflow result: a summary, an HTML report and a batch sheet (#79).

``summarize_batch`` reads a ``plan_fertilizer_workflow`` result and returns plain
JSON-ready data; ``render_report`` and ``render_batch_sheet`` turn that summary into
self-contained HTML (inline CSS and SVG; no script, font or network access). Every
number comes from the workflow; nothing is typed in. These are planning documents,
not dosing instructions: measure EC and pH after mixing.
"""

from .canonical_result import result_statuses, seal_summary, verify_summary
from dataclasses import asdict
from html import escape
import math

from . import __version__
from .delivery_contracts import DeliveryError
from .fertilizer_workflow import NOT_MODELLABLE, unreviewed_reason
from .irrigation_ec import calculate_ec_from_totals
from .saturation_policy import assess_saturation
from .stock_solubility import (
    SINGLE_SALT,
    check_stock_solubility,
    exceeds_message,
    load_solubility_table,
)
from .tank_grouping import group_tanks

MICRO = ('Fe', 'Mn', 'Zn', 'B', 'Cu', 'Mo')


def litres(value):
    """A volume a grower can measure: one decimal from 10 L, three below (never '0 L' for a small
    batch)."""
    return dose_number(value, 1 if value >= 10 else 3)


def grams(value):
    """A weight a grower can read on a scale: never '0 g' for a product that is in the recipe."""
    digits = 1 if value >= 10 else 2 if value >= 0.1 else 3
    shown = number(value, digits)
    return f'{shown} g' if float(shown.replace(',', '')) > 0 else 'less than 0.001 g'


def millilitres(value):
    """A reagent volume, one decimal, the same on every output."""
    return dose_number(value, 1)


def text(value):
    """The value as HTML-escaped text."""
    return escape(str(value), quote=True)


def number(value, digits=4):
    """A readable number: "Not available" for None, scientific notation below 0.0001, otherwise
    grouped with trailing zeros removed.
    """
    if value is None:
        return 'Not available'
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return text(value)
    if abs(value) < 1e-9:
        value = 0.0  # floating-point noise such as 7e-15 mg/L
    if value != 0 and abs(value) < 0.0001:
        return f'{value:.3e}'
    return f'{value:,.{digits}f}'.rstrip('0').rstrip('.') if digits else f'{value:,.0f}'


def table(headers, rows, caption):
    """An HTML table with a caption, header row and escaped cells, in a scrolling wrapper."""
    return (
        '<div class="table-scroll"><table><caption>'
        + text(caption)
        + '</caption><thead><tr>'
        + ''.join('<th scope="col">' + text(h) + '</th>' for h in headers)
        + '</tr></thead><tbody>'
        + ''.join(
            '<tr>' + ''.join('<td>' + text(cell) + '</td>' for cell in row) + '</tr>'
            for row in rows
        )
        + '</tbody></table></div>'
    )


def bars(title, labels, series, unit):
    """Zero-based grouped bars with direct value labels and a visible axis."""
    colors = ['#116c73', '#879bb0', '#e3a128']
    values = [
        v
        for _, samples in series
        for v in samples
        if isinstance(v, (int, float)) and math.isfinite(v)
    ]
    maximum = max(values, default=0)
    maximum = maximum * 1.15 if maximum > 0 else 1
    group = max(56, len(series) * 21 + 12)
    height = 94 + group * len(labels)
    left, width = 265, 545
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 {height}" role="img" '
        f'aria-label="{text(title)}">',
        '<title>' + text(title) + '</title>',
        '<desc>Zero-based horizontal bars. Exact values and units also appear in the '
        'accompanying table. '
        'Missing values are not plotted.</desc>',
    ]
    for i in range(5):
        x = left + width * i / 4
        svg.append(f'<path d="M{x} 38 V{height - 38}" stroke="#dbe4e8"/>')
        svg.append(
            f'<text x="{x}" y="{height - 16}" '
            f'text-anchor="middle">{number(maximum * i / 4, 2)}</text>'
        )
    for index, (name, _) in enumerate(series):
        x = left + index * 170
        svg.append(f'<rect x="{x}" y="9" width="11" height="11" fill="{colors[index % 3]}"/>')
        svg.append(f'<text x="{x + 17}" y="19">{text(name)}</text>')
    for row, label in enumerate(labels):
        y = 45 + group * row
        # Long product labels wrap into separate SVG text elements.
        words, lines, line = str(label).split(), [], ''
        for word in words:
            if len(line + ' ' + word) > 31 and line:
                lines.append(line)
                line = word
            else:
                line = (line + ' ' + word).strip()
        lines.append(line)
        for j, line in enumerate(lines):
            svg.append(f'<text x="12" y="{y + 14 + j * 17}">{text(line)}</text>')
        for j, (_, samples) in enumerate(series):
            value = samples[row]
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                continue
            size = width * value / maximum
            by = y + j * 21
            svg.append(
                f'<rect x="{left}" y="{by}" width="{size}" height="14" rx="3" '
                f'fill="{colors[j % 3]}"/>'
            )
            svg.append(f'<text x="{left + size + 7}" y="{by + 12}">{number(value, 3)}</text>')
    svg.append('</svg>')
    return (
        '<figure><figcaption>'
        + text(title)
        + ' <small>('
        + text(unit)
        + ')</small></figcaption>'
        + ''.join(svg)
        + '</figure>'
    )


def _stage(stage):
    return dict(
        status=stage.status,
        error_code=stage.error_code,
        message=stage.message,
        required_inputs=list(stage.required_inputs),
    )


def _water_and_limits(workflow, recipe):
    """Laboratory and modelled water side by side, and every declared limit decided on the
    laboratory basis."""
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


def summarize_batch(
    workflow,
    products,
    *,
    title,
    water_label,
    injection_ratio=100,
    rules=(),
    temperature_c=25,
    available_tanks=2,
):
    """Plain data for a grower report and batch sheet.

    ``workflow`` is a ``plan_fertilizer_workflow`` result with a final volume;
    ``products`` are the product records it was planned with (they give the tank
    grouping its chemistry); ``rules`` are extra ``compatibilityRule`` records. When
    a pH plan is selected its refitted recipe, which counts the reagent's nutrients,
    is the recipe to weigh. Each concentrate is compared with source-qualified
    references at ``temperature_c``; conditional floors cannot prove dissolution failure.
    """
    canonical = workflow.canonical_result
    if canonical is not None:
        canonical.verify(workflow, products)
    batch = workflow.stages.get('batch')
    # Blocked batches still carry diagnostic volumes; only missing volume refuses the sheet.
    if batch is None or batch.value is None:
        raise DeliveryError('missing_field', 'the workflow needs a final volume for a batch sheet')
    litres = batch.value.final_volume.value
    stages = {name: _stage(stage) for name, stage in workflow.stages.items()}
    ph_stage = workflow.stages.get('ph_adjustment')
    plan = ph_stage.value if ph_stage is not None else None
    chosen = plan.selected if plan is not None else None
    # Rejected-candidate diagnostics must never replace the weighed recipe state.
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
    # The incidental-nutrient review is judged on the recipe that is weighed, not the first fit. A
    # block or any
    # other reason is left alone: review never downgrades a block (#84).
    form, reason = stages['formulation'], unreviewed_reason(recipe)
    if form['status'] == 'calculated' or (
        form['status'] == 'requires_review'
        and form['message'] == unreviewed_reason(workflow.recommendation)
    ):
        form['status'], form['message'] = (
            ('requires_review', reason) if reason else ('calculated', None)
        )

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
                else 1000 * c.reagent_volume_litres,
                mass_g_per_batch=c.reagent_mass_g,
                nutrient_contribution=c.nutrient_contribution,
                message=c.message,
            )

        # mixed_ph: the weighed recipe without its reagent (the refit when a reagent is chosen,
        # #107).
        weighed = (
            chosen.mixed.ph
            if chosen is not None and chosen.mixed is not None
            else plan.unadjusted_ph
        )
        ph = dict(
            status=ph_stage.status,
            direction=plan.direction,
            unadjusted_ph=plan.unadjusted_ph,
            mixed_ph=weighed,
            target_ph=plan.target_ph,
            selected=candidate(chosen) if chosen is not None else None,
            candidates=[candidate(c) for c in plan.candidates if c.status != 'not_applicable'],
        )
    elif ph_stage is not None and ph_stage.error_code == NOT_MODELLABLE:
        # A product that cannot be modelled: the nutrients stand, no reagent is planned; the sheet
        # names it.
        ph = dict(
            status=ph_stage.status,
            direction=None,
            unadjusted_ph=None,
            mixed_ph=None,
            target_ph=workflow.target_ph,
            selected=None,
            candidates=[],
            message=ph_stage.message,
        )

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
    # Rolled-up blocked chemistry may still hold a diagnostic mixed state.
    if chem is not None and chem.value is not None and state_available:
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
            blocking=[dict(phase=p, si=si) for p, si in assessment['blocking']],
            review=[
                dict(phase=p, si=si, reason=r, sources=s) for p, si, r, s in assessment['review']
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

    if type(available_tanks) is not int or available_tanks < 1:
        raise DeliveryError('invalid_value', 'available_tanks must be a positive integer')
    grouping = group_tanks(recipe['salts'], products, rules=rules)
    solubility = check_stock_solubility(
        grouping.tanks, injection_ratio, temperature_c, table=load_solubility_table()
    )
    tanks = dict(
        source=grouping.source,
        required_tanks=len(grouping.tanks),
        available_tanks=available_tanks,
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

    warnings = list(recipe['warnings'])
    if ec:
        warnings.extend(ec.get('warnings', ()))
        if ec.get('reason'):
            warnings.append('EC: ' + ec['reason'].replace('_', ' ') + '.')
        warnings.append(ec.get('qualifier', 'EC accuracy is not established.'))
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

        warnings += [
            f'Review: {r["phase"]} SI {r["si"]:.2f}. {r["reason"]}'
            for r in chemistry['review']
            if not said(r['reason'])
        ]
        warnings += [a for a in chemistry['advisories'] if not said(a)]
    warnings = list(dict.fromkeys(warnings))
    if ph_stage is not None and ph_stage.error_code == NOT_MODELLABLE:
        status = (
            'blocked' if workflow.stages['formulation'].status == 'blocked' else 'requires_review'
        )
        warnings.append(
            f'{ph_stage.message}. pH was not planned: measure it after mixing and adjust before '
            f'use.'
        )
    elif ph_stage is not None:
        # The pH plan carries its own refitted recipe: its stage decides.
        status = {'calculated': 'ready', 'requires_review': 'requires_review'}.get(
            ph_stage.status, 'blocked'
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

    if form['status'] == 'blocked':
        status = 'blocked'
    elif form['status'] == 'requires_review' and status == 'ready':
        status = 'requires_review'
    water, limits = _water_and_limits(workflow, recipe)
    # Final acceptance of the recipe to weigh, on the laboratory basis (#84): a hard limit always
    # blocks, and a decision the charge balancing alone would change asks for review; review never
    # downgrades a block.
    if any(row['decision'] == 'exceeds_limit' for row in limits):
        status = 'blocked'
    elif status == 'ready' and (
        any(row['balancingChangesDecision'] for row in limits)
        or (chem is not None and chem.status == 'requires_review')
    ):
        status = 'requires_review'
    for row in limits:
        if row['decision'] == 'exceeds_limit':
            warnings.append(
                f'{row["symbol"]} {row["analyticalPpm"]:.4g} mg/L exceeds the declared '
                f'{row["maximumPpm"]:g} mg/L maximum (laboratory analysis).'
            )
        if row['balancingChangesDecision'] and not any(row['note'] in w for w in warnings):
            warnings.append(row['note'])
    # A stock that does not dissolve at the entered temperature blocks; nothing here lowers a block
    # (#84).
    if len(grouping.tanks) > available_tanks:
        status = 'blocked'
        warnings.append(
            f'Stock assignment needs {len(grouping.tanks)} tanks; '
            f'only {available_tanks} supplied. No separation is waived.'
        )
    elif status == 'ready':
        status = 'requires_review'
    warnings.append('Tank separation is a structural assignment, not qualified mixture approval.')
    for row in solubility:
        if row.status == 'exceeds':
            status = 'blocked'
            warnings.append(exceeds_message(row, temperature_c))
        elif row.status != 'ok':
            if status != 'blocked':
                status = 'requires_review'
            warnings.append(f'{row.product}: solubility {row.reason.replace("_", " ")}.')
    sources = {r['symbol']: r.get('source', []) for r in recipe['incidentalContributions']}
    summary = dict(
        remedies=workflow.remedies,
        title=title,
        water_label=water_label,
        flahax_version=__version__,
        batch_litres=litres,
        target_ph=workflow.target_ph,
        status=status,
        water=water,
        limits=limits,
        formulation=dict(
            feasible=recipe['feasible'],
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
                if r['target'] or r['final'] > 1e-6
            ],
            unmet=recipe['unmetTargets'],
            ion_balance=recipe['targetIonBalance'],
        ),
        ph=ph,
        chemistry=chemistry,
        ec=ec,
        tanks=tanks,
        stages=stages,
        warnings=warnings,
        concentration_basis=concentration_basis,
        solubility=[dict(**asdict(r), note=SINGLE_SALT) for r in solubility],
        assumptions=[
            'Planning calculation, not a dosing instruction: measure EC and pH after mixing.',
            'Product grades are the supplied records; confirm them against supplier certificates.',
            'EC is the experimental speciation estimate (McCleskey 2012), not a measurement.',
            'Tanks follow '
            + grouping.source
            + '; no equipment or small-dose separation waiver is applied. '
            f'Single-product solubility screening at {temperature_c:g} °C distinguishes '
            'qualified limits from conditional floors; unresolved source, grade or temperature '
            'requires review and no comparison approves a mixed stock.',
            'A positive saturation index is a precipitation risk, not a predicted rate.',
        ],
    )

    summary['statuses'] = result_statuses(summary)
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
        summary['calculation_identity'].update(
            input_sha256=_digest(snapshot['inputs']),
            source_sha256=_digest(snapshot['sources']),
            recipe_sha256=_digest(recipe),
            state_sha256=_digest(state) if state is not None else None,
        )
    return seal_summary(summary)


STYLE = """
:root{color-scheme:light;font-family:Segoe UI,Arial,sans-serif;color:#20353f;background:#eef3f5}
body{margin:0}main{max-width:1100px;margin:auto;padding:28px}
header{background:#103f49;color:white;padding:30px;border-radius:18px}h1{font-size:30px;margin:8px 0}
h2{font-size:22px;color:#103f49}.eyebrow{letter-spacing:2px;font-size:12px;text-transform:uppercase}
section{background:white;border-radius:18px;padding:26px;margin-top:22px;box-shadow:0 1px 3px #0001}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:18px}
.card{background:#f5f8f9;border-radius:14px;padding:16px;color:#20353f}.card strong{display:block;font-size:22px;margin:6px 0}
.card span{font-size:13px}.warn{border-left:5px solid #e3a128;background:#fff8ea;padding:12px 16px;border-radius:8px}
.ok{border-left:5px solid #116c73;background:#eef7f7;padding:12px 16px;border-radius:8px}
.stop{border-left:5px solid #b3261e;background:#fdeeee;padding:12px 16px;border-radius:8px}
table{width:100%;border-collapse:collapse;font-size:14px}caption{text-align:left;font-weight:600;padding:16px 0 8px}
th,td{border-bottom:1px solid #dbe4e8;padding:7px 9px;text-align:left;vertical-align:top}th{background:#f5f8f9}
.table-scroll{overflow-x:auto}figure{margin:18px 0;overflow-x:auto}figcaption{font-weight:600;margin-bottom:8px}
small{font-weight:400;color:#526c77}svg{display:block;width:100%;min-width:760px;height:auto}
svg text{font:16px Segoe UI,Arial,sans-serif;fill:#20353f}ul{line-height:1.6}
@media(max-width:700px){main{padding:12px}section,header{padding:16px}.cards{grid-template-columns:1fr 1fr}}
@media print{body{background:white}main{max-width:none;padding:0}section{break-inside:avoid;box-shadow:none}
header{background:white;color:#103f49;border-bottom:3px solid #103f49}}
"""  # noqa: E501

SHEET_STYLE = """
@page{size:A4;margin:12mm}:root{font-family:Segoe UI,Arial,sans-serif;color:#1d2f37;font-size:12.5px}
body{margin:0;background:white}main{max-width:190mm;margin:auto;padding:8mm 0}
h1{font-size:20px;margin:0 0 2px;color:#103f49}h2{font-size:14px;margin:12px 0 4px;color:#103f49}
.meta{color:#526c77;margin-bottom:8px}.box{border:1.5px solid #103f49;border-radius:6px;padding:7px 10px;margin:6px 0}
.warn{border-color:#c47f0a;background:#fff8ea}.stop{border-color:#b3261e;background:#fdeeee}
table{width:100%;border-collapse:collapse}
th,td{border:1px solid #b9c7cd;padding:4px 6px;text-align:left}th{background:#eef3f5}
td.num,th.num{text-align:right}.tick{width:16px;height:16px;border:1.5px solid #1d2f37;display:inline-block}
.fill{border-bottom:1px solid #1d2f37;display:inline-block;min-width:34mm}.small{font-size:11px;color:#40555e}
@media print{main{padding:0}}
"""  # noqa: E501

STATUS_WORDS = {
    'ready': 'calculation complete',
    'requires_review': 'review required',
    'blocked': 'do not mix',
}
STATUS_TEXT = {
    'ready': ('ok', 'Calculation checks passed; physical validation remains separate.'),
    'requires_review': ('warn', 'Review required: unresolved qualifications remain.'),
    'blocked': ('stop', 'Not usable as planned: see the blocked stages and warnings.'),
}


def remedy_section(summary):
    """Show evaluated alternatives separately from conditional next actions."""
    remedies = summary.get('remedies') or {}
    rows = [(r['id'], r['status'], r['next_action']) for r in remedies.get('requirements', [])]
    rows += [(r['id'], r['status'], r['next_action']) for r in remedies.get('options', [])]
    return (
        (
            '<section><h2>Remedies and next actions</h2>'
            + table(
                ('Requirement or option', 'Status', 'Next action'),
                rows,
                'Conditional planning alternatives; no automatic adoption',
            )
            + '</section>'
        )
        if rows
        else ''
    )


def percentage(value, digits=2, suffix="%"):
    """Format a relative difference without inventing a percentage for zero targets."""
    return 'undefined (zero target)' if value is None else f'{value:+.{digits}f}{suffix}'


def dose_number(value, digits=2):
    """Preserve a positive dose when fixed-point display would round it to zero."""
    shown = number(value, digits)
    if value is not None and value > 0 and float(shown.replace(',', '')) == 0:
        return f'{value:.6g}'
    return shown


def qualification_lines(summary):
    """Keep model applicability and physical validation distinct from feasibility."""
    lines = [
        'Planning calculation; physical validation is not established by this report.',
    ]
    for name, status in (summary.get('statuses') or {}).items():
        lines.append(f'{name}: {status}')
    ec = summary.get('ec')
    if not ec:
        return lines + ['EC: not evaluated; no estimate or uncertainty interval available.']
    lines.append(f"EC status: {ec.get('status', 'not reported')}")
    for key in ('reason', 'qualifier'):
        if ec.get(key):
            lines.append(f"EC {key}: {ec[key]}")
    if ec.get('status') == 'estimated' and ec.get('ec25_ms_cm') is not None:
        lines.append(f"EC25 calculated estimate: {ec['ec25_ms_cm']} mS/cm.")
    if ec.get('known_species_subtotal_ms_cm') is not None:
        lines.append(
            f"Known-species subtotal: {ec['known_species_subtotal_ms_cm']} mS/cm; "
            "not a total EC estimate, bound or midpoint."
        )
    if ec.get('ec25_range_ms_cm') is not None:
        lines.append(f"Reported EC range: {ec['ec25_range_ms_cm']} mS/cm.")
    else:
        lines.append('EC uncertainty interval: not quantified.')
    lines.append(f"EC uncertainty components: {ec.get('uncertainty_components', 'not reported')}")
    audit = ec.get('audit') or {}
    for key in ('model', 'chemistrySha256', 'coefficientsSha256'):
        lines.append(f"EC {key}: {audit.get(key, 'not reported')}")
    if ec.get('missing_species'):
        lines.append(f"Uncovered EC species: {ec['missing_species']}")
    return lines


def evidence_section(summary):
    """Embed escaped, full-precision evidence without scripts or network resources."""
    import json

    lines = ''.join(f'<li>{text(line)}</li>' for line in qualification_lines(summary))
    payload = json.dumps(summary, ensure_ascii=False, allow_nan=False, sort_keys=True)
    return (
        '<section aria-label="Scientific evidence"><h2>Scientific qualifications</h2>'
        f'<ul>{lines}</ul><details><summary>Full calculation evidence</summary>'
        '<p>Digits preserve the computed result; they do not establish measurement '
        'accuracy. Displayed quantities may be rounded.</p>'
        f'<pre id="flahax-result-data">{text(payload)}</pre></details></section>'
    )


def result_reference(summary):
    """Render the calculation content identity or explicitly label an unbound legacy view."""
    identity = summary.get('calculation_identity') or {}
    return (
        '<p class="small">Calculation reference: '
        + text(identity.get('result_id') or 'legacy unverified')
        + '</p>'
        + evidence_section(summary)
    )


def _page(title, body, style):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{text(title)}</title><style>{style}</style></head><body><main>{body}</main></body></html>\n'
    )


def _card(label, value, note):
    return (
        f'<div '
        f'class="card"><span>{text(label)}</span><strong>{text(value)}</strong><span>{text(note)}</span></div>'
    )


def _reagent_amount(candidate):
    """Display a supported liquid volume, otherwise retain the reagent mass."""
    if candidate['volume_ml_per_batch'] is None:
        if candidate['mass_g_per_batch'] is None:
            return 'Not available'
        return grams(candidate['mass_g_per_batch'])
    return f"{millilitres(candidate['volume_ml_per_batch'])} mL"


def _reagent_line(summary):
    ph = summary['ph']
    if summary.get('status') == 'blocked':
        return (
            'Blocked calculation: any reagent quantities are diagnostic only. '
            'Do not prepare this batch; resolve the recorded reasons and recalculate.'
        )
    if ph is None:
        return 'pH was not planned: supply complete water chemistry and pH reagents to plan it.'
    chosen = ph['selected']
    if chosen is None and ph['unadjusted_ph'] is None:
        return (
            f'No pH reagent was planned. {ph["message"]}. Measure the pH after mixing and '
            f'adjust before use.'
        )
    if chosen is None:
        return (
            f'No acceptable pH reagent: the feed mixes at pH {number(ph["unadjusted_ph"], 2)} '
            f'and needs '
            f'{"an acid" if ph["direction"] == "acid" else "a base"} to reach '
            f'{number(ph["target_ph"], 2)}. '
            'See the candidates and their reasons.'
        )
    return (
        f'Add {_reagent_amount(chosen)} of {chosen["product"]} '
        f'({chosen["formula"]}) per '
        f'{number(summary["batch_litres"], 0)} L to go from pH {number(ph["mixed_ph"], 2)} to '
        f'{number(ph["target_ph"], 2)}. Add it in steps and measure.'
    )


def render_report(summary):
    """Self-contained HTML report from ``summarize_batch``."""
    verify_summary(summary)
    s, f = summary, summary['formulation']
    css, line = STATUS_TEXT[s['status']]
    ph, chem, ec, tanks = s['ph'], s['chemistry'], s['ec'], s['tanks']
    targets = [r for r in f['rows'] if r['target'] is not None]
    body = (
        '<header><div class="eyebrow">FlahaX '
        + text(s['flahax_version'])
        + ' &middot; batch report</div>'
        f'<h1>{text(s["title"])}</h1><p>Water: {text(s["water_label"])}. Batch '
        f'{number(s["batch_litres"], 0)} L, '
        f'target pH {number(s["target_ph"], 2)}.</p>'
        '<div class="cards">'
        + _card('Plan', s['status'].replace('_', ' '), STATUS_WORDS[s['status']])
        + _card('Targets met', 'Yes' if f['feasible'] else 'No', f'{len(f["unmet"])} missed')
        + _card(
            'Feed pH',
            number(chem['final_ph'], 2) if chem else 'not planned',
            f'mixed {number(chem["mixed_ph"], 2)}' if chem else 'needs complete water chemistry',
        )
        + _card(
            'EC25 estimate',
            f'{number(ec["ec25_ms_cm"], 2)} mS/cm'
            if ec and ec['status'] == 'estimated' and ec['ec25_ms_cm'] is not None
            else 'n/a',
            'experimental',
        )
        + '</div></header>'
        f'<section><h2>Status</h2><p class="{css}">{text(line)}</p><p>{text(_reagent_line(s))}</p>'
        + (
            ('<ul>' + ''.join(f'<li>{text(w)}</li>' for w in s['warnings']) + '</ul>')
            if s['warnings']
            else ''
        )
        + '</section>'
        '<section><h2>Recipe</h2>'
        + table(
            ['Product', 'g/L', f'g per {number(s["batch_litres"], 0)} L'],
            [
                (x['name'], dose_number(x['gramsPerLitre'], 4), grams(x['gramsPerBatch']))
                for x in f['salts']
            ],
            'Diagnostic recipe quantities' if s['status'] == 'blocked' else 'Products to weigh',
        )
        + ''.join(
            bars(
                f'{label.capitalize()}: target and delivered',
                [r['symbol'] for r in group],
                [
                    ('Target', [r['target'] for r in group]),
                    ('Delivered', [r['final'] for r in group]),
                ],
                'mg/L',
            )
            for group, label in (
                ([r for r in targets if r['symbol'] not in MICRO], 'macronutrients'),
                ([r for r in targets if r['symbol'] in MICRO], 'micronutrients'),
            )
            if group
        )
        + table(
            ['Nutrient', 'Target mg/L', 'Delivered mg/L', 'Difference'],
            [
                (
                    r['symbol'],
                    number(r['target'], 3) if r['target'] is not None else 'not a target',
                    number(r['final'], 3),
                    percentage(r['deltaPct']) if r['target'] is not None else 'incidental',
                )
                for r in f['rows']
            ],
            'Nutrient fit, including what the water and the pH reagent bring',
        )
        + (
            (
                '<p>Missed targets:</p><ul>'
                + ''.join(
                    f'<li><b>{text(u["symbol"])}</b> {percentage(u["deltaPct"])} - '
                    f'{text(u["reason"])}</li>'
                    for u in f['unmet']
                )
                + '</ul>'
            )
            if f['unmet']
            else ''
        )
        + '</section>'
    )
    if ph is not None and ph['unadjusted_ph'] is not None:
        body += (
            '<section><h2>pH adjustment</h2>'
            f'<p>The first recipe mixes at pH {number(ph["unadjusted_ph"], 2)}; it needs '
            f'{"an acid" if ph["direction"] == "acid" else "a base"} to reach '
            f'{number(ph["target_ph"], 2)}. Each '
            'candidate is dosed to the target and the recipe is refitted with its nutrients '
            'counted'
            + (
                f'; the weighed recipe mixes at pH {number(ph["mixed_ph"], 2)} before the reagent'
                if ph['selected'] and ph['mixed_ph'] is not None
                else ''
            )
            + '.</p>'
            + table(
                ['Reagent', 'Formula', 'Quantity per batch', 'Status', 'Reason'],
                [
                    (
                        c['product'],
                        c['formula'],
                        _reagent_amount(c),
                        c['status'],
                        c['message'] or '',
                    )
                    for c in ph['candidates']
                ],
                'Reagents evaluated',
            )
            + '</section>'
        )
    if chem is not None:
        reading = {r['phase']: 'review' for r in chem['review']} | {
            b['phase']: 'blocks' for b in chem['blocking']
        }
        body += (
            '<section><h2>Chemistry of the final feed</h2>'
            + (
                '<p>Rejected-reagent diagnostics are retained separately in the summary; '
                'the chemistry and EC below describe the weighed recipe.</p>'
                if chem.get('rejected_candidate_diagnostics')
                else ''
            )
            + f'<p>Water pH {number(chem["water_ph"], 2)}; mixed {number(chem["mixed_ph"], 2)}; '
            f'final '
            f'{number(chem["final_ph"], 2)}; ionic strength {number(chem["ionic_strength"], 4)} '
            f'mol/kg.</p>'
            + table(
                ['Phase', 'Saturation index', 'Reading'],
                [
                    (
                        p,
                        number(si, 2),
                        reading.get(p, 'undersaturated' if si <= 0 else 'supersaturated'),
                    )
                    for p, si in chem['indices']
                ],
                'Saturation indices above -1',
            )
            + ''.join(
                f'<p class="small"><b>{text(r["phase"])}</b>: {text(r["reason"])} Sources: '
                f'{text(r["sources"])}</p>'
                for r in chem['review']
            )
            + '</section>'
        )
    body += _water_section(s)
    body += _tank_section(s, tanks)
    if s.get('product_notes'):
        body += (
            '<section><h2>Data-sheet notes</h2><ul>'
            + ''.join(
                f'<li>{text(name)}: {text("; ".join(notes))}</li>'
                for name, notes in s['product_notes'].items()
            )
            + '</ul><p class="small">As entered from the product data sheets; FlahaX does not '
            'check them.</p></section>'
        )
    body += (
        '<section><h2>Stages</h2>'
        + table(
            ['Stage', 'Status', 'Reason or missing input'],
            [
                (
                    n,
                    st['status'],
                    st['message'] or st['error_code'] or ', '.join(st['required_inputs']) or '',
                )
                for n, st in s['stages'].items()
            ],
            'Workflow stages',
        )
        + '<h2>Assumptions</h2><ul>'
        + ''.join(f'<li>{text(a)}</li>' for a in s['assumptions'])
        + '</ul></section>'
    )
    body += remedy_section(s)
    return _page(s['title'], body + result_reference(s), STYLE)


def _limit_rows(s):
    return [
        (
            row['symbol'],
            number(row['maximumPpm'], 2),
            number(row['analyticalPpm'], 2),
            'n/a' if row['modelledPpm'] is None else number(row['modelledPpm'], 2),
            ('exceeds' if row['decision'] == 'exceeds_limit' else 'within')
            + (' (balancing would change it: review)' if row['balancingChangesDecision'] else ''),
        )
        for row in s['limits']
    ]


def _limits_text(s):
    if not s['limits']:
        return 'No maximum concentrations were declared, so none were checked.'
    return (
        'Limits are decided on the laboratory analysis plus everything added, at the final '
        'volume. '
        'The charge-balanced value is shown for comparison only.'
    )


def _water_section(s):
    w = s['water']
    ions = sorted(set(w['analysis_mg_per_litre']) | set(w['modelled_mg_per_litre'] or {}))
    rows = [
        (
            ion,
            number(w['analysis_mg_per_litre'].get(ion, 0.0), 3),
            'n/a'
            if w['modelled_mg_per_litre'] is None
            else number(w['modelled_mg_per_litre'].get(ion, 0.0), 3),
            f'{w["adjustment_mg_per_litre"][ion]:+.3f}'
            if ion in w['adjustment_mg_per_litre']
            else '',
        )
        for ion in ions
        if w['analysis_mg_per_litre'].get(ion) or (w['modelled_mg_per_litre'] or {}).get(ion)
    ]
    state = w['reconciliation']
    if state is None:
        note = ''
    elif state == 'unchanged':
        note = (
            f'<p>The analysis closes its charge at its measured pH '
            f'{number(w["measured_ph"], 2)}: no adjustment '
            'was needed, and the chemistry uses it as measured.</p>'
        )
    elif state == 'closed_on_alkalinity':
        note = (
            f'<p>For the chemistry only, the analysis ({number(w["imbalance_percent"], 2)}% out '
            f'of charge balance '
            f'at its measured pH {number(w["measured_ph"], 2)}) has no chloride, so it is '
            f'closed on positive, nonfixed directly supplied carbon '
            '(not a titration). That is a modelling step, not a '
            'corrected measurement: '
            'targets and limits use the laboratory values.</p>'
        )
    else:
        how = (
            f'within its stated ±{number(w["balance_ion_uncertainty_percent"], 2)}% measurement '
            f'uncertainty'
            if state == 'reconciled'
            else 'without a stated measurement uncertainty, so the chemistry needs review'
        )
        note = (
            f'<p>For the chemistry only, the analysis ({number(w["imbalance_percent"], 2)}% out '
            f'of charge balance '
            f'at its measured pH {number(w["measured_ph"], 2)}) is closed on '
            f'{text(w["balance_ion"])}, {how}. That is '
            'a modelling step, not a corrected measurement: targets and limits use the '
            'laboratory values.</p>'
        )
    if state is not None:
        note += (
            '<p class="small">Measured pH and charge balance constrain the chemistry model. '
            'Reconciliation changes only the model inventory, never laboratory nutrient limits. '
            'Measured zeros, fixed carbon and titrated alkalinity are preserved.</p>'
        )
    if w['below_detection']:
        note += (
            '<p>Reported below detection (taken as zero, not confirmed zero): '
            + text(', '.join(w['below_detection']))
            + '.</p>'
        )
    return (
        '<section><h2>Water and limits</h2>'
        + note
        + (
            table(
                ['Nutrient', 'Laboratory mg/L', 'Charge-balanced model mg/L', 'Adjustment'],
                rows,
                'Water in the final solution (decision basis: laboratory analysis)',
            )
            if rows
            else '<p>The water brings no ions.</p>'
        )
        + f'<p>{text(_limits_text(s))}</p>'
        + (
            table(
                [
                    'Nutrient',
                    'Maximum mg/L',
                    'Final, laboratory basis',
                    'Final, model basis',
                    'Decision',
                ],
                _limit_rows(s),
                'Declared maximum concentrations',
            )
            if s['limits']
            else ''
        )
        + '</section>'
    )


def _tank_section(s, tanks):
    rows = [
        (
            f'Tank {t["name"]}',
            p['name'],
            grams(p['gramsPerBatch']),
            number(p['stockGramsPerLitre'], 2),
            p['basis'],
        )
        for t in tanks['tanks']
        for p in t['products']
    ]
    notes = ''.join(
        f'<li>Tank {text(t["name"])}: {text(n)}</li>' for t in tanks['tanks'] for n in t['notes']
    )
    separated = ''.join(
        f'<li>{text(a)} / {text(b)}: {text(why)}</li>' for a, b, why in tanks['separations']
    )
    waived = ''.join(
        f'<li>{text(a)} / {text(b)}: {text(why)}</li>' for a, b, why in tanks['waived']
    )
    return (
        '<section><h2>Concentrate tanks</h2>'
        + table(
            [
                'Tank',
                'Product',
                f'g per {number(s["batch_litres"], 0)} L',
                f'Stock g/L at 1:{tanks["injection_ratio"]:g}',
                'Why here',
            ],
            rows,
            'Tanks from the default compatibility table',
        )
        + table(
            [
                'Tank',
                'Product',
                'Stock g/L',
                f'Reference g/L at {number(tanks["temperature_c"], 1)} °C',
                'Solubility',
                'Source',
            ],
            _solubility_rows(s),
            'Single-product solubility screening',
        )
        + f'<p class="small">Solubility basis: {text(SINGLE_SALT)}.</p>'
        + (f'<ul>{notes}</ul>' if notes else '')
        + (
            f'<details><summary>Pairs kept apart</summary><ul>{separated}</ul></details>'
            if separated
            else ''
        )
        + (f'<p>Shared by rule, against Yara p. 65:</p><ul>{waived}</ul>' if waived else '')
        + f'<p class="small">Source: {text(tanks["source"])}.</p></section>'
    )


SOLUBILITY_TEXT = {
    'ok': 'within single-product limit',
    'exceeds': 'above single-product limit',
    'not_checked': 'not checked',
    'screening_only': 'conditional screening only',
    'inconclusive': 'above floor; inconclusive',
}


def _solubility_rows(s):
    return [
        (
            f'Tank {r["tank"]}',
            r['product'],
            number(r['stock_g_per_l'], 1),
            number(
                r['limit_g_per_l']
                if r['limit_g_per_l'] is not None
                else r.get('screening_g_per_l'),
                1,
            ),
            SOLUBILITY_TEXT[r['status']],
            r['source'] or 'no sourced data',
        )
        for r in s['solubility']
    ]


def _unchecked_line(s):
    names = [r['product'] for r in s['solubility'] if r['status'] not in {'ok', 'exceeds'}]
    return (
        (
            'Solubility not checked as a qualified limit '
            '(basis, grade or temperature unresolved): ' + ', '.join(names) + '. '
            'Confirm these dissolve with your supplier.'
        )
        if names
        else ''
    )


def render_batch_sheet(summary):
    """Printable A4 batch sheet from ``summarize_batch``."""
    verify_summary(summary)
    s, tanks = summary, summary['tanks']
    blocked = s['status'] == 'blocked'
    css, line = STATUS_TEXT[s['status']]
    litres, ratio = s['batch_litres'], tanks['injection_ratio']
    rows = ''.join(
        f'<tr><td>{text(t["name"])}</td><td>{text(p["name"])}</td><td '
        f'class="num">{dose_number(p["gramsPerBatch"], 1)}</td>'
        f'<td class="num">{dose_number(p["stockGramsPerLitre"], 2)}</td><td><span '
        f'class="{"muted" if blocked else "tick"}"></span></td></tr>'
        for t in tanks['tanks']
        for p in t['products']
    )
    ec = s['ec']
    checks = [
        (
            'EC25 (mS/cm)',
            f'about {number(ec["ec25_ms_cm"], 2)} (experimental)'
            if ec and ec['status'] == 'estimated' and ec['ec25_ms_cm'] is not None
            else 'measure',
        ),
        ('pH', number(s['target_ph'], 2)),
    ]
    check_rows = ''.join(
        f'<tr><td>{text(k)}</td><td>{text(v)}</td><td><span class="fill"></span></td></tr>'
        for k, v in checks
    )
    tank_notes = ''.join(
        f'<li>Tank {text(t["name"])}: {text(n)}</li>' for t in tanks['tanks'] for n in t['notes']
    )
    warnings = ''.join(f'<li>{text(w)}</li>' for w in s['warnings'])
    body = (
        f'<h1>{text(s["title"])}</h1><div class="meta">Batch sheet &middot; FlahaX '
        f'{text(s["flahax_version"])} '
        f'&middot; {number(litres, 0)} L final solution</div>'
        f'<div class="box {css}"><b>{text(STATUS_WORDS[s["status"]].capitalize())}.</b> '
        f'{text(line)}</div>'
        f'<div class="box"><b>Water:</b> {text(s["water_label"])}</div>'
        f'<h2>{"Diagnostic quantities — do not prepare" if blocked else "Weigh and dissolve"}</h2>'
        '<table><thead><tr><th>Tank</th><th>Product</th>'
        f'<th class="num">g per {number(litres, 0)} L batch</th><th class="num">Concentrate g/L '
        f'at 1:{ratio}</th>'
        f'<th>Done</th></tr></thead><tbody>{rows}</tbody></table>'
        + (
            '<p class="small">Blocked calculation: quantities are diagnostic only; '
            'do not prepare this batch.</p>'
            if blocked
            else f'<p class="small">Direct batch: dissolve everything in {number(litres, 0)} L. '
            f'Concentrates: {number(litres / ratio, 1)} L of each tank per batch '
            f'at 1:{ratio}; keep the tanks apart as listed.</p>'
        )
        + (f'<ul class="small">{tank_notes}</ul>' if tank_notes else '')
        + f'<h2>Solubility at {number(tanks["temperature_c"], 1)} '
        f'&deg;C</h2><table><thead><tr><th>Tank</th>'
        '<th>Product</th><th class="num">Concentrate g/L</th><th class="num">Reference '
        'g/L</th><th>Result</th>'
        '</tr></thead><tbody>'
        + ''.join(
            f'<tr><td>{text(r[0])}</td><td>{text(r[1])}</td><td class="num">{r[2]}</td>'
            f'<td class="num">{r[3]}</td><td>{text(r[4])}</td></tr>'
            for r in _solubility_rows(s)
        )
        + '</tbody></table>'
        + (f'<p class="small">{text(_unchecked_line(s))}</p>' if _unchecked_line(s) else '')
        + f'<p class="small">Basis: {text(SINGLE_SALT)}.</p>'
        + f'<h2>pH</h2><div class="box warn">{text(_reagent_line(s))}</div>'
        + '<h2>Limits</h2><p class="small">'
        + text(_limits_text(s))
        + '</p>'
        + (
            (
                '<table><thead><tr><th>Nutrient</th><th class="num">Maximum mg/L</th><th '
                'class="num">Final mg/L '
                '(laboratory basis)</th><th>Decision</th></tr></thead><tbody>'
                + ''.join(
                    f'<tr><td>{text(r[0])}</td><td class="num">{r[1]}</td><td '
                    f'class="num">{r[2]}</td>'
                    f'<td>{text(r[4])}</td></tr>'
                    for r in _limit_rows(s)
                )
                + '</tbody></table>'
            )
            if s['limits']
            else ''
        )
        + (f'<h2>Read before mixing</h2><ul class="small">{warnings}</ul>' if warnings else '')
        + (
            '<h2>Measure after '
            'mixing</h2><table><thead><tr><th>Check</th><th>Planned</th><th>Measured</th></tr></thead>'
            f'<tbody>{check_rows}</tbody></table>'
            '<p class="small">Operator <span class="fill"></span> &nbsp; Date <span '
            'class="fill"></span> &nbsp; '
            'Signature <span class="fill"></span></p>'
            if not blocked
            else ''
        )
        + '<p class="small">Planning calculation from FlahaX; not a dosing instruction. Stock '
        'solubility is checked '
        'only where source basis, grade and temperature are qualified. Confirm assays against '
        'your supplier '
        'certificates.</p>'
    )
    return _page(s['title'] + ' - batch sheet', body + result_reference(s), SHEET_STYLE)
