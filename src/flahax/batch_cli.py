# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""``flahax batch``: one formula and one water to a report, a batch
sheet and a JSON summary (#79).

Water is ``ro`` (no ions) or a JSON file::

    {"id": "well-104", "measured_ph": 7.8,
     "mg_per_litre": {"Ca": 244, "Mg": 100.8, "K": 44.2, "Na": 680, "Cl": 1280.4,
                      "S": 241.4, "N_NO3": 3.47, "HCO3": 197}}

Elements are mg/L of the element (S as S, N_NO3 and N_NH4 as N);
``HCO3`` is the legacy equivalent-carbon input in mg/L as HCO3, not
titrated alkalinity. For a titration use signed
``alkalinity_meq_per_litre`` instead of HCO3. Iron is taken as Fe(III),
the form in aerated water. Explicit final solvent mass/volume or
solution density/nonwater mass define the concentration basis. Legacy
inputs report an unquantified 1 kg solvent/L assumption.

A value of 0 is a measured zero and stays zero (``"Cl": 0`` for
chloride-free water, ``"HCO3": 0`` for carbon-free water); an omitted
ion is not measured, and measured-pH chemistry needs ``HCO3`` (0 if
none). Optional keys: ``"below_detection": {"Mn": 0.01}`` (detection
limits, mg/L; taken as zero, never adjusted).

Nutrient targets and concentration limits use the analysis exactly as
entered. For the chemistry only (pH, saturation, EC, reagent dose) the
analysis is speciated at its measured pH exactly as measured: its charge
imbalance is reported, and no ion is added, removed or adjusted to close
it. The report shows the imbalance and never lets it pass or fail a
limit (#84).

Limits are never assumed: declare each maximum with ``--limit
Cl=106.35`` (mg/L in the final solution); unspecified limits are not
checked. The packaged pH products (KOH 45%, KHCO3, K2CO3, H3PO4 75%,
HNO3 65%) are always evaluated; pass your own acid's certificate values
with ``--acid``.
"""

import argparse
import json
import math
from pathlib import Path
import sys

from . import __version__
from .batch_request import BatchOptions, run_batch
from .delivery_contracts import DeliveryError
from .engine import load_library
from .inputs import read_json
from .planning_cli import serializable
from .report_html import render_batch_sheet, render_report
from .result_wording import reagent_amount
from .sonneveld import design_targets


def int_at_least(name, low):
    """An argparse type: a whole number of at least ``low``."""

    def parse(text):
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f'{name} {text!r} is not a whole number') from None
        if value < low:
            raise argparse.ArgumentTypeError(f'{name} must be at least {low}, not {text}')
        return value

    return parse


def number_in(name, low, high=None, *, above=True):
    """An argparse type: a finite number above ``low`` (or at least,
    with ``above=False``) and at most ``high``.
    """

    def parse(text):
        try:
            value = float(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f'{name} {text!r} is not a number') from None
        if (
            not math.isfinite(value)
            or (value <= low if above else value < low)
            or (high is not None and value > high)
        ):
            bound = f'above {low:g}' if above else f'at least {low:g}'
            raise argparse.ArgumentTypeError(
                f'{name} must be {bound}'
                + (f' and at most {high:g}' if high else '')
                + f', not {text}'
            )
        return value

    return parse


def limit_entry(spec):
    """``SYMBOL=MG_PER_L``: a maximum concentration in the final
    solution.
    """
    symbol, _, value = spec.partition('=')
    if not symbol.strip() or not value.strip():
        raise argparse.ArgumentTypeError(
            f'--limit {spec}: expected SYMBOL=MG_PER_L, for example Cl=106.35'
        )
    try:
        return symbol.strip(), float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f'--limit {spec}: {value!r} is not a number') from None


def render(summary):
    """File name -> text: the report, the batch sheet and the JSON summary."""
    return {
        'report.html': render_report(summary),
        'batch-sheet.html': render_batch_sheet(summary),
        'summary.json': json.dumps(serializable(summary), indent=1, allow_nan=False) + '\n',
    }


def render_saved_result(record):
    """Validate an archived result/consent before rendering its original
    qualified outputs.
    """
    from .result_acceptance import load_result

    return render(load_result(record)['summary'])


def build(args):
    """Run the batch for parsed ``flahax batch`` arguments; returns the
    rendered terminal text and the summary.
    """
    summary = run_batch(
        BatchOptions(
            water=args.water,
            formula=args.formula,
            crop=args.crop,
            targets=args.targets,
            sonneveld_targets=args.sonneveld_targets,
            water_share=args.water_share,
            volume=args.volume,
            ph=5.8 if args.ph is None else args.ph,
            ph_min=args.ph_min,
            ph_max=args.ph_max,
            range_percent=args.range_percent,
            ranges=args.range,
            require_ranges=args.require_ranges,
            ratio=args.ratio,
            acid=args.acid,
            limit=args.limit,
            max_reagent_litres=args.max_reagent_litres,
            max_solid_reagent_grams=args.max_solid_reagent_grams,
            confirmed_products=args.confirmed_product,
            alternative_products=args.alternative_products,
            alternative_search_preferences=tuple(
                args.alternative_search_preference or ['relative_residual']
            ),
            alternative_search_budget=args.alternative_search_budget,
            volumetric_stocks=args.volumetric_stocks,
            ec=args.ec,
            products=args.products,
            reagents=args.reagents,
            rules=args.rules,
            available_tanks=args.available_tanks,
            tank_capacities=args.tank_capacity,
            fit_equipment=args.fit_equipment,
        )
    )
    return render(summary), summary


def main(argv=None):
    """The ``flahax batch`` command; returns the process exit code."""
    parser = argparse.ArgumentParser(
        prog='flahax batch',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pick = parser.add_mutually_exclusive_group()
    pick.add_argument('--formula', help='exact name of a packaged formula')
    pick.add_argument('--crop', help='text that matches exactly one packaged formula name')
    pick.add_argument('--targets', help='JSON file of target mg/L (N_NO3 and N_NH4 as N)')
    pick.add_argument(
        '--sonneveld-targets',
        help='JSON baseline, corrections and irrigation EC for Sonneveld A-D',
    )
    parser.add_argument(
        '--preview-targets',
        action='store_true',
        help='print the Sonneveld A-D design without formulating a batch',
    )
    parser.add_argument(
        '--list-formulas', action='store_true', help='list the packaged formulas and exit'
    )
    parser.add_argument('--water', help='"ro" or a water analysis JSON file (see above)')
    parser.add_argument(
        '--water-share',
        type=number_in('--water-share', 0, 100),
        metavar='PERCENT',
        help='use the analysed water as this percentage of the batch water, the rest ion-free '
        '(desalinated or RO); default 100',
    )
    parser.add_argument(
        '--volume',
        type=number_in('--volume', 0),
        default=1000,
        help='final batch litres (default 1000)',
    )
    parser.add_argument(
        '--ph',
        type=number_in('--ph', 0, 14, above=False),
        help='target feed pH (default 5.8)',
    )
    parser.add_argument(
        '--ph-min',
        type=number_in('--ph-min', 0, 14, above=False),
        help='lowest acceptable feed pH; with --ph-max the target is this interval, judged '
        'against its bounds, and no midpoint is used',
    )
    parser.add_argument(
        '--ph-max',
        type=number_in('--ph-max', 0, 14, above=False),
        help='highest acceptable feed pH (see --ph-min)',
    )
    parser.add_argument(
        '--range-percent',
        type=number_in('--range-percent', 0, above=False),
        help='acceptable deviation, in percent either side of every positive target; no '
        'default, so no range is used unless you give one',
    )
    parser.add_argument(
        '--range',
        action='append',
        default=[],
        metavar='SYMBOL=SHORTAGE:EXCESS',
        help='a nutrient\'s own range, each side as 5%% or 3mg (mg/L), for example K=2%%:5%% or '
        'Ca=:4mg; an empty side keeps --range-percent',
    )
    parser.add_argument(
        '--require-ranges',
        action='store_true',
        help='constrain the fit by the ranges (default: only assess the result against them); '
        'a zero target and a declared maximum are never relaxed',
    )
    parser.add_argument(
        '--ratio',
        type=number_in('--ratio', 0),
        default=100,
        help='final litres per litre of concentrate (default 100)',
    )
    parser.add_argument(
        '--available-tanks',
        type=int_at_least('--available-tanks', 1),
        help='concentrate tanks you have (default: two assumed, and the report says so)',
    )
    parser.add_argument(
        '--fit-equipment',
        action='store_true',
        help='when the recipe does not fit your tanks, search --alternative-products for '
        'one that does (your equipment and the separation rules are never changed)',
    )
    parser.add_argument(
        '--tank-capacity',
        action='append',
        type=number_in('--tank-capacity', 0),
        metavar='LITRES',
        help='capacity of a tank in litres; repeat once per tank, in tank order',
    )
    parser.add_argument(
        '--ec',
        type=number_in('--ec', 0),
        help='requested EC25 in mS/cm, compared with the estimated range (never enforced)',
    )
    parser.add_argument(
        '--acid',
        action='append',
        default=[],
        metavar='FORMULA:FRACTION:DENSITY[:NAME[:SOLVENT_FRACTION]]',
        help='certificate acid; append the declared solvent fraction for joint fitting '
        '(e.g. HNO3:0.60:1.37:aqueous:0.40)',
    )
    parser.add_argument(
        '--limit',
        action='append',
        default=[],
        type=limit_entry,
        metavar='SYMBOL=MG_PER_L',
        help='a maximum concentration in the final solution, e.g. Cl=106.35; repeat for more. '
        'Checked on the laboratory analysis; none is assumed',
    )
    parser.add_argument(
        '--max-reagent-litres',
        type=number_in('--max-reagent-litres', 0),
        help='largest reagent volume per batch (default volume/200)',
    )
    parser.add_argument(
        '--volumetric-stocks', help='JSON settings for rounded dry and volumetric batch doses'
    )
    parser.add_argument(
        '--alternative-products',
        help='JSON array of available products to combine when nutrient targets are missed',
    )
    parser.add_argument(
        '--alternative-search-preference',
        action='append',
        choices=('relative_residual', 'incidental_mg_l', 'product_count'),
        help='ranking preference after target attainment, repeat in priority order',
    )
    parser.add_argument(
        '--alternative-search-budget',
        type=int,
        default=4,
        help='maximum expanded and focused alternative-product fits (default 4)',
    )
    parser.add_argument(
        '--confirmed-product',
        action='append',
        default=[],
        metavar='CATALOGUE_ID',
        help='rerun an available excluded catalogue fertilizer as a separate remedy',
    )
    parser.add_argument(
        '--max-solid-reagent-grams',
        type=number_in('--max-solid-reagent-grams', 0, above=False),
        help='maximum dry pH reagent mass per batch (g) for joint fitting',
    )
    parser.add_argument(
        '--products', help='JSON array of your product records (default: the packaged catalogue)'
    )
    parser.add_argument(
        '--reagents',
        help='JSON array of available pH reagent records; replaces catalogue '
        'reagents, including when empty. Explicit --acid certificates are added to this list.',
    )
    parser.add_argument(
        '--rules', help='JSON array of extra compatibilityRule records separating products'
    )
    parser.add_argument(
        '--output', help='new directory for report.html, batch-sheet.html and summary.json'
    )
    args = parser.parse_args(argv)
    if args.ph is not None and (args.ph_min is not None or args.ph_max is not None):
        parser.error('--ph is one pH; use either --ph or --ph-min with --ph-max, not both')
    if (args.ph_min is None) != (args.ph_max is None):
        parser.error('--ph-min and --ph-max go together')
    if args.list_formulas:
        print('\n'.join(f['name'] for f in load_library()['formulas']))
        return 0
    if args.preview_targets:
        if not args.sonneveld_targets:
            parser.error('--preview-targets requires --sonneveld-targets')
        try:
            design = design_targets(read_json(args.sonneveld_targets, 'Sonneveld targets'))
        except (DeliveryError, ValueError, OSError) as exc:
            print(f'flahax batch: {exc}', file=sys.stderr)
            return 1
        print(json.dumps(design, indent=2, allow_nan=False))
        return 0
    if (
        not (args.formula or args.crop or args.targets or args.sonneveld_targets)
        or not args.water
        or not args.output
    ):
        parser.error('A target source, --water and --output are required')
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
    if summary['ph'] and summary['ph'].get('direction') == 'none':
        print('  pH: already within target tolerance; no reagent needed')
    elif selected:
        print(
            f'  pH: {reagent_amount(selected)} {selected["product"]} per '
            f'{summary["batch_litres"]:g} L'
        )
    print(f'Wrote {", ".join(files)} to {output}')
    return 3 if summary['status'] == 'blocked' else 0
