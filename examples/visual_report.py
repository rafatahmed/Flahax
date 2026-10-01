"""Portable, offline HTML report with inline SVG charts and accessible tables.

No JS, external fonts, plotting package or network connection is required.
Graphs use the same serialized results as report.json, never invented values.
"""
from html import escape
import math


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
    return ('<div class="table-scroll"><table><caption>'+text(caption)+'</caption><thead><tr>'
            + ''.join('<th scope="col">'+text(h)+'</th>' for h in headers)
            + '</tr></thead><tbody>'
            + ''.join('<tr>'+''.join('<td>'+text(cell)+'</td>' for cell in row)+'</tr>' for row in rows)
            + '</tbody></table></div>')


def bars(title, labels, series, unit):
    """Zero-based grouped bars with direct value labels and a visible axis."""
    colors = ['#116c73', '#879bb0', '#e3a128']
    values = [v for _, samples in series for v in samples if isinstance(v, (int, float)) and math.isfinite(v)]
    maximum = max(values, default=0)
    maximum = maximum*1.15 if maximum > 0 else 1
    group = max(56, len(series)*21+12)
    height = 94 + group*len(labels)
    left, width = 265, 545
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 {height}" role="img" aria-label="{text(title)}">',
           '<title>'+text(title)+'</title>',
           '<desc>Zero-based horizontal bars. Exact values and units also appear in the accompanying table. Missing values are not plotted.</desc>']
    for i in range(5):
        x = left + width*i/4
        svg.append(f'<path d="M{x} 38 V{height-38}" stroke="#dbe4e8"/>')
        svg.append(f'<text x="{x}" y="{height-16}" text-anchor="middle">{number(maximum*i/4, 2)}</text>')
    for index, (name, _) in enumerate(series):
        x = left + index*170
        svg.append(f'<rect x="{x}" y="9" width="11" height="11" fill="{colors[index % 3]}"/>')
        svg.append(f'<text x="{x+17}" y="19">{text(name)}</text>')
    for row, label in enumerate(labels):
        y = 45 + group*row
        # Long product labels wrap into separate SVG text elements.
        words, lines, line = str(label).split(), [], ''
        for word in words:
            if len(line+' '+word) > 31 and line:
                lines.append(line)
                line = word
            else:
                line = (line+' '+word).strip()
        lines.append(line)
        for j, line in enumerate(lines):
            svg.append(f'<text x="12" y="{y+14+j*17}">{text(line)}</text>')
        for j, (_, samples) in enumerate(series):
            value = samples[row]
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                continue
            size = width*value/maximum
            by = y+j*21
            svg.append(f'<rect x="{left}" y="{by}" width="{size}" height="14" rx="3" fill="{colors[j % 3]}"/>')
            svg.append(f'<text x="{left+size+7}" y="{by+12}">{number(value, 3)}</text>')
    svg.append('</svg>')
    return '<figure><figcaption>'+text(title)+' <small>('+text(unit)+')</small></figcaption>'+''.join(svg)+'</figure>'


def render_html(report):
    s = report['scenarios']
    pepper = s['pepper']['workflow']
    recipe = pepper['recommendation']
    rows = recipe['rows']
    parts = ['''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FlahaX | Formulation and delivery report</title>
<style>
:root{color-scheme:light;font-family:Segoe UI,Arial,sans-serif;color:#20353f;background:#eef3f5}
*{box-sizing:border-box}body{margin:0}main{max-width:1200px;margin:auto;padding:32px}
header{background:#103f49;color:white;padding:34px;border-radius:18px}h1{font-size:34px;margin:8px 0}
h2{font-size:24px;color:#103f49}h3{margin-top:0}.eyebrow{letter-spacing:2px;font-size:12px;text-transform:uppercase}
section{background:white;border:1px solid #dce5e9;border-radius:14px;padding:26px;margin-top:24px}
p{line-height:1.6}.notice{padding:16px 20px;border-left:5px solid #d99a25;background:#fff5dd;line-height:1.55;margin:20px 0}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin:20px 0}.card{padding:20px;background:#eaf4f3;border-radius:10px}
.card strong{display:block;font-size:27px;margin:8px 0}.card span{font-size:13px}
nav{display:flex;flex-wrap:wrap;gap:16px;margin:22px 0}a{color:#08747c}header a{color:white}
table{width:100%;border-collapse:collapse;font-size:14px}caption{text-align:left;font-weight:600;padding:18px 0 10px}
th{background:#eaf0f3;text-align:left}th,td{padding:11px;border-bottom:1px solid #e0e8ec;vertical-align:top}
tbody tr:nth-child(even){background:#f7fafb}.table-scroll{overflow-x:auto}figure{margin:22px 0;padding:18px;background:#f8fbfc;border-radius:10px}
figcaption{font-weight:600;margin-bottom:10px}small{font-weight:400;color:#526c77}figure{overflow-x:auto}svg{display:block;width:100%;min-width:800px;height:auto}svg text{font:16px Segoe UI,Arial,sans-serif;fill:#20353f}
.tag{font-size:12px;font-weight:bold;letter-spacing:1px;color:#8a5304}details{margin-top:18px}summary{cursor:pointer;font-weight:600}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef3f5;padding:16px}.muted{color:#526c77}
@media(max-width:650px){main{padding:12px}section,header{padding:18px}.cards{grid-template-columns:1fr}h1{font-size:27px}figure{padding:4px}}
@media print{body{background:white}main{max-width:none;padding:0}section{break-inside:avoid;border-radius:0}nav{display:none}details{display:none}header{background:white;color:#103f49;border-bottom:3px solid #103f49}figure{break-inside:avoid}}
</style></head><body><main>
<header><div class="eyebrow">FlahaX / capability report / unreleased development</div>
<h1>From crop targets to delivery planning</h1>
<p>Readable results, visible limits and traceable evidence. Pepper formulation and synthetic demonstrations are kept separate.</p></header>
<nav><a href="#nutrients">Nutrients</a><a href="#doses">Fertilizers</a><a href="#tank-allocation">Tank A / B / acid</a><a href="#chemistry">Chemistry</a><a href="#acids">Acids</a><a href="#ec">EC &amp; injection</a><a href="#readiness">Readiness</a></nav>''',
        '<div class="notice">'+text(report['notice'])+' No dosing approval is implied.</div>',
        '<div class="cards"><div class="card">Crop calcium target<strong>'+number(s['pepper']['targets_mg_per_l'].get('Ca'))+' mg/L</strong><span>User-supplied pepper target</span></div>'
        '<div class="card">Source-water calcium<strong>'+number(pepper['water'].get('Ca',0))+' mg/L</strong><span>Not an alkalinity measurement</span></div>'
        '<div class="card">Fertilizer calcium gap<strong>'+number(pepper['nutrient_gap']['Ca'])+' mg/L</strong><span>Crop target minus water contribution</span></div></div>',
        '<section id="nutrients"><h2>01 / Pepper nutrient balance</h2>'
        '<p>Water is included in the calculated final concentration. Macro and trace nutrients have separate scales so small targets remain visible.</p>']
    for title, ions in [('Macronutrients', ('N_NO3', 'N_NH4', 'P', 'K', 'Ca', 'Mg', 'S')),
                        ('Trace nutrients', ('Fe', 'Mn', 'Zn', 'B', 'Cu', 'Mo'))]:
        selected = [r for r in rows if r['symbol'] in ions]
        parts.append(bars(title, [r['symbol'] for r in selected], [
            ('Target', [r['target'] for r in selected]),
            ('Water', [pepper['water'].get(r['symbol'], 0) for r in selected]),
            ('Final', [r['final'] for r in selected])], 'mg/L'))
    parts.append(table(['Nutrient','Target mg/L','Water mg/L','Final mg/L','Deviation %','Assessment'], [
        [r['symbol'], number(r['target']), number(pepper['water'].get(r['symbol'], 0)), number(r['final'],6),
         'Not defined' if r['deltaPct'] is None else number(r['deltaPct']),
         'Incidental — review separately' if r['target'] in (0,None) and r['final'] > 1e-12 else
         ('Within 1% target' if abs(r['deltaPct']) <= 1 else 'Outside 1% target') if r['target'] else 'No addition']
        for r in rows], 'Full nutrient balance; nitrogen forms are expressed as N'))
    parts.append('<div class="notice">A zero NH4 or Na target is not an automatic prohibition. Incidental additions need separate assessment; no safe threshold is inferred.</div></section>')
    salts = recipe['salts']
    batch_l = pepper['stages']['batch']['value']['final_volume']['value']
    parts.append('<section id="doses"><h2>02 / Fertilizer quantities</h2><p>Illustrative '+number(batch_l)+' L final batch. Confirm commercial assays before physical use, particularly the catalogue’s Phosphoric Acid (75%) entry.</p>')
    parts.append(bars('Product mass for the final batch', [p['name'] for p in salts],
                      [('Mass', [p['gramsPerLitre']*batch_l for p in salts])], 'g'))
    parts.append(table(['Product','g/L','Batch mass g'], [[p['name'],number(p['gramsPerLitre'],6),number(p['gramsPerLitre']*batch_l,6)] for p in salts], 'Catalogue-based fertilizer recipe'))
    allocation = s['pepper']['stock_allocation_review']
    parts.append('</section><section id="tank-allocation"><span class="tag">YOUR PEPPER RECIPE - ALLOCATION REVIEW, NOT MIXING APPROVAL</span><h2>What goes in Tank A, Tank B and the acid channel?</h2><p>Source: Yara 04_Fertilizer.pdf, pages 63, 65 and 66. The macro separation is clear, but the source does not approve every trace product or stock concentration. A/B are labels for separate concentrates, not ingredients to premix together.</p>')
    parts.append('<div class="notice"><strong>Not ready for mixing.</strong> The groups below are proposed destinations, not a calculated StockPlan. Unassigned products have not been omitted from the nutrient recipe. Their stock location remains unresolved.</div>')
    for channel, title in [('A','Tank A - calcium / nitrate / chelate candidates'),
                           ('B','Tank B - phosphate / sulfate candidates'),
                           ('Acid','Dedicated acid channel - proposed design'),
                           ('Unassigned','Unassigned - additional compatibility evidence needed')]:
        members = [r for r in allocation['rows'] if r['proposed_channel'] == channel]
        parts.append('<h3>'+text(title)+'</h3>')
        parts.append(table(['Product','Recipe mass g / '+number(batch_l)+' L final','Basis / remaining check'],
            [[r['product'], number(r['recipe_mass_g'],6), r['reason']] for r in members],
            'Candidate only; no stock volume or stock g/L approved' if channel != 'Unassigned' else 'Do not automatically place these products in B'))
    parts.append('<div class="notice"><strong>Acid accounting:</strong> '+text(allocation['acid_accounting'])+'</div>')
    parts.append('<p>'+text(allocation['acid_policy'])+' Do not acidify the chelate-containing A tank. A two-tank-only system is not yet demonstrated for all twelve products.</p>')
    parts.append(table(['Still required before preparing stocks'], [[m] for m in allocation['missing']], 'Missing design and compatibility inputs'))
    parts.append('</section><section id="chemistry"><span class="tag">SEPARATE SYNTHETIC DEMONSTRATION</span><h2>03 / Mixed chemistry and phases</h2><p>This is not the pepper solution. SI above zero indicates supersaturation; allocated solids are a separate result. Molal values are per kg of water.</p>')
    chemical = s['chemistry']['mixed']
    parts.append(table(['pH imposed','Ionic strength mol/kg','Charge residual mol-charge/kg','Iterations'],
        [[number(chemical['ph']), number(chemical['ionic_strength'],6),number(chemical['charge_balance'],6),chemical['iterations']]], 'Aqueous-only mixed demonstration; imposed pH is not a calculated neutral-charge condition'))
    si = sorted([(k,v) for k,v in chemical['saturation_indices'].items() if isinstance(v,(int,float)) and math.isfinite(v)], key=lambda p:p[1], reverse=True)
    parts.append(table(['Phase','Saturation index','Interpretation'], [[k,number(v), 'Supersaturated' if v>1e-7 else 'Undersaturated' if v < -1e-7 else 'Near equilibrium'] for k,v in si], 'All finite saturation indices (highest first); unavailable/absent-component indices remain in JSON'))
    species = sorted(chemical['species'].items(), key=lambda p:p[1], reverse=True)
    parts.append('<details><summary>All aqueous species and complexes</summary>'+table(['Species','Mol/kg-water'], [[k,number(v,8)] for k,v in species], 'Model species concentrations')+'</details>')
    precip = s['chemistry']['precipitation']['precipitated']
    parts.append(table(['Phase','Allocated mol/kg-water'], [[k,number(v,8)] for k,v in precip.items() if v>0], 'Separate calcium/phosphate precipitation demonstration'))
    parts.append('</section><section id="acids"><span class="tag">SEPARATE SYNTHETIC DEMONSTRATION</span><h2>04 / pH and acid options</h2>')
    stages = s['delivery']['workflow']['stages']
    parts.append(table(['Calculated initial pH','Target pH','Commercial HNO3 volume mL'], [[number(stages['chemistry']['value']['mixed']['ph']),6.5,number(stages['nitric']['value']['reagent_volume_litres']*1000,6)]], 'Synthetic pure-water/KNO3 case, not a pepper acid recommendation'))
    candidates = stages['acid_selection']['value']['candidates']
    parts.append(table(['Candidate','Status','Dose mol/kg','Product mass g','Product volume mL'], [[p['formula'],p['status'],number(p['dose_molal'],8),number(p['reagent_mass_g'],6),number(p['reagent_volume_litres']*1000,6) if p['reagent_volume_litres'] is not None else 'Not available'] for p in candidates], 'Candidate assays differ from the separate HNO3 delivery record; do not compare volumes without their assays'))
    parts.append('</section><section id="ec"><span class="tag">FICTIONAL CALIBRATION DATA — NOT FIELD PREDICTIONS</span><h2>05 / EC, tanks and injection</h2><p>These values demonstrate the calibrated EC algorithm. Stock A/B and combined irrigation EC are independently estimated—not added or multiplied by the injection ratio.</p>')
    ec = s['ec_injection']['ec_and_injection']
    demo_stocks = s['ec_injection']['stock_plan']
    parts.append(table(['Demo tank','Product actually assigned','Stock g/L','Prepared stock L','Product mass g'],
        [[tank['tank']['tank_id'], salt['name'], number(salt['concentration']['value']),
          number(tank['stock_volume']['value']), number(salt['concentration']['value']*tank['stock_volume']['value'])]
         for tank in demo_stocks['tanks'] for salt in tank['salts']],
        'Actual assignment in this two-product SYNTHETIC example only - NOT the pepper tank plan'))
    parts.append('<p><strong>Acid location in this EC demonstration: none.</strong> No acid dose is included. The separate pH example uses its own acid channel; it must not be read as part of these A/B tanks.</p>')
    predictions = list(ec['predictions'].items())
    parts.append(bars('EC25 comparison — synthetic example', ['Water']+[k for k,p in predictions],
                      [('EC25', [ec['water_ec_ms_cm']]+[p['ec_ms_cm'] for k,p in predictions])], 'mS/cm at 25 °C'))
    parts.append(table(['Location','EC25 mS/cm','Status','Validated error bound mS/cm'], [[k,number(p['ec_ms_cm']),p['status'],number(p['uncertainty_ms_cm'])] for k,p in predictions], 'No supplied error bound means unknown uncertainty, not zero'))
    commands = {p['channel_id']:p for p in ec['pump_commands']}
    parts.append(table(['Tank','Final L / stock L','Inject L','mL/L final','Pump minutes','Volume uncertainty L'], [
        [k,number(p['final_litres_per_stock_litre']),number(p['volume_litres']),number(p['ml_per_litre_final']),
         number(commands[k]['runtime']['value']) if k in commands else 'Not planned',
         number(commands[k]['volume_uncertainty']['value'],6) if k in commands else 'Not planned'] for k,p in ec['injections'].items()], '100 L synthetic final batch: 1 L from each tank; 100× is per tank'))
    parts.append('<div class="notice">Missing measured EC profiles produce “needs_input”, not zero EC. Pump values preserve the recipe; they do not authorize automatic EC correction or device operation.</div></section>')
    if 'calculated_site' in s:
        site = s['calculated_site']
        parts.append('<section><span class="tag">NO NEW MEASUREMENTS - SCREENING ONLY</span><h2>Calculated EC and equipment requirements</h2><p>Separate SQM brochure-based example, not the pepper recipe. Linear/additive pre-acid estimate with unknown accuracy. No measured calibration profile is needed for this screening calculation.</p>')
        parts.append(bars('Manufacturer-anchor EC25 screening', ['Water', 'Irrigation', 'Stock A', 'Stock B'],
            [('EC25', [site['irrigation']['water_ec_ms_cm'], site['irrigation']['ec_ms_cm'],
                       site['stock_a']['ec_ms_cm'], site['stock_b']['ec_ms_cm']])], 'mS/cm'))
        parts.append(table(['Location', 'EC25 mS/cm', 'Status', 'Boundary'],
            [[name, number(site[key]['ec_ms_cm']), site[key]['status'], site[key].get('error_code', 'Unknown numerical accuracy')]
             for name, key in [('Irrigation','irrigation'),('Stock A','stock_a'),('Stock B','stock_b')]],
            'Missing stock EC is not zero; dilute anchors do not define concentrated behavior'))
        sizing = site['sizing']
        parts.append(table(['Channel', 'Required stock L', 'Required flow L/h', 'Stock / final %'],
            [[name, number(row['required_stock_litres']), number(row['required_flow_litres_per_hour']),
              number(row['stock_percent_of_final'])] for name, row in sizing['channels'].items()],
            '10,000 L final irrigation over 2 hours; equipment model awaits manufacturer operating-point checks'))
        parts.append('</section>')
    parts.append('<section id="readiness"><h2>06 / What is ready for the pepper recipe?</h2>')
    parts.append(table(['Stage','Status','Missing inputs / message'], [[k,p['status'],', '.join(p['required_inputs']) or p['message'] or 'See assumptions and evidence'] for k,p in pepper['stages'].items()], 'Actual pepper workflow status — independent of the synthetic demonstrations'))
    parts.append('<p><a href="report.json">Complete machine-readable inputs and outputs</a> · <a href="report.md">Markdown report</a></p><details><summary>Assumptions by scenario</summary>')
    for name, scenario in s.items():
        parts.append('<h3>'+text(name)+'</h3><ul>'+''.join('<li>'+text(a)+'</li>' for a in scenario['assumptions'])+'</ul>')
    parts.append('</details></section><p class="muted">Generated from FlahaX example results. No external resources, tracking or JavaScript. Print from your browser for a paper/PDF copy.</p></main></body></html>')
    return ''.join(parts)
