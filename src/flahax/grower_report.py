"""Grower outputs from a workflow result: a summary, an HTML report and a batch sheet (#79).

``summarize_batch`` reads a ``plan_fertilizer_workflow`` result and returns plain
JSON-ready data; ``render_report`` and ``render_batch_sheet`` turn that summary into
self-contained HTML (inline CSS and SVG; no script, font or network access). Every
number comes from the workflow; nothing is typed in. These are planning documents,
not dosing instructions: measure EC and pH after mixing.
"""
from html import escape
import math

from . import __version__
from .delivery_contracts import DeliveryError
from .fertilizer_workflow import unreviewed_reason
from .irrigation_ec import calculate_ec_from_totals
from .saturation_policy import assess_saturation
from .tank_grouping import group_tanks

MICRO = ('Fe', 'Mn', 'Zn', 'B', 'Cu', 'Mo')


def text(value):
    return escape(str(value), quote=True)


def number(value, digits=4):
    if value is None:
        return 'Not available'
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return text(value)
    if value != 0 and abs(value) < .0001:
        return f'{value:.3e}'
    return f'{value:,.{digits}f}'.rstrip('0').rstrip('.') if digits else f'{value:,.0f}'


def table(headers, rows, caption):
    return ('<div class="table-scroll"><table><caption>' + text(caption) + '</caption><thead><tr>'
            + ''.join('<th scope="col">' + text(h) + '</th>' for h in headers)
            + '</tr></thead><tbody>'
            + ''.join('<tr>' + ''.join('<td>' + text(cell) + '</td>' for cell in row) + '</tr>' for row in rows)
            + '</tbody></table></div>')


def bars(title, labels, series, unit):
    """Zero-based grouped bars with direct value labels and a visible axis."""
    colors = ['#116c73', '#879bb0', '#e3a128']
    values = [v for _, samples in series for v in samples if isinstance(v, (int, float)) and math.isfinite(v)]
    maximum = max(values, default=0)
    maximum = maximum * 1.15 if maximum > 0 else 1
    group = max(56, len(series) * 21 + 12)
    height = 94 + group * len(labels)
    left, width = 265, 545
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 {height}" role="img" aria-label="{text(title)}">',
           '<title>' + text(title) + '</title>',
           '<desc>Zero-based horizontal bars. Exact values and units also appear in the accompanying table. '
           'Missing values are not plotted.</desc>']
    for i in range(5):
        x = left + width * i / 4
        svg.append(f'<path d="M{x} 38 V{height - 38}" stroke="#dbe4e8"/>')
        svg.append(f'<text x="{x}" y="{height - 16}" text-anchor="middle">{number(maximum * i / 4, 2)}</text>')
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
            svg.append(f'<rect x="{left}" y="{by}" width="{size}" height="14" rx="3" fill="{colors[j % 3]}"/>')
            svg.append(f'<text x="{left + size + 7}" y="{by + 12}">{number(value, 3)}</text>')
    svg.append('</svg>')
    return '<figure><figcaption>' + text(title) + ' <small>(' + text(unit) + ')</small></figcaption>' + ''.join(svg) + '</figure>'


def _stage(stage):
    return dict(status=stage.status, error_code=stage.error_code, message=stage.message,
                required_inputs=list(stage.required_inputs))


def _water_and_limits(workflow, recipe):
    """Laboratory and modelled water side by side, and every declared limit decided on the laboratory basis."""
    basis = getattr(workflow, 'water_basis', None)
    water = dict(decision_basis='laboratory analysis',
                 analysis_mg_per_litre=dict(basis['analyticalPpm'] if basis else workflow.water),
                 modelled_mg_per_litre=dict(basis['modelledPpm']) if basis else None,
                 adjustment_mg_per_litre=dict(basis['adjustmentPpm']) if basis else {},
                 balance_ion=basis['balanceIon'] if basis else None,
                 reconciliation=basis['reconciliation'] if basis else None,
                 balance_ion_uncertainty_percent=basis['balanceIonUncertaintyPercent'] if basis else None,
                 below_detection=sorted(basis['belowDetectionMolal']) if basis else [],
                 imbalance_percent=basis['imbalancePercent'] if basis else None,
                 measured_ph=basis['measuredPh'] if basis else None,
                 dilution_fraction=basis['dilutionFraction'] if basis else None)
    finals = {row['symbol']: row['final'] for row in recipe['rows']}
    limits = []
    for ion, limit in sorted((getattr(workflow, 'maximum_concentrations', None) or {}).items()):
        lab = finals.get(ion, 0.)
        model = lab - basis['analyticalPpm'].get(ion, 0.) + basis['modelledPpm'].get(ion, 0.) if basis else None
        exceeds = lab > limit + 1e-12
        flips = model is not None and (model > limit + 1e-12) != exceeds
        limits.append(dict(
            symbol=ion, maximumPpm=limit, analyticalPpm=lab, modelledPpm=model,
            decision='exceeds_limit' if exceeds else 'within_limit', basis='laboratory analysis',
            balancingChangesDecision=flips,
            note=(f'{ion}: {lab:.4g} mg/L on the laboratory analysis is {"above" if exceeds else "within"} the '
                  f'{limit:g} mg/L maximum; the charge-balanced model gives {model:.4g} mg/L. The decision uses the '
                  'laboratory value; check the analysis.') if flips else None))
    return water, limits


def summarize_batch(workflow, products, *, title, water_label, injection_ratio=100, rules=()):
    """Plain data for a grower report and batch sheet.

    ``workflow`` is a ``plan_fertilizer_workflow`` result with a final volume;
    ``products`` are the product records it was planned with (they give the tank
    grouping its chemistry); ``rules`` are extra ``compatibilityRule`` records. When
    a pH plan is selected its refitted recipe, which counts the reagent's nutrients,
    is the recipe to weigh.
    """
    batch = workflow.stages.get('batch')
    if batch is None or batch.status != 'calculated':
        raise DeliveryError('missing_field', 'the workflow needs a final volume for a batch sheet')
    litres = batch.value.final_volume.value
    stages = {name: _stage(stage) for name, stage in workflow.stages.items()}
    ph_stage = workflow.stages.get('ph_adjustment')
    plan = ph_stage.value if ph_stage is not None else None
    chosen = plan.selected if plan is not None else None
    # Without a selected reagent, report the pH plan's own recipe (acids are not nutrient sources there)
    # and the rejected state of its first computed candidate, so the blocking phases are shown.
    rejected = None
    if plan is not None and chosen is None:
        rejected = next((c for c in plan.candidates if c.target is not None and c.direction == plan.direction), None)
    if chosen is not None:
        recipe = chosen.recommendation
    elif plan is not None and plan.unadjusted_recommendation is not None:
        recipe = plan.unadjusted_recommendation
    else:
        recipe = workflow.recommendation
    # The incidental-nutrient review is judged on the recipe that is weighed, not the first fit. A block or any
    # other reason is left alone: review never downgrades a block (#84).
    form, reason = stages['formulation'], unreviewed_reason(recipe)
    if form['status'] == 'calculated' or (form['status'] == 'requires_review'
                                          and form['message'] == unreviewed_reason(workflow.recommendation)):
        form['status'], form['message'] = ('requires_review', reason) if reason else ('calculated', None)

    ph = None
    if plan is not None:
        def candidate(c):
            name = (c.product_record or {}).get('name') or c.product_id
            return dict(product_id=c.product_id, product=name, formula=c.formula, direction=c.direction,
                        status=c.status, volume_ml_per_batch=None if c.reagent_volume_litres is None
                        else 1000 * c.reagent_volume_litres, mass_g_per_batch=c.reagent_mass_g,
                        nutrient_contribution=c.nutrient_contribution, message=c.message)
        ph = dict(status=ph_stage.status, direction=plan.direction, unadjusted_ph=plan.unadjusted_ph,
                  target_ph=plan.target_ph, selected=candidate(chosen) if chosen is not None else None,
                  candidates=[candidate(c) for c in plan.candidates if c.status != 'not_applicable'])

    chemistry = ec = None
    chem = workflow.stages.get('chemistry')
    if chem is not None and chem.status in ('calculated', 'requires_review'):
        picked = chosen or rejected
        mixed = picked.mixed if picked is not None and picked.mixed is not None else chem.value['mixed']
        state = picked.target if picked is not None else mixed
        assessment = assess_saturation(state)
        chemistry = dict(
            water_ph=chem.value['water'].ph, mixed_ph=mixed.ph, final_ph=state.ph, ionic_strength=state.ionic_strength,
            blocking=[dict(phase=p, si=si) for p, si in assessment['blocking']],
            review=[dict(phase=p, si=si, reason=r, sources=s) for p, si, r, s in assessment['review']],
            advisories=assessment['advisories'], solids=assessment['solids'],
            indices=sorted(([p, si] for p, si in state.saturation_indices.items()
                            if isinstance(si, float) and si > -1), key=lambda item: -item[1]))
        try:
            result = calculate_ec_from_totals(state.totals, solution_id='batch', ph_mode='supplied', ph=state.ph,
                                              phase_policy='dissolved')
            ec = dict(status=result.status, ec25_ms_cm=result.ec25_ms_cm, ph=result.ph)
        except DeliveryError as exc:
            ec = dict(status='not_supported', ec25_ms_cm=None, ph=state.ph, message=str(exc))

    grouping = group_tanks(recipe['salts'], products, rules=rules)
    tanks = dict(source=grouping.source, injection_ratio=injection_ratio, solubility_checked=False,
                 reagent_channel=list(grouping.reagent_channel),
                 separations=[list(s) for s in grouping.separations],
                 waived=[list(w) for w in grouping.waived],
                 tanks=[dict(name=t.name, acid_allowed=t.acid_allowed, notes=list(t.notes),
                             stock_litres_per_batch=litres / injection_ratio,
                             products=[dict(id=p.product_id, name=p.name, gramsPerLitre=p.grams_per_litre,
                                            gramsPerBatch=p.grams_per_litre * litres,
                                            stockGramsPerLitre=p.grams_per_litre * injection_ratio, basis=p.basis)
                                       for p in t.products]) for t in grouping.tanks])

    warnings = list(recipe['warnings'])
    for name, stage in stages.items():
        if stage['status'] in ('blocked', 'requires_review') and stage['message']:
            warnings.append(f'{name}: {stage["message"]}')
    if chemistry:
        warnings += [f'Review: {r["phase"]} SI {r["si"]:.2f}. {r["reason"]}' for r in chemistry['review']]
        warnings += chemistry['advisories']
    if ph_stage is not None:
        # The pH plan carries its own refitted recipe: its stage decides.
        status = {'calculated': 'ready', 'requires_review': 'requires_review'}.get(ph_stage.status, 'blocked')
    elif any(workflow.stages[n].status == 'blocked' for n in ('formulation', 'chemistry') if n in workflow.stages):
        status = 'blocked'
    else:
        status = 'requires_review'      # pH not planned
        warnings.append('pH was not planned: measure it after mixing and adjust before use.')

    if form['status'] == 'requires_review' and status == 'ready':
        status = 'requires_review'
    water, limits = _water_and_limits(workflow, recipe)
    # Final acceptance of the recipe to weigh, on the laboratory basis (#84): a hard limit always blocks,
    # and a decision the charge balancing alone would change asks for review; review never downgrades a block.
    if any(row['decision'] == 'exceeds_limit' for row in limits):
        status = 'blocked'
    elif status == 'ready' and (any(row['balancingChangesDecision'] for row in limits)
                                or (chem is not None and chem.status == 'requires_review')):
        status = 'requires_review'
    for row in limits:
        if row['decision'] == 'exceeds_limit':
            warnings.append(f'{row["symbol"]} {row["analyticalPpm"]:.4g} mg/L exceeds the declared '
                            f'{row["maximumPpm"]:g} mg/L maximum (laboratory analysis).')
        if row['balancingChangesDecision'] and not any(row['note'] in w for w in warnings):
            warnings.append(row['note'])
    return dict(
        title=title, water_label=water_label, flahax_version=__version__, batch_litres=litres,
        target_ph=workflow.target_ph, status=status, water=water, limits=limits,
        formulation=dict(feasible=recipe['feasible'], salts=[dict(id=s['id'], name=s['name'], gramsPerLitre=s['gramsPerLitre'],
                                                                  gramsPerBatch=s['gramsPerLitre'] * litres)
                                                             for s in recipe['salts']],
                         rows=[dict(symbol=r['symbol'], target=r['target'], final=r['final'], deltaPct=r['deltaPct'])
                               for r in recipe['rows'] if r['target'] or r['final'] > 1e-6],
                         unmet=recipe['unmetTargets'], ion_balance=recipe['targetIonBalance']),
        ph=ph, chemistry=chemistry, ec=ec, tanks=tanks, stages=stages, warnings=warnings,
        assumptions=[
            'Planning calculation, not a dosing instruction: measure EC and pH after mixing.',
            'Product grades are the supplied records; confirm them against supplier certificates.',
            'EC is the experimental speciation estimate (McCleskey 2012), not a measurement.',
            'Tanks follow ' + grouping.source + '; micronutrients and chelates go to tank A (FlahaX rule). '
            'Stock solubility is not checked: confirm each concentrate dissolves at its strength and temperature.',
            'A positive saturation index is a precipitation risk, not a predicted rate.'])


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
"""

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
"""

STATUS_TEXT = {
    'ready': ('ok', 'Every target is met and the pH plan is accepted.'),
    'requires_review': ('warn', 'Usable after review: read the warnings before mixing.'),
    'blocked': ('stop', 'Not usable as planned: see the blocked stages and warnings.'),
}


def _page(title, body, style):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{text(title)}</title><style>{style}</style></head><body><main>{body}</main></body></html>\n')


def _card(label, value, note):
    return f'<div class="card"><span>{text(label)}</span><strong>{text(value)}</strong><span>{text(note)}</span></div>'


def _reagent_line(summary):
    ph = summary['ph']
    if ph is None:
        return 'pH was not planned: supply complete water chemistry and pH reagents to plan it.'
    chosen = ph['selected']
    if chosen is None:
        return (f'No acceptable pH reagent: the feed mixes at pH {number(ph["unadjusted_ph"], 2)} and needs '
                f'{"an acid" if ph["direction"] == "acid" else "a base"} to reach {number(ph["target_ph"], 2)}. '
                'See the candidates and their reasons.')
    return (f'Add {number(chosen["volume_ml_per_batch"], 0)} mL of {chosen["product"]} ({chosen["formula"]}) per '
            f'{number(summary["batch_litres"], 0)} L to go from pH {number(ph["unadjusted_ph"], 2)} to '
            f'{number(ph["target_ph"], 2)}. Add it in steps and measure.')


def render_report(summary):
    """Self-contained HTML report from ``summarize_batch``."""
    s, f = summary, summary['formulation']
    css, line = STATUS_TEXT[s['status']]
    ph, chem, ec, tanks = s['ph'], s['chemistry'], s['ec'], s['tanks']
    targets = [r for r in f['rows'] if r['target']]
    body = ('<header><div class="eyebrow">FlahaX ' + text(s['flahax_version']) + ' &middot; batch report</div>'
            f'<h1>{text(s["title"])}</h1><p>Water: {text(s["water_label"])}. Batch {number(s["batch_litres"], 0)} L, '
            f'target pH {number(s["target_ph"], 2)}.</p>'
            '<div class="cards">'
            + _card('Plan', s['status'].replace('_', ' '), 'ready / requires review / blocked')
            + _card('Targets met', 'Yes' if f['feasible'] else 'No', f'{len(f["unmet"])} missed')
            + _card('Feed pH', number(chem['final_ph'], 2) if chem else 'not planned',
                    f'mixed {number(chem["mixed_ph"], 2)}' if chem else 'needs complete water chemistry')
            + _card('EC25 estimate', f'{number(ec["ec25_ms_cm"], 2)} mS/cm' if ec and ec['ec25_ms_cm'] else 'n/a',
                    'experimental')
            + '</div></header>'
            f'<section><h2>Status</h2><p class="{css}">{text(line)}</p><p>{text(_reagent_line(s))}</p>'
            + (('<ul>' + ''.join(f'<li>{text(w)}</li>' for w in s['warnings']) + '</ul>') if s['warnings'] else '')
            + '</section>'
            '<section><h2>Recipe</h2>'
            + table(['Product', 'g/L', f'g per {number(s["batch_litres"], 0)} L'],
                    [(x['name'], number(x['gramsPerLitre'], 4), number(x['gramsPerBatch'], 1)) for x in f['salts']],
                    'Products to weigh')
            + ''.join(bars(f'{label.capitalize()}: target and delivered', [r['symbol'] for r in group],
                           [('Target', [r['target'] for r in group]), ('Delivered', [r['final'] for r in group])], 'mg/L')
                      for group, label in (([r for r in targets if r['symbol'] not in MICRO], 'macronutrients'),
                                           ([r for r in targets if r['symbol'] in MICRO], 'micronutrients')) if group)
            + table(['Nutrient', 'Target mg/L', 'Delivered mg/L', 'Difference'],
                    [(r['symbol'], number(r['target'], 3) if r['target'] else 'not a target', number(r['final'], 3),
                      f'{r["deltaPct"]:+.2f}%' if r['deltaPct'] is not None else 'incidental') for r in f['rows']],
                    'Nutrient fit, including what the water and the pH reagent bring')
            + (('<p>Missed targets:</p><ul>' + ''.join(
                f'<li><b>{text(u["symbol"])}</b> {u["deltaPct"]:+.2f}% - {text(u["reason"])}</li>' for u in f['unmet'])
                + '</ul>') if f['unmet'] else '')
            + '</section>')
    if ph is not None:
        body += ('<section><h2>pH adjustment</h2>'
                 f'<p>The recipe mixes at pH {number(ph["unadjusted_ph"], 2)}; it needs '
                 f'{"an acid" if ph["direction"] == "acid" else "a base"} to reach {number(ph["target_ph"], 2)}. Each '
                 'candidate is dosed to the target and the recipe is refitted with its nutrients counted.</p>'
                 + table(['Reagent', 'Formula', 'mL per batch', 'Status', 'Reason'],
                         [(c['product'], c['formula'], number(c['volume_ml_per_batch'], 0), c['status'], c['message'] or '')
                          for c in ph['candidates']], 'Reagents evaluated')
                 + '</section>')
    if chem is not None:
        reading = {r['phase']: 'review' for r in chem['review']} | {b['phase']: 'blocks' for b in chem['blocking']}
        body += ('<section><h2>Chemistry of the final feed</h2>'
                 f'<p>Water pH {number(chem["water_ph"], 2)}; mixed {number(chem["mixed_ph"], 2)}; final '
                 f'{number(chem["final_ph"], 2)}; ionic strength {number(chem["ionic_strength"], 4)} mol/kg.</p>'
                 + table(['Phase', 'Saturation index', 'Reading'],
                         [(p, number(si, 2), reading.get(p, 'undersaturated' if si <= 0 else 'supersaturated'))
                          for p, si in chem['indices']], 'Saturation indices above -1')
                 + ''.join(f'<p class="small"><b>{text(r["phase"])}</b>: {text(r["reason"])} Sources: '
                           f'{text(r["sources"])}</p>' for r in chem['review'])
                 + '</section>')
    body += _water_section(s)
    body += _tank_section(s, tanks)
    body += ('<section><h2>Stages</h2>'
             + table(['Stage', 'Status', 'Reason or missing input'],
                     [(n, st['status'], st['message'] or st['error_code'] or ', '.join(st['required_inputs']) or '')
                      for n, st in s['stages'].items()], 'Workflow stages')
             + '<h2>Assumptions</h2><ul>' + ''.join(f'<li>{text(a)}</li>' for a in s['assumptions']) + '</ul></section>')
    return _page(s['title'], body, STYLE)


def _limit_rows(s):
    return [(row['symbol'], number(row['maximumPpm'], 2), number(row['analyticalPpm'], 2),
             'n/a' if row['modelledPpm'] is None else number(row['modelledPpm'], 2),
             ('exceeds' if row['decision'] == 'exceeds_limit' else 'within')
             + (' (balancing would change it: review)' if row['balancingChangesDecision'] else ''))
            for row in s['limits']]


def _limits_text(s):
    if not s['limits']:
        return 'No maximum concentrations were declared, so none were checked.'
    return ('Limits are decided on the laboratory analysis plus everything added, at the final volume. '
            'The charge-balanced value is shown for comparison only.')


def _water_section(s):
    w = s['water']
    ions = sorted(set(w['analysis_mg_per_litre']) | set(w['modelled_mg_per_litre'] or {}))
    rows = [(ion, number(w['analysis_mg_per_litre'].get(ion, 0.), 3),
             'n/a' if w['modelled_mg_per_litre'] is None else number(w['modelled_mg_per_litre'].get(ion, 0.), 3),
             f'{w["adjustment_mg_per_litre"][ion]:+.3f}' if ion in w['adjustment_mg_per_litre'] else '')
            for ion in ions if w['analysis_mg_per_litre'].get(ion) or (w['modelled_mg_per_litre'] or {}).get(ion)]
    state = w['reconciliation']
    if state is None:
        note = ''
    elif state == 'unchanged':
        note = (f'<p>The analysis closes its charge at its measured pH {number(w["measured_ph"], 2)}: no adjustment '
                'was needed, and the chemistry uses it as measured.</p>')
    else:
        how = (f'within its stated ±{number(w["balance_ion_uncertainty_percent"], 2)}% measurement uncertainty'
               if state == 'reconciled' else 'without a stated measurement uncertainty, so the chemistry needs review')
        note = (f'<p>For the chemistry only, the analysis ({number(w["imbalance_percent"], 2)}% out of charge balance '
                f'at its measured pH {number(w["measured_ph"], 2)}) is closed on {text(w["balance_ion"])}, {how}. That is '
                'a modelling step, not a corrected measurement: targets and limits use the laboratory values.</p>')
    if w['below_detection']:
        note += ('<p>Reported below detection (taken as zero, not confirmed zero): '
                 + text(', '.join(w['below_detection'])) + '.</p>')
    return ('<section><h2>Water and limits</h2>' + note
            + (table(['Nutrient', 'Laboratory mg/L', 'Charge-balanced model mg/L', 'Adjustment'], rows,
                     'Water in the final solution (decision basis: laboratory analysis)') if rows else
               '<p>The water brings no ions.</p>')
            + f'<p>{text(_limits_text(s))}</p>'
            + (table(['Nutrient', 'Maximum mg/L', 'Final, laboratory basis', 'Final, model basis', 'Decision'],
                     _limit_rows(s), 'Declared maximum concentrations') if s['limits'] else '')
            + '</section>')


def _tank_section(s, tanks):
    rows = [(f'Tank {t["name"]}', p['name'], number(p['gramsPerBatch'], 1), number(p['stockGramsPerLitre'], 2), p['basis'])
            for t in tanks['tanks'] for p in t['products']]
    notes = ''.join(f'<li>Tank {text(t["name"])}: {text(n)}</li>' for t in tanks['tanks'] for n in t['notes'])
    separated = ''.join(f'<li>{text(a)} / {text(b)}: {text(why)}</li>' for a, b, why in tanks['separations'])
    waived = ''.join(f'<li>{text(a)} / {text(b)}: {text(why)}</li>' for a, b, why in tanks['waived'])
    return ('<section><h2>Concentrate tanks</h2>'
            + table(['Tank', 'Product', f'g per {number(s["batch_litres"], 0)} L', f'Stock g/L at 1:{tanks["injection_ratio"]}',
                     'Why here'], rows, 'Tanks from the default compatibility table (solubility not checked)')
            + (f'<ul>{notes}</ul>' if notes else '')
            + (f'<details><summary>Pairs kept apart</summary><ul>{separated}</ul></details>' if separated else '')
            + (f'<p>Shared by rule, against Yara p. 65:</p><ul>{waived}</ul>' if waived else '')
            + f'<p class="small">Source: {text(tanks["source"])}.</p></section>')


def render_batch_sheet(summary):
    """Printable A4 batch sheet from ``summarize_batch``."""
    s, tanks = summary, summary['tanks']
    css, line = STATUS_TEXT[s['status']]
    litres, ratio = s['batch_litres'], tanks['injection_ratio']
    rows = ''.join(
        f'<tr><td>{text(t["name"])}</td><td>{text(p["name"])}</td><td class="num">{number(p["gramsPerBatch"], 1)}</td>'
        f'<td class="num">{number(p["stockGramsPerLitre"], 2)}</td><td><span class="tick"></span></td></tr>'
        for t in tanks['tanks'] for p in t['products'])
    ec = s['ec']
    checks = [('EC25 (mS/cm)', f'about {number(ec["ec25_ms_cm"], 2)} (experimental)' if ec and ec['ec25_ms_cm'] else 'measure'),
              ('pH', number(s['target_ph'], 2))]
    check_rows = ''.join(f'<tr><td>{text(k)}</td><td>{text(v)}</td><td><span class="fill"></span></td></tr>'
                         for k, v in checks)
    tank_notes = ''.join(f'<li>Tank {text(t["name"])}: {text(n)}</li>' for t in tanks['tanks'] for n in t['notes'])
    warnings = ''.join(f'<li>{text(w)}</li>' for w in s['warnings'])
    body = (f'<h1>{text(s["title"])}</h1><div class="meta">Batch sheet &middot; FlahaX {text(s["flahax_version"])} '
            f'&middot; {number(litres, 0)} L final solution</div>'
            f'<div class="box {css}"><b>{text(s["status"].replace("_", " ").capitalize())}.</b> {text(line)}</div>'
            f'<div class="box"><b>Water:</b> {text(s["water_label"])}</div>'
            '<h2>Weigh and dissolve</h2><table><thead><tr><th>Tank</th><th>Product</th>'
            f'<th class="num">g per {number(litres, 0)} L batch</th><th class="num">Concentrate g/L at 1:{ratio}</th>'
            f'<th>Done</th></tr></thead><tbody>{rows}</tbody></table>'
            f'<p class="small">Direct batch: dissolve everything in {number(litres, 0)} L. Concentrates: '
            f'{number(litres / ratio, 1)} L of each tank per batch at 1:{ratio}; keep the tanks apart as listed.</p>'
            + (f'<ul class="small">{tank_notes}</ul>' if tank_notes else '')
            + f'<h2>pH</h2><div class="box warn">{text(_reagent_line(s))}</div>'
            + '<h2>Limits</h2><p class="small">' + text(_limits_text(s)) + '</p>'
            + (('<table><thead><tr><th>Nutrient</th><th class="num">Maximum mg/L</th><th class="num">Final mg/L '
                '(laboratory basis)</th><th>Decision</th></tr></thead><tbody>'
                + ''.join(f'<tr><td>{text(r[0])}</td><td class="num">{r[1]}</td><td class="num">{r[2]}</td>'
                          f'<td>{text(r[4])}</td></tr>' for r in _limit_rows(s))
                + '</tbody></table>') if s['limits'] else '')
            + (f'<h2>Read before mixing</h2><ul class="small">{warnings}</ul>' if warnings else '')
            + '<h2>Measure after mixing</h2><table><thead><tr><th>Check</th><th>Planned</th><th>Measured</th></tr></thead>'
            f'<tbody>{check_rows}</tbody></table>'
            '<p class="small">Operator <span class="fill"></span> &nbsp; Date <span class="fill"></span> &nbsp; '
            'Signature <span class="fill"></span></p>'
            '<p class="small">Planning calculation from FlahaX; not a dosing instruction. Stock solubility is not '
            'checked. Confirm products, assays and reagent grades against your supplier certificates.</p>')
    return _page(s['title'] + ' - batch sheet', body, SHEET_STYLE)
