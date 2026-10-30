# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Public example commands and docs hooks preserve partial results and output files."""

import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from examples import common, run_all, tomato_simple, tomato_advanced, tomato_report
from tests.catalogue_history import historical_catalogue

ROOT = Path(__file__).resolve().parents[1]


class ExampleCommandTests(unittest.TestCase):
    def test_real_module_commands_complete_with_qualified_output(self):
        self.enterContext(historical_catalogue())
        for name in (
            'calculated_site_planning',
            'cli_usage',
            'ec_and_injection',
            'equilibrium_delivery',
            'mixed_chemistry',
            'pepper_formulation',
            'titration_and_stocks',
            'tomato_simple',
            'tomato_advanced',
        ):
            with self.subTest(name=name), contextlib.redirect_stdout(io.StringIO()) as out:
                runpy.run_module('examples.' + name, run_name='__main__')
            self.assertTrue(out.getvalue().strip())
            if name.startswith('tomato_'):
                self.assertIn('unavailable', out.getvalue())
            if name == 'tomato_advanced':
                self.assertIn('diagnostic only', out.getvalue())
                self.assertIn('No accepted reagent plan', out.getvalue())

    # Owner catalogue: re-enable in PR 4 (G5)
    def test_presentation_handles_available_missing_and_nonfinite_values(self):
        self.enterContext(historical_catalogue())
        self.assertEqual(common.serializable([float('inf'), float('-inf')]), ['inf', '-inf'])
        with self.assertRaisesRegex(AssertionError, 'unexpectedly succeeded'):
            common.rejection(lambda: None)
        self.assertIn(
            '1.25 mS/cm', common.ec_summary(dict(ec25_ms_cm=1.25, ph=5.5, status='estimated'))
        )
        self.assertIn(
            'pH: unavailable',
            common.ec_summary(dict(ec25_ms_cm=None, ph=None, status='unavailable')),
        )
        report = tomato_simple.run()
        for ph in (5.5, None):
            report['ec']['ph'] = ph
            with (
                patch.object(tomato_simple, 'run', return_value=report),
                contextlib.redirect_stdout(io.StringIO()) as out,
            ):
                tomato_simple.main()
            self.assertNotIn('outside the', out.getvalue())
        report = tomato_advanced.run()
        report['acid']['selected'] = 'synthetic-accepted-presentation-only'
        with (
            patch.object(tomato_advanced, 'run', return_value=report),
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            tomato_advanced.main()
        self.assertNotIn('No accepted reagent plan', out.getvalue())

    def test_report_command_outputs_and_refuses_overwrite(self):
        self.enterContext(historical_catalogue())
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'reports'
            with (
                patch.object(sys, 'argv', ['run_all', '--output', str(target)]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                runpy.run_module('examples.run_all', run_name='__main__')
            report = json.loads((target / 'report.json').read_text(encoding='utf-8'))
            self.assertEqual(set(report['scenarios']), set(run_all.SCENARIOS))
            self.assertIn(
                'NOT READY FOR MIXING', (target / 'report.md').read_text(encoding='utf-8')
            )
            self.assertIn('<html', (target / 'report.html').read_text(encoding='utf-8'))
            before = {p.name: p.read_bytes() for p in target.iterdir()}
            with (
                patch.object(sys, 'argv', ['run_all', '--output', str(target)]),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as e,
            ):
                run_all.main()
            self.assertEqual(e.exception.code, 2)
            self.assertEqual(before, {p.name: p.read_bytes() for p in target.iterdir()})
            # The real scenarios were checked above; this branch checks stdout serialization.
            with (
                patch.object(run_all, 'SCENARIOS', {'small': lambda: {'assumptions': []}}),
                patch.object(sys, 'argv', ['run_all']),
                contextlib.redirect_stdout(io.StringIO()) as out,
            ):
                run_all.main()
            self.assertEqual(
                json.loads(out.getvalue())['scenarios'], {'small': {'assumptions': []}}
            )
            target = Path(folder) / 'tomato'
            with (
                patch.object(sys, 'argv', ['tomato_report', '--output', str(target)]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                runpy.run_module('examples.tomato_report', run_name='__main__')
            self.assertTrue(list(target.glob('*.html')))
            with (
                patch.object(sys, 'argv', ['tomato_report', '--output', str(target)]),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                tomato_report.main()

    def test_docs_include_hooks_are_in_memory_and_scoped(self):
        cfg = runpy.run_path(str(ROOT / 'docs/site/conf.py'))
        app = Mock()
        cfg['setup'](app)
        app.connect.assert_called_once_with('include-read', cfg['_rewrite_included_links'])
        for name, original, expected in (
            ('USER_GUIDE.md', '[api](API_REFERENCE.md)', '[api](api.md)'),
            ('API_REFERENCE.md', '[manual](USER_GUIDE.md)', '[manual](manual.md)'),
            (
                'CONTRIBUTING.md',
                '[conduct](CODE_OF_CONDUCT.md)',
                '[conduct](../project/code-of-conduct.md)',
            ),
            ('other.md', '[api](API_REFERENCE.md)', '[api](API_REFERENCE.md)'),
        ):
            content = [original]
            cfg['_rewrite_included_links'](app, Path(name), 'unused', content)
            self.assertEqual(content, [expected])

    def test_remaining_empty_presentation_and_blend_boundaries(self):
        self.enterContext(historical_catalogue())
        from types import SimpleNamespace
        from examples import visual_report

        with patch.object(tomato_advanced, 'water_mg_l', return_value={'Na': 1e9, 'Cl': 1e9}):
            self.assertEqual(
                tomato_advanced.largest_blend(SimpleNamespace(analytical_totals={})), 0
            )
        self.assertEqual(tomato_report.nutrient_charts([], 'empty'), '')
        report = {
            'notice': 'synthetic',
            'scenarios': {
                name: common.serializable(run())
                for name, run in run_all.SCENARIOS.items()
                if name != 'calculated_site'
            },
        }
        self.assertIn('<html', visual_report.render_html(report))
