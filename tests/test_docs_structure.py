# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The documentation site keeps its structure: every page in the menu once, moved pages
redirected, and the command-line reference current (approved restructure, 2026-10-23)."""

from pathlib import Path
import ast
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / 'docs' / 'site'


def pages():
    """Docnames of every Markdown page of the site."""
    return {
        p.relative_to(SITE).with_suffix('').as_posix()
        for p in SITE.rglob('*.md')
        if '_static' not in p.parts and '_build' not in p.parts
    }


def menu_entries():
    """Docnames listed in every toctree of the site, resolved from the page that lists them."""
    entries = []
    for doc in sorted(pages()):
        text = (SITE / f'{doc}.md').read_text(encoding='utf-8')
        base = Path(doc).parent
        for block in re.findall(r'(?s)(?:```|:::)\{toctree\}\n(.*?)(?:```|:::)', text):
            for line in block.splitlines():
                line = line.strip()
                if line and not line.startswith(':'):
                    target = re.sub(r'^.*<(.+)>$', r'\1', line)
                    entries.append((base / target).as_posix())
    return entries


def redirects():
    tree = ast.parse((SITE / 'conf.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', None) == 'redirects':
            return ast.literal_eval(node.value)
    return {}


class DocsStructureTests(unittest.TestCase):
    def test_every_page_is_in_the_menu_once(self):
        entries = menu_entries()
        self.assertEqual(len(entries), len(set(entries)), 'a page is listed twice')
        standalone = {
            doc
            for doc in pages()
            if (SITE / f'{doc}.md').read_text(encoding='utf-8').startswith('---\norphan: true')
        }
        missing = pages() - set(entries) - standalone - {'index'}
        self.assertEqual(missing, set(), 'pages not in the menu')
        self.assertEqual(set(entries) - pages(), set(), 'menu entries without a page')

    def test_moved_pages_redirect_to_existing_pages(self):
        moved = redirects()
        self.assertIn('growers', moved)
        for old, target in moved.items():
            with self.subTest(old=old):
                self.assertNotIn(old, pages(), 'a redirect hides a real page')
                new = (Path(old).parent / target).as_posix().removesuffix('.html')
                new = Path(new).as_posix()
                resolved = (SITE / Path(old).parent / target).resolve()
                self.assertTrue(resolved.with_suffix('.md').exists(), (old, target, new))

    @unittest.skipIf(
        sys.version_info < (3, 13),
        'argparse lays help out slightly differently before 3.13; the docs build uses 3.13',
    )
    def test_command_line_reference_is_current(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / 'tools' / 'cli_reference.py'), '--check'],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
