#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Reject coverage gaps, missing sources and evidence from changed source files.

Record a manifest immediately before measuring; check against it after combining
coverage. A local success is not a substitute for required native-platform CI jobs.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def inventory(root):
    paths = []
    for directory in ('src/flahax', 'tools', 'examples', 'benchmarks'):
        paths.extend((root / directory).rglob('*.py'))
    paths.append(root / 'docs/site/conf.py')
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


def validate(report, manifest, current, revision, config_hash):
    errors = []
    totals = {
        area: {'statements': 0, 'missing_statements': 0, 'branches': 0, 'missing_branches': 0}
        for area in ('runtime', 'support', 'docs_build')
    }
    try:
        if manifest['source_revision'] != revision:
            errors.append('source revision mismatch')
        if manifest['files'] != current:
            errors.append('source inventory or hash mismatch')
        if manifest['configuration_sha256'] != config_hash:
            errors.append('coverage configuration mismatch')
        if report['meta']['branch_coverage'] is not True:
            errors.append('branch measurement required')
        files = {key.replace('\\', '/'): value for key, value in report['files'].items()}
        if set(files) != set(current):
            errors.append(
                f'report inventory mismatch: missing={sorted(set(current) - set(files))}; '
                f'extra={sorted(set(files) - set(current))}'
            )
        for name, data in files.items():
            summary = data['summary']
            statements = summary['num_statements']
            branches = summary['num_branches']
            missing_lines = data['missing_lines']
            missing_branches = data['missing_branches']
            if (
                statements != len(set(data['executed_lines']) | set(missing_lines))
                or summary['missing_lines'] != len(missing_lines)
                or summary['missing_branches'] != len(missing_branches)
                or branches != len(data['executed_branches']) + len(missing_branches)
                or statements < 0
                or branches < 0
            ):
                errors.append(f'{name}: inconsistent raw counts')
            if data.get('excluded_lines'):
                errors.append(f'{name}: excluded executable lines')
            if missing_lines or missing_branches:
                errors.append(
                    f'{name}: {len(missing_lines)} missing statements, '
                    f'{len(missing_branches)} missing branch destinations'
                )
            area = (
                'runtime'
                if name.startswith('src/flahax/')
                else 'docs_build'
                if name == 'docs/site/conf.py'
                else 'support'
            )
            totals[area]['statements'] += statements
            totals[area]['branches'] += branches
            totals[area]['missing_statements'] += len(missing_lines)
            totals[area]['missing_branches'] += len(missing_branches)
        if not files or totals['runtime']['statements'] == 0:
            errors.append('empty runtime measurement')
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        errors.append(f'invalid coverage evidence: {error}')
    return {'passed': not errors, 'errors': errors, 'totals': totals}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--record-manifest', action='store_true')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    revision = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=args.root, text=True
    ).strip()
    current = inventory(args.root)
    config_hash = hashlib.sha256((args.root / 'pyproject.toml').read_bytes()).hexdigest()
    if args.record_manifest:
        if args.manifest.exists():
            parser.error('manifest already exists; preserve it and choose a new run path')
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(
                {
                    'source_revision': revision,
                    'files': current,
                    'configuration_sha256': config_hash,
                },
                indent=2,
            )
            + '\n',
            encoding='utf-8',
        )
        return 0
    if not args.report:
        parser.error('--report required when checking')
    result = validate(
        json.loads(args.report.read_text(encoding='utf-8')),
        json.loads(args.manifest.read_text(encoding='utf-8')),
        current,
        revision,
        config_hash,
    )
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    print(text, end='')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
