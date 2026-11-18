# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Release metadata and documentation must agree with the package
checkout.
"""

from pathlib import Path
import re
import contextlib
import io
import tomllib
import unittest
from urllib.parse import unquote, urlsplit

import flahax

ROOT = Path(__file__).resolve().parents[1]


class ReleaseHygieneTests(unittest.TestCase):
    def test_readme_quick_start(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        examples = re.findall(r'```python\n(.*?)```', readme, re.S)
        self.assertTrue(examples)
        for index, example in enumerate(examples):
            with self.subTest(example=index), contextlib.redirect_stdout(io.StringIO()):
                exec(
                    compile(example, f'README example {index}', 'exec'), {'__name__': '__readme__'}
                )

    def test_readme_markdown_links_are_portable_to_pypi(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        targets = re.findall(r'\]\(([^)]+)\)', readme)
        invalid = [
            target
            for target in targets
            if not target.startswith('#')
            and urlsplit(target).scheme not in ('https', 'http', 'mailto')
        ]
        self.assertEqual(invalid, [], 'README links must resolve outside a repository checkout')

    def test_shipped_manual_examples(self):
        from importlib.resources import files

        manual = files('flahax').joinpath('data/USER_GUIDE.md').read_text(encoding='utf-8')
        self.assertIn(f'FlahaX {flahax.__version__}', manual)
        examples = re.findall(r'```python\n(.*?)```', manual, re.S)
        self.assertTrue(examples, 'the shipped manual must include executable examples')
        for index, example in enumerate(examples):
            with self.subTest(example=index + 1), contextlib.redirect_stdout(io.StringIO()):
                exec(
                    compile(example, f'USER_GUIDE example {index + 1}', 'exec'),
                    {'__name__': '__manual__'},
                )

    def test_public_api_reference_is_current(self):
        from tools.generate_api_reference import DESTINATION, render

        reference = DESTINATION.read_text(encoding='utf-8')
        self.assertEqual(reference, render())
        names = re.findall(r'^### `([^`]+)`$', reference, re.M)
        self.assertEqual(sorted(names), sorted(flahax.__all__))

    def test_public_exports_and_release_version(self):
        project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
        self.assertEqual(project['version'], flahax.__version__)
        self.assertEqual(project['dependencies'], [])
        self.assertEqual(len(flahax.__all__), len(set(flahax.__all__)))
        for name in flahax.__all__:
            self.assertTrue(hasattr(flahax, name), name)
        # Between releases main carries <next>.devN (#99); the citation
        # names the latest release.
        cited = project['version']
        if '.dev' in cited:
            changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
            cited = re.search(r'(?m)^## \[(\d+\.\d+\.\d+)\] - \d{4}-', changelog).group(1)
            self.assertLess(
                tuple(map(int, cited.split('.'))),
                tuple(map(int, project['version'].split('.dev')[0].split('.'))),
            )
        citation = (ROOT / 'CITATION.cff').read_text(encoding='utf-8')
        self.assertRegex(citation, rf'(?m)^version:\s*[\"\']?{re.escape(cited)}[\"\']?\s*$')

    def test_local_documentation_links_resolve(self):
        documents = list(ROOT.glob('*.md')) + list((ROOT / 'docs').rglob('*.md'))
        for document in documents:
            text = document.read_text(encoding='utf-8')
            for target in re.findall(r'\]\(([^)]+)\)', text):
                if re.match(r'^[a-zA-Z][\w+.-]*:', target) or target.startswith('#'):
                    continue
                path = unquote(target.split('#', 1)[0].strip('<>'))
                if path:
                    with self.subTest(document=str(document.relative_to(ROOT)), target=target):
                        self.assertTrue((document.parent / path).is_file(), target)
