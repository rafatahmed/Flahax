# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Every Python file starts with the FlahaX header in PEP 8 order (template of 2026-10-23)."""

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('src', 'tests', 'tools', 'examples', 'benchmarks')
SHEBANG = '#!/usr/bin/env python3\n'
HEADER = (
    '# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.\n'
    '# SPDX-License-Identifier: Apache-2.0\n'
    '# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);\n'
    '# its results are calculations, not dosing instructions.\n'
)


def python_files():
    for folder in FOLDERS:
        yield from sorted((ROOT / folder).rglob('*.py'))


class FileHeaderTests(unittest.TestCase):
    def test_header_then_docstring(self):
        for path in python_files():
            with self.subTest(file=str(path.relative_to(ROOT))):
                text = path.read_text(encoding='utf-8')
                runnable = path.parts[len(ROOT.parts)] in ('tools', 'examples') and (
                    "__name__ == '__main__'" in text or '__name__ == "__main__"' in text
                )
                self.assertEqual(
                    text.startswith(SHEBANG), runnable, 'shebang only on runnable scripts'
                )
                body = text[len(SHEBANG) :] if runnable else text
                self.assertTrue(body.startswith(HEADER), 'missing or altered header')
                tree = ast.parse(body)
                self.assertIsNotNone(
                    ast.get_docstring(tree), 'module docstring must follow the header'
                )
                self.assertNotIn('coding:', body.splitlines()[0])

    def test_package_dunders_come_before_imports(self):
        tree = ast.parse((ROOT / 'src' / 'flahax' / '__init__.py').read_text(encoding='utf-8'))
        kinds = [
            'import' if isinstance(n, (ast.Import, ast.ImportFrom)) else 'other'
            for n in tree.body[1:]
        ]
        self.assertEqual(
            kinds, sorted(kinds, key=lambda k: k == 'import'), '__all__/__version__ first'
        )


if __name__ == '__main__':
    unittest.main()
