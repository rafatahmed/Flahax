# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Execute current site examples and keep migration/version boundaries
explicit.
"""

import contextlib
from datetime import date
import io
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import flahax

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'docs/site'


class DocumentationMigrationTests(unittest.TestCase):
    def test_current_site_python_examples(self):
        """Every current executable fence runs independently without
        caller globals.
        """
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
        self.assertGreater(count, 0, 'the current site must include executable examples')

    def test_manual_current_version_is_not_historical_release(self):
        text = (ROOT / 'src/flahax/data/USER_GUIDE.md').read_text(encoding='utf-8')
        version = next(line for line in text.splitlines() if line.startswith('**Version:**'))
        self.assertRegex(version, rf'^\*\*Version:\*\* {re.escape(flahax.__version__)}(?:,|$)')
        evidence = (SITE / 'evidence/release-evidence.md').read_text(encoding='utf-8')
        publications = re.findall(r'^## (\d+\.\d+\.\d+) publication', evidence, re.M)
        changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
        dated = re.search(
            rf'^## \[{re.escape(flahax.__version__)}\] - (\d{{4}}-\d{{2}}-\d{{2}})$',
            changelog,
            re.M,
        )
        self.assertEqual('unpublished' in version, dated is None)
        if dated:
            try:
                date.fromisoformat(dated.group(1))
            except ValueError:
                self.fail('The release declaration must contain a valid calendar date')
            self.assertIn(f'released {dated.group(1)}', version)
        else:
            self.assertNotIn(flahax.__version__, publications)
        self.assertIn('### Historical release changes', text)

    def test_release_index_covers_recorded_publications(self):
        text = (SITE / 'evidence/release-evidence.md').read_text(encoding='utf-8')
        index = text.split('## ', 1)[0]
        publications = re.findall(r'^## (\d+\.\d+\.\d+) publication', text, re.M)
        for version in publications:
            self.assertIn(f'| {version} |', index)
        if flahax.__version__ not in publications:
            self.assertIn(f'**{flahax.__version__}**', index)
            self.assertIn('unpublished', index)
            self.assertNotIn(flahax.__version__, publications)
        else:
            self.assertIn(flahax.__version__, publications)


class ReleaseLifecycleTests(unittest.TestCase):
    def check_fixture(self, wording, declaration, *, published=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'src/flahax/data'
            data.mkdir(parents=True)
            site = root / 'docs/site'
            (site / 'evidence').mkdir(parents=True)
            version = flahax.__version__
            (data / 'USER_GUIDE.md').write_text(
                f'**Version:** {version}, {wording}\n\n### Historical release changes\n',
                encoding='utf-8',
            )
            (root / 'CHANGELOG.md').write_text(
                f'## [Unreleased]\n\n## [{version}] - {declaration}\n', encoding='utf-8'
            )
            evidence = f'**{version}**, upload pending.\n\n## 0.6.0 publication\n'
            if published:
                evidence += f'\n## {version} publication\nVerified upload receipt.\n'
            (site / 'evidence/release-evidence.md').write_text(evidence, encoding='utf-8')
            result = unittest.TestResult()
            with patch.dict(globals(), ROOT=root, SITE=site):
                DocumentationMigrationTests(
                    'test_manual_current_version_is_not_historical_release'
                ).run(result)
            self.assertEqual(result.errors, [])
            return result

    def test_finalized_artifact_does_not_require_a_publication_record(self):
        result = self.check_fixture('released 2026-11-18.', '2026-11-18')
        self.assertTrue(result.wasSuccessful(), result.failures)

    def test_finalized_manual_must_match_the_changelog_date(self):
        result = self.check_fixture('released 2026-11-17.', '2026-11-18')
        self.assertEqual(len(result.failures), 1)

    def test_candidate_cannot_have_a_recorded_publication(self):
        result = self.check_fixture('unpublished candidate.', 'not yet released', published=True)
        self.assertEqual(len(result.failures), 1)

    def test_invalid_calendar_date_cannot_finalize_an_artifact(self):
        result = self.check_fixture('released 2026-02-30.', '2026-02-30')
        self.assertEqual(len(result.failures), 1)

    def test_unpublished_candidate_is_valid(self):
        result = self.check_fixture('unpublished candidate.', 'not yet released')
        self.assertTrue(result.wasSuccessful(), result.failures)

    def test_published_artifact_keeps_the_same_finalized_metadata(self):
        result = self.check_fixture('released 2026-11-18.', '2026-11-18', published=True)
        self.assertTrue(result.wasSuccessful(), result.failures)

    def test_finalized_artifact_cannot_keep_candidate_wording(self):
        result = self.check_fixture('unpublished candidate.', '2026-11-18')
        self.assertEqual(len(result.failures), 1)

    def test_undated_candidate_cannot_claim_a_release(self):
        result = self.check_fixture('released 2026-11-18.', 'not yet released')
        self.assertEqual(len(result.failures), 1)
