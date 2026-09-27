"""Named phase allocation references and low/high saturation boundaries."""
import json
import tempfile
import shutil
from pathlib import Path
from phreeqc_evidence import ROOT, INSTALL, merge, execute, input_text, sha, fixed_ammonium, CASES as PRODUCTS
from flahax.aqueous_model import chemistry
from flahax.product_conversion import catalogue_dose_totals

CASES={
 'calcite':({'Ca+2':.001,'CO3-2':.002},9.,['Calcite']),
 'calcium_phosphate':({'Ca+2':.002,'PO4-3':.001},7.4,['Hydroxylapatite','CaHPO4:2H2O','CaHPO4']),
 'gypsum':({'Ca+2':.04,'SO4-2':.04},6.,['Gypsum','Anhydrite']),
 'trace_hydroxides':({'Fe+3':1e-4,'Zn+2':1e-4,'Cu+2':1e-4,'Mn+2':1e-4},8.,['Ferrihydrite','Zincite','Cu(OH)2','Pyrochroite']),
 'trace_phosphates':({'Fe+3':1e-4,'Zn+2':1e-4,'Cu+2':1e-4,'Mn+2':1e-4,'PO4-3':.001},6.,['Strengite','Zn3(PO4)2:4H2O','Cu3(PO4)2','Mn3(PO4)2']),
 'trace_carbonates':({'Zn+2':1e-4,'Cu+2':1e-4,'Mn+2':1e-4,'CO3-2':.002},8.5,['Smithsonite','Malachite','Rhodochrosite']),
 'magnesium_salts':({'Mg+2':.001,'SO4-2':.001},6.,['Epsomite','Kieserite']),
 'zero_stock':({'Ca+2':1e-8,'CO3-2':1e-8},6.,['Calcite']),
 'struvite':({'Mg+2':.002,'NH4+':.002,'PO4-3':.002},9.,['Struvite']),
 'ferrous_phases':({'Fe+2':.0001,'PO4-3':.001,'CO3-2':.001},7.,['Vivianite','Siderite','Fe(OH)2']),
 'mixed_product_phases':(catalogue_dose_totals(PRODUCTS['mixed_products']),6.,[r['name'] for r in chemistry()['phases']]),
}

def generate():
    exe=INSTALL/'bin/Release/phreeqc.exe'
    base=INSTALL/'database/minteq.v4.dat'
    with tempfile.TemporaryDirectory(prefix='flahax-phases-') as tmp:
        db=Path(tmp)/'merged.dat'
        merge(base,db)
        for name,(totals,ph,phases) in CASES.items():
            folder=ROOT/'tests/fixtures/phreeqc/phases'/name
            previous=folder/(name+'.out')
            if previous.exists() and any(marker in previous.read_text(errors='replace') for marker in ('ERROR:', 'WARNING:')):
                archive=ROOT/'tests/fixtures/phreeqc/failures'/('phase_'+name+'_initial_charge')
                archive.mkdir(parents=True,exist_ok=True)
                for artifact in folder.glob(name+'.*'):
                    shutil.copy2(artifact,archive/artifact.name)
            totals=totals|{'Na+':.01,'Cl-':.01}
            definitions={r['name']:r for r in chemistry()['phases']}
            phases=[p for p in phases if set(definitions[p]['powers']) <= set(totals)|{'H+','H2O'}]
            text=input_text(name,totals,ph,phases=phases)
            if name=='mixed_product_phases':
                text=fixed_ammonium(text)
            rows=execute(exe,db,folder,name,text)
            # Phase equilibration changes pH naturally in a closed solution.
            # Runtime is compared at that independently obtained final pH.
            totals['Na+']=rows[0]['Na']
            water=rows[-1]['mass_H2O']
            totals={b:v/water for b,v in totals.items()}
            data={'schema':1,'runtime_totals':totals,'phases':phases,'selected_rows':rows,
                  'reference':{'software':'PHREEQC 3.8.6-17100','base_sha256':sha(base),'merged_sha256':sha(db)},
                  'tolerances':{'molality_relative':.15,'molality_absolute':2e-8,'si_absolute':.25,'phase_relative':.08,'phase_absolute':2e-8},
                  'hashes':{p.name:sha(p) for p in folder.iterdir() if p.suffix in ('.pqi','.sel','.out','.screen')}}
            (folder/'expected.json').write_text(json.dumps(data,indent=2)+'\n')
            print(name,'pH',rows[-1]['pH'],'charge',rows[-1]['pct_err'],flush=True)

if __name__=='__main__':
    generate()
