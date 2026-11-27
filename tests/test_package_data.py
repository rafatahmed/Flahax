# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Packaged data is read directly, with the same content as
importlib.resources, and a fresh first call does not import it (#342).
"""

from importlib.resources import files
import os
from pathlib import Path
import subprocess
import sys
import unittest

from flahax.package_data import read_bytes, read_text

ROOT = Path(__file__).resolve().parents[1]
DATA = sorted(p.name for p in (ROOT / 'src' / 'flahax' / 'data').iterdir() if p.is_file())


class PackageDataTests(unittest.TestCase):
    def test_every_data_file_reads_like_importlib_resources(self):
        self.assertIn('library.json', DATA)
        for name in DATA:
            with self.subTest(name=name):
                resource = files('flahax').joinpath(f'data/{name}')
                self.assertEqual(read_bytes(f'data/{name}'), resource.read_bytes())
                self.assertEqual(read_text(f'data/{name}'), resource.read_text(encoding='utf-8'))

    def test_first_recommend_does_not_import_importlib_resources_or_pathlib(self):
        script = (
            'import sys, flahax\n'
            "flahax.recommend(flahax.load_library()['salts'], {'Ca': 100.0, 'N': 150.0}, {})\n"
            "names = ('importlib.resources', 'tempfile', 'pathlib')\n"
            'print(sorted(m for m in names if m in sys.modules))'
        )
        env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src')}
        shown = subprocess.run(
            [sys.executable, '-c', script], capture_output=True, text=True, check=True, env=env
        ).stdout.strip()
        self.assertEqual(shown, '[]')


if __name__ == '__main__':
    unittest.main()
