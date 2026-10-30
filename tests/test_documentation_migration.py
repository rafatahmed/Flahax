# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Execute current site examples and keep migration/version boundaries explicit."""

import contextlib
import io
import os
from pathlib import Path
import re
import tempfile
import unittest

import flahax

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'docs/site'


class DocumentationMigrationTests(unittest.TestCase):
    def test_current_site_python_examples(self):
        """Every current executable fence runs independently without caller globals."""
        count = 0
        for page in sorted(SITE.rglob('*.md')):
            if any(part in page.parts for part in ('_static', 'audit', 'evidence')):
                continue  # Historical records are not current tutorials.
            blocks = re.findall(r'```python\n(.*?)```', page.read_text(encoding='utf-8'), re.S)
            for index, block in enumerate(blocks, 1):
                count += 1
                with self.subTest(page=page.relative_to(SITE), example=index):
                    with tempfile.TemporaryDirectory() as tmp:
                        previous = Path.cwd()
                        try:
                            os.chdir(tmp)
                            with contextlib.redirect_stdout(io.StringIO()):
                                exec(
                                    compile(block, f'{page}:{index}', 'exec'),
                                    {'__name__': '__documentation_example__'},
                                )
                        finally:
                            os.chdir(previous)
        self.assertGreaterEqual(count, 15)

    def test_manual_current_version_is_not_historical_release(self):
        text = (ROOT / 'src/flahax/data/USER_GUIDE.md').read_text(encoding='utf-8')
        self.assertIn(f'**Version:** {flahax.__version__}, unpublished', text)
        self.assertIn('### Historical release changes', text)

    def test_release_index_covers_recorded_publications(self):
        text = (SITE / 'evidence/release-evidence.md').read_text(encoding='utf-8')
        index = text.split('## ', 1)[0]
        publications = re.findall(r'^## (\d+\.\d+\.\d+) publication', text, re.M)
        for version in publications:
            self.assertIn(f'| {version} |', index)
        self.assertIn('unpublished development version', index)
