"""Generate the shipped public API inventory; --check detects signature drift."""
import argparse
from collections import defaultdict
from dataclasses import fields, is_dataclass
import inspect
from pathlib import Path

import flahax

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'src/flahax/data/API_REFERENCE.md'


def render():
    lines = [
        f'# FlahaX {flahax.__version__} - Public API reference', '',
        'Generated from `flahax.__all__`, runtime signatures and source docstrings.',
        'Do not edit this inventory by hand. Regenerate with',
        '`PYTHONPATH=src python tools/generate_api_reference.py` (PowerShell:',
        '`$env:PYTHONPATH="src"; python tools/generate_api_reference.py`).', '',
        'Start with the [User Manual](USER_GUIDE.md) for units, complete examples,',
        'input provenance, errors and scientific limits. This inventory is not a',
        'substitute for the linked workflow contracts or a claim of field validation.', '',
        '## Choosing an entry point', '',
        '| Task | Entry point | Contract |', '|---|---|---|',
        '| Nutrient fit | `recommend`, `solve_weights` | Elemental mg/L in; product g/L out |',
        '| Staged site workflow | `plan_fertilizer_workflow` | Explicit water; inspect every stage status |',
        '| One mixed chemistry solve | `solve_catalogue_product_doses` | Product g/kg water; fixed pH |',
        '| Calculated pH | `calculate_equilibrium_ph` | Complete analytical mol/kg-water totals |',
        '| Nitric reagent volume | `plan_equilibrium_delivery` | Final solvent mass, assay and density |',
        '| Standard acid candidates | `plan_acid_options` | Workflow restricts to nitric/phosphoric |',
        '| Stock compatibility | `plan_stocks` | Sourced rules and solubility limits required |',
        '| Measured titration | `plan_ph` | Matching measured curve, not inferred water chemistry |',
        '| Approximate EC | `estimate_manufacturer_ec` | Restricted pre-acid irrigation screening |',
        '| Calibrated EC | `plan_ec_delivery` | Matching measured profiles |',
        '| Injector requirements | `size_injection_requirements` | Volume/flow only, not model selection |',
        '| Calibrated delivery | `plan_pump_command`, `compose_delivery_plan` | Planning only; no hardware I/O |', '',
        '## Compatibility and error handling', '',
        'Only the names listed here are the top-level import surface. Submodule',
        'helpers are not automatically public contracts. Legacy single-system kernels',
        'remain available for compatibility and reference tests; do not combine their',
        'independent results as a substitute for the coupled mixed solver.',
        'Signatures show keyword-only arguments after `*`; omitted defaults do not',
        'supply missing measured chemistry. Handle `InputError` and `DeliveryError`',
        'as described in the manual. A returned result is not necessarily an approved',
        'plan: inspect feasibility, stage status, residuals and warnings.', '',
    ]
    grouped = defaultdict(list)
    for name in sorted(flahax.__all__):
        grouped[getattr(flahax, name).__module__].append(name)
    for module, names in sorted(grouped.items()):
        lines += [f'## {module}', '']
        for name in names:
            obj = getattr(flahax, name)
            lines += [f'### `{name}`', '']
            try:
                signature = str(inspect.signature(obj))
            except (ValueError, TypeError):
                signature = None
            if signature is not None:
                lines += ['```text', name + signature, '```', '']
            doc = inspect.cleandoc(obj.__doc__ or '')
            # Dataclasses without prose get an auto-generated signature docstring.
            if doc and not (is_dataclass(obj) and doc.startswith(name + '(')):
                lines += [doc, '']
            if is_dataclass(obj):
                lines += ['Record fields: ' + ', '.join(f'`{f.name}`' for f in fields(obj)) + '.', '']
            lines += [f'Source module: `{module}`. Import with `from flahax import {name}`.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    expected = render()
    if args.check:
        if not DESTINATION.exists() or DESTINATION.read_text(encoding='utf-8') != expected:
            parser.exit(1, 'API reference is stale; regenerate it.\n')
    else:
        DESTINATION.write_text(expected, encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
