"""Release metadata and documentation must agree with the package checkout."""
from pathlib import Path
import re
import contextlib
import io
import tomllib
import unittest
from urllib.parse import unquote

import flahax

ROOT = Path(__file__).resolve().parents[1]


class ReleaseHygieneTests(unittest.TestCase):
    def test_shipped_manual_examples(self):
        from importlib.resources import files
        manual = files('flahax').joinpath('data/USER_GUIDE.md').read_text(encoding='utf-8')
        self.assertIn(f'FlahaX {flahax.__version__}', manual)
        examples = re.findall(r'```python\n(.*?)```', manual, re.S)
        self.assertEqual(len(examples), 4)
        for index, example in enumerate(examples):
            with self.subTest(example=index + 1), contextlib.redirect_stdout(io.StringIO()):
                exec(compile(example, f'USER_GUIDE example {index + 1}', 'exec'), {'__name__': '__manual__'})

    def test_public_exports_and_release_version(self):
        project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
        self.assertEqual(project['version'], flahax.__version__)
        self.assertEqual(project['dependencies'], [])
        self.assertEqual(len(flahax.__all__), len(set(flahax.__all__)))
        for name in flahax.__all__:
            self.assertTrue(hasattr(flahax, name), name)
        citation = (ROOT / 'CITATION.cff').read_text(encoding='utf-8')
        self.assertRegex(citation, rf'(?m)^version:\s*[\"\']?{re.escape(project["version"])}[\"\']?\s*$')

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
