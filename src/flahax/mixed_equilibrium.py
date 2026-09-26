"""Single public entry point for macro and declared CH-micro equilibrium."""
from __future__ import annotations
from dataclasses import dataclass, replace
from .fertilizer_equilibrium import FertilizerTotals, FertilizerEquilibrium, solve_fertilizer_equilibrium
from .trace_equilibrium import ChMicroTotals, TraceEquilibrium, solve_ch_micro_equilibrium

@dataclass(frozen=True, slots=True)
class MixedFertilizerEquilibrium:
    macro: FertilizerEquilibrium
    trace: TraceEquilibrium | None

def solve_mixed_fertilizer_equilibrium(totals: FertilizerTotals, ph: float, *, trace_totals: ChMicroTotals | None = None, allow_precipitation: bool = True) -> MixedFertilizerEquilibrium:
    """Solve the shared-pH macro/trace system; trace receives macro Ca/Mg totals."""
    macro = solve_fertilizer_equilibrium(totals, ph, allow_precipitation=allow_precipitation)
    trace = None if trace_totals is None else solve_ch_micro_equilibrium(
        replace(trace_totals, calcium=trace_totals.calcium + macro.totals.calcium,
                magnesium=trace_totals.magnesium + macro.totals.magnesium), ph, macro.ionic_strength)
    return MixedFertilizerEquilibrium(macro, trace)
