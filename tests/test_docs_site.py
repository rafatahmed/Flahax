# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The Read the Docs site source must be configured, pinned and free of
private material.
"""

from pathlib import Path
import importlib.util
import json
import re
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'docs' / 'site'


class DocsSiteTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('yaml'), 'YAML tooling unavailable')
    def test_readthedocs_config(self):
        import yaml

        if not (ROOT / '.readthedocs.yaml').exists():
            self.skipTest('repository-checkout-only check')
        config = yaml.safe_load((ROOT / '.readthedocs.yaml').read_text(encoding='utf-8'))
        self.assertIsInstance(config, dict)
        self.assertEqual(config['version'], 2)
        self.assertEqual(config['sphinx']['configuration'], 'docs/site/conf.py')
        self.assertIs(config['sphinx']['fail_on_warning'], True)
        self.assertEqual(config['build']['tools']['python'], '3.13')
        self.assertIn({'requirements': 'docs/site/requirements.txt'}, config['python']['install'])
        self.assertIn({'method': 'pip', 'path': '.'}, config['python']['install'])

    def test_docs_requirements_pinned(self):
        if not (SITE / 'requirements.txt').exists():
            self.skipTest('repository-checkout-only check')
        lines = [
            line.strip()
            for line in (SITE / 'requirements.txt').read_text(encoding='utf-8').splitlines()
        ]
        lines = [line for line in lines if line and not line.startswith('#')]
        names = set()
        for line in lines:
            with self.subTest(line=line):
                self.assertRegex(line, r'^[A-Za-z0-9_.-]+==[0-9][^ ]*$')
            names.add(line.split('==')[0].lower())
        for required in ('sphinx', 'myst-parser', 'furo'):
            self.assertIn(required, names)

    def test_site_excludes_private_material(self):
        forbidden = {
            'development-roadmap.md',
            'implementation-roadmap.md',
            'development-status.md',
            'release-readiness.md',
            'publishing.md',
            'documentation-maintenance.md',
            'landscape-comparison-swot.md',
            'delivery-control-design.md',
            'stock-conductivity-service-design.md',
        }
        for path in SITE.rglob('*'):
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertFalse(path.name.lower().endswith('.pdf'))
                self.assertNotIn(path.name, forbidden)
                relative = path.relative_to(SITE).as_posix().lower()
                self.assertNotIn('superpowers', relative)
                self.assertNotIn('publication', relative)

    def test_site_has_no_local_user_paths(self):
        pattern = re.compile(r'[A-Za-z]:[\\/]Users[\\/]|/home/[a-z]', re.IGNORECASE)
        for path in SITE.rglob('*.md'):
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIsNone(pattern.search(path.read_text(encoding='utf-8')))

    def test_public_pages_have_no_roadmap_codes(self):
        # Release evidence cites roadmap phases and gates and explains
        # them once.
        pattern = re.compile(r'\b[PG][0-9](?:\.[0-9])?\b')
        for path in SITE.rglob('*.md'):
            if path.name == 'release-evidence.md':
                continue
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIsNone(pattern.search(path.read_text(encoding='utf-8')))

    def test_published_readme_paths_resolve(self):
        names = (
            'method usage chemistry-coverage-matrix computational-review delivery-contracts '
            'delivery-quantities equilibrium-kernel fertilizer-equilibrium-model '
            'full-fertilizer-chemistry package-verification ph-planning reference-fixtures '
            'release-evidence stock-planning site-planning index publishing '
            'implementation-roadmap release-readiness development-roadmap development-status '
            'delivery-control-design stock-conductivity-service-design'
        ).split()
        for name in names:
            with self.subTest(name=name):
                old = ROOT / 'docs' / f'{name}.md'
                self.assertTrue(old.exists(), f'{old} must exist for published READMEs')
                if name != 'index' and any(SITE.rglob(f'{name}.md')):
                    self.assertIn(
                        'https://flahax.readthedocs.io/', old.read_text(encoding='utf-8')
                    )
        audit = ROOT / 'docs' / 'audit' / '2026-10-18-materials-identity' / 'README.md'
        self.assertTrue(audit.exists())
        self.assertIn('https://flahax.readthedocs.io/', audit.read_text(encoding='utf-8'))

    def test_shipped_text_paths_resolve(self):
        for name in ('water-to-delivery', 'site-planning'):
            with self.subTest(name=name):
                old = ROOT / 'docs' / f'{name}.md'
                self.assertTrue(old.exists())
                self.assertIn('https://flahax.readthedocs.io/', old.read_text(encoding='utf-8'))

    def test_chemistry_matrix_tool_writes_site_page(self):
        from tools import build_chemistry_model

        data = json.loads((ROOT / 'src/flahax/data/chemistry_25c.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / 'docs/site/models/chemistry-coverage-matrix.md'
            destination.parent.mkdir(parents=True)
            with patch.object(build_chemistry_model, 'ROOT', root):
                build_chemistry_model.write_coverage(data)
            text = destination.read_text()
            self.assertTrue(text.startswith('# Chemistry coverage matrix\n'))
            self.assertIn(data['database_sha256'], text)
            for record in data['aqueous'] + data['phases']:
                with self.subTest(name=record['name']):
                    self.assertIn(
                        f'| `{record["name"]}` | `{record["equation"]}` | '
                        f'{record["log_k"]:g} | {record["source"]}:{record["line"]} |',
                        text,
                    )
            self.assertFalse((root / 'docs/chemistry-coverage-matrix.md').exists())

    def test_built_site_has_audit_data(self):
        built = ROOT / 'build' / 'docs-html'
        if not built.exists():
            self.skipTest('build/docs-html has not been built')
        for name in ('bench_ec.csv', 'materials-audit.csv'):
            with self.subTest(name=name):
                self.assertTrue(any(built.rglob(name)), f'{name} missing from the built site')

    def test_superpowers_ignored(self):
        if not (ROOT / '.gitignore').exists():
            self.skipTest('repository-checkout-only check')
        lines = (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines()
        self.assertIn('docs/superpowers/', [line.strip() for line in lines])


if __name__ == '__main__':
    unittest.main()
