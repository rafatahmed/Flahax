#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Capture additional single-acid references without changing existing evidence.

Run: python tools/acid_selection_evidence.py --output NEW_DIRECTORY
Uses the existing external pinned installation and temporary database merge.
"""

import json
import argparse
import tempfile
from pathlib import Path

from phreeqc_evidence import INSTALL, execute, merge, sha, new_capture_root


def generate(destination):
    destination = new_capture_root(destination)
    exe = INSTALL / 'bin/Release/phreeqc.exe'
    base = INSTALL / 'database/minteq.v4.dat'
    with tempfile.TemporaryDirectory(prefix='flahax-acids-') as temporary:
        database = Path(temporary) / 'merged.dat'
        merge(base, database)
        for formula, reagent, component in [
            ('HNO3', 'HNO3', 'N(5)'),
            ('H3PO4', 'H3PO4', 'P'),
            ('H2SO4', 'H2SO4', 'S(6)'),
            ('C6H8O7', 'H3Citrate', 'Citrate'),
        ]:
            folder = destination / formula
            text = f'''TITLE FlahaX single-acid reference {formula}; closed, 25 C
PHASES
Fix_H+
 H+ = H+
 log_k 0
SOLUTION 1
 temp 25
 pH 7 charge
 units mol/kgw
 -water 1
 Na 0.002
 Cl 0.002
EQUILIBRIUM_PHASES 1
 Fix_H+ -6.5 {reagent} 1
SELECTED_OUTPUT
 -file reference.sel
 -reset false
 -high_precision true
 -pH true
 -ionic_strength true
 -charge_balance true
 -percent_error true
 -water true
 -totals Na Cl {component}
END
'''
            rows = execute(exe, database, folder, 'reference', text)
            data = dict(
                formula=formula,
                totals={'Na+': 0.002, 'Cl-': 0.002},
                target_ph=6.5,
                selected_rows=rows,
                acid_molal=rows[-1][component],
                tolerances=dict(
                    ph_absolute=0.01,
                    dose_relative=0.03,
                    dose_absolute=1e-9,
                    charge_error_percent=0.1,
                ),
                database_sha256=sha(base),
                merged_database_sha256=sha(database),
                executable_sha256=sha(exe),
                version='3.8.6-17100',
                regeneration='python tools/acid_selection_evidence.py --output NEW_DIRECTORY',
                notes='Synthetic NaCl background; no agronomic acceptance implied. '
                'H3Citrate preserves the organic citrate component, not inorganic carbon.',
                hashes={p.name: sha(p) for p in folder.glob('reference.*')},
            )
            (folder / 'expected.json').write_bytes((json.dumps(data, indent=2) + '\n').encode())
            print(formula, data['acid_molal'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new capture directory')
    generate(parser.parse_args().output)
