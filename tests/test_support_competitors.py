# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Competitor adapter contracts with synthetic external engines, not comparison evidence."""

import contextlib
import importlib.util
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.competitors import chemistry_track as chemistry, ec_track as ec
from tools.competitors import formulation_track as formulation, irriblend_adapter as irriblend


@contextlib.contextmanager
def horticalc_fixture():
    chemistry_stub = SimpleNamespace(
        OXIDE_ELEMENT_RULES={'K2O': ('K', 2)}, FORM_ELEMENT_RULES={'SO4': ('S', 1)}
    )
    masses = {'K': 39.0, 'K2O': 94.0, 'S': 32.0, 'SO4': 96.0}

    def contrib(fert, mm):
        return {
            'K': fert.comp.get('K2O', 0) * 1000 * 78 / 94,
            'S': fert.comp.get('SO4', 0) * 1000 * 32 / 96,
            'N_NO3': fert.comp.get('NO3', 0) * 1000,
        }

    solver = SimpleNamespace(
        solve_recipe_data=Mock(return_value=SimpleNamespace(fertilizers=[])),
        _fertilizer_element_contrib_per_g=contrib,
    )
    modules = {
        'horticalc': SimpleNamespace(chemistry=chemistry_stub),
        'horticalc.data_io': SimpleNamespace(
            Fertilizer=SimpleNamespace, load_molar_masses=lambda: masses
        ),
        'horticalc.solver': solver,
    }
    name = 'tools.competitors.horticalc_adapter'
    previous = sys.modules.pop(name, None)
    try:
        with patch.dict(sys.modules, modules):
            adapter = importlib.import_module(name)
            yield adapter, solver
    finally:
        sys.modules.pop(name, None)
        if previous is not None:
            sys.modules[name] = previous
        import tools.competitors

        if hasattr(tools.competitors, 'horticalc_adapter'):
            del tools.competitors.horticalc_adapter


class CompetitorContractTests(unittest.TestCase):
    def test_horticalc_roundtrip_and_solver_request(self):
        with horticalc_fixture() as (adapter, solver):
            salts = [{'name': 'test', 'elements': {'K': 10, 'S': 5, 'N_NO3': 2}}]
            translated = adapter.translate(salts)
            self.assertLess(adapter.validate_translation(salts, translated), 1e-15)
            with self.assertRaises(KeyError):
                adapter._form_for('unsupported')
            result = adapter.solve(translated, {'K': 100}, {'K': 10}, 'aligned')
            self.assertIs(result, solver.solve_recipe_data.return_value)
            args = solver.solve_recipe_data.call_args
            self.assertEqual(args.kwargs['water_profile_data']['mg_per_l'], {'K': 10})
            self.assertEqual(args.args[0]['solver_config'], adapter.CONFIGS['aligned'])

    def test_irriblend_pinning_filter_and_temporary_spreadsheet(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            module = root / 'irriblend_dsw_funs.py'
            module.write_text('synthetic external module')
            with self.assertRaisesRegex(RuntimeError, 'pinned'):
                irriblend.load(root)
            fake = SimpleNamespace(ferti_eco_min=Mock())
            with (
                patch.dict(
                    irriblend.PIN,
                    {'module_sha256': hashlib.sha256(module.read_bytes()).hexdigest()},
                ),
                patch.dict(sys.modules, {'irriblend_dsw_funs': fake}),
                patch.dict(os.environ),
            ):
                self.assertIs(irriblend.load(root), fake)
                self.assertNotIn(str(root), sys.path)
            # The workbook adapter contract is exercised using a writer stub, not an XLSX claim.
            writer = Mock()
            writer.__enter__ = Mock(return_value=writer)
            writer.__exit__ = Mock(return_value=False)
            frame = Mock()
            pandas = SimpleNamespace(
                DataFrame=Mock(return_value=frame), ExcelWriter=Mock(return_value=writer)
            )
            products = [dict(id='k', name='K', elements={'K': 10})]
            with (
                patch.dict(sys.modules, {'pandas': pandas}),
                patch.object(irriblend, 'load', return_value=fake),
            ):
                adapter = irriblend.Irriblend(products)
                self.addCleanup(adapter.close)
                frame.to_excel.assert_called_once_with(writer, sheet_name='ferts')
                fake.ferti_eco_min.return_value = (None, ['K'], [1.0], [-1])
                self.assertIsNone(adapter.solve({'N_NO3': 1}, {}))
                fake.ferti_eco_min.return_value = (None, ['K'], [1.0], [1])
                self.assertEqual(
                    adapter.solve({}, {}), {'salts': [{'id': 'k', 'gramsPerLitre': 1.0}]}
                )

    @unittest.skipUnless(importlib.util.find_spec("scipy"), "optional scipy dependency")
    def test_formulation_track_preserves_no_result_and_rescores_external_output(self):
        with horticalc_fixture() as (_, solver):
            salts = [dict(id='k', name='K', elements={'K': 10})]
            library = {'salts': salts, 'formulas': [dict(name='synthetic', targets={'K': 100})]}
            external = SimpleNamespace(
                solve=Mock(return_value=None),
                close=Mock(),
                translation_error=0,
                rows={'K': {}},
                excluded={},
            )
            solver.solve_recipe_data.return_value = SimpleNamespace(
                fertilizers=[{'name': 'K', 'grams': 1}]
            )
            with (
                patch.object(formulation, 'load_library', return_value=library),
                patch.object(irriblend, 'Irriblend', return_value=external),
            ):
                report = formulation.run()
            self.assertEqual(report['summary']['irriblend_dsw']['recipes_returned'], 0)
            self.assertEqual(report['summary']['horticalc_aligned']['whole_recipes_passing'], 2)
            external.close.assert_called_once()
            for targets in ({'K': 100, 'Ca': 1, 'unknown': 1, 'Na': 0}, {'K': 100}):
                result = formulation.irriblend_method(salts, targets, {})
                if 'Ca' in targets:
                    self.assertIsNone(result)
                else:
                    self.assertAlmostEqual(result['salts'][0]['gramsPerLitre'], 1)
            with (
                tempfile.TemporaryDirectory() as folder,
                patch.object(formulation, 'run', return_value=report),
                patch.object(
                    sys, 'argv', ['formulation', '--output', str(Path(folder) / 'report.json')]
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                formulation.main()
                self.assertEqual(
                    json.loads((Path(folder) / 'report.json').read_text())['summary'],
                    report['summary'],
                )

    def test_ec_external_calls_and_status_retention(self):
        self.assertIsNone(ec.flahax_ec({'K+': 1, 'Cl-': 1})['ec_us_cm'])
        self.assertGreater(ec.flahax_ec({'K+': 0.01, 'Cl-': 0.01})['ec_us_cm'], 0)
        compute = Mock(return_value={'warnings': ['ignored']})
        with patch.dict(sys.modules, {'horticalc.ec': SimpleNamespace(compute_ec=compute)}):
            with self.assertRaisesRegex(ValueError, 'ignored'):
                ec.horticalc_ec({'K+': 0.001})
            compute.return_value = {'ec_uS_per_cm': {'25.0': 100}}
            self.assertEqual(ec.horticalc_ec({'K+': 0.001})['ec_us_cm'], 100)
        solution = SimpleNamespace(sc=123, pH=6, forget=Mock())
        pp = SimpleNamespace(add_solution=Mock(return_value=solution))
        self.assertEqual(ec.phreeqc_ec(pp, {})['ec_us_cm'], 123)
        solution.forget.assert_called_once()
        quantity = SimpleNamespace(to=lambda unit: SimpleNamespace(magnitude=456))
        with patch.dict(
            sys.modules,
            {
                'pyEQL': SimpleNamespace(
                    Solution=lambda *a, **k: SimpleNamespace(conductivity=quantity)
                )
            },
        ):
            self.assertEqual(ec.pyeql_ec({})['ec_us_cm'], 456)
        calls = {
            'good': lambda *args: dict(ec_us_cm=100, status='estimated'),
            'missing': lambda *args: dict(ec_us_cm=None, status='unavailable'),
        }
        report = ec.standards_part(calls)
        self.assertTrue(all(r['missing']['error_percent'] is None for r in report['rows']))
        self.assertIsNone(ec.summarise(report, calls, 'error_percent')['missing']['max_abs'])

    def test_phreeqpython_adapter_restores_cwd_and_validates_reference_identity(self):
        pp = SimpleNamespace(
            ip=SimpleNamespace(
                run_string=Mock(),
                get_selected_output_array=Mock(
                    return_value=[[' m_AmmH4+(mol/kgw)', 'charge(eq)'], [1, 0]]
                ),
            )
        )
        before = os.getcwd()
        rows = chemistry.phreeqpython_rows(pp, 'synthetic')
        self.assertEqual(rows, [{'m_NH4+': 1.0, 'charge': 0.0}])
        self.assertEqual(os.getcwd(), before)
        pp.ip.run_string.side_effect = RuntimeError('injected')
        with self.assertRaises(RuntimeError):
            chemistry.phreeqpython_rows(pp, 'synthetic')
        self.assertEqual(os.getcwd(), before)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = root / 'base'
            base.write_text('synthetic')
            case = root / 'case'
            case.mkdir()
            (case / 'case.pqi').write_text('synthetic')
            data = {'selected_rows': [{'pH': 6}], 'reference': {}}
            with patch.dict(
                sys.modules, {'phreeqpython': SimpleNamespace(PhreeqPython=lambda **kw: pp)}
            ):
                with self.assertRaisesRegex(ValueError, 'pinned'):
                    chemistry.run(base)
                with (
                    patch.object(chemistry, 'sha', return_value=chemistry.PINNED_BASE_SHA256),
                    patch.object(chemistry, 'merge'),
                    patch.object(chemistry, 'fixtures', return_value=[('case', case)]),
                    patch.object(chemistry, 'read_fixture', return_value=data),
                    patch.object(chemistry, 'phreeqpython_rows', return_value=[{'pH': 6}]),
                    patch.object(chemistry, 'solve_fixture', return_value=('synthetic', None)),
                    patch.object(
                        chemistry,
                        'evaluate_chemistry',
                        return_value={
                            'passes': False,
                            'checks': [{'quantity': 'test', 'passes': False}],
                        },
                    ),
                ):
                    report = chemistry.run(base)
                    self.assertEqual(report['cases'][0]['failed'], ['test'])
                    data['selected_rows'] *= 2
                    with self.assertRaisesRegex(ValueError, 'live rows'):
                        chemistry.run(base)
                    data['reference'] = {'merged_sha256': 'wrong'}
                    with self.assertRaisesRegex(ValueError, 'merged database'):
                        chemistry.run(base)

    def test_ec_catalogue_missing_and_zero_estimates_are_not_numeric_comparisons(self):
        names = ('flahax', 'horticalc', 'phreeqc', 'pyeql')
        library = {'salts': [], 'formulas': [dict(name='synthetic', targets={})]}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'database').mkdir()
            (root / 'database/phreeqc.dat').write_text('synthetic')
            module = SimpleNamespace(
                __file__=str(root / '__init__.py'), PhreeqPython=lambda **kw: None
            )
            for estimate in (None, 0.0, 100.0):
                calls = {
                    n: (lambda *a, value=estimate: dict(ec_us_cm=value, status='synthetic'))
                    for n in names
                }
                with (
                    patch.dict(sys.modules, {'phreeqpython': module}),
                    patch('flahax.load_library', return_value=library),
                    patch('flahax.recommend', return_value={'salts': []}),
                    patch.object(ec, 'engines', return_value=calls),
                    patch.object(
                        ec, 'flahax_ec', return_value=dict(ec_us_cm=estimate, status='synthetic')
                    ),
                ):
                    report = ec.run()
                row = report['catalogue']['rows'][0]
                expected = 0.0 if estimate else None
                self.assertEqual(row['spread_percent'], expected)
                self.assertEqual(row['flahax']['vs_flahax_percent'], expected)
                output = root / 'result.json'
                with (
                    patch.object(ec, 'run', return_value=report),
                    patch.object(sys, 'argv', ['ec', '--output', str(output)]),
                    patch.object(ec.logging, 'disable'),
                    patch.object(ec.warnings, 'filterwarnings'),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    ec.main()
                self.assertEqual(json.loads(output.read_text())['catalogue'], report['catalogue'])
            # Test the actual engine dispatch lambdas without optional packages.
            with (
                patch.object(ec, 'flahax_ec', return_value='a'),
                patch.object(ec, 'horticalc_ec', return_value='b'),
                patch.object(ec, 'phreeqc_ec', return_value='c'),
                patch.object(ec, 'pyeql_ec', return_value='d'),
            ):
                self.assertEqual([f({}, {}, {}) for f in ec.engines(None).values()], list('abcd'))

    def test_competitor_main_entrypoints_and_fixture_selection(self):
        import runpy

        for name in ('chemistry_track', 'ec_track', 'formulation_track'):
            with (
                patch.object(sys, 'argv', [name, '--help']),
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaises(SystemExit) as caught,
            ):
                runpy.run_module('tools.competitors.' + name, run_name='__main__')
            self.assertEqual(caught.exception.code, 0)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for group in ('products', 'phases'):
                (root / group / 'yes').mkdir(parents=True)
                (root / group / 'no').mkdir()
                (root / group / 'yes/expected.json').write_text('{}')
                (root / group / 'yes/yes.pqi').write_text('synthetic')
            with patch.object(chemistry, 'FIXTURES', root):
                self.assertEqual(len(list(chemistry.fixtures())), 2)
            report = {
                'merged_sha256': 'synthetic',
                'cases': [
                    dict(
                        fixture='synthetic',
                        replay_max_difference=0.0,
                        flahax_passes=False,
                        checks=1,
                        phreeqpython_ms=1.0,
                        flahax_ms=1.0,
                        failed=['synthetic'],
                    )
                ],
            }
            with (
                patch.object(chemistry, 'run', return_value=report),
                patch.object(
                    sys,
                    'argv',
                    ['chemistry', '--database', 'unused', '--output', str(root / 'out.json')],
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                chemistry.main()
            self.assertEqual(json.loads((root / 'out.json').read_text()), report)
        rows, _ = irriblend.translate([dict(id='k', name='K', elements={'K': 10})])
        rows['K']['Na+'] = 1
        with self.assertRaisesRegex(ValueError, 'appeared from nothing'):
            irriblend.validate_translation([dict(name='K', elements={'K': 10})], rows)
