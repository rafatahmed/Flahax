#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Measure import, first-call and solver work, and compare it with agreed budgets (#347).

Run from the repository root:

    python -m tools.performance_budgets check
    python -m tools.performance_budgets measure --output build/performance.json
    python -m tools.performance_budgets write-budgets

Counts (modules loaded, equilibrium solves, Newton iterations) do not depend on the machine, so
``check`` fails when one exceeds its ceiling in ``benchmarks/budgets.json``. Timings depend on the
machine, so each is divided by a fixed pure-Python calibration loop timed in the same run; a
relative median above its budget is reported, and fails only with ``--strict-timing``. The
standard library only; compiled bytecode is created first so imports are not recompiled.
"""

import argparse
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BUDGETS = ROOT / 'benchmarks' / 'budgets.json'
FIXTURES = (
    'products/mixed_products',
    'phases/calcite',
    'phases/mixed_product_phases',
    'products/mixed_target_ph_nitric',
)
GRID = (5.5, 5.75, 6.0, 6.25, 6.5, 6.75, 7.0, 7.25, 7.5)
INFORMATIONAL = ('first_call.modules',)
TIMED = ('import', 'first_call', 'second_call')
TIMING_SLACK = 3.0
TARGETS = {'Ca': 100.0, 'K': 150.0, 'Mg': 40.0, 'P': 40.0, 'S': 60.0, 'N': 150.0}
WATER = {'Ca': 20.0, 'Mg': 5.0, 'N_NO3': 2.0}

PROCESS_SCRIPT = """
import json, sys, time
sys.path.insert(0, {src!r})
start = time.perf_counter()
import flahax
imported = time.perf_counter()
bare = sorted(m for m in sys.modules if m.startswith('flahax.'))
salts = flahax.load_library()['salts']
flahax.recommend(salts, {targets!r}, {water!r})
first = time.perf_counter()
flahax.recommend(salts, {targets!r}, {water!r})
second = time.perf_counter()
print(json.dumps({{
    'import_ms': (imported - start) * 1000,
    'first_call_ms': (first - imported) * 1000,
    'second_call_ms': (second - first) * 1000,
    'modules_after_first_call': len(sys.modules),
    'flahax_modules_after_first_call': len([m for m in sys.modules if m.startswith('flahax.')]),
    'flahax_modules_after_import': len(bare),
}}))
"""


def bytecode_environment():
    """The child environment with bytecode writing allowed, so imports are not recompiled."""
    env = dict(os.environ)
    env.pop('PYTHONDONTWRITEBYTECODE', None)
    return env


def compile_package():
    subprocess.run(
        [sys.executable, '-m', 'compileall', '-q', str(ROOT / 'src' / 'flahax')],
        check=True,
        env=bytecode_environment(),
    )


def counted(function):
    """Wrap an aqueous solve so the calls and Newton iterations are summed."""
    state = {'solves': 0, 'iterations': 0}

    def wrapper(*args, **kwargs):
        result = function(*args, **kwargs)
        state['solves'] += 1
        state['iterations'] += result.iterations
        return result

    return wrapper, state


def measure_counts():
    """Machine-independent work: solves and Newton iterations for fixed cases."""
    sys.path.insert(0, str(ROOT / 'src'))
    sys.path.insert(0, str(ROOT))
    from benchmarks.cases import read_fixture, solve_fixture
    from flahax import aqueous_model
    from flahax.ratio_ph_refinement import warm_started

    counts = {}
    original = aqueous_model.solve
    for name in FIXTURES:
        wrapper, state = counted(original)
        aqueous_model.solve = wrapper
        try:
            solve_fixture(read_fixture(name))
        finally:
            aqueous_model.solve = original
        key = name.replace('/', '_')
        counts[f'{key}.solves'] = state['solves']
        counts[f'{key}.iterations'] = state['iterations']
    totals = read_fixture('products/mixed_products')['runtime_totals']
    cold = sum(original(totals, ph).iterations for ph in GRID)
    iterations = []

    def seeded(ph, start):
        result = original(totals, ph, start=start)
        iterations.append(result.iterations)
        return result

    solve_at = warm_started(seeded)
    for ph in GRID:
        solve_at(ph)
    counts['ph_grid.cold_iterations'] = cold
    counts['ph_grid.warm_iterations'] = sum(iterations)
    return counts


def run_process(repeats):
    script = PROCESS_SCRIPT.format(src=str(ROOT / 'src'), targets=TARGETS, water=WATER)
    runs = []
    for _ in range(repeats):
        done = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            check=True,
            env=bytecode_environment(),
            timeout=120,
        )
        runs.append(json.loads(done.stdout))
    return runs


def calibration():
    """Best of five runs of a fixed pure-Python loop, in milliseconds."""
    best = math.inf
    for _ in range(5):
        start = time.perf_counter()
        total = 0.0
        for i in range(1, 200_000):
            total += math.sqrt(i) / (i + 1.5)
        best = min(best, time.perf_counter() - start)
    return best * 1000


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)]


def measure(repeats):
    compile_package()
    runs = run_process(repeats)
    scale = calibration()
    timings = {}
    for name in TIMED:
        values = [run[f'{name}_ms'] for run in runs]
        median = statistics.median(values)
        timings[name] = {
            'median_ms': round(median, 3),
            'p90_ms': round(percentile(values, 0.9), 3),
            'relative_median': round(median / scale, 4),
        }
    counts = measure_counts()
    first = runs[0]
    counts['import.flahax_modules'] = first['flahax_modules_after_import']
    counts['first_call.flahax_modules'] = first['flahax_modules_after_first_call']
    counts['first_call.modules'] = first['modules_after_first_call']
    return {
        'metadata': metadata(repeats, scale),
        'counts': counts,
        'timings': timings,
    }


def metadata(repeats, scale):
    sys.path.insert(0, str(ROOT / 'src'))
    import flahax

    return {
        'flahax': getattr(flahax, '__version__', None),
        'python': platform.python_version(),
        'implementation': platform.python_implementation(),
        'platform': platform.platform(),
        'machine': platform.machine(),
        'repeats': repeats,
        'calibration_ms': round(scale, 3),
        'bytecode_precompiled': True,
    }


def compare(measured, budgets, strict_timing=False):
    """Return (failures, warnings) of a measurement against the budgets."""
    failures, warnings = [], []
    for name, ceiling in budgets['counts'].items():
        value = measured['counts'].get(name)
        if value is None:
            failures.append(f'{name}: not measured')
        elif value > ceiling:
            failures.append(f'{name}: {value} exceeds the ceiling {ceiling}')
    cold = measured['counts'].get('ph_grid.cold_iterations')
    warm = measured['counts'].get('ph_grid.warm_iterations')
    limit = budgets.get('max_warm_over_cold')
    if cold and warm is not None and limit is not None and warm > limit * cold:
        failures.append(f'ph_grid: warm start needs {warm} of {cold} iterations, limit {limit}')
    for name, budget in budgets.get('timings_relative_median', {}).items():
        timing = measured['timings'].get(name)
        if timing is None:
            failures.append(f'{name}: timing not measured')
        elif timing['relative_median'] > budget:
            message = f'{name}: relative median {timing["relative_median"]} exceeds {budget}'
            (failures if strict_timing else warnings).append(message)
    return failures, warnings


def count_ceiling(name, value):
    """Exact for module and solve counts; iteration counts get 10 percent, at least 2."""
    if name.endswith('iterations'):
        return value + max(2, -(-value // 10))
    return value


def budgets_from(measured):
    counts = {
        name: count_ceiling(name, value)
        for name, value in measured['counts'].items()
        if name not in INFORMATIONAL
    }
    return {
        'note': (
            'Counts are ceilings: the measured value for modules and solves (so one extra '
            'module or solve fails), the measured value plus 10 percent (at least 2) for '
            'Newton iterations, '
            'which can differ by a step between platform math libraries. The total module count '
            'depends on the Python version and is recorded only. Timings are medians '
            'relative to a fixed calibration loop, budgeted at 3 times the measured value. '
            'Regenerate only for an intended change: '
            'python -m tools.performance_budgets write-budgets'
        ),
        'recorded_with': measured['metadata'],
        'measured_timings': measured['timings'],
        'counts': counts,
        'max_warm_over_cold': 0.6,
        'timings_relative_median': {
            name: round(value['relative_median'] * TIMING_SLACK, 4)
            for name, value in measured['timings'].items()
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=('measure', 'check', 'write-budgets'))
    parser.add_argument('--repeats', type=int, default=7)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--strict-timing', action='store_true')
    args = parser.parse_args(argv)
    measured = measure(args.repeats)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(measured, indent=1, sort_keys=True) + '\n', 'utf-8')
    if args.command == 'measure':
        print(json.dumps(measured, indent=1, sort_keys=True))
        return 0
    if args.command == 'write-budgets':
        text = json.dumps(budgets_from(measured), indent=1, sort_keys=True) + '\n'
        BUDGETS.write_text(text, encoding='utf-8', newline='\n')
        print(f'wrote {BUDGETS}')
        return 0
    failures, warnings = compare(
        measured, json.loads(BUDGETS.read_text(encoding='utf-8')), args.strict_timing
    )
    for message in warnings:
        print(f'warning: {message}')
    for message in failures:
        print(f'FAIL: {message}')
    print('performance budgets: ' + ('FAILED' if failures else 'ok'))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
