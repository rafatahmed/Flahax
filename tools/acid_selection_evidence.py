"""Capture additional single-acid references without changing existing evidence.

Run: python tools/acid_selection_evidence.py
Uses the existing external pinned installation and temporary database merge.
"""
import json
import tempfile
from pathlib import Path

from phreeqc_evidence import INSTALL, ROOT, execute, merge, sha


def generate():
    exe = INSTALL / 'bin/Release/phreeqc.exe'
    base = INSTALL / 'database/minteq.v4.dat'
    destination = ROOT / 'tests/fixtures/phreeqc/acid_selection'
    with tempfile.TemporaryDirectory(prefix='flahax-acids-') as temporary:
        database = Path(temporary) / 'merged.dat'
        merge(base, database)
        for formula, reagent, component in [('HNO3', 'HNO3', 'N(5)'),
                                             ('H3PO4', 'H3PO4', 'P'),
                                             ('H2SO4', 'H2SO4', 'S(6)'),
                                             ('C6H8O7', 'H3Citrate', 'Citrate')]:
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
            data = dict(formula=formula, totals={'Na+': .002, 'Cl-': .002},
                        target_ph=6.5, selected_rows=rows,
                        acid_molal=rows[-1][component],
                        tolerances=dict(ph_absolute=.01, dose_relative=.03, dose_absolute=1e-9,
                                        charge_error_percent=.1),
                        database_sha256=sha(base), merged_database_sha256=sha(database),
                        executable_sha256=sha(exe),
                        version='3.8.6-17100',
                        regeneration='python tools/acid_selection_evidence.py',
                        notes='Synthetic NaCl background; no agronomic acceptance implied. '
                              'H3Citrate preserves the organic citrate component, not inorganic carbon.',
                        hashes={p.name: sha(p) for p in folder.glob('reference.*')})
            (folder / 'expected.json').write_text(json.dumps(data, indent=2) + '\n')
            print(formula, data['acid_molal'])


if __name__ == '__main__':
    generate()
