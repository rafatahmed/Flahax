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

KINDS = ('waters', 'formulas', 'stores', 'acids', 'sessions', 'results')


def default_root():
    """Where saved items live: ``$FLAHAX_HOME``, or ``~/.flahax``."""
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
    """Saved waters, formulas, fertilizer stores, acids and sessions as JSON files."""

    def __init__(self, root=None):
        self.root = Path(root) if root is not None else default_root()

    def path(self, kind, name):
        """The JSON file for a saved item; raises DeliveryError for an unknown kind."""
        if kind not in KINDS:
            raise DeliveryError(
                'invalid_value', f'unknown saved-item kind {kind!r}; use one of {KINDS}'
            )
        return self.root / kind / f'{slug(name)}.json'

    def list(self, kind):
        """The names saved under one kind, sorted."""
        folder = self.path(kind, 'x').parent
        return sorted(p.stem for p in folder.glob('*.json')) if folder.is_dir() else []

    def load(self, kind, name):
        """A saved item; raises DeliveryError when it is missing or damaged."""
        path = self.path(kind, name)
        if not path.is_file():
            raise DeliveryError(
                'unknown_item', f'no saved {kind[:-1]} named {name!r} in {path.parent}'
            )
        from .batch_cli import read_json  # names the file and the line if it is damaged

        data = read_json(path, f'saved {kind[:-1]}')
        if kind == 'results':
            from .result_acceptance import load_result

            load_result(data)
        if kind == 'sessions':
            from .mix_cli import check_session

            check_session(data, path)
        return data

    def save(self, kind, name, data):
        """Write a saved item atomically and return its path."""
        if kind == 'sessions':
            from .mix_cli import check_session

            check_session(data, name)
            data = bind_session(self, data)
        if kind == 'results':
            from .result_acceptance import load_result

            load_result(data)
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


def session_inputs(data):
    """User answers only; stored metadata cannot grant result acceptance."""
    return {k: v for k, v in data.items() if k != 'saved_state'}


def check_saved_state(data):
    """Validate versioned answers; legacy inputs have no asserted provenance."""
    from .canonical_result import _digest

    if 'acceptance' in data or 'accepted' in data:
        raise DeliveryError('invalid_session', 'acceptance belongs to an exact saved result')
    if 'saved_state' not in data:
        return
    state = data['saved_state']
    if (
        not isinstance(state, dict)
        or set(state) != {'schema_version', 'inputs_sha256', 'references', 'sources'}
        or type(state['schema_version']) is not int
        or state['schema_version'] != 1
        or not isinstance(state['references'], dict)
        or not isinstance(state['sources'], dict)
        or state['inputs_sha256'] != _digest(session_inputs(data))
    ):
        raise DeliveryError('invalid_session', 'saved session metadata or inputs changed')


def _references(store, data):
    from .canonical_result import _digest
    from .engine import load_library

    packaged = {f['name'] for f in load_library()['formulas']}
    names = [('acids', name) for name in data['acids']]
    for kind, key, builtin in [
        ('waters', 'water', {'ro'}),
        ('formulas', 'formula', packaged),
        ('stores', 'store', {'catalogue'}),
    ]:
        if data[key] not in builtin:
            names.append((kind, data[key]))
    return {f'{kind}/{name}': _digest(store.load(kind, name)) for kind, name in names}


def bind_session(store, data):
    """Explicitly capture current answers/references; legacy provenance is not reconstructed."""
    from copy import deepcopy
    from .canonical_result import _digest, _sources

    check_saved_state(data)
    if 'saved_state' in data:
        verify_session(store, data)
        return deepcopy(data)
    result = deepcopy(data)
    result['saved_state'] = dict(
        schema_version=1,
        inputs_sha256=_digest(data),
        references=_references(store, data),
        sources=_sources(),
    )
    return result


def verify_session(store, data):
    """Detect reference/model drift before running saved answers. Legacy answers rerun normally."""
    from .canonical_result import _sources

    check_saved_state(data)
    if 'saved_state' not in data:
        return
    state = data['saved_state']
    if state['references'] != _references(store, data) or state['sources'] != _sources():
        raise DeliveryError(
            'stale_session', 'saved inputs or model changed; review and resave answers'
        )


def migrate_session(store, data):
    """Explicitly rebind reviewed answers to current inputs; discard all old consent metadata.

    This returns a new object without writing the old session or claiming its history.
    Call Store.save only after reviewing the returned answers and referenced inputs.
    """
    from .mix_cli import check_session

    if not isinstance(data, dict):
        raise DeliveryError('invalid_session', 'session must be an object')
    answers = {k: v for k, v in data.items() if k not in ('saved_state', 'acceptance', 'accepted')}
    check_session(answers, 'migration')
    return bind_session(store, answers)
