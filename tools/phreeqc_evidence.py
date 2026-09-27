"""Reproducible PHREEQC product evidence; retain successes and failures.

Run with PYTHONPATH=src. No executable or merged database enters the repository.
Captures are generated artifacts, not hand-authored numerical expectations.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from flahax.aqueous_model import chemistry, solve, nitric_target
from flahax.product_conversion import catalogue_dose_totals

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'tests/fixtures/phreeqc/products'
INSTALL=Path(os.environ.get('TEMP',tempfile.gettempdir()))/'flahax-phreeqc/installed/phreeqc-3.8.6-17100-x64'
BASIS_NAMES=dict(zip(chemistry()['bases'],['Ca','Mg','K','Na','Cl','N(5)','N(-3)','S(6)',
    'C(4)','P','Fe(3)','Fe(2)','Mn(2)','Zn','Cu(2)','B','Mo','Edta','Citrate','Dtp','Edd','Ure']))
CASES={
 'fe_edta':{'Iron EDTA':.01}, 'mn_edta':{'Mn EDTA':.01},
 'zn_edta':{'Zn EDTA':.01}, 'cu_edta':{'Copper EDTA':.01},
 'fe_dtpa':{'Iron DTPA':.01}, 'fe_eddha':{'Iron EDDHA':.01},
 'ch_micro':{'CH - micro':.01},
 'citrate':{'Potassium Citrate':.02},
 'mixed_products':{'Calcium Nitrate (ag grade)':.15,'Magnesium Sulfate (Heptahydrate)':.10,
                   'Potassium Monobasic Phosphate':.05,'Potassium Nitrate':.10,
                   'Iron DTPA':.004,'Iron EDDHA':.003,'CH - micro':.005,'Urea':.005},
}
CASES['mixed_target_ph_nitric']=CASES['mixed_products']|{'Potassium Carbonate':.10}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def merge(base,destination):
    """Remove only the terminal END in the temporary copy before appending."""
    original=sha(base)
    text=re.sub(r'(?ms)\nEND\s*\Z','\n',base.read_text())
    if text.rstrip().endswith('END'):
        raise ValueError('base database terminal END was not removed')
    for name in ('flahax-chelates-25c.dat','flahax-phases-25c.dat'):
        text+='\n'+(ROOT/'tests/fixtures/phreeqc/database'/name).read_text()
    destination.write_text(text+'\nEND\n')
    assert sha(base)==original

def selected(path):
    lines=[line.split() for line in path.read_text().splitlines() if line.strip()]
    headings=[h.replace('AmmH4','NH4').replace('AmmH3','NH3') for h in lines[0]]
    return [dict(zip(headings,map(float,row))) for row in lines[1:]]


def fixed_ammonium(text):
    """USGS Amm.dat technique: conserve nitrogen oxidation states in batches."""
    header=['SOLUTION_MASTER_SPECIES',' Amm AmmH4+ 0 Amm 14.0067','SOLUTION_SPECIES',
            'AmmH4+ = AmmH4+',' log_k 0']
    for r in chemistry()['aqueous']:
        if 'NH4+' not in r['powers'] or r['name']=='NH4+':
            continue
        header += [r['equation'],f' log_k {r["log_k"]:.17g}']
        if 'gamma' in r:
            header += [' -gamma '+' '.join(map(str,r['gamma']))]
    struvite=next(r for r in chemistry()['phases'] if r['name']=='Struvite')
    header += ['PHASES','Struvite',struvite['equation'],f' log_k {struvite["log_k"]:.17g}']
    return ('\n'.join(header)+'\n'+text).replace('NH4','AmmH4').replace('NH3','AmmH3').replace('N(-3)','Amm')

def input_text(name,totals,ph,*,balance='Na+',phases=()):
    present={b:v for b,v in totals.items() if v>0}
    if balance:
        present.setdefault(balance,1e-6)
    permitted=set(present)|{'H+','H2O'}
    aqueous=[r['name'] for r in chemistry()['aqueous'] if r['name']!='H2O' and set(r['powers'])<=permitted]
    eligible=[r['name'] for r in chemistry()['phases'] if set(r['powers'])<=permitted]
    lines=[f'TITLE FlahaX {name}; 25 C fixed analytical oxidation states',
           'SOLUTION 1',' temp 25',f' pH {ph:.17g}',' units mol/kgw',' -water 1']
    for b,v in present.items():
        lines.append(f' {BASIS_NAMES[b]} {v:.17g}'+(' charge' if b==balance else ''))
    if phases:
        lines += ['EQUILIBRIUM_PHASES 1']+[f' {p} 0 0' for p in phases]
    lines+=['SELECTED_OUTPUT',f' -file {name}.sel',' -reset false',' -high_precision true',
            ' -pH true',' -ionic_strength true',' -charge_balance true',' -percent_error true',
            ' -water true',' -totals '+' '.join(BASIS_NAMES[b] for b in present),
            ' -molalities '+' '.join(aqueous),' -activities '+' '.join(aqueous),
            ' -si '+' '.join(eligible)]
    if phases:
        lines+=[' -equilibrium_phases '+' '.join(phases)]
    lines+=['END','']
    return '\n'.join(lines)

def execute(exe,db,folder,name,text):
    folder.mkdir(parents=True,exist_ok=True)
    (folder/f'{name}.pqi').write_text(text)
    run=subprocess.run([str(exe),name+'.pqi',name+'.out',str(db)],cwd=folder,capture_output=True,timeout=90)
    (folder/f'{name}.screen').write_bytes(run.stdout+run.stderr)
    output=(folder/f'{name}.out').read_text(errors='replace')
    screen=(run.stdout+run.stderr).decode(errors='replace')
    if run.returncode or 'ERROR:' in output or 'ERROR:' in screen:
        raise RuntimeError(f'{name}: PHREEQC failed; preserved in {folder}')
    if 'WARNING:' in output or 'WARNING:' in screen:
        raise RuntimeError(f'{name}: PHREEQC warning; inspect preserved capture')
    rows=selected(folder/f'{name}.sel')
    for row in rows:
        if not math.isfinite(row['pct_err']) or abs(row['pct_err'])>.1:
            raise RuntimeError(f'{name}: rejected charge error {row["pct_err"]}%')
    return rows

def generate(exe,base):
    FIXTURES.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='flahax-evidence-') as tmp:
        db=Path(tmp)/'minteq-flahax.dat'
        merge(base,db)
        for name,doses in CASES.items():
            folder=FIXTURES/name
            totals=catalogue_dose_totals(doses)
            # Explicit background electrolyte permits fixed-pH charge balance
            # by sodium without assuming unlabelled product counterions.
            totals['Na+']=totals.get('Na+',0.)+.002
            totals['Cl-']=.002
            ph=7.4 if name=='mixed_target_ph_nitric' else 6.
            rows=execute(exe,db,folder,name,input_text(name,totals,ph))
            initial=rows[-1]
            totals['Na+']=initial['Na']
            acid=None
            if name=='mixed_target_ph_nitric':
                # Fixed oxidation-state acid titration: at the lower pH only
                # N(5) is charge-adjusted. Its increase is the HNO3 dose. This
                # avoids batch redox equilibration, not any aqueous reaction.
                target_name=name+'_target'
                rows=execute(exe,db,folder,target_name,input_text(target_name,totals,6.,balance='NO3-'))
                acid=rows[-1]['N(5)']-totals['NO3-']
                if acid<=0:
                    raise RuntimeError('target requires base, not HNO3')
                # Batch proof with NHx decoupled from nitrate, following the
                # documented PHREEQC Amm.dat technique. Reactions/log K are
                # exact name substitutions of the same pinned nitrogen data.
                batch_name=name+'_fix_h'
                header=['SOLUTION_MASTER_SPECIES',' Amm AmmH4+ 0 Amm 14.0067','SOLUTION_SPECIES',
                        'AmmH4+ = AmmH4+',' log_k 0']
                for r in chemistry()['aqueous']:
                    if 'NH4+' not in r['powers'] or r['name']=='NH4+':
                        continue
                    equation=r['equation'].replace('NH4','AmmH4').replace('NH3','AmmH3')
                    header += [equation,f' log_k {r["log_k"]:.17g}']
                    if 'gamma' in r:
                        header += [' -gamma '+' '.join(map(str,r['gamma']))]
                header+=['PHASES','Fix_H+',' H+ = H+',' log_k 0']
                body=input_text(batch_name,totals,ph,balance=None).replace(' N(-3) ',' Amm ')
                body=body.replace('SELECTED_OUTPUT','EQUILIBRIUM_PHASES 1\n Fix_H+ -6 HNO3 1\nSELECTED_OUTPUT')
                body=body.replace('END\n',' -equilibrium_phases Fix_H+\nEND\n')
                batch_rows=execute(exe,db,folder,batch_name,'\n'.join(header)+'\n'+body)
                batch_acid=-batch_rows[-1]['d_Fix_H+']
                if abs(batch_acid-acid)>2e-6+.03*acid:
                    raise RuntimeError(f'fixed-valence batch acid {batch_acid} disagrees with titration {acid}')
            reference={'software':'PHREEQC 3.8.6-17100','base_sha256':sha(base),'executable_sha256':sha(exe),
                       'merged_sha256':sha(db),'extensions':{p.name:sha(p) for p in (ROOT/'tests/fixtures/phreeqc/database').glob('*.dat')}}
            data={'schema':1,'case':name,'reference':reference,'product_doses_g_per_kgw':doses,
                  'initial_ph':ph,'runtime_totals':totals,'selected_rows':rows,'nitric_acid_molal':acid,
                  'fix_h_nitric_acid_molal':batch_acid if acid is not None else None,
                  'tolerances':{'replay_relative':1e-8,'replay_absolute':1e-12,'charge_error_percent':.1,
                    'runtime_log_activity_absolute':.12,'runtime_molality_relative':.15,
                    'runtime_molality_absolute':1e-10,'runtime_si_absolute':.25,
                    'acid_relative':.03,'acid_absolute':2e-6},
                  'hashes':{p.name:sha(p) for p in folder.iterdir() if p.suffix in ('.pqi','.sel','.out','.screen')}}
            (folder/'expected.json').write_text(json.dumps(data,indent=2)+'\n')
            print(name,'charge',max(abs(r['pct_err']) for r in rows),'acid',acid,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--exe',type=Path,default=INSTALL/'bin/Release/phreeqc.exe')
    parser.add_argument('--database',type=Path,default=INSTALL/'database/minteq.v4.dat')
    args=parser.parse_args()
    generate(args.exe,args.database)
