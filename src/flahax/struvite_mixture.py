"""Fixed-pH Mg/NH4/phosphate reference-mixture speciation at 25 °C."""
from __future__ import annotations
from dataclasses import dataclass
import math
from .ammonia import ammonia_speciation
from .delivery_contracts import DeliveryError
from .equilibrium import davies_gamma
from .phosphate import LOG_BETA_H2PO4_25C, LOG_BETA_H3PO4_25C, LOG_BETA_HPO4_25C
from .phosphate_complexes import LOG_BETA_MG_H2PO4, LOG_BETA_MG_HPO4, LOG_BETA_MG_PO4, LOG_BETA_NA_HPO4
from .struvite import struvite_saturation_index

@dataclass(frozen=True, slots=True)
class StruviteMixtureSpeciation:
    magnesium_molal: float; ammoniacal_nitrogen_molal: float; phosphate_molal: float; sodium_molal: float; ph: float; ionic_strength: float
    free_magnesium_molal: float; ammonium_molal: float; free_phosphate_molal: float; struvite_si: float

def struvite_mixture_speciation(magnesium_molal: float, ammoniacal_nitrogen_molal: float, phosphate_molal: float, sodium_molal: float, ph: float, ionic_strength: float) -> StruviteMixtureSpeciation:
    """Solve Mg/P and NHx mass balances at supplied pH and ionic strength."""
    values = (magnesium_molal, ammoniacal_nitrogen_molal, phosphate_molal, sodium_molal, ph, ionic_strength)
    if not all(math.isfinite(v) for v in values) or min(values[:4]) <= 0 or not 0 <= ph <= 14 or not 0 <= ionic_strength <= .1:
        raise DeliveryError("out_of_range", "invalid fixed-pH struvite mixture inputs")
    g1, g2, g3 = (davies_gamma(z, ionic_strength) for z in (1,2,3)); ah=10**-ph; ana=sodium_molal*g1
    def at(mg):
        amg=mg*g2; hpo=10**LOG_BETA_HPO4_25C*ah; h2=10**LOG_BETA_H2PO4_25C*ah**2; h3=10**LOG_BETA_H3PO4_25C*ah**3
        b=1/g3+hpo/g2+h2/g1+h3+10**LOG_BETA_MG_PO4*amg/g1+10**LOG_BETA_MG_HPO4*amg*hpo+10**LOG_BETA_MG_H2PO4*amg*h2/g1+10**LOG_BETA_NA_HPO4*ana*hpo/g1
        apo=phosphate_molal/b
        complexes=10**LOG_BETA_MG_PO4*amg*apo/g1+10**LOG_BETA_MG_HPO4*amg*hpo*apo+10**LOG_BETA_MG_H2PO4*amg*h2*apo/g1
        return apo, complexes
    lo,hi=0.,magnesium_molal
    for _ in range(100):
        mg=(lo+hi)/2; _,complexes=at(mg)
        if mg+complexes < magnesium_molal: lo=mg
        else: hi=mg
    mg=(lo+hi)/2; apo,_=at(mg); nh=ammonia_speciation(ammoniacal_nitrogen_molal,ph,ionic_strength)
    return StruviteMixtureSpeciation(magnesium_molal, ammoniacal_nitrogen_molal, phosphate_molal, sodium_molal, ph, ionic_strength, mg, nh.ammonium_molal, apo/g3, struvite_saturation_index(mg*g2,nh.ammonium_activity,apo))
