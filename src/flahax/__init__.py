"""FlahaX: choose salt weights that minimize formulation Δ%."""

from .composition import InputError
from .delivery_contracts import DeliveryError, make_audit_record, validate_delivery_request
from .delivery_quantities import (
    DurationMinutes,
    FinalSolutionRecipe,
    FlowLitresPerMinute,
    GramsPerLitre,
    InjectionRatio,
    MassGrams,
    MilliEquivalentsPerLitre,
    MilligramsPerLitre,
    TemperatureCelsius,
    VolumeLitres,
    elemental_contribution,
    final_solution_recipe,
    rescore_with_reagent,
)
from .engine import gap_for, load_library, recommend, solve_weights
from .equilibrium import (
    CalciteCo2Equilibrium,
    calcite_co2_reference_values,
    davies_gamma,
    solve_calcite_co2_equilibrium,
)
from .ph_planning import PhPlan, alkalinity_meq_per_litre, plan_ph
from .stock_planning import StockPlan, StockSaltDose, StockTank, StockTankPlan, plan_stocks
from .thermodynamics import MineralPhase, phase_saturation_index

__all__ = [
    "DeliveryError",
    "CalciteCo2Equilibrium",
    "DurationMinutes",
    "FinalSolutionRecipe",
    "FlowLitresPerMinute",
    "GramsPerLitre",
    "InjectionRatio",
    "InputError",
    "MassGrams",
    "MineralPhase",
    "MilliEquivalentsPerLitre",
    "MilligramsPerLitre",
    "PhPlan",
    "StockPlan",
    "StockSaltDose",
    "StockTank",
    "StockTankPlan",
    "TemperatureCelsius",
    "VolumeLitres",
    "alkalinity_meq_per_litre",
    "calcite_co2_reference_values",
    "davies_gamma",
    "elemental_contribution",
    "final_solution_recipe",
    "rescore_with_reagent",
    "gap_for",
    "load_library",
    "make_audit_record",
    "plan_stocks",
    "plan_ph",
    "phase_saturation_index",
    "recommend",
    "solve_weights",
    "solve_calcite_co2_equilibrium",
    "validate_delivery_request",
]
__version__ = "0.2.0"
