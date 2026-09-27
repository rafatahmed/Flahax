"""Extract the fixed-valence fertilizer reaction closure from pinned MINTEQ.

Offline only. The source database is never modified. Each exported reaction
retains its original equation, line number, log K and source identity.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASES = ['Ca+2', 'Mg+2', 'K+', 'Na+', 'Cl-', 'NO3-', 'NH4+', 'SO4-2',
         'CO3-2', 'PO4-3', 'Fe+3', 'Fe+2', 'Mn+2', 'Zn+2', 'Cu+2',
         'H3BO3', 'MoO4-2', 'Edta-4', 'Citrate-3', 'Dtp-5', 'Edd-4', 'Ure']
PHASES = ['Calcite', 'Gypsum', 'Anhydrite', 'Epsomite', 'Kieserite',
          'Hydroxylapatite', 'CaHPO4:2H2O', 'CaHPO4', 'Struvite',
          'Ferrihydrite', 'Goethite', 'Fe(OH)2', 'Pyrochroite', 'Zincite',
          'Cu(OH)2', 'Tenorite', 'Siderite', 'Rhodochrosite', 'Smithsonite',
          'Malachite', 'Strengite', 'Vivianite', 'Mn3(PO4)2', 'MnHPO4',
          'Zn3(PO4)2:4H2O', 'Cu3(PO4)2', 'Halite', 'Sylvite']

def side(text):
    values = {}
    for term in text.strip().split(' + '):
        fields = term.strip().split()
        if not fields:
            continue
        coefficient, name = (float(fields[0]), fields[1]) if len(fields) == 2 else (1., fields[0])
        values[name] = values.get(name, 0.) + coefficient
    return values

def charge(name):
    match = re.search(r'([+-])(\d*)$', name)
    return (1 if match[1] == '+' else -1) * int(match[2] or 1) if match else 0

def records(text, source):
    section, pending, phase_name = '', None, None
    result = []
    for index, raw in enumerate(text.splitlines(), 1):
        line = raw.split('#')[0].strip()
        if not line:
            continue
        if line in ('SOLUTION_SPECIES', 'SOLUTION_MASTER_SPECIES', 'PHASES', 'EXCHANGE_MASTER_SPECIES',
                    'EXCHANGE_SPECIES', 'SURFACE_MASTER_SPECIES', 'SURFACE_SPECIES', 'END'):
            section = line
            pending = None
            continue
        if section not in ('SOLUTION_SPECIES', 'PHASES'):
            continue
        if '=' in line:
            left, right = map(side, line.split('='))
            name = phase_name if section == 'PHASES' else next(iter(right))
            pending = dict(name=name, equation=line, left=left, right=right,
                           source=source, line=index, kind=section, log_k=0.)
            result.append(pending)
        elif line.split()[0].lstrip('-').lower() == 'log_k' and pending:
            pending['log_k'] = float(line.split()[1])
        elif line.startswith('-gamma') and pending:
            pending['gamma'] = [float(x) for x in line.split()[1:3]]
        elif section == 'PHASES' and not raw[0].isspace():
            phase_name = line
    return result

def build(database):
    raw = database.read_bytes()
    sources = [(database.read_text(), 'minteq.v4.dat')]
    for filename in ('flahax-chelates-25c.dat', 'flahax-phases-25c.dat'):
        sources.append(((ROOT / 'tests/fixtures/phreeqc/database' / filename).read_text(), filename))
    entries = [r for text, name in sources for r in records(text, name)]
    known = {n: ({n: 1.}, 0.) for n in BASES + ['H+', 'H2O']}
    selected = {}
    for _ in range(20):
        changed = False
        for r in entries:
            if r['kind'] != 'SOLUTION_SPECIES' or r['name'] in selected:
                continue
            name = r['name']
            if name == 'e-' or any(n == 'e-' for n in r['left'] | r['right']):
                continue
            if name in BASES + ['H+', 'H2O']:
                if r['left'] == r['right']:
                    selected[name] = dict(r, powers={name: 1.}, beta=0., charge=charge(name))
                continue
            other = (set(r['left']) | set(r['right'])) - {name}
            if not other <= known.keys():
                continue
            coefficient = r['right'].get(name, 0) - r['left'].get(name, 0)
            if not coefficient:
                continue
            powers, beta = {}, r['log_k']
            for sign, terms in ((1, r['left']), (-1, r['right'])):
                for n, count in terms.items():
                    if n == name:
                        continue
                    p, k = known[n]
                    beta += sign * count * k
                    for b, v in p.items():
                        powers[b] = powers.get(b, 0.) + sign * count * v
            powers = {b: v / coefficient for b, v in powers.items() if v}
            if any(v < 0 for b, v in powers.items() if b not in ('H+', 'H2O')):
                continue
            beta /= coefficient
            known[name] = powers, beta
            selected[name] = dict(r, powers=powers, beta=beta, charge=charge(name))
            changed = True
        if not changed:
            break
    phases = {}
    for name in BASES + ['H+']:
        if name not in selected:
            selected[name] = dict(name=name, equation=f'{name} = {name}', powers={name:1.},
                                 beta=0., log_k=0., charge=charge(name), line=0,
                                 source='fixed-valence analytical basis')
    for r in entries:
        if r['kind'] != 'PHASES' or r['name'] not in PHASES:
            continue
        solid = next(iter(r['left']))
        if not ((set(r['left']) | set(r['right'])) - {solid}) <= known.keys():
            continue
        powers, beta = {}, r['log_k']
        for sign, terms in ((1, r['right']), (-1, r['left'])):
            for n, count in terms.items():
                if n == solid:
                    continue
                p, k = known[n]
                beta -= sign * count * k
                for b, v in p.items():
                    powers[b] = powers.get(b, 0.) + sign * count * v
        phases[r['name']] = dict(r, powers={b:v for b,v in powers.items() if v}, beta=beta)
    missing = set(PHASES) - phases.keys()
    if missing:
        raise ValueError(f'unresolved phase names: {missing}')
    data = dict(schema=1, temperature_c=25, database_sha256=hashlib.sha256(raw).hexdigest(),
                source_url='https://github.com/usgs-coupled-subtrees/phreeqc3-database/blob/master/minteq.v4.dat',
                bases=BASES, aqueous=list(selected.values()), phases=list(phases.values()),
                aliases={'Hydroxyapatite': 'Hydroxylapatite', 'Hopeite': 'Zn3(PO4)2:4H2O',
                         'Brushite': 'CaHPO4:2H2O', 'B(OH)3':'H3BO3', 'B(OH)4-':'H2BO3-'})
    (ROOT / 'src/flahax/data/chemistry_25c.json').write_text(json.dumps(data, indent=2)+'\n')
    print(f'{len(selected)} aqueous species; {len(phases)} phases')
    write_coverage(data)


def write_coverage(data):
    """Exact, reviewable inventory; no guessed species or phase names."""
    lines = ['# P2/P3 chemistry coverage matrix', '',
             'Generated by `tools/build_chemistry_model.py` from the pinned 25 C database and extensions.',
             'Every entry below is evaluated by `src/flahax/aqueous_model.py`; phase entries also participate',
             'in the nonnegative active-set allocation. The machine-readable coefficients, source lines,',
             'original equations and transformed master-basis powers are in `src/flahax/data/chemistry_25c.json`.', '',
             f'Base SHA-256: `{data["database_sha256"]}`.', '',
             '## Alias resolution and genuine gaps', '',
             '| Requested name/family | Exact entry or resolution | Classification |',
             '|---|---|---|',
             '| Hydroxyapatite | Hydroxylapatite | Native alias, not missing data |',
             '| Brushite; hopeite | CaHPO4:2H2O; Zn3(PO4)2:4H2O | Native aliases |',
             '| B(OH)3; B(OH)4- | H3BO3; H2BO3- | Native aqueous aliases |',
             '| Trace hydroxides/phosphates/carbonates | Named native entries below | Not missing data |',
             '| Struvite; kieserite; sylvite | flahax-phases-25c.dat | Absent from this base; cited extension |',
             '| Fe-DTPA; Fe-o,o-EDDHA | Dtp/Edd protonation and Fe-only 1:1 reactions | Absent from base; selected cited profile |',
             '| Urea | Ure = Ure | Neutral conserved inventory, not invented hydrolysis |', '',
             'Sources and scientific conditions: [chelate profile](sources/flahax-chelate-thermodynamic-profile.md),',
             '[model](fertilizer-equilibrium-model.md), [fixture contract](reference-fixtures.md).', '',
             'Only the frozen product oxidation states are conserved; redox reactions containing electrons',
             'are not imported. A fixed analytical master identity needs no fitted equilibrium constant.', '',
             '## Exact aqueous species and ion pairs', '',
             '| Species | Original reaction | log K (25 C) | Source:line |', '|---|---|---:|---|']
    for r in data['aqueous']:
        lines.append(f'| `{r["name"]}` | `{r["equation"]}` | {r["log_k"]:g} | {r["source"]}:{r["line"]} |')
    lines += ['', '## Exact solid phases', '',
              '| Phase | Dissolution reaction | log K (25 C) | Source:line |', '|---|---|---:|---|']
    for r in data['phases']:
        lines.append(f'| `{r["name"]}` | `{r["equation"]}` | {r["log_k"]:g} | {r["source"]}:{r["line"]} |')
    (ROOT/'docs/chemistry-coverage-matrix.md').write_text('\n'.join(lines)+'\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('database', type=Path)
    build(parser.parse_args().database)
