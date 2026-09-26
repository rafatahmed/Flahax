"""Coupled 25 C Davies-domain macro/trace equilibrium entry point.

This iterates the shared ionic strength and the Ca/Mg inventory available
after ligand binding; it is not a completed macro solve followed by trace.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
import math
from typing import Mapping

from .delivery_contracts import DeliveryError
from .fertilizer_equilibrium import FertilizerTotals, FertilizerEquilibrium, _at_fixed_ionic_strength, _fixed_ph_equilibrium, _valid_ph
from .trace_equilibrium import ChMicroTotals, TraceEquilibrium, solve_ch_micro_equilibrium

@dataclass(frozen=True, slots=True)
class MixedFertilizerEquilibrium:
    macro: FertilizerEquilibrium
    trace: TraceEquilibrium | None
    ionic_strength: float
    iterations: int

    @property
    def species(self) -> Mapping[str, float]:
        values = dict(self.macro.species)
        if self.trace:
            values.update(self.trace.species)
        return values

_CHARGES = {"Fe+3": 3, "Mn+2": 2, "Zn+2": 2, "Cu+2": 2, "Ca+2": 2, "Mg+2": 2, "EDTA-4": -4, "B(OH)4-": -1, "MoO4-2": -2, "HMoO4-": -1, "Fe(III)-EDTA": -1, "Mn-EDTA": -2, "Zn-EDTA": -2, "Cu-EDTA": -2, "Ca-EDTA": -2, "Mg-EDTA": -2}
_MACRO_CHARGES = {"Ca+2": 2, "Mg+2": 2, "PO4-3": -3, "HPO4-2": -2, "H2PO4-": -1, "SO4-2": -2, "NH4+": 1, "NO3-": -1, "K+": 1, "Na+": 1, "Cl-": -1, "CO3-2": -2, "HCO3-": -1}

def _mixed_ionic_strength(macro: Mapping[str, float], trace: Mapping[str, float]) -> float:
    value = .5 * sum(macro.get(key, 0.0) * z * z for key, z in _MACRO_CHARGES.items() if key not in {"Ca+2", "Mg+2"})
    return value + .5 * sum(trace.get(key, 0.0) * z * z for key, z in _CHARGES.items())

def solve_mixed_fertilizer_equilibrium(totals: FertilizerTotals, ph: float, *, trace_totals: ChMicroTotals | None = None, allow_precipitation: bool = True) -> MixedFertilizerEquilibrium:
    """Jointly converge macro ions, EDTA/B/Mo species, and ionic strength.

    Existing macro phase allocations are preserved for macro-only calls. Trace
    phases are omitted rather than invented: no compatible trace phase dataset
    is currently source-backed.
    """
    if not isinstance(totals, FertilizerTotals):
        raise DeliveryError("invalid_type", "totals must be FertilizerTotals")
    ph = _valid_ph(ph)
    if trace_totals is None:
        macro = _fixed_ph_equilibrium(totals, ph)
        return MixedFertilizerEquilibrium(macro, None, macro.ionic_strength, 1)
    if not isinstance(trace_totals, ChMicroTotals):
        raise DeliveryError("invalid_type", "trace_totals must be ChMicroTotals")
    ionic_strength = .01
    bound_ca = bound_mg = 0.0
    for iteration in range(1, 81):
        available = replace(totals, calcium=max(0.0, totals.calcium-bound_ca), magnesium=max(0.0, totals.magnesium-bound_mg))
        macro_species, macro_activities, saturation = _at_fixed_ionic_strength(available, ph, ionic_strength)
        trace = solve_ch_micro_equilibrium(replace(trace_totals, calcium=trace_totals.calcium + macro_species["Ca+2"], magnesium=trace_totals.magnesium + macro_species["Mg+2"]), ph, ionic_strength)
        updated = _mixed_ionic_strength(macro_species, trace.species)
        if not math.isfinite(updated) or updated > .1:
            raise DeliveryError("activity_model_out_of_range", "Davies model is limited to I <= 0.1 mol/kgw")
        next_ca, next_mg = trace.species["Ca-EDTA"], trace.species["Mg-EDTA"]
        if max(abs(updated-ionic_strength), abs(next_ca-bound_ca), abs(next_mg-bound_mg)) < 1e-10:
            macro = FertilizerEquilibrium(available, ph, updated, macro_species, macro_activities, saturation, ())
            return MixedFertilizerEquilibrium(macro, replace(trace, ionic_strength=updated), updated, iteration)
        ionic_strength = (ionic_strength + updated) / 2
        bound_ca, bound_mg = next_ca, next_mg
    raise DeliveryError("nonconvergent", "coupled macro/trace ionic-strength iteration did not converge")
