"""Build and smoke-test wheel and sdist in separate clean, non-editable installs.

Run with a development interpreter containing `build`. Does not publish.
Build/install dependencies are confined to temporary virtual environments.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SMOKE = r'''
import importlib.metadata, json, math, subprocess, sys, re, contextlib, io
from importlib.resources import files
import flahax
assert all(hasattr(flahax, name) for name in flahax.__all__)
from flahax import load_library, solve_catalogue_product_doses, plan_catalogue_nitric_target
import hashlib
assert not importlib.metadata.requires('flahax'), 'unexpected runtime dependency'
manual = files('flahax').joinpath('data/USER_GUIDE.md').read_text(encoding='utf-8')
assert f'FlahaX {flahax.__version__}' in manual
examples = re.findall(r'```python\n(.*?)```', manual, re.S)
assert len(examples) == 4
for index, example in enumerate(examples):
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(example, f'USER_GUIDE example {index + 1}', 'exec'), {'__name__': '__manual__'})
library = load_library()
result = solve_catalogue_product_doses({'Iron DTPA': .01}, 6., allow_precipitation=False)
assert result.aqueous.species['FeDtp-2'] > 0
plan = plan_catalogue_nitric_target({'Potassium Carbonate': .01},7.4,6.,water_totals={'Na+':.002,'Cl-':.002})
assert plan.nitric_acid_molal > 0 and plan.post_mix_measurement_required
assert hasattr(flahax, 'plan_equilibrium_delivery')
products={p['name']:p for p in library['salts']}
recipe=flahax.final_solution_recipe({'feasible':True,'salts':[
 {'id':products[n]['id'],'name':n,'gramsPerLitre':g*.95}
 for n,g in {'Potassium Carbonate':.01,'Potassium Nitrate':.02}.items()]},flahax.VolumeLitres(100))
delivery=flahax.plan_equilibrium_delivery(recipe,water_mass_kg=95.,
 water_totals={'Na+':.002,'Cl-':.0020776451648549022},water_analysis_id='synthetic-example-v1',
 initial_ph=7.4,target_ph=6.,reagent_channel_id='acid',
 reagent={'schemaVersion':'0.1','id':'nitric','source':'synthetic-example','revision':'1',
 'recordedAt':'2026-09-27T00:00:00Z','name':'Nitric acid','kind':'acid','chemicalFormula':'HNO3',
 'elements':{'N_NO3':13.8},'densityKgPerL':1.4},
 maximum_reagent_volume=flahax.VolumeLitres(.1),targets={'K':12.72},maximum_nutrient_error_percent=1.)
assert delivery.reagent_volume_litres>0 and delivery.post_mix_measurement_required
salt = next(p for p in library['salts'] if p['name'] == 'Potassium Nitrate')
payload=json.dumps({'salts':[salt],'targets':{'K':100},'water':{}})
run=subprocess.run([sys.executable,'-I','-m','flahax'],input=payload,text=True,capture_output=True,check=True)
assert json.loads(run.stdout)['salts']
console=subprocess.run([sys.argv[1]],input=payload,text=True,capture_output=True,check=True)
assert json.loads(console.stdout)==json.loads(run.stdout)
print(json.dumps({'version':flahax.__version__, 'python':sys.version, 'catalogue_count':len(library['salts']),
 'manual_examples':len(examples),
 'manual_sha256':hashlib.sha256(files('flahax').joinpath('data/USER_GUIDE.md').read_bytes()).hexdigest(),
 'chemistry_sha256':hashlib.sha256(files('flahax').joinpath('data/chemistry_25c.json').read_bytes()).hexdigest(),
 'library_sha256':hashlib.sha256(files('flahax').joinpath('data/library.json').read_bytes()).hexdigest(),
 'fe_dtpa':result.aqueous.species['FeDtp-2'],'acid':plan.nitric_acid_molal,
 'delivery_reagent_litres':delivery.reagent_volume_litres,
 'module':flahax.__file__}))
'''


def verify(report, interpreter, artifacts_dir=None):
    if artifacts_dir is not None and artifacts_dir.exists() and any(artifacts_dir.iterdir()):
        raise RuntimeError('artifact destination is not empty; refusing to overwrite release files')
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    with tempfile.TemporaryDirectory(prefix='flahax-distribution-') as tmp:
        folder = Path(tmp)
        artifacts = folder/'artifacts'
        subprocess.run([sys.executable,'-m','build','--outdir',str(artifacts)],cwd=ROOT,env=env,check=True)
        results = []
        for index, artifact in enumerate(sorted(artifacts.iterdir())):
            if artifact.suffix == '.whl':
                with zipfile.ZipFile(artifact) as archive:
                    names=archive.namelist()
            else:
                with tarfile.open(artifact) as archive:
                    names=archive.getnames()
                if not any(n.endswith('/tests/fixtures/phreeqc/products/fe_dtpa/expected.json') for n in names):
                    raise RuntimeError('sdist is missing its reference evidence')
            if any(Path(n).suffix.lower() in ('.exe','.dll','.msi') for n in names):
                raise RuntimeError('unexpected binary in package distribution')
            install = folder/f'install-{index}'
            subprocess.run([interpreter,'-m','venv',str(install)],cwd=folder,env=env,check=True)
            scripts = install/('Scripts' if os.name == 'nt' else 'bin')
            python = scripts/('python.exe' if os.name == 'nt' else 'python')
            cli = scripts/('flahax.exe' if os.name == 'nt' else 'flahax')
            subprocess.run([str(python),'-m','pip','install','--no-deps',str(artifact)],cwd=folder,env=env,check=True)
            run = subprocess.run([str(python),'-I','-c',SMOKE,str(cli)],cwd=folder,env=env,text=True,capture_output=True,check=True)
            result = json.loads(run.stdout)
            if result['manual_sha256'] != hashlib.sha256((ROOT/'src/flahax/data/USER_GUIDE.md').read_bytes()).hexdigest():
                raise RuntimeError('packaged user manual differs from source')
            if not Path(result.pop('module')).resolve().is_relative_to(install.resolve()):
                raise RuntimeError('smoke imported source checkout rather than installed package')
            if result['catalogue_count'] != 28:
                raise RuntimeError('missing packaged catalogue data')
            # Verify the builder retained the resource bytes from this checkout.
            source = (ROOT/'src/flahax/data/chemistry_25c.json').read_bytes()
            if result['chemistry_sha256'] != hashlib.sha256(source).hexdigest():
                raise RuntimeError('packaged chemistry data differs from source')
            if result['library_sha256'] != hashlib.sha256((ROOT/'src/flahax/data/library.json').read_bytes()).hexdigest():
                raise RuntimeError('packaged catalogue differs from source')
            results.append({'artifact':artifact.name,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'result':result})
        if len(results) != 2 or results[0]['result'] != results[1]['result']:
            raise RuntimeError('wheel and sdist smoke results differ')
        if artifacts_dir is not None:
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            for result in results:
                shutil.copy2(artifacts/result['artifact'], artifacts_dir/result['artifact'])
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps({'status':'passed','build_python':sys.version,'installs':results},indent=2)+'\n')
        print('PASS: isolated wheel and sdist installs, resources, public APIs and both CLI entry points')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',type=Path,default=ROOT/'build/distribution-verification.json')
    parser.add_argument('--python',default=sys.executable,help='interpreter used for clean installs and smoke tests')
    parser.add_argument('--artifacts-dir',type=Path,help='retain verified artifacts in a new or empty directory; never uploads')
    args=parser.parse_args()
    verify(args.report,args.python,args.artifacts_dir)
