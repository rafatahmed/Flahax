# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Byte identities and canonical manifest format; no chemistry calculations."""

import hashlib
import json
from pathlib import Path

MANIFEST = Path(__file__).with_name('chemistry_sources.json')
SOURCE_NAMES = ('minteq.v4.dat', 'flahax-chelates-25c.dat', 'flahax-phases-25c.dat')


def manifest_digest(sources):
    """SHA-256 of UTF-8 JSON, filename order, sorted keys, compact separators, no newline."""
    raw = json.dumps(
        sorted(sources, key=lambda row: row['filename']),
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
        allow_nan=False,
    ).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def describe_sources(raw_sources, *, allow_unpinned=False):
    """Describe exact consumed bytes; unpinned synthetic inputs require explicit opt-in."""
    pinned = {row['filename']: row for row in json.loads(MANIFEST.read_bytes())}
    result = []
    for name in SOURCE_NAMES:
        raw = raw_sources[name]
        digest = hashlib.sha256(raw).hexdigest()
        row = pinned[name]
        if digest != row['sha256'] or len(raw) != row['bytes']:
            if not allow_unpinned:
                raise ValueError(f'{name}: source bytes differ from pinned provenance')
            row = dict(
                filename=name,
                sha256=digest,
                bytes=len(raw),
                encoding='utf-8',
                origin='unverified input; not the pinned scientific source',
                transformations=[],
            )
        result.append(row)
    return result


def verify_sources(data, raw_sources):
    """Return integrity errors for the complete consumed-input manifest and legacy alias."""
    errors = []
    if hashlib.sha256(raw_sources['minteq.v4.dat']).hexdigest() != data['database_sha256']:
        errors.append('base database hash differs from pinned model')
    if data.get('schema', 1) < 2:
        errors.append('complete source manifest missing (requires schema 2)')
        return errors
    sources = data.get('sources', [])
    names = [row.get('filename') for row in sources]
    if len(names) != len(SOURCE_NAMES) or set(names) != set(SOURCE_NAMES):
        errors.append('source manifest must contain each consumed input exactly once')
        return errors
    if manifest_digest(sources) != data.get('sources_sha256'):
        errors.append('complete source manifest digest mismatch')
    for row in sources:
        name = row['filename']
        raw = raw_sources[name]
        if row.get('sha256') != hashlib.sha256(raw).hexdigest() or row.get('bytes') != len(raw):
            errors.append(f'{name}: source bytes differ from manifest')
        if row.get('encoding') != 'utf-8' or row.get('transformations') != []:
            errors.append(f'{name}: unsupported decoding or transformation policy')
    return errors
