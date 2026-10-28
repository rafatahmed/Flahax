# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Do not lose successful intermediate references when a later case fails."""

import hashlib
import json
from pathlib import Path
import unittest

from tools.phreeqc_evidence import selected

ROOT = Path(__file__).parent / 'fixtures/phreeqc'


class PreservedEvidenceTests(unittest.TestCase):
    def test_preserved_successes_and_failure_reproducers(self):
        manifest = json.loads((ROOT / 'preserved-evidence.json').read_text())
        successes = 0
        for record in manifest['artifacts']:
            successes += record['kind'] == 'historical_success'
            if record['kind'] == 'historical_success':
                name = record['case']
                self.assertEqual(selected(ROOT / (name + '.sel')), record['selected_rows'])
                output = (ROOT / (name + '.out')).read_text()
                self.assertNotIn('ERROR:', output)
                self.assertNotIn('WARNING:', output)
            for name, digest in record['hashes'].items():
                self.assertEqual(
                    hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest, name
                )
        self.assertEqual(successes, 6)
        for prefix in ('01_macro_original', '02_add_fe_dtpa_original'):
            data = json.loads((ROOT / 'failures' / (prefix + '.json')).read_text())
            self.assertNotEqual(data['exit_code'], 0)
            text = (ROOT / 'failures' / (prefix + '.out')).read_text()
            self.assertIn('ERROR:', text)
