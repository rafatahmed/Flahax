# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Saved items for ``flahax mix``: plain JSON files ``flahax batch`` also reads.

The root is ``$FLAHAX_HOME``, else ``~/.flahax``. Kinds: ``waters`` (the ``--water``
format), ``formulas`` (``--targets``), ``stores`` (``--products``), ``acids``
(``{"formula", "fraction", "density", "name"}``) and ``sessions`` (``mix`` only; they
refer to the other items by name). A save writes a temporary file and renames it, so
a file is never left half written.
"""

import json
import os
from pathlib import Path
import re
import tempfile

from .delivery_contracts import DeliveryError

KINDS = ('waters', 'formulas', 'stores', 'acids', 'sessions')


def default_root():
    return Path(os.environ.get('FLAHAX_HOME') or Path.home() / '.flahax')


def slug(name):
    """``Well 104`` -> ``well-104``: lower case letters, digits and single hyphens."""
    text = re.sub(r'[^a-z0-9]+', '-', str(name).lower()).strip('-')
    if not text:
        raise DeliveryError(
            'invalid_value', f'{name!r} needs at least one letter or digit to be saved'
        )
    return text


class Store:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else default_root()

    def path(self, kind, name):
        if kind not in KINDS:
            raise DeliveryError(
                'invalid_value', f'unknown saved-item kind {kind!r}; use one of {KINDS}'
            )
        return self.root / kind / f'{slug(name)}.json'

    def list(self, kind):
        folder = self.path(kind, 'x').parent
        return sorted(p.stem for p in folder.glob('*.json')) if folder.is_dir() else []

    def load(self, kind, name):
        path = self.path(kind, name)
        if not path.is_file():
            raise DeliveryError(
                'unknown_item', f'no saved {kind[:-1]} named {name!r} in {path.parent}'
            )
        from .batch_cli import read_json  # names the file and the line if it is damaged

        return read_json(path, f'saved {kind[:-1]}')

    def save(self, kind, name, data):
        path = self.path(kind, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(prefix=f'.{path.stem}-', suffix='.tmp', dir=path.parent)
        try:
            with os.fdopen(handle, 'wb') as stream:
                stream.write(
                    (
                        json.dumps(data, indent=1, ensure_ascii=False, allow_nan=False) + '\n'
                    ).encode('utf-8')
                )
            os.replace(temp, path)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise
        return path
