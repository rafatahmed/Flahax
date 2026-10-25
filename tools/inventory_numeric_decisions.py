#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Inventory numeric literals, comparisons, defaults and packaged numeric data for review.

Syntax does not determine scientific applicability. Every entry starts unreviewed;
the inventory is a discovery aid, not automatic qualification of a source or range.
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def python_entries(path, root):
    text = path.read_text(encoding='utf-8')
    tree = ast.parse(text)
    relative = path.relative_to(root).as_posix()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    rows = []
    for node in ast.walk(tree):
        kinds = []
        if isinstance(node, ast.Constant) and numeric(node.value):
            kinds.append('numeric_literal')
        if isinstance(node, ast.Compare):
            kinds.append('comparison')
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults + [
                d for d in node.args.kw_defaults if d is not None
            ]:
                rows.append(
                    {
                        'id': f'{relative}:{default.lineno}:{default.col_offset}:default',
                        'path': relative,
                        'line': default.lineno,
                        'syntax_kind': 'default',
                        'expression': ast.get_source_segment(text, default),
                        'function': node.name,
                        'source_sha256': digest,
                    }
                )
        for kind in kinds:
            rows.append(
                {
                    'id': f'{relative}:{node.lineno}:{node.col_offset}:{kind}',
                    'path': relative,
                    'line': node.lineno,
                    'syntax_kind': kind,
                    'expression': ast.get_source_segment(text, node),
                    'source_sha256': digest,
                }
            )
    return rows


def json_entries(path, root):
    relative = path.relative_to(root).as_posix()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    rows = []

    def visit(value, pointer):
        encoded_number = isinstance(value, str) and re.fullmatch(
            r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', value
        )
        if numeric(value) or encoded_number:
            rows.append(
                {
                    'id': f'{relative}#{pointer}',
                    'path': relative,
                    'json_pointer': pointer,
                    'syntax_kind': 'data_numeric_string' if encoded_number else 'data_number',
                    'value': value,
                    'source_sha256': digest,
                }
            )
        elif isinstance(value, dict):
            for key, item in value.items():
                escaped = str(key).replace('~', '~0').replace('/', '~1')
                visit(item, pointer + '/' + escaped)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, pointer + '/' + str(index))

    visit(json.loads(path.read_text(encoding='utf-8')), '')
    return rows


def inventory(root):
    rows = []
    for path in sorted((root / 'src/flahax').rglob('*.py')):
        rows.extend(python_entries(path, root))
    for path in sorted((root / 'src/flahax/data').glob('*.json')):
        rows.extend(json_entries(path, root))
    for row in rows:
        row.update(
            classification='unreviewed',
            applicability='unassessed',
            source_or_derivation=None,
            units=None,
            decision=None,
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('refusing to overwrite review dispositions; choose a new snapshot')
    rows = inventory(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                'entries': rows,
                'review_complete': False,
                'limitations': [
                    'String-encoded numbers and computed data '
                    'need semantic review; syntax is not '
                    'scientific qualification.'
                ],
            },
            indent=2,
        )
        + '\n',
        encoding='utf-8',
    )
    print(json.dumps({'entries': len(rows), 'reviewed': 0, 'review_complete': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
