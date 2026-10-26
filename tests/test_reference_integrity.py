# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Golden evidence cannot be repaired by overwriting or accepting malformed output."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flahax.delivery_contracts import DeliveryError
from flahax.reference_fixtures import load_reference_fixture, assert_reference_result
from tools import phreeqc_evidence as evidence

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/phreeqc'


class FixtureValidationTests(unittest.TestCase):
    def fixture(self):
        return json.loads((FIXTURES / 'calcite_co2_equilibrium.json').read_text())

    def test_loader_and_direct_comparator_reject_invalid_expected(self):
        changes = [
            None,
            {},
            {'absoluteTolerance': 0, 'values': {}},
            {'absoluteTolerance': 0, 'values': []},
        ]
        changes += [
            dict(absoluteTolerance=v, values={'x': 1})
            for v in [True, '1', -1, float('nan'), float('inf'), 10**1000]
        ]
        changes += [
            dict(absoluteTolerance=0, values={'x': v})
            for v in [True, '1', float('nan'), float('inf'), 10**1000]
        ]
        changes += [dict(absoluteTolerance=0, values={k: 1}) for k in ['', 1]]
        for expected in changes:
            f = self.fixture()
            f['expected'] = expected
            with self.assertRaises(DeliveryError):
                assert_reference_result(f, {'x': 123})
            # Integer JSON keys become strings; test the in-memory invalid key above.
            if isinstance(expected, dict) and 1 in expected.get('values', {}):
                continue
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'fixture.json'
                path.write_text(json.dumps(f))
                with self.assertRaises(DeliveryError):
                    load_reference_fixture(path)

    def test_loader_structural_and_hash_failures(self):
        f = self.fixture()
        changes = [
            [],
            {},
            f | {'reference': []},
            f | {'phreeqcInput': None},
            f | {'inputSha256': 'bad'},
        ]
        for key in ('sourceUrl', 'software', 'database', 'activityModel'):
            altered = copy.deepcopy(f)
            altered['reference'][key] = ''
            changes.append(altered)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'fixture.json'
            with self.assertRaises(DeliveryError):
                load_reference_fixture(path)
            path.write_text('{')
            with self.assertRaises(DeliveryError):
                load_reference_fixture(path)
            for payload in changes:
                path.write_text(json.dumps(payload))
                with self.assertRaises(DeliveryError):
                    load_reference_fixture(path)

    def test_actual_failures_and_exact_boundary(self):
        f = {'expected': {'absoluteTolerance': 0.5, 'values': {'x': 1}}}
        assert_reference_result(f, {'x': '1.5'})
        for actual in [
            {},
            {'x': True},
            {'x': None},
            {'x': 'bad'},
            {'x': 10**1000},
            {'x': float('nan')},
            {'x': float('inf')},
            {'x': 1.6},
        ]:
            with self.assertRaises(AssertionError):
                assert_reference_result(f, actual)
        for fixture, actual in [([], {}), ({}, [])]:
            with self.assertRaises(TypeError):
                assert_reference_result(fixture, actual)


class InventoryTests(unittest.TestCase):
    def test_every_retained_family_and_byte_is_pinned(self):
        inventory = evidence.verify_reference_inventory()
        self.assertEqual(len(inventory['files']), 197)
        self.assertEqual(
            {k: len(v['cases']) for k, v in inventory['families'].items()},
            {'products': 10, 'phases': 11, 'acid_selection': 4},
        )
        self.assertEqual(len(inventory['historical']['legacy_json']), 4)
        self.assertEqual(len(inventory['historical']['retained_successes']), 6)
        self.assertTrue(inventory['shared_data_limits'])
        for name in inventory['historical']['legacy_json']:
            load_reference_fixture(FIXTURES / name)

    def test_missing_changed_extra_empty_and_wrong_schema_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'captures'
            root.mkdir()
            payload = root / 'expected.json'
            payload.write_bytes(b'original')
            manifest = Path(tmp) / 'inventory.json'
            original = dict(schema=1, files={'expected.json': evidence.sha(payload)})
            manifest.write_text(json.dumps(original))
            evidence.verify_reference_inventory(root, manifest)
            payload.write_bytes(b'changed allowance')
            with self.assertRaises(ValueError):
                evidence.verify_reference_inventory(root, manifest)
            payload.unlink()
            with self.assertRaises(ValueError):
                evidence.verify_reference_inventory(root, manifest)
            payload.write_bytes(b'original')
            extra = root / 'unregistered'
            extra.touch()
            with self.assertRaises(ValueError):
                evidence.verify_reference_inventory(root, manifest)
            extra.unlink()
            for altered in [original | {'schema': 2}, original | {'files': {}}]:
                manifest.write_text(json.dumps(altered))
                with self.assertRaises(ValueError):
                    evidence.verify_reference_inventory(root, manifest)

    def test_installation_hashes_all_required_including_phase_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / n for n in ('exe', 'base', 'merged')]
            for p in paths:
                p.write_bytes(p.name.encode())
            keys = ('executable_sha256', 'base_sha256', 'merged_sha256')
            inventory = dict(live_reference={k: evidence.sha(p) for k, p in zip(keys, paths)})
            evidence.verify_reference_installation(*paths, inventory)
            for key in keys:
                bad = copy.deepcopy(inventory)
                bad['live_reference'][key] = '0' * 64
                with self.assertRaisesRegex(ValueError, key):
                    evidence.verify_reference_installation(*paths, bad)


class CaptureTests(unittest.TestCase):
    def test_selected_rows_are_nonempty_finite_and_rectangular(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'values.sel'
            for text in [
                '',
                'x\n',
                'x x\n1 2\n',
                'x y\n1\n',
                'x\n1 2\n',
                'x\nNaN\n',
                'x\ninf\n',
                'x\nwrong\n',
                'AmmH4 NH4\n1 2\n',
            ]:
                path.write_text(text)
                with self.assertRaises(ValueError):
                    evidence.selected(path)
            path.write_text('AmmH4 AmmH3\n1 2\n\n')
            self.assertEqual(evidence.selected(path), [{'NH4': 1, 'NH3': 2}])

    def test_new_destinations_and_captures_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = evidence.new_capture_root(Path(tmp) / 'fresh')
            with self.assertRaises(FileExistsError):
                evidence.new_capture_root(root)
            for suffix in ('.pqi', '.out', '.sel', '.screen'):
                existing = root / ('case' + suffix)
                existing.write_bytes(b'preserved')
                with (
                    self.assertRaises(FileExistsError),
                    patch.object(evidence.subprocess, 'run') as run,
                ):
                    evidence.execute(None, None, root, 'case', 'new')
                run.assert_not_called()
                self.assertEqual(existing.read_bytes(), b'preserved')
                existing.unlink()
            for name in ('', '.', '..', '../escape'):
                with self.assertRaises(ValueError):
                    evidence.execute(None, None, root, name, '')
        with self.assertRaisesRegex(ValueError, 'immutable'):
            evidence.new_capture_root(FIXTURES / 'new-child')
        with self.assertRaisesRegex(ValueError, 'immutable'):
            evidence.execute(None, None, FIXTURES, 'new-case', '')

    def test_generators_fail_before_touching_retained_outputs(self):
        before = evidence.verify_reference_inventory()
        with self.assertRaises(ValueError):
            evidence.generate(None, None, destination=FIXTURES / 'products')
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        for script in (
            'phreeqc_evidence.py',
            'phreeqc_phase_evidence.py',
            'acid_selection_evidence.py',
        ):
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / 'tools' / script),
                    '--output',
                    str(FIXTURES / 'products'),
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('immutable', result.stderr)
        self.assertEqual(before, evidence.verify_reference_inventory())

    def test_execution_rejects_failure_warning_missing_charge_and_bad_charge(self):
        cases = [
            (1, '', b'', 'pct_err\n0\n'),
            (0, 'ERROR: bad', b'', 'pct_err\n0\n'),
            (0, '', b'ERROR: bad', 'pct_err\n0\n'),
            (0, 'WARNING: bad', b'', 'pct_err\n0\n'),
            (0, '', b'WARNING: bad', 'pct_err\n0\n'),
            (0, '', b'', 'other\n0\n'),
            (0, '', b'', 'pct_err\n0.11\n'),
        ]
        for code, output, screen, selected in cases + [(0, '', b'', 'pct_err\n0.1\n')]:
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp) / 'capture'

                def fake_run(*args, **kwargs):
                    (folder / 'case.out').write_text(output)
                    (folder / 'case.sel').write_text(selected)
                    return SimpleNamespace(returncode=code, stdout=screen, stderr=b'')

                with patch.object(evidence.subprocess, 'run', side_effect=fake_run):
                    if selected == 'pct_err\n0.1\n':
                        self.assertEqual(
                            evidence.execute('exe', 'db', folder, 'case', 'input'),
                            [{'pct_err': 0.1}],
                        )
                    else:
                        with self.assertRaises(RuntimeError):
                            evidence.execute('exe', 'db', folder, 'case', 'input')
                self.assertEqual((folder / 'case.pqi').read_text(), 'input')
                self.assertTrue((folder / 'case.screen').exists())
