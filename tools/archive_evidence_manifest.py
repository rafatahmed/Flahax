"""Index preserved pre-closure successes and diagnostic artifacts without editing them."""
import json
from phreeqc_evidence import ROOT, sha, selected

folder=ROOT/'tests/fixtures/phreeqc'
files=[]
for name in ('fe_edta','mn_edta','zn_edta','cu_edta','fe_dtpa','fe_eddha'):
    paths=[folder/(name+ext) for ext in ('.pqi','.out','.sel')]
    files.append({'case':name,'kind':'historical_success','selected_rows':selected(paths[-1]),
                  'replay_relative':1e-4,'replay_absolute':1e-8,
                  'hashes':{str(p.relative_to(folder)).replace('\\','/'):sha(p) for p in paths}})
for p in sorted((folder/'failures').rglob('*')):
    if p.is_file() and p.suffix in ('.pqi','.out','.screen','.sel','.json','.inp'):
        files.append({'kind':'preserved_diagnostic','hashes':{str(p.relative_to(folder)).replace('\\','/'):sha(p)}})
(folder/'preserved-evidence.json').write_text(json.dumps({'schema':1,'artifacts':files},indent=2)+'\n')
