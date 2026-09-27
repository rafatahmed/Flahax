"""Preserved reduction ladder for the historical Fix_H+ failure."""
from pathlib import Path
import json
import subprocess
import tempfile
from phreeqc_evidence import ROOT, INSTALL, merge, sha, CASES, catalogue_dose_totals, BASIS_NAMES

folder=ROOT/'tests/fixtures/phreeqc/failures'
folder.mkdir(parents=True,exist_ok=True)
exe=INSTALL/'bin/Release/phreeqc.exe'
base=INSTALL/'database/minteq.v4.dat'
macro={'Ca+2':.001,'Mg+2':.001,'NO3-':.003,'PO4-3':.001,'SO4-2':.001,'CO3-2':.0024,'K+':.002,'Na+':.003,'Cl-':.007}
stages=[('01_macro_original',macro,'pH'),
        ('02_add_fe_dtpa_original',macro|{'Fe+3':1e-5,'Dtp-5':1e-5},'pH'),
        ('03_macro_sodium_balance',macro,'Na+'),
        ('04_add_fe_dtpa_sodium_balance',macro|{'Fe+3':1e-5,'Dtp-5':1e-5},'Na+'),
        ('05_actual_products_sodium_balance',catalogue_dose_totals(CASES['mixed_target_ph_nitric'])|{'Na+':.002,'Cl-':.002},'Na+')]
with tempfile.TemporaryDirectory(prefix='flahax-debug-') as tmp:
    db=Path(tmp)/'merged.dat'
    merge(base,db)
    for name,totals,balance in stages:
        text='TITLE Preserved target-pH reduction '+name+'\nPHASES\nFix_H+\n H+ = H+\n log_k 0\nSOLUTION 1\n temp 25\n pH 7.4'+(' charge' if balance=='pH' else '')+'\n units mol/kgw\n'
        text+='\n'.join(f' {BASIS_NAMES[b]} {v:.17g}'+(' charge' if b==balance else '') for b,v in totals.items())
        text+='\nEQUILIBRIUM_PHASES 1\n Fix_H+ -6 HNO3 1\nSELECTED_OUTPUT\n -file '+name+'.sel\n -reset false\n -high_precision true\n -pH true\n -percent_error true\n -pe true\n -totals Fe(3) Fe(2) N(5) N(-3) Dtp\n -equilibrium_phases Fix_H+\nEND\n'
        (folder/(name+'.pqi')).write_text(text)
        result=subprocess.run([str(exe),name+'.pqi',name+'.out',str(db)],cwd=folder,capture_output=True,timeout=60)
        (folder/(name+'.screen')).write_bytes(result.stdout+result.stderr)
        data={'software':'PHREEQC 3.8.6-17100','exit_code':result.returncode,
              'database_sha256':sha(base),'merged_sha256':sha(db),'executable_sha256':sha(exe),
              'generation_command':'python tools/debug_nitric_phreeqc.py',
              'hashes':{p.name:sha(p) for p in folder.glob(name+'.*') if p.suffix!='.json'}}
        (folder/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')
        print(name,result.returncode,flush=True)
