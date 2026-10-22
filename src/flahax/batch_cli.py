"""``flahax batch``: one formula and one water to a report, a batch sheet and a JSON summary (#79).

Water is ``ro`` (no ions) or a JSON file::

    {"id": "well-104", "measured_ph": 7.8,
     "mg_per_litre": {"Ca": 244, "Mg": 100.8, "K": 44.2, "Na": 680, "Cl": 1280.4,
                      "S": 241.4, "N_NO3": 3.47, "HCO3": 197}}

Elements are mg/L of the element (S as S, N_NO3 and N_NH4 as N); ``HCO3`` is
bicarbonate in mg/L as HCO3. Iron is taken as Fe(III), the form in aerated water.
The analysis is closed at its measured pH on chloride; one litre of water is
taken as one kilogram. Acids are never assumed: pass your certificate values with
``--acid``. The packaged bases (KOH 45%, KHCO3, K2CO3) are always evaluated.
"""
import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .delivery_contracts import DeliveryError
from .delivery_quantities import VolumeLitres
from .engine import load_library
from .fertilizer_workflow import plan_fertilizer_workflow
from .grower_report import render_batch_sheet, render_report, summarize_batch
from .measured_water import balance_water_analysis
from .ph_adjustment import catalogue_ph_reagents
from .planning_cli import serializable
from .product_conversion import MOLAR_MASS

# Water analysis key -> (basis, grams per mole of the reported quantity).
WATER_KEYS = {
    'Ca': ('Ca+2', MOLAR_MASS['Ca']), 'Mg': ('Mg+2', MOLAR_MASS['Mg']), 'K': ('K+', MOLAR_MASS['K']),
    'Na': ('Na+', MOLAR_MASS['Na']), 'Cl': ('Cl-', MOLAR_MASS['Cl']), 'S': ('SO4-2', MOLAR_MASS['S']),
    'P': ('PO4-3', MOLAR_MASS['P']), 'N_NO3': ('NO3-', MOLAR_MASS['N']), 'N_NH4': ('NH4+', MOLAR_MASS['N']),
    'Fe': ('Fe+3', MOLAR_MASS['Fe']), 'Mn': ('Mn+2', MOLAR_MASS['Mn']), 'Zn': ('Zn+2', MOLAR_MASS['Zn']),
    'Cu': ('Cu+2', MOLAR_MASS['Cu']), 'B': ('H3BO3', MOLAR_MASS['B']), 'Mo': ('MoO4-2', MOLAR_MASS['Mo']),
    'HCO3': ('CO3-2', 61.0168),
}


def read_water(spec):
    """(label, nutrient mg/L, equilibrium configuration) from ``ro`` or a JSON file."""
    if spec.lower() == 'ro':
        return 'RO water, no ions', {}, dict(water_totals={}, water_analysis_id='RO')
    data = json.loads(Path(spec).read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict) or not isinstance(data.get('mg_per_litre'), dict):
        raise DeliveryError('invalid_type', 'water JSON needs an "mg_per_litre" object')
    if 'measured_ph' not in data:
        raise DeliveryError('missing_field', 'water JSON needs "measured_ph" to close the analysis')
    unknown = set(data['mg_per_litre']) - set(WATER_KEYS)
    if unknown:
        raise DeliveryError('unknown_field', 'unsupported water keys: ' + ', '.join(sorted(unknown))
                            + '; use ' + ', '.join(WATER_KEYS))
    totals = {}
    for key, mg in data['mg_per_litre'].items():
        basis, grams = WATER_KEYS[key]
        totals[basis] = totals.get(basis, 0) + float(mg) / grams / 1000
    balanced = balance_water_analysis(totals, measured_ph=data['measured_ph'])
    # Nutrient mg/L from the closed analysis, so the formulation sees the chloride the chemistry uses.
    nutrients = {key: balanced.totals[basis] * grams * 1000 for key, (basis, grams) in WATER_KEYS.items()
                 if key != 'HCO3' and balanced.totals.get(basis)}
    label = (f"{data.get('id', Path(spec).stem)}: measured pH {data['measured_ph']}, analysis closed with "
             f"{balanced.balance_adjustment_molal * 1000:+.3f} mmol/kg chloride ({balanced.imbalance_percent:+.2f}% imbalance)")
    return label, nutrients, dict(water_totals=balanced.totals, water_analysis_id=str(data.get('id', Path(spec).stem)))


def acid_record(spec):
    """``FORMULA:MASS_FRACTION:DENSITY_KG_PER_L[:NAME]`` from your supplier certificate."""
    parts = spec.split(':')
    if len(parts) not in (3, 4):
        raise DeliveryError('invalid_value', f'--acid {spec}: expected FORMULA:MASS_FRACTION:DENSITY[:NAME]')
    formula, fraction, density = parts[0].strip(), float(parts[1]), float(parts[2])
    name = parts[3].strip() if len(parts) == 4 else f'{formula} {fraction:.0%}'
    return dict(id=f'{formula}-{fraction:g}-{density:g}', name=name, source='user certificate (flahax batch --acid)',
                revision='1', recordedAt='2026-01-01T00:00:00Z', chemicalFormula=formula, massFraction=fraction,
                densityKgPerL=density)


def choose_formula(library, formula, crop):
    names = [f['name'] for f in library['formulas']]
    if formula:
        if formula not in names:
            raise DeliveryError('unknown_formula', f'no formula named {formula!r}; see --list-formulas')
        return formula
    matches = [n for n in names if crop.lower() in n.lower()]
    if len(matches) != 1:
        raise DeliveryError('ambiguous_formula', f'--crop {crop!r} matches {len(matches)} formulas; choose one with '
                            '--formula:\n  ' + '\n  '.join(matches or names))
    return matches[0]


def build(args):
    library = load_library()
    products = json.loads(Path(args.products).read_text(encoding='utf-8-sig')) if args.products else library['salts']
    if args.targets:
        targets, title = json.loads(Path(args.targets).read_text(encoding='utf-8-sig')), Path(args.targets).stem
    else:
        title = choose_formula(library, args.formula, args.crop)
        targets = next(f['targets'] for f in library['formulas'] if f['name'] == title)
    label, water, chemistry = read_water(args.water)
    rules = json.loads(Path(args.rules).read_text(encoding='utf-8-sig')) if args.rules else ()
    reagents = [acid_record(a) for a in args.acid] + catalogue_ph_reagents()
    workflow = plan_fertilizer_workflow(
        products, targets, water, args.ph, final_volume=VolumeLitres(args.volume),
        equilibrium=dict(chemistry, water_mass_kg=args.volume, complete_analysis=True, carbon_boundary='closed',
                         temperature_c=25, phases=[]),
        ph_adjustment=dict(products=reagents, maximum_reagent_volume_litres=args.max_reagent_litres or args.volume / 200))
    summary = summarize_batch(workflow, products, title=title, water_label=label, injection_ratio=args.ratio,
                              rules=rules)
    return {'report.html': render_report(summary), 'batch-sheet.html': render_batch_sheet(summary),
            'summary.json': json.dumps(serializable(summary), indent=1, allow_nan=False) + '\n'}, summary


def main(argv=None):
    parser = argparse.ArgumentParser(prog='flahax batch', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    pick = parser.add_mutually_exclusive_group()
    pick.add_argument('--formula', help='exact name of a packaged formula')
    pick.add_argument('--crop', help='text that matches exactly one packaged formula name')
    pick.add_argument('--targets', help='JSON file of target mg/L (N_NO3 and N_NH4 as N)')
    parser.add_argument('--list-formulas', action='store_true', help='list the packaged formulas and exit')
    parser.add_argument('--water', help='"ro" or a water analysis JSON file (see above)')
    parser.add_argument('--volume', type=float, default=1000, help='final batch litres (default 1000)')
    parser.add_argument('--ph', type=float, default=5.8, help='target feed pH (default 5.8)')
    parser.add_argument('--ratio', type=float, default=100, help='final litres per litre of concentrate (default 100)')
    parser.add_argument('--acid', action='append', default=[], metavar='FORMULA:FRACTION:DENSITY[:NAME]',
                        help='an acid from your certificate, e.g. HNO3:0.60:1.37; repeat for more')
    parser.add_argument('--max-reagent-litres', type=float, help='largest reagent volume per batch (default volume/200)')
    parser.add_argument('--products', help='JSON array of your product records (default: the packaged catalogue)')
    parser.add_argument('--rules', help='JSON array of extra compatibilityRule records separating products')
    parser.add_argument('--output', help='new directory for report.html, batch-sheet.html and summary.json')
    args = parser.parse_args(argv)
    if args.list_formulas:
        print('\n'.join(f['name'] for f in load_library()['formulas']))
        return 0
    if not (args.formula or args.crop or args.targets) or not args.water or not args.output:
        parser.error('--formula, --crop or --targets, and --water and --output are required')
    output = Path(args.output)
    if output.exists():
        parser.error(f'{output} already exists; choose a new directory')
    try:
        files, summary = build(args)
    except (DeliveryError, ValueError, OSError) as exc:
        print(f'flahax batch: {exc}', file=sys.stderr)
        return 1
    output.mkdir(parents=True)
    for name, content in files.items():
        (output / name).write_bytes(content.encode('utf-8'))
    print(f'FlahaX {__version__}: {summary["title"]} - {summary["status"].replace("_", " ")}')
    for tank in summary['tanks']['tanks']:
        print(f'  Tank {tank["name"]}: ' + ', '.join(p['name'] for p in tank['products']))
    selected = summary['ph'] and summary['ph']['selected']
    if selected:
        print(f'  pH: {selected["volume_ml_per_batch"]:.0f} mL {selected["product"]} per {summary["batch_litres"]:g} L')
    print(f'Wrote {", ".join(files)} to {output}')
    return 3 if summary['status'] == 'blocked' else 0
