"""Additional acid-reference hashes, numerical equivalence and live replay."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from flahax import calculate_equilibrium_ph, plan_acid_options
from tools.phreeqc_evidence import INSTALL, merge, execute, selected, sha

FIXTURES = Path(__file__).parent / 'fixtures/phreeqc/acid_selection'


class AcidReferenceTests(unittest.TestCase):
    def test_golden_equivalence_and_conservation(self):
        paths = sorted(FIXTURES.glob('*/expected.json'))
        self.assertEqual(len(paths), 4)
        for path in paths:
            with self.subTest(acid=path.parent.name):
                data = json.loads(path.read_text())
                tolerance = data['tolerances']
                self.assertEqual(data['selected_rows'], selected(path.parent / 'reference.sel'))
                for name, digest in data['hashes'].items():
                    self.assertEqual(sha(path.parent / name), digest)
                for row in data['selected_rows']:
                    self.assertLessEqual(abs(row['pct_err']), tolerance['charge_error_percent'])
                initial = calculate_equilibrium_ph(data['totals'], complete_analysis=True,
                                                    carbon_boundary='closed', phases=[])
                self.assertAlmostEqual(initial.ph, data['selected_rows'][0]['pH'],
                                       delta=tolerance['ph_absolute'])
                result = plan_acid_options(data['totals'], initial.ph, data['target_ph'],
                    products=[dict(id='test', chemicalFormula=data['formula'], massFraction=.5,
                                   densityKgPerL=1.2, source='synthetic test only', revision='1',
                                   recordedAt='2026-09-28T00:00:00Z')],
                    water_mass_kg=100, final_volume_litres=100,
                    achieved={'Na':45.979538, 'Cl':70.906}, targets={'Na':45.979538},
                    maximum_concentrations={'Cl':80, 'N_NO3':1, 'P':1, 'S':1},
                    maximum_nutrient_error_percent=1, maximum_reagent_volume_litres=.1)
                candidate = result.candidates[0]
                self.assertEqual(candidate.status, 'accepted', candidate)
                self.assertAlmostEqual(candidate.dose_molal, data['acid_molal'],
                    delta=tolerance['dose_absolute'] + tolerance['dose_relative'] * data['acid_molal'])
                self.assertLess(abs(candidate.target.charge_balance), 2e-12)
                for component, residual in candidate.target.residuals.items():
                    self.assertLess(abs(residual), 1e-9 * candidate.target.totals[component] + 1e-15)

    def test_live_replay(self):
        exe, base = INSTALL / 'bin/Release/phreeqc.exe', INSTALL / 'database/minteq.v4.dat'
        if not exe.exists() or not base.exists():
            if os.environ.get('FLAHAX_REQUIRE_PHREEQC') == '1':
                self.fail('required external PHREEQC installation is missing')
            self.skipTest('external PHREEQC not installed')
        with tempfile.TemporaryDirectory(prefix='flahax-acid-replay-') as temporary:
            database = Path(temporary) / 'merged.dat'
            merge(base, database)
            for path in sorted(FIXTURES.glob('*/expected.json')):
                data = json.loads(path.read_text())
                self.assertEqual(sha(base), data['database_sha256'])
                self.assertEqual(sha(database), data['merged_database_sha256'])
                self.assertEqual(sha(exe), data['executable_sha256'])
                rows = execute(exe, database, Path(temporary) / path.parent.name,
                               'reference', (path.parent / 'reference.pqi').read_text())
                self.assertEqual(len(rows), len(data['selected_rows']))
                for actual, expected in zip(rows, data['selected_rows']):
                    for key, value in expected.items():
                        self.assertAlmostEqual(actual[key], value, delta=1e-12 + abs(value)*1e-9)
