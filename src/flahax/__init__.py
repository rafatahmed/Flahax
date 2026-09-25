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
from .ph_planning import PhPlan, alkalinity_meq_per_litre, plan_ph
from .stock_planning import StockPlan, StockSaltDose, StockTank, StockTankPlan, plan_stocks

__all__ = [
    "DeliveryError",
    "DurationMinutes",
    "FinalSolutionRecipe",
    "FlowLitresPerMinute",
    "GramsPerLitre",
    "InjectionRatio",
    "InputError",
    "MassGrams",
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
    "elemental_contribution",
    "final_solution_recipe",
    "rescore_with_reagent",
    "gap_for",
    "load_library",
    "make_audit_record",
    "plan_stocks",
    "plan_ph",
    "recommend",
    "solve_weights",
    "validate_delivery_request",
]
__version__ = "0.2.0"
