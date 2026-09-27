"""Product PHREEQC evidence: independent runtime equivalence and live replay."""
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from flahax.aqueous_model import chemistry, solve, nitric_target
from flahax.product_conversion import catalogue_dose_totals, solve_catalogue_product_doses, plan_catalogue_nitric_target
from tools.phreeqc_evidence import FIXTURES, INSTALL, merge, execute, selected

def cases():
    return sorted(FIXTURES.glob('*/expected.json'))

class ProductGoldenTests(unittest.TestCase):
    def test_all_product_captures_and_hashes_are_present(self):
        self.assertEqual(len(cases()),10)
        for path in cases():
            data=json.loads(path.read_text())
            suffix='_target' if data['nitric_acid_molal'] is not None else ''
            self.assertEqual(data['selected_rows'],selected(path.parent/(data['case']+suffix+'.sel')))
            for name,digest in data['hashes'].items():
                self.assertEqual(hashlib.sha256((path.parent/name).read_bytes()).hexdigest(),digest,name)
            for row in data['selected_rows']:
                self.assertLessEqual(abs(row['pct_err']),.1)

    def test_runtime_equivalence_conservation_and_convergence(self):
        for path in cases():
            with self.subTest(case=path.parent.name):
                data=json.loads(path.read_text())
                totals=data['runtime_totals']
                row=data['selected_rows'][-1]
                tolerance=data['tolerances']
                converted=catalogue_dose_totals(data['product_doses_g_per_kgw'])
                water={'Na+':totals['Na+']-converted.get('Na+',0.),'Cl-':totals['Cl-']}
                for b,amount in converted.items():
                    if b != 'Na+':
                        self.assertAlmostEqual(amount,totals[b],places=15,msg=b)
                if data['nitric_acid_molal'] is not None:
                    plan=plan_catalogue_nitric_target(data['product_doses_g_per_kgw'],data['initial_ph'],6.,water_totals=water)
                    result=plan.target
                    self.assertAlmostEqual(plan.nitric_acid_molal,data['nitric_acid_molal'],
                        delta=tolerance['acid_absolute']+tolerance['acid_relative']*data['nitric_acid_molal'])
                    self.assertAlmostEqual(plan.nitric_acid_molal,data['fix_h_nitric_acid_molal'],
                        delta=tolerance['acid_absolute']+tolerance['acid_relative']*data['nitric_acid_molal'])
                else:
                    result=solve_catalogue_product_doses(data['product_doses_g_per_kgw'],row['pH'],water_totals=water,allow_precipitation=False).aqueous
                for b,value in result.residuals.items():
                    self.assertLess(abs(value),1e-9*result.totals[b]+1e-15,b)
                self.assertLess(result.iterations,1500)
                self.assertAlmostEqual(result.ionic_strength,row['mu'],delta=.03*row['mu']+1e-9)
                for key,value in row.items():
                    if key.startswith('m_'):
                        actual=result.species[key[2:]]
                        self.assertAlmostEqual(actual,value,delta=tolerance['runtime_molality_absolute']+tolerance['runtime_molality_relative']*abs(value),msg=key)
                    elif key.startswith('la_') and row.get('m_'+key[3:],0.)>1e-10:
                        self.assertAlmostEqual(math.log10(result.activities[key[3:]]),value,delta=tolerance['runtime_log_activity_absolute'],msg=key)
                    elif key.startswith('si_'):
                        self.assertAlmostEqual(result.saturation_indices[key[3:]],value,delta=tolerance['runtime_si_absolute'],msg=key)

class LiveProductPhreeqcTests(unittest.TestCase):
    def test_replay_every_product_input(self):
        exe=INSTALL/'bin/Release/phreeqc.exe'
        base=INSTALL/'database/minteq.v4.dat'
        if not exe.is_file() or not base.is_file():
            self.skipTest('live PHREEQC installation unavailable; golden tests remain mandatory')
        with tempfile.TemporaryDirectory(prefix='flahax-replay-') as tmp:
            folder=Path(tmp)
            db=folder/'merged.dat'
            merge(base,db)
            for path in cases()+sorted((FIXTURES.parent/'phases').glob('*/expected.json')):
                data=json.loads(path.read_text())
                self.assertEqual(hashlib.sha256(base.read_bytes()).hexdigest(),data['reference']['base_sha256'])
                self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(),data['reference']['merged_sha256'])
                for pqi in path.parent.glob('*.pqi'):
                    with self.subTest(input=pqi.name):
                        rows=execute(exe,db,folder/pqi.stem,pqi.stem,pqi.read_text())
                        from tools.phreeqc_evidence import selected
                        golden=selected(pqi.with_suffix('.sel'))
                        self.assertEqual(len(rows),len(golden))
                        for actual,expected in zip(rows,golden):
                            self.assertEqual(actual.keys(),expected.keys())
                            for key,value in expected.items():
                                self.assertAlmostEqual(actual[key],value,delta=1e-12+1e-8*abs(value),msg=key)

class PhaseGoldenTests(unittest.TestCase):
    def test_phase_allocations_species_and_saturation_indices(self):
        paths=sorted((FIXTURES.parent/'phases').glob('*/expected.json'))
        self.assertEqual(len(paths),11)
        for path in paths:
            with self.subTest(case=path.parent.name):
                data=json.loads(path.read_text())
                for name,digest in data['hashes'].items():
                    self.assertEqual(hashlib.sha256((path.parent/name).read_bytes()).hexdigest(),digest)
                self.assertEqual(data['selected_rows'],selected(path.parent/(path.parent.name+'.sel')))
                row=data['selected_rows'][-1]
                self.assertLessEqual(abs(row['pct_err']),.1)
                result=solve(data['runtime_totals'],row['pH'],phases=data['phases'])
                for b,value in result.residuals.items():
                    self.assertLess(abs(value),1e-9*result.totals[b]+1e-15,b)
                for p in data['phases']:
                    self.assertLessEqual(result.saturation_indices.get(p,-math.inf),1e-7,p)
                    expected=row[p]/row['mass_H2O']
                    self.assertAlmostEqual(result.precipitated.get(p,0.),expected,
                        delta=data['tolerances']['phase_absolute']+data['tolerances']['phase_relative']*abs(expected),msg=p)
                for key,value in row.items():
                    if key.startswith('m_'):
                        self.assertAlmostEqual(result.species[key[2:]],value,
                            delta=data['tolerances']['molality_absolute']+data['tolerances']['molality_relative']*abs(value),msg=key)
                    elif key.startswith('si_'):
                        self.assertAlmostEqual(result.saturation_indices[key[3:]],value,
                            delta=data['tolerances']['si_absolute'],msg=key)
