# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Every public class, method and function in the package has a docstring (hardening 4)."""

import ast
from pathlib import Path
import unittest

PACKAGE = Path(__file__).resolve().parents[1] / 'src' / 'flahax'


def public_definitions(tree):
    """(name, node) for public top-level classes and functions and their public methods."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name.startswith('_'):
                continue
            yield node.name, node
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not (
                        item.name.startswith('_')
                    ):
                        yield f'{node.name}.{item.name}', item


class PublicDocstringTests(unittest.TestCase):
    def test_public_definitions_have_docstrings(self):
        missing = [
            f'{path.name}: {name}'
            for path in sorted(PACKAGE.glob('*.py'))
            for name, node in public_definitions(ast.parse(path.read_text(encoding='utf-8')))
            if not ast.get_docstring(node)
        ]
        self.assertEqual(missing, [], 'add a docstring (CONTRIBUTING, Code style)')


if __name__ == '__main__':
    unittest.main()
