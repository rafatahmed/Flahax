# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Work counts stay inside the agreed performance budgets (#347).

Counts (modules loaded, equilibrium solves, Newton iterations) do not depend on the machine, so
they are checked on every run. Timings are machine-dependent and are checked with
``python -m tools.performance_budgets check``, not here.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

from tools import performance_budgets as pb


def measurement(counts=None, relative=0.5):
    timings = {
        name: {'median_ms': 1.0, 'p90_ms': 2.0, 'relative_median': relative} for name in pb.TIMED
    }
    return {'metadata': {'python': 'test'}, 'counts': counts or {}, 'timings': timings}


def run_main(arguments):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = pb.main(arguments)
    return code, out.getvalue()


class PerformanceBudgetTests(unittest.TestCase):
    def test_work_counts_stay_inside_their_ceilings(self):
        budgets = json.loads(pb.BUDGETS.read_text(encoding='utf-8'))
        counts = pb.measure_counts()
        first = pb.run_process(1)[0]
        counts['import.flahax_modules'] = first['flahax_modules_after_import']
        counts['first_call.flahax_modules'] = first['flahax_modules_after_first_call']
        failures, _ = pb.compare(
            {'counts': counts, 'timings': {}}, {**budgets, 'timings_relative_median': {}}
        )
        self.assertEqual(failures, [])

    def test_a_count_over_its_ceiling_fails(self):
        budgets = {'counts': {'a': 10}}
        self.assertEqual(pb.compare({'counts': {'a': 10}, 'timings': {}}, budgets)[0], [])
        failures, _ = pb.compare({'counts': {'a': 11}, 'timings': {}}, budgets)
        self.assertEqual(len(failures), 1)
        failures, _ = pb.compare({'counts': {}, 'timings': {}}, budgets)
        self.assertEqual(failures, ['a: not measured'])

    def test_a_warm_start_that_saves_too_little_fails(self):
        budgets = {'counts': {}, 'max_warm_over_cold': 0.6}
        saved = {'ph_grid.cold_iterations': 100, 'ph_grid.warm_iterations': 60}
        self.assertEqual(pb.compare({'counts': saved, 'timings': {}}, budgets)[0], [])
        wasted = {'ph_grid.cold_iterations': 100, 'ph_grid.warm_iterations': 61}
        self.assertEqual(len(pb.compare({'counts': wasted, 'timings': {}}, budgets)[0]), 1)

    def test_a_slow_timing_warns_and_fails_only_when_strict(self):
        budgets = {'counts': {}, 'timings_relative_median': {'first_call': 3.0}}
        slow = {'counts': {}, 'timings': {'first_call': {'relative_median': 4.0}}}
        failures, warnings = pb.compare(slow, budgets)
        self.assertEqual((failures, len(warnings)), ([], 1))
        failures, warnings = pb.compare(slow, budgets, strict_timing=True)
        self.assertEqual((len(failures), warnings), (1, []))
        failures, _ = pb.compare({'counts': {}, 'timings': {}}, budgets)
        self.assertEqual(failures, ['first_call: timing not measured'])

    def test_ceilings_are_exact_for_modules_and_solves_and_loose_for_iterations(self):
        self.assertEqual(pb.count_ceiling('import.flahax_modules', 0), 0)
        self.assertEqual(pb.count_ceiling('a.solves', 9), 9)
        self.assertEqual(pb.count_ceiling('a.iterations', 10), 12)
        self.assertEqual(pb.count_ceiling('a.iterations', 200), 220)

    def test_budgets_are_written_from_a_measurement_and_pass_it(self):
        counts = {'a.iterations': 100, 'a.solves': 3, 'first_call.modules': 111}
        measured = measurement(counts)
        budgets = pb.budgets_from(measured)
        self.assertEqual(budgets['counts'], {'a.iterations': 110, 'a.solves': 3})
        self.assertEqual(pb.compare(measured, budgets), ([], []))

    def test_percentile_and_environment(self):
        self.assertEqual(pb.percentile([5, 1, 3], 0.9), 5)
        self.assertEqual(pb.percentile([7], 0.9), 7)
        with patch.dict(os.environ, {'PYTHONDONTWRITEBYTECODE': '1'}):
            self.assertNotIn('PYTHONDONTWRITEBYTECODE', pb.bytecode_environment())
        self.assertGreater(pb.calibration(), 0)

    def test_a_real_measurement_has_counts_timings_and_metadata(self):
        measured = pb.measure(1)
        self.assertEqual(measured['counts']['import.flahax_modules'], 0)
        self.assertEqual(sorted(measured['timings']), sorted(pb.TIMED))
        self.assertEqual(measured['metadata']['repeats'], 1)
        self.assertTrue(measured['metadata']['bytecode_precompiled'])

    def test_running_the_file_as_a_script_measures_and_exits_cleanly(self):
        with patch('sys.argv', ['performance_budgets', 'measure', '--repeats', '1']):
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    runpy.run_path(pb.__file__, run_name='__main__')
        self.assertEqual(raised.exception.code, 0)


class CommandTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.budgets = self.folder / 'budgets.json'
        patcher = patch.object(pb, 'BUDGETS', self.budgets)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_with(self, measured, arguments):
        with patch.object(pb, 'measure', return_value=measured):
            return run_main(arguments)

    def test_measure_prints_and_can_write_a_file(self):
        measured = measurement({'a.solves': 1})
        code, text = self.run_with(measured, ['measure'])
        self.assertEqual((code, json.loads(text)['counts']), (0, {'a.solves': 1}))
        target = self.folder / 'deeper' / 'out.json'
        self.run_with(measured, ['measure', '--output', str(target)])
        self.assertEqual(json.loads(target.read_text(encoding='utf-8')), measured)

    def test_write_budgets_then_check_passes(self):
        measured = measurement({'a.solves': 1, 'a.iterations': 50})
        code, text = self.run_with(measured, ['write-budgets'])
        self.assertEqual(code, 0)
        self.assertIn('wrote', text)
        self.assertNotIn(b'\r', self.budgets.read_bytes())
        code, text = self.run_with(measured, ['check'])
        self.assertEqual(code, 0)
        self.assertIn('performance budgets: ok', text)

    def test_check_fails_on_a_count_and_warns_on_a_timing(self):
        self.run_with(measurement({'a.solves': 1}), ['write-budgets'])
        code, text = self.run_with(measurement({'a.solves': 2}), ['check'])
        self.assertEqual(code, 1)
        self.assertIn('FAIL: a.solves: 2 exceeds the ceiling 1', text)
        slow = measurement({'a.solves': 1}, relative=50)
        code, text = self.run_with(slow, ['check'])
        self.assertEqual(code, 0)
        self.assertIn('warning: first_call', text)
        code, _ = self.run_with(slow, ['check', '--strict-timing'])
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
