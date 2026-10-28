#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Check an external requirement inventory against the current public source surface."""

import argparse
import ast
import json
from pathlib import Path


def source_surface(root):
    tree = ast.parse((root / 'src/flahax/__init__.py').read_text(encoding='utf-8'))
    exports = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == '__all__' for target in node.targets
        ):
            exports = ast.literal_eval(node.value)
    files = sorted(
        path.relative_to(root).as_posix() for path in (root / 'src/flahax').rglob('*.py')
    )
    return {'exports': sorted(exports), 'runtime_files': files}


def validate(register, surface):
    """Check inventory completeness, not whether the recorded requirements are implemented."""
    errors = []
    try:
        requirements = register['requirements']
        ids = {row['id'] for row in requirements}
        if not ids or len(ids) != len(requirements):
            errors.append('missing or duplicate requirement IDs')
        if ids != set(register['required_ids']):
            errors.append('required requirement inventory mismatch')
        for row in requirements:
            if not all(
                row.get(key) for key in ('contract', 'independent_evidence', 'owner_tasks')
            ):
                errors.append(f'{row["id"]}: incomplete contract')
            if not set(row['owner_tasks']) <= set(register['task_ids']):
                errors.append(f'{row["id"]}: unknown owner')
        findings = register['findings']
        if set(findings) != set(register['required_findings']):
            errors.append('finding inventory mismatch')
        for name, links in findings.items():
            if not links or not set(links) <= ids:
                errors.append(f'{name}: missing or unknown requirements')
        for field in ('exports', 'runtime_files'):
            mapping = register[field]
            if set(mapping) != set(surface[field]):
                errors.append(f'{field}: source inventory mismatch')
            for name, links in mapping.items():
                if not links or not set(links) <= ids:
                    errors.append(f'{name}: missing or unknown requirements')
        if register.get('physical_stage_blocks_math') is not False:
            errors.append('physical validation must remain separate')
        for value in register['numerical_criteria']:
            if value['status'] not in {'structural_exact', 'qualification_required'}:
                errors.append('unqualified numerical criterion adopted')
            if not value.get('meaning') or not value.get('qualification_task'):
                errors.append('numerical criterion lacks meaning or qualification owner')
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        errors.append(f'invalid requirement register: {error}')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('register', type=Path)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    register = json.loads(args.register.read_text(encoding='utf-8'))
    errors = validate(register, source_surface(args.root))
    print(json.dumps({'valid': not errors, 'errors': errors}, indent=2))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
