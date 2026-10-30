# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Capture orchestration with simulated external processes; not PHREEQC agreement."""

import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import phreeqc_evidence as evidence
from tests.catalogue_history import historical_catalogue

ROOT = Path(__file__).resolve().parents[1]


class CaptureOrchestrationTests(unittest.TestCase):
    def setup_install(self, root):
        install = root / 'install'
        (install / 'bin/Release').mkdir(parents=True)
        (install / 'database').mkdir()
        (install / 'bin/Release/phreeqc.exe').write_bytes(b'SIMULATED, NOT EXECUTABLE')
        (install / 'database/minteq.v4.dat').write_text('# synthetic boundary fixture\nEND\n')
        return install

    def fake_execute(self, exe, database, folder, name, text):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (name + '.pqi')).write_text(text)
        (folder / (name + '.out')).write_text('SIMULATED OUTPUT')
        return [
            dict(
                Na=0.002,
                **{
                    'N(5)': 1.0,
                    'P': 0.001,
                    'S(6)': 0.001,
                    'Citrate': 0.001,
                    'd_Fix_H+': -self.acid,
                    'pct_err': 0,
                    'mass_H2O': 1,
                    'pH': 6,
                },
            )
        ]

    def test_product_capture_branches_preserve_identity_and_refuse_bad_acid(self):
        self.enterContext(historical_catalogue())
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            install = self.setup_install(root)
            base = install / 'database/minteq.v4.dat'
            exe = install / 'bin/Release/phreeqc.exe'
            totals = evidence.catalogue_dose_totals(evidence.CASES['mixed_target_ph_nitric'])
            self.acid = 1 - totals['NO3-']
            with (
                patch.object(evidence, 'execute', side_effect=self.fake_execute),
                patch.object(
                    evidence,
                    'chemistry',
                    return_value=dict(
                        evidence.chemistry(),
                        aqueous=[
                            {k: v for k, v in r.items() if k != 'gamma'}
                            for r in evidence.chemistry()['aqueous']
                        ],
                    ),
                ),
            ):
                evidence.generate(
                    exe, base, ['fe_edta', 'mixed_target_ph_nitric'], destination=root / 'good'
                )
            data = json.loads((root / 'good/mixed_target_ph_nitric/expected.json').read_text())
            self.assertAlmostEqual(data['nitric_acid_molal'], self.acid)
            self.assertEqual(data['reference']['executable_sha256'], evidence.sha(exe))
            self.assertTrue(data['hashes'])
            self.acid = 100
            with (
                patch.object(evidence, 'execute', side_effect=self.fake_execute),
                self.assertRaisesRegex(RuntimeError, 'disagrees'),
            ):
                evidence.generate(exe, base, ['mixed_target_ph_nitric'], destination=root / 'bad')

            def no_acid(*args):
                rows = self.fake_execute(*args)
                rows[0]['N(5)'] = 0
                return rows

            with (
                patch.object(evidence, 'execute', side_effect=no_acid),
                self.assertRaisesRegex(RuntimeError, 'requires base'),
            ):
                evidence.generate(exe, base, ['mixed_target_ph_nitric'], destination=root / 'base')

    def test_acid_phase_and_historical_capture_scripts_use_temporary_destinations(self):
        self.enterContext(historical_catalogue())
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            install = self.setup_install(root)
            self.acid = 0.001
            with (
                patch.object(evidence, 'INSTALL', install),
                patch.object(evidence, 'execute', side_effect=self.fake_execute),
                patch.dict(sys.modules, {'phreeqc_evidence': evidence}),
            ):
                for script in ('acid_selection_evidence', 'phreeqc_phase_evidence'):
                    with patch.object(sys, 'argv', [script, '--output', str(root / script)]):
                        runpy.run_path(str(ROOT / 'tools' / f'{script}.py'), run_name='__main__')
                    reports = list((root / script).glob('*/expected.json'))
                    self.assertGreater(len(reports), 1)
                    self.assertTrue(all(json.loads(p.read_text())['hashes'] for p in reports))
                with (
                    patch.object(evidence, 'ROOT', root),
                    patch.object(
                        evidence,
                        'merge',
                        side_effect=lambda base, out: out.write_text('synthetic'),
                    ),
                    patch(
                        'subprocess.run',
                        return_value=SimpleNamespace(returncode=1, stdout=b'failure', stderr=b''),
                    ),
                ):
                    runpy.run_path(str(ROOT / 'tools/debug_nitric_phreeqc.py'))
                reports = list((root / 'tests/fixtures/phreeqc/failures').glob('*.json'))
                self.assertEqual(len(reports), 5)
                self.assertTrue(all(json.loads(p.read_text())['exit_code'] == 1 for p in reports))

    def test_merge_requires_terminal_end_and_optional_gamma_is_optional(self):
        self.enterContext(historical_catalogue())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = root / 'bad.dat'
            base.write_text('END')
            with self.assertRaisesRegex(ValueError, 'terminal END'):
                evidence.merge(base, root / 'merged.dat')
        original = evidence.chemistry()
        model = dict(
            original,
            aqueous=[{k: v for k, v in r.items() if k != 'gamma'} for r in original['aqueous']],
        )
        with patch.object(evidence, 'chemistry', return_value=model):
            self.assertIn('AmmH4', evidence.fixed_ammonium('SOLUTION 1\nEND\n'))
        with patch.dict(sys.modules, {'phreeqc_evidence': evidence}):
            for name in ('acid_selection_evidence', 'phreeqc_phase_evidence'):
                runpy.run_path(str(ROOT / 'tools' / f'{name}.py'), run_name='__import__')
