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
    GypsumEquilibrium,
    calcite_co2_reference_values,
    davies_gamma,
    gypsum_reference_values,
    solve_calcite_co2_equilibrium,
    solve_gypsum_equilibrium,
)
from .ph_planning import PhPlan, alkalinity_meq_per_litre, plan_ph
from .phosphate import OrthophosphateSpeciation, orthophosphate_speciation
from .phosphate_complexes import (
    CalciumMagnesiumPhosphateSpeciation,
    calcium_magnesium_phosphate_speciation,
    hydroxyapatite_hpo4_activity_at_equilibrium,
)
from .stock_planning import StockPlan, StockSaltDose, StockTank, StockTankPlan, plan_stocks
from .struvite import struvite_saturation_index
from .thermodynamics import MineralPhase, phase_saturation_index

__all__ = [
    "DeliveryError",
    "CalciteCo2Equilibrium",
    "CalciumMagnesiumPhosphateSpeciation",
    "GypsumEquilibrium",
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
    "OrthophosphateSpeciation",
    "StockPlan",
    "StockSaltDose",
    "StockTank",
    "StockTankPlan",
    "TemperatureCelsius",
    "VolumeLitres",
    "alkalinity_meq_per_litre",
    "calcite_co2_reference_values",
    "calcium_magnesium_phosphate_speciation",
    "hydroxyapatite_hpo4_activity_at_equilibrium",
    "davies_gamma",
    "elemental_contribution",
    "final_solution_recipe",
    "rescore_with_reagent",
    "gap_for",
    "gypsum_reference_values",
    "load_library",
    "make_audit_record",
    "plan_stocks",
    "plan_ph",
    "orthophosphate_speciation",
    "phase_saturation_index",
    "recommend",
    "solve_weights",
    "solve_calcite_co2_equilibrium",
    "solve_gypsum_equilibrium",
    "struvite_saturation_index",
    "validate_delivery_request",
]
__version__ = "0.2.0"
