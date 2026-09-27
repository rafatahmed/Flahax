"""Compatibility views over the single simultaneous MINTEQ reaction model."""
from dataclasses import dataclass
from typing import Mapping
from .aqueous_model import AqueousResult, chemistry, solve
from .delivery_contracts import DeliveryError
from .fertilizer_equilibrium import FertilizerTotals, FertilizerEquilibrium
from .trace_equilibrium import ChMicroTotals, TraceEquilibrium
from .phase_allocation import phase_allocation

MACRO_BASIS = dict(calcium='Ca+2',magnesium='Mg+2',phosphate='PO4-3',carbonate='CO3-2',
                   sulfate='SO4-2',ammonium='NH4+',nitrate='NO3-',potassium='K+',sodium='Na+',chloride='Cl-')
TRACE_BASIS = dict(iron='Fe+3',manganese='Mn+2',zinc='Zn+2',copper='Cu+2',edta='Edta-4',
                   dtpa='Dtp-5',eddha='Edd-4',citrate='Citrate-3',boron='H3BO3',molybdate='MoO4-2',
                   calcium='Ca+2',magnesium='Mg+2')
ALIASES = {'EDTA-4':'Edta-4','Fe(III)-EDTA':'Fe(Edta)-','Mn-EDTA':'Mn(Edta)-2',
           'Zn-EDTA':'Zn(Edta)-2','Cu-EDTA':'Cu(Edta)-2','Ca-EDTA':'Ca(Edta)-2','Mg-EDTA':'Mg(Edta)-2',
           'DTPA-free':'Dtp-5','o,o-EDDHA-free':'Edd-4','citrate-free':'Citrate-3',
           'Fe+3-DTPA':'FeDtp-2','Fe+3-o,o-EDDHA':'FeEdd-',
           'B(OH)3':'H3BO3','B(OH)4-':'H2BO3-'}

def view(values):
    result=dict(values)
    result.update({alias:values.get(native,0.) for alias,native in ALIASES.items()})
    for name in chemistry()['bases']+['OH-','H+','HPO4-2','H2PO4-','HCO3-','CO2','HMoO4-','H2MoO4']:
        result.setdefault(name,0.)
    return result

@dataclass(frozen=True)
class MixedFertilizerEquilibrium:
    macro: FertilizerEquilibrium
    trace: TraceEquilibrium | None
    ionic_strength: float
    iterations: int
    aqueous: AqueousResult

    @property
    def species(self) -> Mapping[str,float]:
        return view(self.aqueous.species)

def analytical_basis(totals, trace_totals=None):
    result={b:getattr(totals,n) for n,b in MACRO_BASIS.items()}
    if trace_totals:
        for n,b in TRACE_BASIS.items():
            result[b]=result.get(b,0.)+getattr(trace_totals,n)
    return result

def from_basis(totals,ph,*,allow_precipitation=True):
    phases=[r['name'] for r in chemistry()['phases']] if allow_precipitation else ()
    result=solve(totals,ph,phases=phases)
    species,activities=view(result.species),view(result.activities)
    saturation=dict(result.saturation_indices)
    saturation['Hydroxyapatite']=saturation.get('Hydroxylapatite',float('-inf'))
    for p in ('Calcite','Gypsum','Struvite'):
        saturation.setdefault(p,float('-inf'))
    dissolved=dict(totals)
    for r in chemistry()['phases']:
        for b,v in r['powers'].items():
            if b in dissolved:
                dissolved[b]-=result.precipitated.get(r['name'],0.)*v
    macro_totals=FertilizerTotals(**{n:max(0.,dissolved.get(b,0.)) for n,b in MACRO_BASIS.items()})
    trace_totals=ChMicroTotals(**{n:max(0.,dissolved.get(b,0.)) for n,b in TRACE_BASIS.items()})
    macro=FertilizerEquilibrium(macro_totals,ph,result.ionic_strength,species,activities,saturation,
                                tuple(phase_allocation(p,0.,v) for p,v in result.precipitated.items() if v>0))
    trace=TraceEquilibrium(trace_totals,ph,result.ionic_strength,species,activities)
    return MixedFertilizerEquilibrium(macro,trace,result.ionic_strength,result.iterations,result)

def solve_mixed_fertilizer_equilibrium(totals,ph,*,trace_totals=None,allow_precipitation=True):
    if not isinstance(totals,FertilizerTotals) or (trace_totals is not None and not isinstance(trace_totals,ChMicroTotals)):
        raise DeliveryError('invalid_type','expected FertilizerTotals and optional ChMicroTotals')
    return from_basis(analytical_basis(totals,trace_totals),ph,allow_precipitation=allow_precipitation)
