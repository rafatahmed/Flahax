# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Offline generators use temporary source trees and assert reproducible transformations."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import add_ph_reagents, build_chemistry_model as model
from tools import cli_reference, generate_api_reference, inventory_numeric_decisions as numeric
from tools import phreeqc_evidence

ROOT = Path(__file__).resolve().parents[1]


class SupportGeneratorTests(unittest.TestCase):
    def test_reagent_generator_is_idempotent_in_temporary_catalogue(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            library = json.loads((ROOT / 'src/flahax/data/library.json').read_bytes())
            library['salts'] = [
                s
                for s in library['salts']
                if s['name'] not in ('Potassium Hydroxide (45% solution)', 'Potassium Bicarbonate')
            ]
            (root / 'library.json').write_text(json.dumps(library))
            (root / 'material_identities.json').write_text('{"identities": []}')
            with patch.object(add_ph_reagents, 'DATA', root):
                add_ph_reagents.main()
                before = {p.name: p.read_bytes() for p in root.iterdir()}
                add_ph_reagents.main()
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})
            self.assertEqual(len(json.loads(before['material_identities.json'])['identities']), 2)
            self.assertIn('Potassium Bicarbonate', before['library.json'].decode())

    def test_reaction_parser_and_closure_use_temporary_model_only(self):
        text = '''# synthetic reaction algebra, not scientific source data
SOLUTION_MASTER_SPECIES
ignored
SOLUTION_SPECIES
H+ = H+
Na+ = Na+
Na+ + H2O = NaOH + H+
 log_k 2
 -gamma 3 4
Na+ = Na+ + H+
e- = e-
Na+ + e- = Red
Unresolved = Other
Na+ + Wrong = Wrong
Na+ = Negative + Ca+2
PHASES
Synthetic
 NaX + H+ = Na+ + H2O
 log_k 1
END
'''
        self.assertEqual(model.side('2 Na+ + Na+'), {'Na+': 3})
        self.assertEqual(model.side(''), {})
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            for part in ('src/flahax/data', 'docs/site/models', 'tests/fixtures/phreeqc/database'):
                (root / part).mkdir(parents=True)
            for name in ('flahax-chelates-25c.dat', 'flahax-phases-25c.dat'):
                (root / 'tests/fixtures/phreeqc/database' / name).write_text('')
            database = root / 'input.dat'
            database.write_text(text)
            original = database.read_bytes()
            with patch.object(model, 'ROOT', root), patch.object(model, 'PHASES', ['Synthetic']):
                model.build(database)
            result = json.loads((root / 'src/flahax/data/chemistry_25c.json').read_text())
            self.assertEqual(database.read_bytes(), original)
            aqueous = {r['name']: r for r in result['aqueous']}
            self.assertEqual(aqueous['NaOH']['powers'], {'Na+': 1, 'H2O': 1, 'H+': -1})
            self.assertEqual(aqueous['NaOH']['beta'], 2)
            self.assertEqual(aqueous['NaOH']['gamma'], [3, 4])
            self.assertNotIn('Negative', aqueous)
            self.assertNotIn('Red', aqueous)
            self.assertEqual(result['database_sha256'], hashlib.sha256(original).hexdigest())
            self.assertIn(
                'Synthetic', (root / 'docs/site/models/chemistry-coverage-matrix.md').read_text()
            )
            with (
                patch.object(model, 'ROOT', root),
                patch.object(model, 'PHASES', ['missing']),
                self.assertRaisesRegex(ValueError, 'unresolved phase'),
            ):
                model.build(database)

    def test_reference_generators_check_missing_and_stale_pages(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            path = Path(folder) / 'reference.md'
            for module, field in (
                (cli_reference, 'PAGE'),
                (generate_api_reference, 'DESTINATION'),
            ):
                with patch.object(module, field, path):
                    path.unlink(missing_ok=True)
                    with patch.object(sys, 'argv', ['generator', '--check']):
                        if module is cli_reference:
                            self.assertEqual(module.main(), 1)
                        else:
                            with self.assertRaises(SystemExit) as e:
                                module.main()
                            self.assertEqual(e.exception.code, 1)
                    with patch.object(sys, 'argv', ['generator']):
                        module.main()
                    before = path.read_bytes()
                    with patch.object(sys, 'argv', ['generator', '--check']):
                        module.main()
                    self.assertEqual(path.read_bytes(), before)
            with patch.object(generate_api_reference.inspect, 'signature', side_effect=ValueError):
                self.assertIn('Source module:', generate_api_reference.render())

    def test_numeric_inventory_command_preserves_review_snapshots(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            (root / 'src/flahax/data').mkdir(parents=True)
            (root / 'src/flahax/model.py').write_text('def f(x=1):\n return x>2\n')
            (root / 'src/flahax/data/example.json').write_text('{"a": [true,"1.5",2]}')
            output = root / 'inventory.json'
            argv = ['inventory', '--root', str(root), '--output', str(output)]
            with patch.object(sys, 'argv', argv):
                self.assertEqual(numeric.main(), 0)
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    numeric.main()
            report = json.loads(output.read_text())
            self.assertFalse(report['review_complete'])
            self.assertTrue(
                any(r['syntax_kind'] == 'data_numeric_string' for r in report['entries'])
            )

    def test_preserved_evidence_index_writes_only_temporary_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            destination = root / 'tests/fixtures/phreeqc'
            destination.mkdir(parents=True)
            source = ROOT / 'tests/fixtures/phreeqc'
            for name in ('fe_edta', 'mn_edta', 'zn_edta', 'cu_edta', 'fe_dtpa', 'fe_eddha'):
                for suffix in ('.pqi', '.out', '.sel'):
                    shutil.copyfile(source / (name + suffix), destination / (name + suffix))
            (destination / 'failures/subdir').mkdir(parents=True)
            (destination / 'failures/ignored.txt').write_text('ignored')
            (destination / 'failures/failure.out').write_text('retained diagnostic')
            before = {str(p): p.read_bytes() for p in destination.rglob('*') if p.is_file()}
            with (
                patch.object(phreeqc_evidence, 'ROOT', root),
                patch.dict(sys.modules, {'phreeqc_evidence': phreeqc_evidence}),
            ):
                runpy.run_path(str(ROOT / 'tools/archive_evidence_manifest.py'))
            report = json.loads((destination / 'preserved-evidence.json').read_text())
            self.assertEqual(len(report['artifacts']), 7)
            self.assertTrue(all(Path(p).read_bytes() == data for p, data in before.items()))

    def test_generator_entrypoints_on_temporary_checkout(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            data = root / 'src/flahax/data'
            data.mkdir(parents=True)
            for name in ('library.json', 'material_identities.json'):
                shutil.copyfile(ROOT / 'src/flahax/data' / name, data / name)
            source = ROOT / 'tools/add_ph_reagents.py'
            exec(
                compile(source.read_text(encoding='utf-8'), str(source), 'exec'),
                {'__name__': '__main__', '__file__': str(root / 'tools/add_ph_reagents.py')},
            )
            self.assertTrue(json.loads((data / 'library.json').read_bytes())['salts'])
            (root / 'docs/site/models').mkdir(parents=True)
            (root / 'tests/fixtures/phreeqc/database').mkdir(parents=True)
            for name in ('flahax-chelates-25c.dat', 'flahax-phases-25c.dat'):
                (root / 'tests/fixtures/phreeqc/database' / name).write_text('')
            # Reverse-order dependencies exhaust the bounded closure scan; no physical model claim.
            text = 'SOLUTION_SPECIES\nK+ = K+ + H+\n'
            text += '\n'.join(f'X{i - 1} + H+ = X{i}' for i in range(30, 0, -1))
            text += '\nK+ = X0\nPHASES\nMissing\n Solid = Unknown\n -delta_h 1\nEND\n'
            database = root / 'chain.dat'
            database.write_text(text)
            with (
                patch.object(model, 'ROOT', root),
                patch.object(model, 'PHASES', ['Missing']),
                self.assertRaisesRegex(ValueError, 'unresolved'),
            ):
                model.build(database)
            # The actual module entry point is also exercised against a small invalid input.
            source = ROOT / 'tools/build_chemistry_model.py'
            with (
                patch.object(sys, 'argv', ['build', str(database)]),
                self.assertRaisesRegex(ValueError, 'unresolved'),
            ):
                exec(
                    compile(source.read_text(encoding='utf-8'), str(source), 'exec'),
                    {
                        '__name__': '__main__',
                        '__file__': str(root / 'tools/build_chemistry_model.py'),
                    },
                )

    def test_auto_dataclass_documentation_is_not_repeated_as_prose(self):
        from dataclasses import make_dataclass
        from types import SimpleNamespace

        record = make_dataclass('Example', [('value', float)])
        fake = SimpleNamespace(__version__='synthetic', __all__=['Example'], Example=record)
        with patch.object(generate_api_reference, 'flahax', fake):
            result = generate_api_reference.render()
        self.assertIn('Record fields: `value`.', result)
        self.assertEqual(result.count('Example(value:'), 1)
