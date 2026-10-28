#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Bind native CI coverage to one clean candidate and fail on any exact coverage gap."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

from tools.check_coverage import inventory, validate

PLATFORMS = ('Linux', 'Windows', 'Darwin')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def candidate(root, expected):
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if not re.fullmatch('[0-9a-f]{40}', expected) or head != expected:
        raise ValueError('checkout does not match the expected candidate revision')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip():
        raise ValueError('candidate checkout must be clean')
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    return {p: digest(root / p) for p in paths if p}


def identity(root, expected):
    return dict(
        source_revision=expected,
        inputs=candidate(root, expected),
        files=inventory(root),
        configuration_sha256=digest(root / 'pyproject.toml'),
        run_id=os.environ['GITHUB_RUN_ID'],
        run_attempt=os.environ['GITHUB_RUN_ATTEMPT'],
    )


def record(root, output, expected):
    if output.exists():
        raise ValueError('preserve existing evidence; choose a new output directory')
    value = identity(root, expected)
    value.update(platform=platform.system(), python=platform.python_version())
    if value['platform'] not in PLATFORMS or sys.version_info[:2] != (3, 13):
        raise ValueError('coverage shards require native Linux/Windows/macOS Python 3.13')
    output.mkdir(parents=True)
    write(output / 'manifest.json', value)


def run_tests(output):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.discover('tests', top_level_dir='.')
    )
    write(
        output / 'tests.json',
        dict(
            tests=result.testsRun,
            failures=len(result.failures),
            errors=len(result.errors),
            skipped=[(t.id(), reason) for t, reason in result.skipped],
            passed=result.wasSuccessful() and result.testsRun > 0,
        ),
    )
    return 0 if result.wasSuccessful() and result.testsRun > 0 else 1


def report(root, output, expected):
    import coverage

    manifest = read(output / 'manifest.json')
    for key, value in identity(root, expected).items():
        if manifest.get(key) != value:
            raise ValueError('candidate or inputs changed during tests: ' + key)
    c = coverage.Coverage(data_file=str(output / '.coverage'))
    c.combine(data_paths=[str(output)], strict=True, keep=True)
    c.save()
    c.json_report(
        morfs=[str(Path(p)) for p in manifest['files']], outfile=str(output / 'coverage.json')
    )
    write(
        output / 'bundle.json',
        {
            name: digest(output / name)
            for name in ('manifest.json', 'tests.json', '.coverage', 'coverage.json')
        },
    )


def shard(root, directory, current):
    bundle = read(directory / 'bundle.json')
    names = {'manifest.json', 'tests.json', '.coverage', 'coverage.json'}
    if set(bundle) != names or any(digest(directory / n) != bundle[n] for n in names):
        raise ValueError('coverage bundle is incomplete or changed')
    manifest, tests = read(directory / 'manifest.json'), read(directory / 'tests.json')
    if any(manifest.get(k) != v for k, v in current.items()):
        raise ValueError('stale candidate, inputs, configuration or workflow run')
    if not manifest.get('python', '').startswith('3.13.'):
        raise ValueError('wrong coverage interpreter')
    if (
        tests.get('passed') is not True
        or type(tests.get('tests')) is not int
        or tests['tests'] < 1
        or tests.get('failures') != 0
        or tests.get('errors') != 0
    ):
        raise ValueError('failed or empty test shard')
    if any('optional' in reason.lower() for _, reason in tests['skipped']):
        raise ValueError('required support coverage dependency was skipped')
    return manifest


def aggregate(root, inputs, output, expected):
    import coverage

    current = identity(root, expected)
    directories = sorted(p.parent for p in inputs.glob('*/bundle.json'))
    if len(directories) != len(PLATFORMS):
        raise ValueError('exactly three native coverage shards are required')
    manifests = [shard(root, p, current) for p in directories]
    if sorted(m['platform'] for m in manifests) != sorted(PLATFORMS):
        raise ValueError('missing, duplicate or unsupported native platform')
    if output.exists():
        raise ValueError('preserve existing aggregate evidence')
    output.mkdir(parents=True)
    c = coverage.Coverage(data_file=str(output / '.coverage'))
    for directory in directories:
        data = coverage.CoverageData(basename=str(directory / '.coverage'))
        data.read()
        if not data.has_arcs():
            raise ValueError('branch measurement required in every shard')
        c.get_data().update(data, map_path=lambda name: str(Path(name.replace('\\', '/'))))
    c.save()
    c.json_report(
        morfs=[str(Path(p)) for p in current['files']], outfile=str(output / 'coverage.json')
    )
    result = validate(
        read(output / 'coverage.json'),
        current,
        current['files'],
        expected,
        current['configuration_sha256'],
    )
    write(output / 'gate.json', result)
    if not result['passed']:
        raise ValueError('exact coverage gate failed; inspect gate.json')
    c.xml_report(
        morfs=[str(Path(p)) for p in current['files']], outfile=str(output / 'coverage.xml')
    )
    xml = ET.parse(output / 'coverage.xml').getroot()
    totals = result['totals'].values()
    statements = sum(t['statements'] for t in totals)
    branches = sum(t['branches'] for t in result['totals'].values())
    if (
        int(xml.attrib['lines-valid']) != statements
        or int(xml.attrib['lines-covered']) != statements
        or int(xml.attrib['branches-valid']) != branches
        or int(xml.attrib['branches-covered']) != branches
    ):
        raise ValueError('Codecov XML differs from exact local counts')
    write(
        output / 'provenance.json',
        dict(
            **current,
            shards=[
                dict(platform=m['platform'], bundle_sha256=digest(p / 'bundle.json'))
                for p, m in zip(directories, manifests)
            ],
            xml_sha256=digest(output / 'coverage.xml'),
            report_sha256=digest(output / 'coverage.json'),
            statements=statements,
            branches=branches,
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('record', 'run', 'report', 'aggregate'))
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--candidate', required=True)
    args = parser.parse_args()
    if args.action == 'aggregate' and args.inputs is None:
        parser.error('--inputs is required for aggregation')
    if args.action == 'run':
        return run_tests(args.output)
    if args.action == 'aggregate':
        aggregate(args.root, args.inputs, args.output, args.candidate)
    else:
        {'record': record, 'report': report}[args.action](args.root, args.output, args.candidate)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
