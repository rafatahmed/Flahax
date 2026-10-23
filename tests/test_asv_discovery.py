# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The ASV suite must import the way ASV discovers it (#64).

ASV makes only the benchmark package importable, through its own meta-path
importer (asv_runner._aux.update_sys_path), and imports every module under it.
The repository root is not on sys.path, so a module there that imports `tools`
(or a development-only package) aborts discovery and no timing runs.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DISCOVER = r"""
import importlib, importlib.machinery, importlib.util, json, os, pkgutil, sys
root, benchmark_dir = sys.argv[1], sys.argv[2]
sys.path[:] = [p for p in sys.path if p and os.path.abspath(p) != root]
package = os.path.basename(benchmark_dir)

class OnlyBenchmarks:
    # Like asv_runner's SpecificImporter: resolve the benchmark package and nothing else.
    def find_spec(self, name, path=None, target=None):
        if name == package or name.startswith(package + "."):
            return importlib.machinery.PathFinder.find_spec(name, [os.path.dirname(benchmark_dir)]
                                                            if name == package else path)
        return None

sys.meta_path.insert(0, OnlyBenchmarks())
imported = []
def walk(name):
    module = importlib.import_module(name)
    imported.append(name)
    for _, child, _ in pkgutil.iter_modules(getattr(module, "__path__", []), name + "."):
        walk(child)
walk(package)
print(json.dumps(imported))
"""


class AsvDiscoveryTests(unittest.TestCase):
    def test_every_benchmark_module_imports_without_the_repository_root(self):
        config = json.loads((ROOT / "asv.conf.json").read_text())
        benchmark_dir = (ROOT / config["benchmark_dir"]).resolve()
        run = subprocess.run(
            [sys.executable, "-c", DISCOVER, str(ROOT), str(benchmark_dir)],
            cwd=benchmark_dir.parent.parent,
            capture_output=True,
            text=True,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        imported = json.loads(run.stdout)
        self.assertIn(f"{benchmark_dir.name}.performance", imported)


if __name__ == "__main__":
    unittest.main()
