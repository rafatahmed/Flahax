# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Public names load on first use without changing the import surface (#335)."""

import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def run(code):
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}
    return subprocess.run(
        [sys.executable, '-c', code], capture_output=True, text=True, check=True, env=env
    ).stdout.strip()


class LazyImportTests(unittest.TestCase):
    def test_bare_import_loads_no_submodule(self):
        loaded = run(
            'import sys, flahax; print(sorted(m for m in sys.modules '
            "if m.startswith('flahax.')))"
        )
        self.assertEqual(loaded, '[]')

    def test_using_one_name_loads_only_its_dependencies(self):
        count = run(
            'import sys, flahax; flahax.InputError; '
            "print(sorted(m for m in sys.modules if m.startswith('flahax.')))"
        )
        self.assertNotIn('report_html', count)
        self.assertNotIn('delivery_plan', count)

    def test_every_public_name_resolves_to_its_defining_object(self):
        script = (
            'import flahax, importlib\n'
            'bad = []\n'
            'for name in flahax.__all__:\n'
            '    module = importlib.import_module("." + flahax._LAZY[name], "flahax")\n'
            '    if getattr(flahax, name) is not getattr(module, name):\n'
            '        bad.append(name)\n'
            'print(bad)'
        )
        self.assertEqual(run(script), '[]')

    def test_function_named_like_its_module_survives_any_import_order(self):
        script = (
            'import flahax.material_chemistry, flahax.phase_allocation\n'
            'import flahax\n'
            'from flahax.material_chemistry import COMPLEXES\n'
            'print(callable(flahax.material_chemistry), callable(flahax.phase_allocation))'
        )
        self.assertEqual(run(script), 'True True')

    def test_submodules_and_unknown_names(self):
        script = (
            'import flahax\n'
            'print(flahax.engine.__name__)\n'
            'try:\n'
            '    flahax.no_such_name\n'
            'except AttributeError as error:\n'
            '    print(error)\n'
            'print("recommend" in dir(flahax))'
        )
        self.assertEqual(
            run(script),
            "flahax.engine\nmodule 'flahax' has no attribute 'no_such_name'\nTrue",
        )

    def test_lazy_table_matches_public_surface(self):
        import flahax

        self.assertFalse(set(flahax.__all__) - set(flahax._LAZY))


if __name__ == '__main__':
    unittest.main()
