#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Partition the complete unittest inventory without splitting shared fixtures.

Weights are scheduling hints from Linux run 43774097468, not test-selection rules
or performance guarantees. New tests receive a default weight and still execute.
"""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def partition(suite, weights, count):
    groups = defaultdict(list)
    for case in flatten(suite):
        cls = type(case)
        module = sys.modules[cls.__module__]
        name = case.id().rsplit('.', 1)[0]
        if hasattr(module, 'setUpModule') or hasattr(module, 'tearDownModule'):
            name = cls.__module__
        elif weights.get(name, 0) > 120 and (
            cls.setUpClass.__func__ == unittest.TestCase.setUpClass.__func__
            and cls.tearDownClass.__func__ == unittest.TestCase.tearDownClass.__func__
        ):
            name = case.id()
        groups[name].append(case.id())
    weighted = [
        (weights.get(name, weights.get(name.rsplit('.', 1)[0], 1)), name, ids)
        for name, ids in groups.items()
    ]
    shards, loads = [[] for _ in range(count)], [0] * count
    for weight, name, ids in sorted(weighted, key=lambda row: (-row[0], row[1])):
        index = min(range(count), key=lambda i: (loads[i], i))
        shards[index].append(ids)
        loads[index] += weight
    return shards


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def collect():
    return unittest.defaultTestLoader.discover('tests', top_level_dir='.')


def measure(output, ids):
    suite = unittest.defaultTestLoader.loadTestsFromNames(ids)
    selected = [case.id() for case in flatten(suite)]
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.wasSuccessful() and result.testsRun == len(selected) > 0
    write(
        output,
        dict(
            tests=result.testsRun,
            test_ids=selected,
            failures=len(result.failures),
            errors=len(result.errors),
            skipped=[(t.id(), reason) for t, reason in result.skipped],
            passed=passed,
        ),
    )
    return 0 if passed else 1


def execute(item):
    output, ids = item
    started = time.monotonic()
    command = [sys.executable]
    coverage = sys.modules.get('coverage')
    if coverage is not None and coverage.Coverage.current() is not None:
        # Coverage-aware tests disable automatic subprocess saving when they
        # construct Coverage objects. An explicit runner always saves its data.
        command += ['-m', 'coverage', 'run']
    command += ['-m', 'tools.ci_parallel', '--output', str(output), '--group', *ids]
    with output.with_suffix('.log').open('w', encoding='utf-8') as log:
        try:
            process = subprocess.run(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=1800,
            )
        except subprocess.TimeoutExpired:
            print(
                f'::error::{ids[0]} exceeded 1800 seconds; see {output.with_suffix(".log")}',
                flush=True,
            )
            raise
    result = json.loads(output.read_text(encoding='utf-8'))
    if result['test_ids'] != ids or result['tests'] != len(ids):
        raise ValueError('worker test inventory differs from assigned cases')
    result['passed'] = result['passed'] and process.returncode == 0
    print(
        f'{ids[0]}: {len(ids)} tests, {time.monotonic() - started:.2f}s, '
        f'passed={result["passed"]}',
        flush=True,
    )
    if not result['passed']:
        print(output.with_suffix('.log').read_text(encoding='utf-8'), flush=True)
    return result


def run(output, index=0, count=1, workers=3, *, suite=None, weights=None):
    if not 0 <= index < count or workers < 1:
        raise ValueError('invalid shard index/count or worker count')
    output.mkdir(parents=True, exist_ok=True)
    if weights is None:
        weights = json.loads(Path(__file__).with_name('ci_test_weights.json').read_text())
    shards = partition(collect() if suite is None else suite, weights, count)
    all_ids = sorted(t for shard in shards for group in shard for t in group)
    if not all_ids or len(all_ids) != len(set(all_ids)) or not shards[index]:
        raise ValueError('empty or duplicate test inventory')
    groups = [(output / f'group-{i}.json', ids) for i, ids in enumerate(shards[index])]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(execute, groups))
    passed = all(r['passed'] for r in results)
    write(
        output / 'tests.json',
        dict(
            tests=sum(r['tests'] for r in results),
            failures=sum(r['failures'] for r in results),
            errors=sum(r['errors'] for r in results),
            skipped=[item for r in results for item in r['skipped']],
            passed=passed,
            test_ids=sorted(t for r in results for t in r['test_ids']),
            inventory=all_ids,
            shard_index=index,
            shard_count=count,
        ),
    )
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--shard-index', type=int, default=0)
    parser.add_argument('--shard-count', type=int, default=1)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--group', nargs='+')
    args = parser.parse_args()
    if args.group:
        return measure(args.output, args.group)
    return run(args.output, args.shard_index, args.shard_count, args.workers)


if __name__ == '__main__':
    raise SystemExit(main())
