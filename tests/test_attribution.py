# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Every data source FlahaX ships is credited in NOTICE, and the USGS notice travels with PHREEQC data.

Adding data with a source NOTICE does not name fails here: credit it in NOTICE (and CITATION.cff) first.
"""

import json
from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'src' / 'flahax' / 'data'
NOTICE = ' '.join(
    (ROOT / 'NOTICE').read_text(encoding='utf-8').split()
)  # line breaks do not matter
CITATION = (ROOT / 'CITATION.cff').read_text(encoding='utf-8')

# Text a source string starts with -> the words NOTICE must contain for it.
CREDITS = {
    'minteq.v4.dat': 'minteq.v4.dat',
    'flahax-chelates-25c.dat': 'flahax-chelates-25c.dat',
    'flahax-phases-25c.dat': 'flahax-phases-25c.dat',
    'fixed-valence analytical basis': None,  # FlahaX's own convention, no external data
    'CRC Handbook': 'CRC Handbook of Chemistry and Physics',
    'Yara': 'YaraTera CALCINIT',
    'U.S. Coast Guard CHRIS': 'U.S. Coast Guard CHRIS',
    'McCleskey': 'McCleskey, Nordstrom, Ryan and Ball (2012)',
    'A. D. Pethybridge': 'Pethybridge, Talbot and House (2006)',
    'Pethybridge et al.': 'Pethybridge, Talbot and House (2006)',
    'phreeqc.dat': 'phreeqc.dat diffusion coefficients',
    'docs/audit/2026-10-18-materials-identity': 'docs/audit/2026-10-18-materials-identity',
    'Haifa Group': 'Haifa Group',
    'Sigma-Aldrich': 'Sigma-Aldrich',
    'ChemicalBook': 'ChemicalBook',
}


def sources():
    """(file, source text) for every source, citation or reference field and every supplier in the data."""
    found = []

    def walk(name, value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ('source', 'citation', 'reference') and isinstance(item, str):
                    found.append((name, item))
                elif key == 'supplier' and isinstance(item, str):
                    found.append((name, item))
                walk(name, item)
        elif isinstance(value, list):
            for item in value:
                walk(name, item)

    for path in sorted(DATA.glob('*.json')):
        walk(path.name, json.loads(path.read_text(encoding='utf-8')))
    return found


class AttributionTests(unittest.TestCase):
    def test_every_shipped_source_is_credited_in_notice(self):
        for file, text in sources():
            with self.subTest(file=file, source=text[:60]):
                key = next((k for k in CREDITS if text.startswith(k)), None)
                self.assertIsNotNone(
                    key,
                    f'{file}: source {text[:80]!r} is not credited; add it to NOTICE and CREDITS',
                )
                if CREDITS[key]:
                    self.assertTrue(
                        CREDITS[key] in NOTICE, f'NOTICE does not credit {CREDITS[key]!r}'
                    )

    def test_crop_formula_sources_are_credited(self):
        library = json.loads((DATA / 'library.json').read_text(encoding='utf-8'))
        named = {
            f['name'].rsplit('(', 1)[-1].rstrip(')').lower()
            for f in library['formulas']
            if '(' in f['name']
        }
        aliases = {'u of florida': 'university of florida'}
        for source in named:
            with self.subTest(source=source):
                credit = aliases.get(source, source)
                self.assertTrue(
                    credit in NOTICE.lower(),
                    f'NOTICE does not credit the formula source {credit!r}',
                )

    def test_phreeqc_data_carries_the_usgs_notice_and_its_modifications(self):
        chemistry = json.loads((DATA / 'chemistry_25c.json').read_text(encoding='utf-8'))
        self.assertIn('Modified data, not the original USGS files', chemistry['notice'])
        self.assertIn('USGS USER RIGHTS NOTICE', NOTICE)
        self.assertIn(
            'The user agrees to appropriately acknowledge the authors and the USGS', NOTICE
        )
        self.assertIn('MODIFICATIONS:', NOTICE)
        self.assertIn('10.3133/tm6A43', CITATION)

    def test_package_metadata_names_author_and_ships_notice(self):
        project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
        self.assertEqual(project['authors'][0]['name'], 'Rafat A. Al Khashan')
        self.assertIn({'name': 'Flaha Agri Tech'}, project['maintainers'])
        self.assertIn('NOTICE', project['license-files'])
        self.assertIn('Rafat A. Al Khashan', NOTICE)


if __name__ == '__main__':
    unittest.main()
