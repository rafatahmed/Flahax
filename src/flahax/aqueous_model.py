"""One dependency-free mass-action solver for the pinned 25 C reaction set.

Every analytical component and ligand is solved simultaneously in log activity
space. Phase amounts are additional unknowns; an active-set method enforces
nonnegative solid amounts and nonpositive SI for every allowed absent phase.
Redox valences are separate conserved inputs, as in PHREEQC SOLUTION speciation.
"""
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
import json
import math
from .delivery_contracts import DeliveryError
from .root_finding import shrink_bracket

LN10 = math.log(10.)

@lru_cache(maxsize=1)
def chemistry():
    return json.loads(files('flahax').joinpath('data/chemistry_25c.json').read_text())

@dataclass(frozen=True)
class AqueousResult:
    totals: dict
    ph: float
    ionic_strength: float
    species: dict
    activities: dict
    saturation_indices: dict
    precipitated: dict
    residuals: dict
    iterations: int
    charge_balance: float
    water_activity: float

def linear(a, b):
    """Pivoted elimination; no optional numerical dependency at runtime."""
    a = [list(row)+[v] for row,v in zip(a,b)]
    n=len(b)
    for k in range(n):
        p=max(range(k,n),key=lambda i:abs(a[i][k]))
        a[k],a[p]=a[p],a[k]
        if abs(a[k][k]) < 1e-25:
            raise DeliveryError('nonconvergent','singular equilibrium Jacobian')
        for i in range(k+1,n):
            f=a[i][k]/a[k][k]
            for j in range(k+1,n+1):
                a[i][j]-=f*a[k][j]
    x=[0.]*n
    for i in range(n-1,-1,-1):
        x[i]=(a[i][n]-sum(a[i][j]*x[j] for j in range(i+1,n)))/a[i][i]
    return x

def _damped_step(evaluate, x, residual, matrix):
    """Levenberg-Marquardt step that lowers the squared residual, or None."""
    m=len(residual)
    normal=[[sum(matrix[r][i]*matrix[r][j] for r in range(m)) for j in range(m)] for i in range(m)]
    gradient=[sum(matrix[r][i]*residual[r] for r in range(m)) for i in range(m)]
    scale=[max(normal[i][i],1e-300) for i in range(m)]
    merit=sum(v*v for v in residual)
    damping=1e-3
    for _ in range(40):
        system=[[normal[i][j]+(damping*scale[i] if i==j else 0.) for j in range(m)] for i in range(m)]
        try:
            step=linear(system,[-g for g in gradient])
        except DeliveryError:
            step=None
        if step is not None:
            trial=[v+d for v,d in zip(x,step)]
            got=evaluate(trial)
            if got and sum(v*v for v in got[0])<merit:
                return trial
        damping*=10
    return None

def solve(totals, ph, *, phases=(), ionic_strength=None, temperature_c=25.):
    if temperature_c != 25:
        raise DeliveryError('temperature_out_of_range','reaction dataset is restricted to 25 C')
    if not math.isfinite(ph) or not 0 <= ph <= 14:
        raise DeliveryError('out_of_range','pH must be finite in [0,14]')
    for name,value in totals.items():
        if name not in chemistry()['bases'] or not math.isfinite(value) or value < 0:
            raise DeliveryError('invalid_totals',f'invalid analytical component {name}: {value}')
    if ionic_strength is not None and (not math.isfinite(ionic_strength) or not 0 <= ionic_strength <= .1):
        raise DeliveryError('activity_model_out_of_range','Davies model requires I <= 0.1 mol/kgw')
    totals={n:v for n,v in totals.items() if v>0}
    bases=list(totals)
    n=len(bases)
    permitted=set(bases)|{'H+','H2O'}
    records=[r for r in chemistry()['aqueous'] if r['name']!='H2O' and set(r['powers'])<=permitted]
    all_phases={r['name']:r for r in chemistry()['phases']}
    phases=[chemistry()['aliases'].get(p,p) for p in phases]
    if any(p not in all_phases for p in phases):
        raise DeliveryError('unknown_phase','phase not in the pinned reaction set')
    candidates={p:all_phases[p] for p in phases if set(all_phases[p]['powers'])<=permitted}
    stoich=[[r['powers'].get(b,0.) for b in bases] for r in records]
    # Each species involves few components; iterate only its non-zero stoichiometry.
    sparse=[[(j,v) for j,v in enumerate(s) if v] for s in stoich]
    strength=ionic_strength if ionic_strength is not None else min(.05,max(1e-8,sum(totals.values())))
    logs=[math.log10(totals[b])-3 for b in bases]
    active=[]
    solids={}
    water=1.
    count=0
    def lgamma(z):
        root=math.sqrt(strength)
        return -.509*z*z*(root/(1+root)-.3*strength) if z else .1*strength

    for outer in range(100):
        offsets=[r['beta']-ph*r['powers'].get('H+',0)+math.log10(water)*r['powers'].get('H2O',0)-lgamma(r['charge']) for r in records]
        def evaluate(x, jacobian=False):
            amounts=[10.**max(-300,min(100,o+sum(v*x[j] for j,v in nz))) for o,nz in zip(offsets,sparse)]
            sums=[0.]*n
            for a,nz in zip(amounts,sparse):
                for j,v in nz:
                    sums[j]+=a*v
            for k,p in enumerate(active):
                for j,b in enumerate(bases):
                    sums[j]+=x[n+k]*all_phases[p]['powers'].get(b,0.)
            if any(v<=0 for v in sums):
                return None
            residual=[math.log10(v/totals[b]) for b,v in zip(bases,sums)]
            for p in active:
                r=all_phases[p]
                residual.append(sum(r['powers'].get(b,0)*x[j] for j,b in enumerate(bases))-ph*r['powers'].get('H+',0)+math.log10(water)*r['powers'].get('H2O',0)-r['beta'])
            if not jacobian:
                return residual,amounts
            moments=[[0.]*n for _ in range(n)]
            for a,nz in zip(amounts,sparse):
                for j,vj in nz:
                    weighted=a*vj
                    row=moments[j]
                    for k,vk in nz:
                        row[k]+=weighted*vk
            matrix=[]
            for j,b in enumerate(bases):
                row=[value/sums[j] for value in moments[j]]
                row += [all_phases[p]['powers'].get(b,0.)/(sums[j]*LN10) for p in active]
                matrix.append(row)
            for p in active:
                matrix.append([all_phases[p]['powers'].get(b,0.) for b in bases]+[0.]*len(active))
            return residual,amounts,matrix
        for phase_step in range(80):
            x=logs+[solids.get(p,0.) for p in active]
            for iteration in range(150):
                count+=1
                residual,amounts,matrix=evaluate(x,True)
                norm=max(map(abs,residual),default=0.)
                if norm<2e-10:
                    break
                step=linear(matrix,[-r for r in residual])
                alpha=min(1.,4/max([abs(v) for v in step[:n]]+[4.]))
                for _ in range(50):
                    trial=[v+alpha*d for v,d in zip(x,step)]
                    got=evaluate(trial)
                    if got and max(map(abs,got[0]),default=0.) < norm:
                        x=trial
                        break
                    alpha*=.5
                else:
                    # A near-singular Jacobian can give a useless Newton direction
                    # (seen after a cold start with a strong chelate); take a damped
                    # least-squares step instead. Paths that converge today are unchanged.
                    x=_damped_step(evaluate,x,residual,matrix)
                    if x is None:
                        raise DeliveryError('nonconvergent',f'equilibrium line search stalled (residual {norm:g})')
            else:
                raise DeliveryError('nonconvergent','aqueous Newton iteration limit')
            logs=x[:n]
            solids=dict(zip(active,x[n:]))
            negative=[p for p in active if solids[p]<-1e-13]
            if negative:
                active.remove(min(negative,key=solids.get))
                continue
            loga=dict(zip(bases,logs))|{'H+':-ph,'H2O':math.log10(water)}
            saturation={p:sum(v*loga[b] for b,v in r['powers'].items())-r['beta'] for p,r in all_phases.items() if set(r['powers'])<=permitted}
            excess=[p for p in candidates if p not in active and saturation[p]>1e-8]
            if not excess:
                break
            active.append(max(excess,key=saturation.get))
        else:
            raise DeliveryError('nonconvergent','phase active set iteration limit')
        species={r['name']:a for r,a in zip(records,amounts)}
        updated=.5*sum(a*r['charge']**2 for a,r in zip(amounts,records))
        next_water=max(.9,1-sum(amounts)/55.5084)
        if updated>.1:
            raise DeliveryError('activity_model_out_of_range',f'Davies ionic strength {updated:g} exceeds 0.1')
        if (ionic_strength is not None or abs(updated-strength)<1e-12) and abs(next_water-water)<1e-12:
            activities={r['name']:species[r['name']]*10**lgamma(r['charge']) for r in records}
            activities['H2O']=water
            residuals={b:sum(a*s[j] for a,s in zip(amounts,stoich))+sum(max(0,v)*all_phases[p]['powers'].get(b,0.) for p,v in solids.items())-totals[b] for j,b in enumerate(bases)}
            return AqueousResult(totals,ph,strength,species,activities,saturation,
                                 {p:max(0,v) for p,v in solids.items()},residuals,count,
                                 sum(a*r['charge'] for a,r in zip(amounts,records)),water)
        if ionic_strength is None:
            strength=(strength+updated)/2
        water=(water+next_water)/2
    raise DeliveryError('nonconvergent','ionic strength/water iteration limit')

@dataclass(frozen=True)
class AcidResult:
    initial: AqueousResult
    target: AqueousResult
    nitric_acid_molal: float
    post_mix_measurement_required: bool = True

def nitric_target(totals, initial_ph, target_ph, *, phases=()):
    """Conserve every component, including added nitrate, through the same solve.

    Initial residual charge defines the strong-ion inventory (water alkalinity
    need not be guessed). HNO3 is neutral as a reagent: the final residual
    electrical charge equals the initial residual charge, after adding nitrate.
    """
    initial=solve(totals,initial_ph,phases=phases)
    if target_ph == initial_ph:
        return AcidResult(initial,initial,0.)
    if target_ph>initial_ph:
        raise DeliveryError('wrong_reagent_direction','target requires base')
    lo,hi=0.,.001
    def at(dose):
        return solve(dict(totals)|{'NO3-':totals.get('NO3-',0.)+dose},target_ph,phases=phases)
    target=at(0.)
    if target.charge_balance < initial.charge_balance-1e-12:
        raise DeliveryError('wrong_reagent_direction','target requires base')
    f_lo=target.charge_balance-initial.charge_balance
    while (f_hi:=at(hi).charge_balance-initial.charge_balance)>0:
        lo,f_lo=hi,f_hi
        hi*=2
    # Same final width as 40 bisection steps from [0, hi], in far fewer solves.
    lo,hi=shrink_bracket(lambda dose:at(dose).charge_balance-initial.charge_balance,
                         lo,f_lo,hi,f_hi,width=hi*2.**-40)
    dose=(lo+hi)/2
    return AcidResult(initial,at(dose),dose)
