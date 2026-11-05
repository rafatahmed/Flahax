# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""A pull request counts as documentation only when git says so; an error never does."""

import contextlib
import io
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import ci_scope


def git(root, *args):
    subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)


class ScopeTests(unittest.TestCase):
    def repository(self, folder, *changes):
        """A repository whose last commit changes the given paths; returns (root, base, head)."""
        root = Path(folder)
        git(root, 'init', '-q')
        git(root, 'config', 'user.email', 'ci@example.invalid')
        git(root, 'config', 'user.name', 'ci')
        git(root, 'commit', '-q', '--allow-empty', '-m', 'base')
        base = self.head(root)
        for path in changes:
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text('x', encoding='utf-8')
        git(root, 'add', '-A')
        git(root, 'commit', '-q', '--allow-empty', '-m', 'change')
        return root, base, self.head(root)

    def head(self, root):
        return subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()

    def scope(self, root, base, head):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ci_scope.main([base, head], root)
        return out.getvalue().strip()

    def test_a_readme_only_change_is_documentation(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(self.scope(*self.repository(folder, 'README.md')), 'code=false')

    def test_documentation_folders_and_the_changelog_are_documentation(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = self.repository(
                folder, 'docs/site/index.md', 'docs/site/conf.py', 'CHANGELOG.md'
            )
            self.assertEqual(self.scope(*repo), 'code=false')

    def test_a_readme_with_python_is_code(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = self.repository(folder, 'README.md', 'src/flahax/engine.py')
            self.assertEqual(self.scope(*repo), 'code=true')

    def test_a_markdown_file_inside_the_package_is_code(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = self.repository(folder, 'src/flahax/data/USER_GUIDE.md')
            self.assertEqual(self.scope(*repo), 'code=true')

    def test_an_empty_change_is_not_called_documentation(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(self.scope(*self.repository(folder)), 'code=true')

    def test_a_comparison_that_fails_fails_instead_of_reading_as_documentation(self):
        with tempfile.TemporaryDirectory() as folder:
            root, _, head = self.repository(folder, 'README.md')
            with self.assertRaises(subprocess.CalledProcessError):
                self.scope(root, 'not-a-revision', head)

    def test_the_command_line_reads_its_revisions_and_prints_the_decision(self):
        with tempfile.TemporaryDirectory() as folder:
            root, base, head = self.repository(folder, 'README.md')
            out = io.StringIO()
            with (
                patch.object(sys, 'argv', ['ci_scope.py', base, head]),
                contextlib.chdir(root),
                contextlib.redirect_stdout(out),
                self.assertRaises(SystemExit) as stop,
            ):
                runpy.run_path(str(Path(ci_scope.__file__)), run_name='__main__')
            self.assertEqual((stop.exception.code, out.getvalue().strip()), (0, 'code=false'))


if __name__ == '__main__':
    unittest.main()
