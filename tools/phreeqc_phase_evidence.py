#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Named phase allocation references and low/high saturation boundaries."""

import json
import tempfile
import argparse
from pathlib import Path
from phreeqc_evidence import (
    INSTALL,
    merge,
    execute,
    input_text,
    sha,
    fixed_ammonium,
    CASES as PRODUCTS,
    new_capture_root,
)
from flahax.aqueous_model import chemistry
from flahax.product_conversion import catalogue_dose_totals

CASES = {
    'calcite': ({'Ca+2': 0.001, 'CO3-2': 0.002}, 9.0, ['Calcite']),
    'calcium_phosphate': (
        {'Ca+2': 0.002, 'PO4-3': 0.001},
        7.4,
        ['Hydroxylapatite', 'CaHPO4:2H2O', 'CaHPO4'],
    ),
    'gypsum': ({'Ca+2': 0.04, 'SO4-2': 0.04}, 6.0, ['Gypsum', 'Anhydrite']),
    'trace_hydroxides': (
        {'Fe+3': 1e-4, 'Zn+2': 1e-4, 'Cu+2': 1e-4, 'Mn+2': 1e-4},
        8.0,
        ['Ferrihydrite', 'Zincite', 'Cu(OH)2', 'Pyrochroite'],
    ),
    'trace_phosphates': (
        {'Fe+3': 1e-4, 'Zn+2': 1e-4, 'Cu+2': 1e-4, 'Mn+2': 1e-4, 'PO4-3': 0.001},
        6.0,
        ['Strengite', 'Zn3(PO4)2:4H2O', 'Cu3(PO4)2', 'Mn3(PO4)2'],
    ),
    'trace_carbonates': (
        {'Zn+2': 1e-4, 'Cu+2': 1e-4, 'Mn+2': 1e-4, 'CO3-2': 0.002},
        8.5,
        ['Smithsonite', 'Malachite', 'Rhodochrosite'],
    ),
    'magnesium_salts': ({'Mg+2': 0.001, 'SO4-2': 0.001}, 6.0, ['Epsomite', 'Kieserite']),
    'zero_stock': ({'Ca+2': 1e-8, 'CO3-2': 1e-8}, 6.0, ['Calcite']),
    'struvite': ({'Mg+2': 0.002, 'NH4+': 0.002, 'PO4-3': 0.002}, 9.0, ['Struvite']),
    'ferrous_phases': (
        {'Fe+2': 0.0001, 'PO4-3': 0.001, 'CO3-2': 0.001},
        7.0,
        ['Vivianite', 'Siderite', 'Fe(OH)2'],
    ),
    # Product doses; converted inside generate() so the destination guard runs first.
    'mixed_product_phases': (PRODUCTS['mixed_products'], 6.0, None),
}


def generate(destination):
    destination = new_capture_root(destination)
    exe = INSTALL / 'bin/Release/phreeqc.exe'
    base = INSTALL / 'database/minteq.v4.dat'
    with tempfile.TemporaryDirectory(prefix='flahax-phases-') as tmp:
        db = Path(tmp) / 'merged.dat'
        merge(base, db)
        for name, (totals, ph, phases) in CASES.items():
            folder = destination / name
            if name == 'mixed_product_phases':
                totals = catalogue_dose_totals(totals)
                phases = [r['name'] for r in chemistry()['phases']]
            totals = totals | {'Na+': 0.01, 'Cl-': 0.01}
            definitions = {r['name']: r for r in chemistry()['phases']}
            phases = [
                p for p in phases if set(definitions[p]['powers']) <= set(totals) | {'H+', 'H2O'}
            ]
            text = input_text(name, totals, ph, phases=phases)
            if name == 'mixed_product_phases':
                text = fixed_ammonium(text)
            rows = execute(exe, db, folder, name, text)
            # Phase equilibration changes pH naturally in a closed solution.
            # Runtime is compared at that independently obtained final pH.
            totals['Na+'] = rows[0]['Na']
            water = rows[-1]['mass_H2O']
            totals = {b: v / water for b, v in totals.items()}
            data = {
                'schema': 1,
                'runtime_totals': totals,
                'phases': phases,
                'selected_rows': rows,
                'reference': {
                    'software': 'PHREEQC 3.8.6-17100',
                    'executable_sha256': sha(exe),
                    'base_sha256': sha(base),
                    'merged_sha256': sha(db),
                },
                'tolerances': {
                    'molality_relative': 0.15,
                    'molality_absolute': 2e-8,
                    'si_absolute': 0.25,
                    'phase_relative': 0.08,
                    'phase_absolute': 2e-8,
                },
                'hashes': {
                    p.name: sha(p)
                    for p in folder.iterdir()
                    if p.suffix in ('.pqi', '.sel', '.out', '.screen')
                },
            }
            (folder / 'expected.json').write_bytes((json.dumps(data, indent=2) + '\n').encode())
            print(name, 'pH', rows[-1]['pH'], 'charge', rows[-1]['pct_err'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new capture directory')
    generate(parser.parse_args().output)
