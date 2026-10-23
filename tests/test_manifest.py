# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The source distribution carries every root policy document (#151)."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
POLICY = (
    'README.md',
    'LICENSE',
    'NOTICE',
    'CITATION.cff',
    'CHANGELOG.md',
    'CONTRIBUTING.md',
    'CODE_OF_CONDUCT.md',
    'SECURITY.md',
)


class ManifestTests(unittest.TestCase):
    def test_policy_documents_are_in_the_sdist(self):
        included = {
            line.split(maxsplit=1)[1].strip()
            for line in (ROOT / 'MANIFEST.in').read_text(encoding='utf-8').splitlines()
            if line.startswith('include ')
        }
        for name in POLICY:
            with self.subTest(name):
                self.assertTrue((ROOT / name).is_file(), name)
                self.assertIn(name, included)


if __name__ == '__main__':
    unittest.main()
