#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Validate disposition of a numeric inventory without mistaking audit for qualification.

The external review register maps every current inventory entry to a reviewed
semantic group. Inherited, unqualified decisions remain explicit downstream work.
No physical/numerical value is adopted merely because a citation or group exists.
"""

import argparse
import hashlib
import json
from pathlib import Path

if __package__:
    from .inventory_numeric_decisions import inventory
else:
    from inventory_numeric_decisions import inventory

CATEGORIES = {'scientific', 'numerical', 'policy', 'input', 'structural'}
DISPOSITIONS = {'retain_unqualified', 'structural', 'qualified'}


def validate(register, root, evidence_root, *, require_qualified=False):
    """Return missing, stale or unsupported review dispositions; never qualify science."""
    try:
        return _validate(register, root, evidence_root, require_qualified)
    except (KeyError, TypeError, ValueError, AttributeError, OSError) as error:
        return [f'invalid numeric review: {error}']


def _validate(register, root, evidence_root, require_qualified):
    errors = []
    if register.get('schema_version') != 1 or register.get('audit_complete') is not True:
        errors.append('review schema or audit completion missing')
    actual = {entry['id']: entry for entry in inventory(root)}
    rows = register['entries']
    entries = {entry['id']: entry for entry in rows}
    if len(entries) != len(rows) or set(entries) != set(actual):
        errors.append('numeric inventory missing, duplicated or stale')
    groups = register['groups']
    owners = set(register['owner_tasks'])
    used = {entry.get('group') for entry in rows}
    if used != set(groups):
        errors.append('review groups must exactly match referenced groups')
    for identifier, entry in entries.items():
        original = actual.get(identifier)
        if original and entry.get('source_sha256') != original['source_sha256']:
            errors.append(f'{identifier}: source changed after review')
        if entry.get('group') not in groups:
            errors.append(f'{identifier}: missing semantic review group')
    for name, group in groups.items():
        categories = set(group.get('categories', []))
        disposition = group.get('disposition')
        if not categories or not categories <= CATEGORIES or disposition not in DISPOSITIONS:
            errors.append(f'{name}: invalid classification/disposition')
        for field in ('rationale', 'units', 'conditions', 'source_status', 'reviewer'):
            if not isinstance(group.get(field), str) or not group[field].strip():
                errors.append(f'{name}: missing {field}')
        if not group.get('owner_tasks') or not set(group['owner_tasks']) <= owners:
            errors.append(f'{name}: missing or unknown follow-up owner')
        if disposition == 'structural' and categories != {'structural'}:
            errors.append(f'{name}: scientific decisions cannot use structural exemption')
        if disposition == 'retain_unqualified':
            if group.get('adopted') is not False:
                errors.append(f'{name}: unqualified decision cannot be adopted')
            if require_qualified:
                errors.append(f'{name}: qualification still required')
        elif disposition == 'qualified':
            proof = group.get('qualification', {})
            for field in ('path', 'sha256', 'independent_method', 'applicability', 'reviewer'):
                if not proof.get(field):
                    errors.append(f'{name}: qualification missing {field}')
            if proof.get('exit_code') != 0:
                errors.append(f'{name}: qualification did not pass')
            path = evidence_root / proof.get('path', '')
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != proof.get(
                'sha256'
            ):
                errors.append(f'{name}: qualification evidence missing or changed')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('register', type=Path)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--require-qualified', action='store_true')
    args = parser.parse_args()
    register = json.loads(args.register.read_text(encoding='utf-8'))
    errors = validate(
        register, args.root, args.register.parent, require_qualified=args.require_qualified
    )
    print(json.dumps({'valid': not errors, 'errors': errors}, indent=2))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
