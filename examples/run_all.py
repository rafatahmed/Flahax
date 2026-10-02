"""Run all examples; optionally write a fresh directory with JSON and Markdown."""
import argparse
import json
from pathlib import Path

from . import pepper_formulation, mixed_chemistry, equilibrium_delivery, titration_and_stocks, cli_usage, ec_and_injection
from .common import serializable
from .visual_report import render_html
from . import calculated_site_planning

SCENARIOS = dict(pepper=pepper_formulation.run, chemistry=mixed_chemistry.run,
                 delivery=equilibrium_delivery.run, titration_stocks=titration_and_stocks.run,
                 cli=cli_usage.run, ec_injection=ec_and_injection.run,
                 calculated_site=calculated_site_planning.run)


def markdown(report):
    scenarios = report['scenarios']
    pepper = scenarios['pepper']['workflow']
    recommendation = pepper['recommendation']
    lines = ['# FlahaX capability examples', report['notice'],
             '## Pepper nutrient balance',
             'Catalogue-assay calculation only. Acid-grade confirmation and incidental review are outstanding.',
             '| Nutrient | Crop target mg/L | Water mg/L | Final mg/L | Deviation % |',
             '|---|---:|---:|---:|---:|']
    for row in recommendation['rows']:
        target = row['target'] if row['target'] is not None else 'not requested'
        delta = f"{row['deltaPct']:.4f}" if row['deltaPct'] is not None else 'not defined'
        lines.append(f"| {row['symbol']} | {target} | {pepper['water'].get(row['symbol'], 0)} | {row['final']:.6f} | {delta} |")
    lines.extend(['', '## Illustrative 1000 L pepper batch',
                  '| Catalogue product | g/L | g per 1000 L |', '|---|---:|---:|'])
    for salt in recommendation['salts']:
        dose = salt['gramsPerLitre']
        lines.append(f"| {salt['name']} | {dose:.6f} | {dose*1000:.6f} |")
    allocation = scenarios['pepper']['stock_allocation_review']
    lines.extend(['', '## Pepper Tank A / B / acid allocation review',
                  'NOT READY FOR MIXING. Source: 04_Fertilizer.pdf pp.63,65,66. Candidate destinations only.',
                  '| Proposed destination | Product | Recipe mass g | Reason / pending check |',
                  '|---|---|---:|---|'])
    for row in allocation['rows']:
        lines.append(f"| {row['proposed_channel']} | {row['product']} | {row['recipe_mass_g']:.6f} | {row['reason']} |")
    lines.extend(['', allocation['acid_policy'], allocation['acid_accounting'], *allocation['missing']])
    lines.extend(['', '## Workflow availability', '| Pepper stage | Status |', '|---|---|'])
    for name, stage in pepper['stages'].items():
        lines.append(f"| {name} | {stage['status']} |")
    delivery = scenarios['delivery']['workflow']['stages']
    lines.extend(['', '## Separate synthetic equilibrium demonstration',
                  f"Calculated mixed pH: {delivery['chemistry']['value']['mixed']['ph']:.6f}; target: 6.5.",
                  f"HNO3 commercial reagent volume: {delivery['nitric']['value']['reagent_volume_litres']:.9g} L.",
                  scenarios['delivery']['human_report'],
                  '## Complete inputs and outputs',
                  'Species/totals: mol/kg-water; activities: dimensionless; SI: log10 saturation ratio. '
                  'Nonfinite SI for absent components is represented as text. Typed quantities retain their named fields.'])
    for name, result in scenarios.items():
        lines.extend([f'### {name}', *result['assumptions'],
                      '```json\n'+json.dumps(result, indent=2, allow_nan=False)+'\n```'])
    return '\n'.join('\n'+line+'\n' if line.startswith('#') else line for line in lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='new report directory; existing paths are never overwritten')
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error('output already exists; choose a new directory')
    report = {'notice':'Educational examples; synthetic inputs are NOT field evidence or dosing instructions.',
              'scenarios':{name:serializable(run()) for name, run in SCENARIOS.items()}}
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.output is None:
        print(text)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'report.json').write_text(text+'\n', encoding='utf-8')
    (args.output/'report.md').write_text(markdown(report), encoding='utf-8')
    (args.output/'report.html').write_text(render_html(report), encoding='utf-8')
    print(f'Created report.html, report.md and report.json in {args.output}')


if __name__ == '__main__':
    main()
