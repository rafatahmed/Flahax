#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tomato capability report and grower batch sheets (offline HTML, no dependencies).

Run from the repository root:
    python -m examples.tomato_report --output build/tomato-report

Creates tomato-report.html (charts and tables for both examples) and one printable
batch sheet per example. Every value comes from tomato_simple.run() and
tomato_advanced.run(); nothing is typed in by hand. Existing paths are never overwritten.
"""

import argparse
from pathlib import Path

import flahax

from . import tomato_advanced, tomato_simple
from .common import serializable
from .visual_report import bars, number, table, text
from flahax.saturation_policy import REVIEW

MICRO = ('Fe', 'Mn', 'Zn', 'B', 'Cu', 'Mo')

STYLE = """
:root{color-scheme:light;font-family:Segoe UI,Arial,sans-serif;color:#20353f;background:#eef3f5}
body{margin:0}main{max-width:1100px;margin:auto;padding:28px}
header{background:#103f49;color:white;padding:30px;border-radius:18px}h1{font-size:32px;margin:8px 0}
h2{font-size:24px;color:#103f49}h3{color:#103f49}.eyebrow{letter-spacing:2px;font-size:12px;text-transform:uppercase}
section{background:white;border-radius:18px;padding:26px;margin-top:22px;box-shadow:0 1px 3px #0001}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:18px}
.card{background:#f5f8f9;border-radius:14px;padding:16px}.card strong{display:block;font-size:24px;margin:6px 0}
.card span{font-size:13px}.warn{border-left:5px solid #e3a128;background:#fff8ea;padding:12px 16px;border-radius:8px}
.ok{border-left:5px solid #116c73;background:#eef7f7;padding:12px 16px;border-radius:8px}
table{width:100%;border-collapse:collapse;font-size:14px}caption{text-align:left;font-weight:600;padding:16px 0 8px}
th,td{border-bottom:1px solid #dbe4e8;padding:7px 9px;text-align:left}th{background:#f5f8f9}
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
.warn{border-color:#c47f0a;background:#fff8ea}table{width:100%;border-collapse:collapse}
th,td{border:1px solid #b9c7cd;padding:4px 6px;text-align:left}th{background:#eef3f5}
td.num,th.num{text-align:right}.tick{width:16px;height:16px;border:1.5px solid #1d2f37;display:inline-block}
.fill{border-bottom:1px solid #1d2f37;display:inline-block;min-width:34mm}.small{font-size:11px;color:#40555e}
@media print{main{padding:0}}
"""  # noqa: E501


def page(title, body, style=STYLE):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{text(title)}</title><style>{style}</style></head><body><main>{body}</main></body></html>\n'
    )


def card(label, value, note):
    return (
        f'<div '
        f'class="card"><span>{text(label)}</span><strong>{text(value)}</strong><span>{text(note)}</span></div>'
    )


def nutrient_charts(rows, title):
    target_rows = [r for r in rows if r['target']]
    macro = [r for r in target_rows if r['symbol'] not in MICRO]
    micro = [r for r in target_rows if r['symbol'] in MICRO]
    out = ''
    for group, label in ((macro, 'macronutrients'), (micro, 'micronutrients')):
        if group:
            out += bars(
                f'{title}: {label}, target and delivered',
                [r['symbol'] for r in group],
                [
                    ('Target', [r['target'] for r in group]),
                    ('Delivered', [r['final'] for r in group]),
                ],
                'mg/L',
            )
    return out


def simple_section(s):
    rows = [
        (r['name'], number(r['grams_per_litre'], 4), number(r['grams_in_batch'], 1), r['identity'])
        for r in s['recipe']
    ]
    fit = [
        (r['symbol'], number(r['target'], 3), number(r['final'], 3), f"{r['deltaPct']:+.2f}%")
        for r in s['nutrients']
    ]
    b, ec = s['ion_balance'], s['ec']
    ph_note = (
        '<p class="ok">Mixed pH is inside the 5.3-5.8 feed range.</p>'
        if 5.3 <= ec['ph'] <= 5.8
        else f'<p class="warn">Mixed pH {number(ec["ph"], 2)} is outside the 5.3-5.8 feed '
        f'range: an acid dose '
        'is needed. The advanced example plans it on real water.</p>'
    )
    return (
        f'<section id="simple"><h2>1. Simple: {text(s["formula"])} in RO water</h2>'
        '<p>One formula, water with no nutrients, one batch. FlahaX chooses the products, fits '
        'every '
        'target, scales the batch and estimates EC.</p>'
        '<div class="cards">'
        + card('Targets met', 'Yes' if s['feasible'] else 'No', 'every target within 1%')
        + card('Products', len(s['recipe']), f'for {s["batch_litres"]} L')
        + card('Ion balance', f"{b['imbalancePercent']:+.1f}%", 'cations vs anions of the formula')
        + card(
            'EC25 estimate',
            f"{number(ec['ec25_ms_cm'], 2)} mS/cm",
            f"at pH {number(ec['ph'], 2)}, experimental",
        )
        + '</div>'
        + ph_note
        + table(
            ['Product', 'g/L', f'g per {s["batch_litres"]} L', 'Chemical identity'], rows, 'Recipe'
        )
        + nutrient_charts([dict(r) for r in s['nutrients']], 'Simple recipe')
        + table(['Nutrient', 'Target mg/L', 'Delivered mg/L', 'Difference'], fit, 'Nutrient fit')
        + '</section>'
    )


def advanced_section(a):
    w = a['well']
    blend_rows = [
        (
            f"{b['well_percent']}%",
            number(b['Na'], 1),
            number(b['Cl'], 1),
            number(b['Cl_model'], 1),
            number(b['Ca'], 1),
            number(b['S'], 1),
            'Yes'
            if b['Na'] <= a['limits_mg_l']['Na'] and b['Cl'] <= a['limits_mg_l']['Cl']
            else 'No',
        )
        for b in a['blends']
    ]
    rec = a['recipe']
    recipe_rows = [
        (
            x['name'],
            number(x['gramsPerLitre'], 4),
            number(x['gramsPerLitre'] * tomato_advanced.BATCH_LITRES, 1),
            x['provenance']['identityId'],
        )
        for x in rec['salts']
    ]
    fit = [
        (
            r['symbol'],
            number(r['target'], 3) if r['target'] else 'not a target',
            number(r['final'], 3),
            f"{r['deltaPct']:+.2f}%" if r['deltaPct'] is not None else 'incidental',
        )
        for r in rec['rows']
    ]
    unmet = ''.join(
        f"<li><b>{text(u['symbol'])}</b> {u['deltaPct']:+.2f}% - {text(u['reason'])}"
        + (f" (with {text(', '.join(u['conflictsWith']))})" if u.get('conflictsWith') else '')
        + '</li>'
        for u in rec['unmet']
    )
    c, acid, pc = a['chemistry'], a['acid'], a['phosphoric_check']
    review = set(REVIEW)
    si_rows = [
        (
            p,
            number(si, 2),
            'undersaturated'
            if si <= 0
            else 'supersaturated, review (#78)'
            if p in review
            else 'supersaturated, blocks',
        )
        for p, si in c['saturation']
    ]
    acid_rows = [(x['product'], x['status'], x['message'] or '') for x in acid['candidates']]
    ec_rows = [
        (label, number(e['ec25_ms_cm'], 2), number(e['ph'], 2), e['status'])
        for label, e in a['ec'].items()
    ]
    tank_rows = [
        (
            f'Tank {name}',
            p['name'],
            p['analogue'],
            number(p['gramsPerLitre'] * a['injection_ratio'], 2),
            p['basis'],
        )
        for name, tank in a['tanks']['tanks'].items()
        for p in tank['products']
    ]
    sizing = a['sizing']
    size_rows = [
        (
            f'Tank {name}',
            number(ch['required_stock_litres'], 1),
            number(ch['required_flow_litres_per_hour'], 1),
        )
        for name, ch in sizing['channels'].items()
    ]
    stage_rows = [
        (
            s['stage'],
            'Yes' if s['feasible'] else 'No',
            f"{s['worst_miss_percent']:.1f}%",
            f"{s['ion_imbalance_percent']:+.1f}%",
            ', '.join(f'{sym} ({why})' for sym, why in s['unmet']) or '-',
        )
        for s in a['stages']
    ]
    return (
        '<section id="advanced"><h2>2. Advanced: a published brackish well, from analysis to '
        'batch</h2>'
        '<div class="cards">'
        + card(
            'Well analysis',
            f"{w['imbalance_percent']:+.2f}%",
            f"charge imbalance, closed at pH {w['measured_ph']}",
        )
        + card(
            'Blend',
            f"{a['blend_percent']}% well",
            'largest share within Na and Cl limits, laboratory values',
        )
        + card('Feed pH', number(c['mixed_ph'], 2), f"target {a['target_ph']}")
        + card(
            'EC25 estimate',
            f"{number(a['ec']['acidified']['ec25_ms_cm'], 2)} mS/cm",
            'after acid, experimental',
        )
        + '</div>'
        '<h3>Step 1. Balance the laboratory analysis</h3>'
        f'<p>The well (Shomar et al. 2024, station 104) is {number(w["imbalance_percent"], 2)}% '
        f'out of charge '
        f'balance at its measured pH {w["measured_ph"]}. For the chemistry FlahaX keeps the '
        f'measured pH and '
        f'closes the gap on chloride ({w["chloride_adjustment_percent"]:+.1f}%), instead of '
        f'turning it into a pH '
        'error. That balanced chloride is a modelling assumption, not a corrected measurement: '
        'every limit and '
        'target below uses the laboratory values.</p>'
        '<h3>Step 2. Choose the blend with desalinated water</h3>'
        f'<p>The blend is chosen on the laboratory analysis. {a["blend_percent"]}% is the '
        f'largest whole-percent '
        f'share within both limits; {a["blend_percent"] + 1}% exceeds the chloride limit on the '
        f'laboratory value '
        'even though the balanced model would pass it. The continuous chloride boundary is about '
        f'{number(a["chloride_boundary_percent"], 1)}% (ion-free dilution water assumed), not a '
        f'safety margin.</p>'
        + table(
            [
                'Well share',
                'Na',
                'Cl (laboratory)',
                'Cl (balanced model, not used)',
                'Ca',
                'S',
                'Within 3 mmol/L Na and Cl',
            ],
            blend_rows,
            'Water quality by blend (mg/L, laboratory basis)',
        )
        + bars(
            'Sodium and chloride by blend',
            [r[0] for r in blend_rows],
            [('Na', [b['Na'] for b in a['blends']]), ('Cl', [b['Cl'] for b in a['blends']])],
            'mg/L',
        )
        + '<h3>Step 3. Formulate on that water</h3>'
        f'<p class="warn">With the whole catalogue the fit takes P from phosphoric acid '
        f'({number(pc["phosphoric_g_per_litre"] * tomato_advanced.BATCH_LITRES, 0)} g per '
        f'batch) and the feed '
        f'mixes to pH {number(pc["mixed_ph"], 2)}, below the {a["target_ph"]} target. It is '
        f'withdrawn as a P source; '
        'potassium phosphate supplies P instead.</p>'
        + table(
            ['Product', 'g/L', f'g per {tomato_advanced.BATCH_LITRES} L', 'Chemical identity'],
            recipe_rows,
            'Recipe on the blend',
        )
        + nutrient_charts(rec['rows'], 'Advanced recipe')
        + table(
            ['Nutrient', 'Target mg/L', 'Delivered mg/L', 'Difference'],
            fit,
            'Nutrient fit, including what the water brings',
        )
        + (
            f'<p>Targets missed by more than 1%, with the reason FlahaX gives:</p><ul>{unmet}</ul>'
            if unmet
            else ''
        )
        + '<h3>Step 4. Chemistry of the mixed feed</h3>'
        f'<p>Blend water pH {number(c["water_ph"], 2)}; mixed feed pH '
        f'{number(c["mixed_ph"], 2)}; ionic strength '
        f'{number(c["ionic_strength"], 4)} mol/kg.</p>'
        + table(['Phase', 'Saturation index', 'Reading'], si_rows, 'Saturation indices above -1')
        + '<h3>Step 5. Acid to the target pH</h3>'
        + table(['Acid', 'Status', 'Reason'], acid_rows, 'Acid plans evaluated by FlahaX')
        + f'<p class="warn">Nitric demand: about <b>{number(acid["nitric_ml_per_batch"], 0)} '
        f'mL</b> of '
        f'{text(acid["nitric_grade"])} per {tomato_advanced.BATCH_LITRES} L to reach pH '
        f'{a["target_ph"]}, adding '
        f'{number(acid["added_nitrate_n_mg_l"], 1)} mg/L nitrate-N (nitrate-N '
        f'{number(acid["nitrate_before_mg_l"], 1)} '
        f'&rarr; {number(acid["nitrate_after_mg_l"], 1)}, target '
        f'{number(acid["nitrate_target_mg_l"], 1)}). FlahaX asks '
        'for review before accepting it, because these phases are supersaturated: '
        + text(', '.join(f'{p} {si:.2f}' for p, si in acid['supersaturated_after_acid']) or 'none')
        + '. They are review-class phases (cited reasons in flahax.saturation_policy), not a '
        'predicted '
        'precipitate: add the acid in steps and measure.</p>'
        + table(
            ['State', 'EC25 mS/cm', 'pH', 'Status'],
            ec_rows,
            'Estimated EC (experimental, McCleskey 2012 conductivities)',
        )
        + '<h3>Step 6. Concentrate tanks and injection</h3>'
        + table(
            [
                'Tank',
                'Product',
                'Page 65 analogue',
                f'Stock g/L at 1:{a["injection_ratio"]}',
                'Why here',
            ],
            tank_rows,
            'Tanks from the packaged default compatibility table (solubility not verified)',
        )
        + ''.join(
            f'<p class="small">Tank {text(name)}: {text(note)}</p>'
            for name, tank in a['tanks']['tanks'].items()
            for note in tank['notes']
        )
        + f'<p class="small">Source: {text(a["tanks"]["source"])}.</p>'
        + table(
            ['Channel', 'Stock needed (L)', 'Injection flow (L/h)'],
            size_rows,
            f"Injection for {number(sizing['final_volume_litres'], 0)} L in "
            f"{number(sizing['duration_hours'], 1)} h "
            f"(illustrative {a['site']['active_area_m2']} m2, {a['site']['gross_depth_mm']} mm)",
        )
        + '<h3>Step 7. Growth stages, each as its own batch</h3>'
        + table(
            [
                'Stage formula',
                'Targets met',
                'Worst miss',
                'Formula ion balance',
                'Missed targets',
            ],
            stage_rows,
            'Howard Resh stage formulas on the same water',
        )
        + '</section>'
    )


def render_report(simple, advanced):
    sources = ''.join(
        f'<li>{text(line)}</li>' for line in advanced['assumptions'] + simple['assumptions']
    )
    return page(
        'FlahaX tomato report',
        (
            '<header><div class="eyebrow">FlahaX '
            + text(flahax.__version__)
            + ' &middot; capability report</div>'
            '<h1>Tomato nutrient solutions, simple and advanced</h1>'
            '<p>Every number below is computed by FlahaX from the stated inputs. This is a '
            'planning calculation, '
            'not a dosing instruction: measure EC and pH after mixing.</p></header>'
            + simple_section(simple)
            + advanced_section(advanced)
            + f'<section><h2>Sources and assumptions</h2><ul>{sources}</ul></section>'
        ),
    )


def render_sheet(title, water, products, tanks, acid_note, checks, ratio=100, batch=1000):
    by_tank = {p['name']: name for name, tank in tanks['tanks'].items() for p in tank['products']}
    rows = ''.join(
        f'<tr><td>{text(by_tank[p["name"]])}</td><td>{text(p["name"])}</td>'
        f'<td class="num">{number(p["gramsPerLitre"] * batch, 1)}</td>'
        f'<td class="num">{number(p["gramsPerLitre"] * ratio, 2)}</td><td><span '
        f'class="tick"></span></td></tr>'
        for p in sorted(products, key=lambda p: (by_tank[p['name']], -p['gramsPerLitre']))
    )
    check_rows = ''.join(
        f'<tr><td>{text(k)}</td><td>{text(v)}</td><td><span class="fill"></span></td></tr>'
        for k, v in checks
    )
    body = (
        f'<h1>{text(title)}</h1><div class="meta">Batch sheet &middot; FlahaX '
        f'{text(flahax.__version__)} &middot; '
        f'{batch} L final solution</div>'
        f'<div class="box"><b>Water:</b> {text(water)}</div>'
        '<h2>Weigh and dissolve</h2><table><thead><tr><th>Tank</th><th>Product</th>'
        f'<th class="num">g per {batch} L batch</th><th class="num">Concentrate g/L at '
        f'1:{ratio}</th><th>Done</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>'
        f'<p class="small">Direct batch: dissolve everything in {batch} L. Concentrates: keep '
        f'tanks apart as listed '
        f'({text(tanks["source"])}). Micronutrients and chelates are in tank A with calcium: '
        f'never acidify '
        'tank A. Stock solubility is not verified: check each concentrate.</p>'
        f'<h2>pH</h2><div class="box warn">{acid_note}</div>'
        '<h2>Measure after '
        'mixing</h2><table><thead><tr><th>Check</th><th>Planned</th><th>Measured</th></tr></thead>'
        f'<tbody>{check_rows}</tbody></table>'
        '<p class="small">Operator <span class="fill"></span> &nbsp; Date <span '
        'class="fill"></span> &nbsp; '
        'Signature <span class="fill"></span></p>'
        '<p class="small">Planning calculation from FlahaX; not a dosing instruction. EC is an '
        'experimental '
        'estimate. Confirm products, assays and acid grade against your supplier certificates.</p>'
    )
    return page(title, body, SHEET_STYLE)


def sheets(simple, advanced):
    simple_salts = [
        dict(id=r['id'], name=r['name'], gramsPerLitre=r['grams_per_litre'])
        for r in simple['recipe']
    ]
    ec = simple['ec']
    simple_sheet = render_sheet(
        f"{simple['formula']} - RO water",
        'RO water, no nutrients',
        simple_salts,
        tomato_advanced.tank_table(simple_salts, flahax.load_library()['salts']),
        f'Mixed pH is estimated at {number(ec["ph"], 2)}, outside the 5.3-5.8 feed range. Acid '
        f'is needed but '
        'not calculated in the simple example; plan it on your water (see the advanced sheet).',
        [
            ('EC25 (mS/cm)', f'about {number(ec["ec25_ms_cm"], 2)} (experimental)'),
            ('pH', '5.3-5.8 after acid'),
        ],
    )
    a, acid = advanced, advanced['acid']
    advanced_sheet = render_sheet(
        'Tomato (De Kreij open system) - well blend',
        f"{a['blend_percent']} L well water (Shomar et al. 2024, station 104) + "
        f"{100 - a['blend_percent']} L desalinated "
        f"water per 100 L. Na {number(a['blends'][-1]['Na'], 1)} and Cl "
        f"{number(a['blends'][-1]['Cl'], 1)} mg/L, "
        'within 3 mmol/L.',
        a['recipe']['salts'],
        a['tanks'],
        f'Add about <b>{number(acid["nitric_ml_per_batch"], 0)} mL</b> of '
        f'{text(acid["nitric_grade"])} per 1000 L to go '
        f'from pH {number(a["chemistry"]["mixed_ph"], 2)} to {a["target_ph"]}. Add in steps and '
        f'measure: FlahaX asks for '
        'review first ('
        + text(', '.join(p for p, _ in acid['supersaturated_after_acid']))
        + ' supersaturated, '
        'review-class). The example acid grade must be replaced by your certificate values.',
        [
            (
                'EC25 (mS/cm)',
                f"about {number(a['ec']['acidified']['ec25_ms_cm'], 2)} (experimental)",
            ),
            ('pH', str(a['target_ph'])),
            ('Nitrate-N (mg/L)', f"{number(acid['nitrate_after_mg_l'], 1)} with the acid"),
        ],
        ratio=a['injection_ratio'],
        batch=tomato_advanced.BATCH_LITRES,
    )
    return simple_sheet, advanced_sheet


def build():
    simple = serializable(tomato_simple.run())
    advanced = serializable(tomato_advanced.run())
    simple_sheet, advanced_sheet = sheets(simple, advanced)
    return {
        'tomato-report.html': render_report(simple, advanced),
        'batch-sheet-simple.html': simple_sheet,
        'batch-sheet-advanced.html': advanced_sheet,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='new directory; existing paths are never overwritten',
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; choose a new directory')
    files = build()
    args.output.mkdir(parents=True)
    for name, html in files.items():
        (args.output / name).write_bytes(html.encode('utf-8'))
    print(f"Created {', '.join(files)} in {args.output}")


if __name__ == '__main__':
    main()
