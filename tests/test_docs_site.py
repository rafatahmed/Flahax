"""The Read the Docs site source must be configured, pinned and free of private material."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'docs' / 'site'


class DocsSiteTests(unittest.TestCase):
    def test_readthedocs_config(self):
        if not (ROOT / '.readthedocs.yaml').exists():
            self.skipTest('repository-checkout-only check')
        text = (ROOT / '.readthedocs.yaml').read_text(encoding='utf-8')
        for needle in ('version: 2', 'configuration: docs/site/conf.py', 'fail_on_warning: true',
                       'docs/site/requirements.txt', 'python: "3.13"'):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_docs_requirements_pinned(self):
        if not (SITE / 'requirements.txt').exists():
            self.skipTest('repository-checkout-only check')
        lines = [line.strip() for line in (SITE / 'requirements.txt').read_text(encoding='utf-8').splitlines()]
        lines = [line for line in lines if line and not line.startswith('#')]
        names = set()
        for line in lines:
            with self.subTest(line=line):
                self.assertRegex(line, r'^[A-Za-z0-9_.-]+==[0-9][^ ]*$')
            names.add(line.split('==')[0].lower())
        for required in ('sphinx', 'myst-parser', 'furo'):
            self.assertIn(required, names)

    def test_site_excludes_private_material(self):
        forbidden = {'development-roadmap.md', 'implementation-roadmap.md', 'development-status.md',
                     'release-readiness.md', 'publishing.md', 'documentation-maintenance.md',
                     'landscape-comparison-swot.md', 'delivery-control-design.md',
                     'stock-conductivity-service-design.md'}
        for path in SITE.rglob('*'):
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertFalse(path.name.lower().endswith('.pdf'))
                self.assertNotIn(path.name, forbidden)
                relative = path.relative_to(SITE).as_posix().lower()
                self.assertNotIn('superpowers', relative)
                self.assertNotIn('publication', relative)

    def test_published_readme_paths_resolve(self):
        names = ('method usage chemistry-coverage-matrix computational-review delivery-contracts '
                 'delivery-quantities equilibrium-kernel fertilizer-equilibrium-model '
                 'full-fertilizer-chemistry package-verification ph-planning reference-fixtures '
                 'release-evidence stock-planning site-planning index publishing '
                 'implementation-roadmap release-readiness development-roadmap development-status '
                 'delivery-control-design stock-conductivity-service-design').split()
        for name in names:
            with self.subTest(name=name):
                old = ROOT / 'docs' / f'{name}.md'
                self.assertTrue(old.exists(), f'{old} must exist for published READMEs')
                if name != 'index' and any(SITE.rglob(f'{name}.md')):
                    self.assertIn('https://flahax.readthedocs.io/', old.read_text(encoding='utf-8'))
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
        text = (ROOT / 'tools' / 'build_chemistry_model.py').read_text(encoding='utf-8')
        self.assertIn('docs/site/models/chemistry-coverage-matrix.md', text)
        self.assertNotIn("'docs/chemistry-coverage-matrix.md'", text)

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
