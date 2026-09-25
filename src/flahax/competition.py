"""Named mineral saturation comparison from free-ion activities."""
from __future__ import annotations
from dataclasses import dataclass
import math
from .delivery_contracts import DeliveryError
from .struvite import struvite_saturation_index

@dataclass(frozen=True, slots=True)
class CalciumSulfateStruviteCompetition:
    gypsum_si: float
    struvite_si: float

@dataclass(frozen=True, slots=True)
class CarbonateCompetition:
    calcite_si: float
    gypsum_si: float
    struvite_si: float

def calcium_sulfate_struvite_competition(calcium_activity: float, sulfate_activity: float, magnesium_activity: float, ammonium_activity: float, phosphate_activity: float) -> CalciumSulfateStruviteCompetition:
    """Compare gypsum and struvite SI at supplied free-ion activities."""
    values=(calcium_activity,sulfate_activity,magnesium_activity,ammonium_activity,phosphate_activity)
    if not all(math.isfinite(v) and v>0 for v in values):
        raise DeliveryError("out_of_range","competition activities must be positive and finite")
    return CalciumSulfateStruviteCompetition(math.log10(calcium_activity*sulfate_activity)+4.58, struvite_saturation_index(magnesium_activity,ammonium_activity,phosphate_activity))

def carbonate_competition(calcium_activity: float, carbonate_activity: float, sulfate_activity: float, magnesium_activity: float, ammonium_activity: float, phosphate_activity: float) -> CarbonateCompetition:
    """Compare calcite, gypsum, and struvite SI from free-ion activities."""
    base=calcium_sulfate_struvite_competition(calcium_activity,sulfate_activity,magnesium_activity,ammonium_activity,phosphate_activity)
    if not math.isfinite(carbonate_activity) or carbonate_activity <= 0:
        raise DeliveryError("out_of_range","carbonate activity must be positive and finite")
    return CarbonateCompetition(math.log10(calcium_activity*carbonate_activity)+8.45,base.gypsum_si,base.struvite_si)
