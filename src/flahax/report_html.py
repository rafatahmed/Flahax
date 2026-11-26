# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The HTML report and the batch sheet, drawn from a batch summary."""

from .canonical_result import verify_summary
from .report_format import (
    bars,
    display_residue,
    dose_number,
    ec_text,
    grams,
    number,
    percentage,
    table,
    text,
)
from .requirement_fit import met
from .result_wording import (
    STATUS_TEXT,
    STATUS_WORDS,
    joint_verdict,
    limit_rows,
    limits_text,
    miss_difference,
    missed_rows,
    nitrogen_paragraphs,
    ph_goal,
    qualification_lines,
    reagent_amount,
    reagent_line,
    reagent_preparation_lines,
    review_reason,
    rounded_dose_rows,
    solubility_rows,
    unchecked_line,
)
from .stock_solubility import SINGLE_SALT


MICRO = ('Fe', 'Mn', 'Zn', 'B', 'Cu', 'Mo')


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


def remedy_section(summary):
    """Show evaluated alternatives separately from conditional next
    actions.
    """
    remedies = summary.get('remedies') or {}
    rows = [(r['id'], r['status'], r['next_action']) for r in remedies.get('requirements', [])]
    rows += [(r['id'], r['status'], r['next_action']) for r in remedies.get('options', [])]
    best = remedies.get('best_candidate_id')
    ranking = (
        f'<p>Best candidate found in this bounded search: {text(best)}.</p>'
        if best is not None
        else ''
    )
    return (
        (
            '<section><h2>Remedies and next actions</h2>'
            + ranking
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


def evidence_section(summary):
    """Embed escaped, full-precision evidence without scripts or network
    resources.
    """
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
    """Render the calculation content identity or explicitly label an
    unbound legacy view.
    """
    identity = summary.get('calculation_identity') or {}
    return (
        '<p class="small">Calculation reference: '
        + text(identity.get('result_id') or 'legacy unverified')
        + '</p>'
        + evidence_section(summary)
    )


def page(title, body, style):
    """One self-contained HTML page around ``body``."""
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


def ranges_table(summary):
    """The user's acceptable deviation ranges against the delivered recipe, or nothing."""
    ranges = summary.get('deviation_ranges')
    if not ranges:
        return ''

    def bound(value):
        return 'open' if value is None else number(value, 3)

    mode = (
        'Required: the fit was constrained by these ranges.'
        if ranges['mode'] == 'require'
        else 'Assessed only: the fit was not changed.'
    )
    return table(
        ['Nutrient', 'Target mg/L', 'Range mg/L', 'Delivered mg/L', 'Position'],
        [
            (
                r['symbol'],
                number(r['target'], 3),
                f'{bound(r["low"])} to {bound(r["high"])}',
                number(r['final'], 3),
                r['position']
                if r['position'] == 'inside'
                else f'{r["position"]} by {number(r["outsideBy"], 3)}',
            )
            for r in ranges['assessment']
        ],
        f'Acceptable deviation ranges you declared. {mode}',
    )


def render_report(summary):
    """Self-contained HTML report from ``summarize_batch``."""
    verify_summary(summary)
    s, f = summary, summary['formulation']
    css, line = STATUS_TEXT[s['status']]
    plan_note = review_reason(s) if s['status'] == 'requires_review' else STATUS_WORDS[s['status']]
    ph, chem, ec, tanks = s['ph'], s['chemistry'], s['ec'], s['tanks']
    targets = [r for r in f['rows'] if r['target'] is not None]
    body = (
        '<header><div class="eyebrow">FlahaX '
        + text(s['flahax_version'])
        + ' &middot; batch report</div>'
        f'<h1>{text(s["title"])}</h1><p>Water: {text(s["water_label"])}. Batch '
        f'{number(s["batch_litres"], 0)} L, '
        f'target pH {ph_goal(s)}.'
        + (
            f' The plan aims at the nearest bound, {number(s["target_ph"], 2)}, not a midpoint.'
            if s.get('target_ph_interval') and s.get('target_ph') is not None
            else ''
        )
        + '</p>'
        '<div class="cards">'
        + _card('Plan', s['status'].replace('_', ' '), plan_note)
        + _card(
            'Targets met',
            'Yes' if f.get('targets_met', f['feasible']) else 'No',
            f'{len(f["unmet"])} missed',
        )
        + _card(
            'Feed pH',
            number(chem['final_ph'], 2) if chem else 'not planned',
            f'mixed {number(chem["mixed_ph"], 2)}' if chem else 'needs complete water chemistry',
        )
        + _card(
            'EC25 estimate',
            f'{ec_text(ec)} mS/cm' if ec_text(ec) else 'n/a',
            'experimental',
        )
        + '</div></header>'
        '<section><h2>Status</h2>'
        + (f'<p class="{css}">{text(line)}</p>' if s['status'] != 'requires_review' else '')
        + f'<p>{text(reagent_line(s))}</p>'
        + ''.join(f'<p>{text(line)}</p>' for line in reagent_preparation_lines(s))
        + (
            ('<ul>' + ''.join(f'<li>{text(w)}</li>' for w in s['warnings']) + '</ul>')
            if s['warnings']
            else ''
        )
        + (f'<p>{text(joint_verdict(s))}</p>' if joint_verdict(s) else '')
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
                    miss_difference(r['target'], r['final'])
                    if r['target'] is not None and not met(r['target'], r['final'])
                    else percentage(r['deltaPct'])
                    if r['target'] is not None
                    else 'incidental',
                )
                for r in f['rows']
            ],
            'Nutrient fit, including what the water and the pH reagent bring',
        )
        + nitrogen_paragraphs(s)
        + ranges_table(s)
        + (
            (
                '<p>Missed targets:</p><ul>'
                + ''.join(
                    f'<li><b>{text(u["symbol"])}</b> '
                    f'{miss_difference(u["target"], u["final"])} - {text(u["reason"])}</li>'
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
        needed = {'acid': 'an acid', 'base': 'a base', 'none': 'no reagent'}[ph['direction']]
        body += (
            '<section><h2>pH adjustment</h2>'
            f'<p>The first recipe mixes at pH {number(ph["unadjusted_ph"], 2)}; it needs '
            f'{needed} to reach {number(ph["target_ph"], 2)}'
            + (
                f'; the weighed recipe mixes at pH {number(ph["mixed_ph"], 2)} before the reagent'
                if ph['selected'] and ph['mixed_ph'] is not None
                else ''
            )
            + '.</p>'
            + table(
                ['Reagent', 'Formula', 'Quantity per batch', 'Status', 'Reason', 'Search outcome'],
                [
                    (
                        c['product'],
                        c['formula'],
                        reagent_amount(c),
                        c['status'],
                        c['message'] or '',
                        (c.get('joint') or {}).get('reason', ''),
                    )
                    for c in [*ph['candidates'], *ph.get('skipped', [])]
                ],
                'Reagents evaluated or skipped',
            )
            + '</section>'
        )
    if chem is not None:
        reading = {r['phase']: 'information' for r in chem['information']} | {
            r['phase']: 'precipitation risk' for r in chem['risk']
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
                ['Species', 'mol/kg water'],
                [
                    (name, f'{amount:.3e}')
                    for name, amount in list(chem['species_mol_per_kg'].items())[:12]
                ],
                'Dissolved species, largest first (the twelve largest); nutrient totals are above',
            )
            + (
                table(
                    ['Phase', 'mol/kg water'],
                    [(n, f'{a:.3e}') for n, a in chem['precipitated_mol_per_kg'].items()],
                    'Predicted precipitate',
                )
                if chem['precipitated_mol_per_kg']
                else '<p>No precipitate is predicted at this pH and composition.</p>'
            )
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
                f'<p class="small"><b>{text(r["phase"])}</b>: supersaturated; '
                f'{text(r["basis"])}.</p>'
                for r in chem['information']
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
    if 'volumetric_stocks' in s:
        body += volumetric_stock_section(s)
    body += remedy_section(s)
    return page(s['title'], body + result_reference(s), STYLE)


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
    else:
        note = (
            f'<p>The analysis is {number(abs(w["imbalance_percent"]), 2)}% out of charge balance '
            f'at its measured pH {number(w["measured_ph"], 2)}. It is used as measured: '
            'no ion is added, removed or adjusted, and the chemistry carries the imbalance. '
            'Targets and limits use the laboratory values.</p>'
        )
    if state is not None:
        note += (
            '<p class="small">The measured pH sets the chemistry model. '
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
        + f'<p>{text(limits_text(s))}</p>'
        + (
            table(
                [
                    'Nutrient',
                    'Maximum mg/L',
                    'Final, laboratory basis',
                    'Final, model basis',
                    'Decision',
                ],
                limit_rows(s),
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
                'Limit g/L',
                'Solubility',
                'Source',
            ],
            solubility_rows(s),
            'Single-product solubility check',
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


def volumetric_stock_section(summary):
    """Show only the delivered quantities for the rounded preparation
    option.
    """
    stage = summary['stages']['volumetric_stocks']
    delivered = summary['volumetric_stocks']
    heading = '<section><h2>Rounded batch doses</h2>'
    if delivered is None:
        return heading + f'<p>{text(stage["message"])}</p></section>'
    risk = ', '.join(name for name, _ in delivered['saturation']['risk'])
    notice = (
        'Review before mixing. Make up to the stated final volume including stock doses, '
        'then measure pH and EC.'
        if summary['status'] != 'blocked'
        else 'Diagnostic quantities only. This batch is blocked.'
    )
    return (
        heading
        + f'<p>{text(notice)}</p>'
        + f'<p>Modeled final pH {number(delivered["ph"], 5)}.</p>'
        + (f'<p>Modeled saturation risk: {text(risk)}.</p>' if risk else '')
        + table(
            ('Product', 'Dose', 'Delivery'), rounded_dose_rows(delivered), 'Rounded preparation'
        )
        + f'<p>{text(delivered["assumptions"])}</p></section>'
    )


def render_batch_sheet(summary):
    """Printable A4 batch sheet from ``summarize_batch``."""
    verify_summary(summary)
    if 'volumetric_stocks' in summary:
        title = summary['title']
        heading = (
            f'<h1>{text(title)}</h1><p>{number(summary["batch_litres"], 0)} L final solution.</p>'
        )
        return page(title, heading + volumetric_stock_section(summary), STYLE)
    s, tanks = summary, summary['tanks']
    blocked = s['status'] == 'blocked'
    css, line = STATUS_TEXT[s['status']]
    if s['status'] == 'requires_review':
        line = review_reason(s)
    litres, ratio = s['batch_litres'], tanks['injection_ratio']
    rows = []
    for tank in tanks['tanks']:
        for product in tank['products']:
            mass = product['gramsPerBatch']
            residue = display_residue(mass)
            weight = grams(mass) if residue else dose_number(mass, 1)
            marker = 'muted' if blocked or residue else 'tick'
            rows.append(
                f'<tr><td>{text(tank["name"])}</td><td>{text(product["name"])}</td>'
                f'<td class="num">{weight}</td>'
                f'<td class="num">{dose_number(product["stockGramsPerLitre"], 2)}</td>'
                f'<td><span class="{marker}"></span></td></tr>'
            )
    rows = ''.join(rows)
    ec = s['ec']
    checks = [
        (
            'EC25 (mS/cm)',
            f'{ec_text(ec, about=True)} (experimental)' if ec_text(ec) else 'measure',
        ),
        ('pH', ph_goal(s)),
    ]
    check_rows = ''.join(
        f'<tr><td>{text(k)}</td><td>{text(v)}</td><td><span class="fill"></span></td></tr>'
        for k, v in checks
    )
    tank_notes = ''.join(
        f'<li>Tank {text(t["name"])}: {text(n)}</li>' for t in tanks['tanks'] for n in t['notes']
    )
    warnings = ''.join(f'<li>{text(w)}</li>' for w in s['warnings'])
    misses = missed_rows(s)
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
            for r in solubility_rows(s)
        )
        + '</tbody></table>'
        + (f'<p class="small">{text(unchecked_line(s))}</p>' if unchecked_line(s) else '')
        + f'<p class="small">Basis: {text(SINGLE_SALT)}.</p>'
        + f'<h2>pH</h2><div class="box warn">{text(reagent_line(s))}</div>'
        + ''.join(f'<p>{text(line)}</p>' for line in reagent_preparation_lines(s))
        + (f'<p>{text(joint_verdict(s))}</p>' if joint_verdict(s) else '')
        + (
            '<h2>Missed nutrient targets</h2>'
            + table(
                ['Nutrient', 'Difference from target'],
                [(row['symbol'], miss_difference(row['target'], row['final'])) for row in misses],
                'Final recipe deviations',
            )
            if misses
            else ''
        )
        + '<h2>Limits</h2><p class="small">'
        + text(limits_text(s))
        + '</p>'
        + nitrogen_paragraphs(s)
        + (
            (
                '<table><thead><tr><th>Nutrient</th><th class="num">Maximum mg/L</th><th '
                'class="num">Final mg/L '
                '(laboratory basis)</th><th>Decision</th></tr></thead><tbody>'
                + ''.join(
                    f'<tr><td>{text(r[0])}</td><td class="num">{r[1]}</td><td '
                    f'class="num">{r[2]}</td>'
                    f'<td>{text(r[4])}</td></tr>'
                    for r in limit_rows(s)
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
        'only where a product has solubility data. Confirm assays against '
        'your supplier '
        'certificates.</p>'
    )
    return page(s['title'] + ' - batch sheet', body + result_reference(s), SHEET_STYLE)
