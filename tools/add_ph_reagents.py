#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""One-off data change for #75: sourced pH-up reagents in the catalogue (decisions
2026-10-22).

Adds Potassium Hydroxide (45% solution) and Potassium Bicarbonate, links Potassium
Carbonate to its sourced identity-theoretical analysis, and marks all three
`role: ph_reagent` so formulation never selects them as nutrient salts. Values
and sources are recorded on rafatahmed/Flahax#75. Writes byte-compatible JSON.
"""

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'src/flahax/data'
ATOMIC = {'H': 1.00784, 'C': 12.011, 'O': 15.999, 'K': 39.0983}  # flahax.composition.ATOMIC
KOH = ATOMIC['K'] + ATOMIC['O'] + ATOMIC['H']
KHCO3 = ATOMIC['K'] + ATOMIC['H'] + ATOMIC['C'] + 3 * ATOMIC['O']
KOH_FRACTION = 0.45  # Sigma-Aldrich 417661: 45 wt. % in H2O (43.0-47.0 % by HCl titration)
KOH_DENSITY = 1.456  # same page: 1.456 g/mL at 25 C
ACCESSED = '2026-10-22'


def sigma(code, title):
    return {
        'supplier': 'Sigma-Aldrich',
        'title': title,
        'issued': ACCESSED,
        'entered': ACCESSED,
        'url': f'https://www.sigmaaldrich.com/US/en/product/sigald/{code}',
        'sha256': None,
    }


def main():
    library_path = DATA / 'library.json'
    library = json.loads(library_path.read_bytes())
    salts = library['salts']
    names = {s['name'] for s in salts}
    carbonate = next(s for s in salts if s['name'] == 'Potassium Carbonate')
    carbonate.update(
        elements={'K': 2 * ATOMIC['K'] / (2 * ATOMIC['K'] + ATOMIC['C'] + 3 * ATOMIC['O']) * 100},
        analysisBasis='identity_theoretical',
        source=sigma(
            '209619', 'Potassium carbonate, ACS reagent >=99.0% (209619) product specification'
        ),
        role='ph_reagent',
        notes='Pure K2CO3 theoretical analysis (replaces the unsourced 56.581 %, #75 decision '
        '2026-10-22). '
        'pH-up reagent only; never a nutrient salt in formulation.',
    )
    if 'Potassium Hydroxide (45% solution)' not in names:
        salts.append(
            {
                'id': 'cmz1kohsol45q8z9phup00001',
                'name': 'Potassium Hydroxide (45% solution)',
                'formula': 'KOH',
                'elements': {'K': KOH_FRACTION * ATOMIC['K'] / KOH * 100},
                'identityId': 'idn-potassium-hydroxide',
                'analysisBasis': 'grade_typical',
                'source': sigma(
                    '417661',
                    'Potassium hydroxide solution, 45 wt. % in H2O (417661) product specification',
                ),
                'role': 'ph_reagent',
                'massFraction': KOH_FRACTION,
                'densityKgPerL': KOH_DENSITY,
                'notes': '45 % w/w aqueous solution (43.0-47.0 % KOH by titration), 1.456 g/mL '
                'at 25 C; '
                'product-mass dosing. pH-up reagent only; never a nutrient salt in formulation.',
            }
        )
    if 'Potassium Bicarbonate' not in names:
        salts.append(
            {
                'id': 'cmz1khco3q8z9phup00000002',
                'name': 'Potassium Bicarbonate',
                'formula': 'KHCO3',
                'elements': {'K': ATOMIC['K'] / KHCO3 * 100},
                'identityId': 'idn-potassium-bicarbonate',
                'analysisBasis': 'identity_theoretical',
                'source': sigma(
                    '237205',
                    'Potassium bicarbonate, ACS reagent 99.7% (237205) product specification',
                ),
                'role': 'ph_reagent',
                'massFraction': 1.0,
                'notes': 'Pure KHCO3 theoretical analysis; ACS assay 99.7-100.5 %. pH-up '
                'reagent only; '
                'adds alkalinity (bicarbonate); never a nutrient salt in formulation.',
            }
        )
    salts.sort(key=lambda s: s['name'])
    library_path.write_bytes(json.dumps(library, separators=(',', ':')).encode())

    identities_path = DATA / 'material_identities.json'
    identities = json.loads(identities_path.read_bytes())
    known = {i['id'] for i in identities['identities']}
    if 'idn-potassium-hydroxide' not in known:
        identities['identities'].append(
            {
                'id': 'idn-potassium-hydroxide',
                'products': ['Potassium Hydroxide (45% solution)'],
                'name': 'Potassium hydroxide (aqueous solution)',
                'formula': 'KOH',
                'hydration': 'aqueous solution, not a crystal hydrate',
                'molecular_weight': None,
                'cas': '1310-58-3',
                'ion_forms': {'K+': 1, 'OH-': 1},
                'theoretical_analysis': {'K': ATOMIC['K'] / KOH * 100},
                'comparator': {
                    'product': 'Sigma-Aldrich 417661 (45 wt. % solution)',
                    'url': 'https://www.sigmaaldrich.com/US/en/product/sigald/417661',
                    'accessed': ACCESSED,
                },
                'status': 'aqueous_solution',
                'notes': 'Identity is the KOH solute; theoretical analysis is the pure-KOH '
                'value (K 69.69 %). The 45 % w/w '
                'solution is K 31.36 % and is dosed by product mass. Molecular weight is null '
                'because a solution '
                'has none (solute 56.11). Added 2026-10-22 as a pH-up reagent (#75).',
            }
        )
    if 'idn-potassium-bicarbonate' not in known:
        identities['identities'].append(
            {
                'id': 'idn-potassium-bicarbonate',
                'products': ['Potassium Bicarbonate'],
                'name': 'Potassium hydrogen carbonate',
                'formula': 'KHCO3',
                'hydration': 'anhydrous',
                'molecular_weight': 100.12,
                'cas': '298-14-6',
                'ion_forms': {'K+': 1, 'HCO3-': 1},
                'theoretical_analysis': {'K': ATOMIC['K'] / KHCO3 * 100},
                'comparator': {
                    'product': 'Sigma-Aldrich 237205',
                    'url': 'https://www.sigmaaldrich.com/US/en/product/sigald/237205',
                    'accessed': ACCESSED,
                },
                'status': 'identity_consistent',
                'notes': 'Added 2026-10-22 as a pH-up reagent (#75). Sigma-Aldrich 237205, ACS '
                'reagent, assay 99.7 % '
                '(ACS 99.7-100.5 %).',
            }
        )
    identities_path.write_bytes((json.dumps(identities, indent=2) + '\n').encode())


if __name__ == '__main__':
    main()
