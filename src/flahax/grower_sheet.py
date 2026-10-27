# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The ``flahax mix`` batch sheet: tank cards for the grower, the nutrient table for the
agronomist.

Depth 1 (grower) is the tank cards, the acid container, the checks and at most three notes.
Depth 2 (agronomist) adds the nutrient table (target, water, required, achieved, final, diff),
the limits and the pH path. Depth 3 (developer, manager) writes the full report beside it.
Every number comes from ``summarize_batch``, i.e. from the recipe that is weighed.
"""

import re

from .grower_report import (
    SHEET_STYLE,
    STATUS_WORDS,
    _limit_rows,
    _page,
    _reagent_line,
    grams,  # noqa: F401
    litres,
    millilitres,
    number,
    text,
)

LABEL = {'N_NO3': 'NO3-N', 'N_NH4': 'NH4-N', 'N_UREA': 'Urea-N'}
REASON_WORDS = {
    '(no_source)': '(no product supplies it)',
    '(conflicting_targets)': '(conflicts with other targets)',
}


def readable(warning):
    """A warning in grower words: NO3-N for N_NO3, plain reasons, "pH adjustment:" for a stage."""
    stage = re.match(r'([a-z]+(?:_[a-z]+)*): ', warning)
    if stage:
        name = stage.group(1).replace('_', ' ')
        name = 'pH' + name[2:] if name.startswith('ph ') else name.capitalize()
        warning = f'{name}: {warning[stage.end():]}'
    for code, words in REASON_WORDS.items():
        warning = warning.replace(code, words)
    return re.sub(r'\bN_(NO3|NH4|UREA)\b', lambda m: LABEL[m.group(0)], warning)


CARD_STYLE = (
    SHEET_STYLE
    + """
.cards{display:grid;grid-template-columns:1fr 1fr;gap:8px}.card{border:1.5px solid #103f49;border-radius:6px;padding:7px 10px}
.card h2{margin:0 0 4px}.ok{border-color:#116c73;background:#eef7f7}.hi{color:#b3261e;font-weight:600}
.muted{color:#6b7f88}@media(max-width:640px){main{padding:12px}.cards{grid-template-columns:1fr}}
"""  # noqa: E501
)


def key_reasons(summary, n=3):
    """The warnings a grower must read, blocking ones first (a blocked stage, a hard limit, a
    stock that won't dissolve)."""
    stopped = tuple(
        f'{name}:' for name, s in summary['stages'].items() if s['status'] == 'blocked'
    )
    return sorted(
        summary['warnings'],
        key=lambda w: not (
            w.startswith(stopped)
            or 'exceeds the declared' in w
            or ' does not dissolve in tank ' in w
        ),
    )[:n]


def agronomist_rows(summary):
    """Per nutrient: target, water, required (target - water), achieved (final - water), final,
    diff (final - target)."""
    water = summary['water']['analysis_mg_per_litre']
    rows = []
    for r in summary['formulation']['rows']:
        target, final, w = r['target'], r['final'], water.get(r['symbol'], 0.0)
        if not target and final < 1e-6:
            continue
        rows.append(
            dict(
                nutrient=r['symbol'],
                target=target or None,
                water=w,
                required=None if not target else target - w,
                achieved=final - w,
                final=final,
                diff_mg_l=None if not target else final - target,
                diff_pct=None if not target else 100.0 * (final - target) / target,
                source=r.get('source', []),
            )
        )
    return sorted(rows, key=lambda r: r['target'] is None)


def limited_by(volumes):
    """In fill mode, the container that sets the batch when another one could hold more."""
    if not volumes or volumes.get('mode') != 'fill':
        return ''
    capacity = volumes['capacity_litres']
    smallest = min(capacity, key=capacity.get)
    if all(c == capacity[smallest] for c in capacity.values()):
        return ''
    name = 'acid container' if smallest == 'acid' else f'tank {smallest}'
    return f' (your {litres(capacity[smallest])} L {name} sets the batch)'


def _grams(product):
    return grams(product['gramsPerBatch'])


def _tank_card(tank, volumes, blocked):
    name = tank['name']
    head = (
        (
            f'prepare <b>{litres(volumes["prepared_litres"][name])} L</b> in your '
            f'{litres(volumes["capacity_litres"][name])} L tank{limited_by(volumes)}'
        )
        if volumes and not blocked
        else ('not to be prepared (do not mix)' if blocked else '')
    )
    box = '<span class="muted">-</span>' if blocked else '<span class="tick"></span>'
    rows = ''.join(
        f'<tr><td>{box}</td><td>{text(p["name"])}</td><td class="num">{_grams(p)}</td></tr>'
        for p in tank['products']
    )
    rule = (
        ''
        if tank['acid_allowed']
        else f'<p class="small"><b>Never add acid to tank {text(name)}.</b></p>'
    )
    return (
        f'<div class="card"><h2>Tank '
        f'{text(name)}</h2><p>{head}</p><table><tbody>{rows}</tbody></table>'
        f'{rule}</div>'
    )


def _reagent_card(summary, volumes):
    ph = summary['ph']
    chosen = ph and ph['selected']
    if not chosen:
        return (
            f'<div class="card warn"><h2>pH '
            f'reagent</h2><p>{text(_reagent_line(summary))}</p></div>'
        )
    if chosen['volume_ml_per_batch'] is None:
        return (
            f'<div class="card"><h2>pH reagent</h2>' f'<p>{text(_reagent_line(summary))}</p></div>'
        )
    title = 'Acid' if chosen['direction'] == 'acid' else 'pH reagent'
    per_1000 = chosen['volume_ml_per_batch'] * 1000.0 / summary['batch_litres']
    container = (
        (
            f'<p>Acid container: add <b>{millilitres(chosen["volume_ml_per_batch"])} mL</b> to '
            f'water and make up to '
            f'<b>{litres(volumes["prepared_litres"]["acid"])} L</b>.</p>'
        )
        if volumes
        else ''
    )
    return (
        f'<div class="card"><h2>{title}</h2><p><b>{text(chosen["product"])}</b> '
        f'({text(chosen["formula"])}): '
        f'{millilitres(per_1000)} mL per 1,000 L of irrigation, on its own '
        f'injector.</p>{container}'
        '<p class="small"><b>Add acid to water, never water to acid.</b></p></div>'
    )


def _check_card(summary):
    ec = summary['ec']
    expected = (
        f'about {number(ec["ec25_ms_cm"], 2)} mS/cm' if ec and ec.get('ec25_ms_cm') else 'measure'
    )
    return (
        '<div class="card"><h2>Check after mixing</h2><table><tbody>'
        f'<tr><td>pH</td><td>expect {number(summary["target_ph"], 2)}</td><td><span '
        f'class="fill"></span></td></tr>'
        f'<tr><td>EC</td><td>{text(expected)}</td><td><span '
        f'class="fill"></span></td></tr></tbody></table></div>'
    )


def _agronomist_section(summary):
    def cell(v, digits=2):
        return '' if v is None else number(v, digits)

    body = ''
    for r in agronomist_rows(summary):
        name = LABEL.get(r['nutrient'], r['nutrient'])
        if r['target'] is None:
            source = ', '.join(r['source']) or 'water'
            body += (
                f'<tr class="muted"><td>{text(name)}<br><span class="small">from '
                f'{text(source)}, not in formula'
                f'</span></td><td></td><td class="num">{cell(r["water"])}</td><td></td>'
                f'<td class="num">{cell(r["achieved"])}</td><td '
                f'class="num">{cell(r["final"])}</td><td></td></tr>'
            )
            continue
        hi = ' class="num hi"' if abs(r['diff_pct']) > 1 else ' class="num"'
        body += (
            f'<tr><td>{text(name)}</td><td class="num">{cell(r["target"])}</td><td '
            f'class="num">{cell(r["water"])}</td>'
            f'<td class="num">{cell(r["required"])}</td><td class="num">{cell(r["achieved"])}</td>'
            f'<td class="num">{cell(r["final"])}</td><td{hi}>{r["diff_mg_l"]:+.2f} '
            f'({r["diff_pct"]:+.1f} %)</td></tr>'
        )
    table = (
        '<h2>Nutrients, mg/L in the irrigation solution</h2><div '
        'class="table-scroll"><table><thead><tr>'
        '<th>Nutrient</th><th class="num">Target</th><th class="num">From water</th><th '
        'class="num">Required</th>'
        '<th class="num">Achieved</th><th class="num">Final</th><th '
        'class="num">Diff</th></tr></thead>'
        f'<tbody>{body}</tbody></table></div><p class="small">Required = target - water; '
        f'achieved = fertilizers '
        '+ pH reagent; final = water + achieved; diff = final - target (beyond 1 % in red).</p>'
    )
    limits = ''.join(
        f'<li>{text(r[0])}: {r[2]} of {r[1]} mg/L ({text(r[4])})</li>'
        for r in _limit_rows(summary)
    )
    ph, chem = summary['ph'], summary.get('chemistry')
    path = []
    if chem:
        path.append(f'water {number(chem["water_ph"], 2)}')
    if ph and ph.get('mixed_ph') is not None:
        path.append(f'after fertilizers {number(ph["mixed_ph"], 2)}')
    if ph and ph['selected']:
        path.append(f'after {ph["selected"]["direction"]} {number(ph["target_ph"], 2)}')
        adds = ', '.join(
            f'{LABEL.get(k, k)} {number(v, 2)} mg/L'
            for k, v in (ph['selected'].get('nutrient_contribution') or {}).items()
        )
    else:
        adds = ''
    reasons = ''.join(f'<li>{text(readable(w))}</li>' for w in summary['warnings'])
    return (
        table
        + (
            f'<h2>Limits (laboratory basis)</h2><ul class="small">{limits}</ul>'
            if limits
            else '<p class="small">No limits declared; none are assumed.</p>'
        )
        + (
            f'<h2>pH</h2><p>{" &rarr; ".join(path)}'
            + (f'. The reagent adds {text(adds)}.' if adds else '')
            + '</p>'
            if path
            else ''
        )
        + (f'<h2>Why review</h2><ul class="small">{reasons}</ul>' if reasons else '')
    )


def render_mix_sheet(summary, depth=1):
    """Printable sheet: depth 1 tank cards; depth 2 and 3 add the nutrient table, limits and pH
    path."""
    from .canonical_result import verify_summary

    verify_summary(summary)
    s, volumes = summary, summary.get('volumes')
    blocked = s['status'] == 'blocked'
    css = {'ready': 'ok', 'requires_review': 'warn', 'blocked': 'stop'}[s['status']]
    supplied = volumes['irrigation_litres'] if volumes else s['batch_litres']
    notes = ''.join(f'<li>{text(readable(w))}</li>' for w in key_reasons(s))
    head = (
        f'<h1>{text(s["title"])}</h1><div class="meta">FlahaX {text(s["flahax_version"])} '
        f'&middot; '
        f'{number(supplied, 0)} L of irrigation at 1:{s["tanks"]["injection_ratio"]:g} &middot; '
        f'pH '
        f'{number(s["target_ph"], 2)} &middot; {text(s["water_label"])}</div>'
        f'<div class="box {css}"><b>{text(STATUS_WORDS[s["status"]].capitalize())}.</b>'
        + (f'<ul class="small">{notes}</ul>' if notes else '')
        + '</div>'
    )
    cards = ''.join(_tank_card(t, volumes, blocked) for t in s['tanks']['tanks'])
    if not blocked:
        cards += _reagent_card(s, volumes) + _check_card(s)
    body = (
        head + f'<div class="cards">{cards}</div>' + (_agronomist_section(s) if depth >= 2 else '')
    )
    body += (
        '<p class="small">Planning calculation from FlahaX; not a dosing instruction. Confirm '
        'products and '
        'assays against your supplier certificates.</p>'
    )
    from .grower_report import result_reference

    return _page(s['title'] + ' - batch sheet', body + result_reference(s), CARD_STYLE)
