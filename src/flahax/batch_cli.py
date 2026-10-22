"""``flahax batch``: one formula and one water to a report, a batch sheet and a JSON summary (#79).

Water is ``ro`` (no ions) or a JSON file::

    {"id": "well-104", "measured_ph": 7.8,
     "mg_per_litre": {"Ca": 244, "Mg": 100.8, "K": 44.2, "Na": 680, "Cl": 1280.4,
                      "S": 241.4, "N_NO3": 3.47, "HCO3": 197}}

Elements are mg/L of the element (S as S, N_NO3 and N_NH4 as N); ``HCO3`` is
bicarbonate in mg/L as HCO3. Iron is taken as Fe(III), the form in aerated water.
One litre of water is taken as one kilogram.

A value of 0 is a measured zero and stays zero (``"Cl": 0`` for chloride-free
water, ``"HCO3": 0`` for carbon-free water); an omitted ion is not measured, and
measured-pH chemistry needs ``HCO3`` (0 if none). Optional keys:
``"below_detection": {"Mn": 0.01}`` (detection limits, mg/L; taken as zero, never
adjusted), ``"balance_ion": "Cl"`` or ``"Na"`` and
``"balance_ion_uncertainty_percent": 10`` (the stated uncertainty of that ion).

Nutrient targets and concentration limits use the analysis exactly as entered.
For the chemistry only (pH, saturation, EC, reagent dose) the analysis is
speciated at its measured pH: used unchanged if it already balances, otherwise
closed on the balance ion, within its stated uncertainty, or as an assumption
flagged for review. The report shows both and never lets that balancing pass or
fail a limit (#84).

Limits are never assumed: declare each maximum with ``--limit Cl=106.35`` (mg/L in
the final solution); unspecified limits are not checked. Acids are never assumed
either: pass your certificate values with ``--acid``. The packaged bases (KOH 45%,
KHCO3, K2CO3) are always evaluated.
"""
import argparse
from dataclasses import asdict, dataclass, field
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
from .stock_volumes import prepare_stocks

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
    below = data.get('below_detection') or {}
    if not isinstance(below, dict) or set(below) - set(WATER_KEYS):
        raise DeliveryError('unknown_field', '"below_detection" maps water keys to detection limits in mg/L')
    totals = {}
    for key, mg in data['mg_per_litre'].items():
        basis, grams = WATER_KEYS[key]
        totals[basis] = totals.get(basis, 0) + float(mg) / grams / 1000
    # Nutrients straight from the laboratory analysis; the workflow balances it for chemistry only.
    nutrients = {key: float(mg) for key, mg in data['mg_per_litre'].items() if key != 'HCO3'}
    analysis_id = str(data.get('id', Path(spec).stem))
    label = f'{analysis_id}: laboratory analysis, measured pH {data["measured_ph"]}'
    config = dict(water_totals=totals, measured_ph=data['measured_ph'], water_analysis_id=analysis_id,
                  below_detection={WATER_KEYS[k][0]: float(v) / WATER_KEYS[k][1] / 1000 for k, v in below.items()})
    if 'balance_ion' in data:
        ions = {'Cl': 'Cl-', 'Na': 'Na+'}
        if data['balance_ion'] not in ions:
            raise DeliveryError('unsupported_balance_ion', '"balance_ion" must be "Cl" or "Na"')
        config['balance_ion'] = ions[data['balance_ion']]
    if 'balance_ion_uncertainty_percent' in data:
        config['balance_ion_uncertainty_percent'] = float(data['balance_ion_uncertainty_percent'])
    return label, nutrients, config


def blend(label, water, chemistry, percent):
    """The analysed water as ``percent`` of the batch water, the rest ion-free (desalinated or RO).

    Nutrients and limits scale the laboratory analysis; the chemistry dilutes its
    measured-pH record (#84). If the analysis cannot be closed, the chemistry is
    left out with the reason, and nutrient accounting goes on.
    """
    if chemistry.get('measured_ph') is None:
        raise DeliveryError('invalid_value', '--water-share needs a measured water analysis file, not ro')
    if not 0 < percent <= 100:
        raise DeliveryError('invalid_value', '--water-share must be a percentage in (0, 100]')
    fraction = percent / 100
    options = {key: chemistry[key] for key in ('balance_ion', 'balance_ion_uncertainty_percent', 'below_detection')
               if key in chemistry}
    label = f'{percent:g}% {label}, {100 - percent:g}% ion-free water'
    water = {key: value * fraction for key, value in water.items()}
    try:
        balanced = balance_water_analysis(chemistry['water_totals'], measured_ph=chemistry['measured_ph'],
                                          analysis_id=chemistry['water_analysis_id'], **options)
    except DeliveryError as exc:
        return f'{label}. Chemistry not calculated: {exc}', water, None
    return label, water, dict(water_balance=balanced.diluted(fraction),
                              water_analysis_id=f'{chemistry["water_analysis_id"]}-{percent:g}pct')


def limit_entry(spec):
    """``SYMBOL=MG_PER_L``: a maximum concentration in the final solution."""
    symbol, _, value = spec.partition('=')
    if not symbol.strip() or not value.strip():
        raise argparse.ArgumentTypeError(f'--limit {spec}: expected SYMBOL=MG_PER_L, for example Cl=106.35')
    try:
        return symbol.strip(), float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f'--limit {spec}: {value!r} is not a number') from None


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


@dataclass
class BatchOptions:
    """The ``flahax batch`` flags, plus the interactive mix's tanks, fill mode, temperature and depth.

    With ``tank_litres`` (keys A, B and acid) the batch volume is the irrigation the
    stocks supply (``stock_volumes.prepare_stocks``) and ``volume`` is not used.
    """
    water: str
    formula: str | None = None
    crop: str | None = None
    targets: str | None = None
    water_share: float | None = None
    volume: float = 1000
    ph: float = 5.8
    ratio: float = 100
    acid: list = field(default_factory=list)
    limit: list = field(default_factory=list)
    max_reagent_litres: float | None = None
    products: str | None = None
    rules: str | None = None
    tank_litres: dict | None = None
    mode: str = 'fill'
    irrigation_litres: float | None = None
    temperature_c: float = 25
    depth: int = 3


def run_batch(options):
    """The batch summary (``summarize_batch``); with tanks, ``summary['volumes']`` gives the stock volumes."""
    volumes = None
    if options.tank_litres is not None:
        volumes = prepare_stocks(tank_litres=options.tank_litres, ratio=options.ratio, mode=options.mode,
                                 irrigation_litres=options.irrigation_litres)
    volume = options.volume if volumes is None else volumes.irrigation_litres
    library = load_library()
    products = (json.loads(Path(options.products).read_text(encoding='utf-8-sig')) if options.products
                else library['salts'])
    if options.targets:
        targets, title = json.loads(Path(options.targets).read_text(encoding='utf-8-sig')), Path(options.targets).stem
    else:
        title = choose_formula(library, options.formula, options.crop)
        targets = next(f['targets'] for f in library['formulas'] if f['name'] == title)
    label, water, chemistry = read_water(options.water)
    if options.water_share is not None:
        label, water, chemistry = blend(label, water, chemistry, options.water_share)
    rules = json.loads(Path(options.rules).read_text(encoding='utf-8-sig')) if options.rules else ()
    reagents = [acid_record(a) for a in options.acid] + catalogue_ph_reagents()
    limits = dict(options.limit)
    workflow = plan_fertilizer_workflow(
        products, targets, water, options.ph, final_volume=VolumeLitres(volume),
        equilibrium=None if chemistry is None else dict(
            chemistry, water_mass_kg=volume, complete_analysis=True, carbon_boundary='closed',
            temperature_c=25, phases=[]),
        ph_adjustment=dict(products=reagents, maximum_reagent_volume_litres=options.max_reagent_litres or volume / 200),
        maximum_concentrations=limits or None)
    summary = summarize_batch(workflow, products, title=title, water_label=label, injection_ratio=options.ratio,
                              rules=rules, temperature_c=options.temperature_c)
    if volumes is not None:
        summary['volumes'] = asdict(volumes)
    return summary


def render(summary):
    """File name -> text: the report, the batch sheet and the JSON summary."""
    return {'report.html': render_report(summary), 'batch-sheet.html': render_batch_sheet(summary),
            'summary.json': json.dumps(serializable(summary), indent=1, allow_nan=False) + '\n'}


def build(args):
    summary = run_batch(BatchOptions(
        water=args.water, formula=args.formula, crop=args.crop, targets=args.targets, water_share=args.water_share,
        volume=args.volume, ph=args.ph, ratio=args.ratio, acid=args.acid, limit=args.limit,
        max_reagent_litres=args.max_reagent_litres, products=args.products, rules=args.rules))
    return render(summary), summary


def main(argv=None):
    parser = argparse.ArgumentParser(prog='flahax batch', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    pick = parser.add_mutually_exclusive_group()
    pick.add_argument('--formula', help='exact name of a packaged formula')
    pick.add_argument('--crop', help='text that matches exactly one packaged formula name')
    pick.add_argument('--targets', help='JSON file of target mg/L (N_NO3 and N_NH4 as N)')
    parser.add_argument('--list-formulas', action='store_true', help='list the packaged formulas and exit')
    parser.add_argument('--water', help='"ro" or a water analysis JSON file (see above)')
    parser.add_argument('--water-share', type=float, metavar='PERCENT',
                        help='use the analysed water as this percentage of the batch water, the rest ion-free '
                             '(desalinated or RO); default 100')
    parser.add_argument('--volume', type=float, default=1000, help='final batch litres (default 1000)')
    parser.add_argument('--ph', type=float, default=5.8, help='target feed pH (default 5.8)')
    parser.add_argument('--ratio', type=float, default=100, help='final litres per litre of concentrate (default 100)')
    parser.add_argument('--acid', action='append', default=[], metavar='FORMULA:FRACTION:DENSITY[:NAME]',
                        help='an acid from your certificate, e.g. HNO3:0.60:1.37; repeat for more')
    parser.add_argument('--limit', action='append', default=[], type=limit_entry, metavar='SYMBOL=MG_PER_L',
                        help='a maximum concentration in the final solution, e.g. Cl=106.35; repeat for more. '
                             'Checked on the laboratory analysis; none is assumed')
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
