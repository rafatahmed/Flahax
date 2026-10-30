# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The pre-owner catalogue, frozen for tests written against it.

The fixture is the byte copy of ``src/flahax/data/library.json`` at commit 33c5df2, the
data the engine-mechanics tests were written against before the owner catalogue
(Flaha Agri Tech Analysis Ver 0.0) replaced it. ``historical_catalogue()`` makes the
package load that library; ``historical_library()`` returns it parsed.
"""

from contextlib import contextmanager
import json
from pathlib import Path
import sys

import flahax.engine

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests' / 'fixtures' / 'catalogue-pre-owner-33c5df2.json'
FIXTURE_GIT_BLOB = '82f48097c58983e8cb007cfd13bdee97f311b027'
_TEXT = FIXTURE.read_text(encoding='utf-8')
_LOAD_LIBRARY = flahax.engine.load_library


def historical_library() -> dict:
    """The pre-owner library, freshly parsed so no caller can change another's copy."""
    return json.loads(_TEXT)


def _load_library():
    """The patched ``load_library``: a function of its own, so restoring it on exit never
    touches a module that imported ``historical_library`` itself."""
    return historical_library()


def _formula_names_replacement():
    """``tools.publish_benchmark_report.formula_names`` reads library.json from a source tree;
    for this repository it reads the fixture instead."""
    import tools.publish_benchmark_report as report

    original = report.formula_names

    def formula_names(source):
        if Path(source).resolve() == ROOT:
            return {f['id']: f['name'] for f in historical_library()['formulas']}
        return original(source)

    return original, formula_names


def _replacements():
    """(original, replacement) for every catalogue reader bound by name somewhere."""
    pairs = [(_LOAD_LIBRARY, _load_library)]
    if 'tools.publish_benchmark_report' in sys.modules:
        pairs.append(_formula_names_replacement())
    return pairs


def _bound(pairs):
    """(module, attribute, replacement) for every loaded module holding an original reader;
    this module keeps its own references."""
    for module in list(sys.modules.values()):
        if module is sys.modules[__name__]:
            continue
        try:
            namespace = vars(module)
        except TypeError:
            continue
        for name, value in list(namespace.items()):
            for original, replacement in pairs:
                if value is original:
                    yield module, name, replacement


def _reset_catalogue_chemistry():
    from flahax.catalogue_chemistry import _CatalogueChemistry

    _CatalogueChemistry._data = None


_ACTIVE = []


@contextmanager
def historical_catalogue():
    """Within the block, the package loads the pre-owner library.

    Patches ``flahax.engine.load_library`` and every loaded module that imported it by name
    (the package itself, batch_cli, mix_cli, ph_adjustment, fertilizer_workflow, conductivity,
    equilibrium_delivery, tools and test modules); deferred imports go through the engine.
    ``tools.publish_benchmark_report.formula_names``, which reads library.json directly, is
    patched the same way when loaded. The catalogue-chemistry cache is cleared on entry and
    exit.

    Only the outermost block patches; a nested block (for example a fixture class's
    ``setUpClass`` called from another class) changes nothing, so blocks may close in any
    order. On the last exit every binding of a replacement, including those of modules
    imported inside the block, is set back to its original.
    """
    if _ACTIVE:
        yield
        return
    pairs = _replacements()
    patched = [(module, name, getattr(module, name)) for module, name, _ in _bound(pairs)]
    for module, name, original in patched:
        setattr(module, name, dict(pairs)[original])
    _ACTIVE.append(pairs)
    _reset_catalogue_chemistry()
    try:
        yield
    finally:
        _ACTIVE.pop()
        for module, name, original in patched:
            setattr(module, name, original)
        back = {replacement: original for original, replacement in pairs}
        for module, name, replacement in list(_bound(list(back.items()))):
            setattr(module, name, back[getattr(module, name)])
        _reset_catalogue_chemistry()
