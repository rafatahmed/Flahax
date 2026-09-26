"""FlahaX: choose salt weights that minimize formulation Δ%."""

from .composition import InputError
from .competition import CalciumSulfateStruviteCompetition, CarbonateCompetition, calcium_sulfate_struvite_competition, carbonate_competition
from .ammonia import AmmoniaSpeciation, ammonia_speciation
from .delivery_contracts import DeliveryError, make_audit_record, validate_delivery_request
from .fertilizer_equilibrium import FertilizerEquilibrium, FertilizerTotals, NitricAcidTargetPlan, plan_nitric_acid_target, solve_fertilizer_equilibrium
from .delivery_plan import DeliveryPlan, compose_delivery_plan, delivery_report, transition_plan
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
from .pump_planning import PumpCommand, plan_pump_command
from .phase_allocation import PhaseAllocation, phase_allocation
from .phosphate import OrthophosphateSpeciation, orthophosphate_speciation
from .phosphate_complexes import (
    CalciumMagnesiumPhosphateSpeciation,
    calcium_magnesium_phosphate_speciation,
    hydroxyapatite_hpo4_activity_at_equilibrium,
)
from .stock_planning import StockPlan, StockSaltDose, StockTank, StockTankPlan, plan_stocks
from .struvite import struvite_saturation_index
from .struvite_mixture import ChargeBalancedStruviteMixture, StruviteMixtureSpeciation, solve_charge_balanced_struvite_mixture, struvite_mixture_speciation
from .thermodynamics import MineralPhase, phase_saturation_index
from .trace_equilibrium import ChMicroProductDose, ChMicroTotals, TraceEquilibrium, solve_ch_micro_equilibrium
from .catalogue_chemistry import ProductChemistry, assert_catalogue_coverage, chemistry_for_product
from .mixed_equilibrium import MixedFertilizerEquilibrium, solve_mixed_fertilizer_equilibrium

__all__ = [
    "DeliveryError",
    "DeliveryPlan",
    "FertilizerEquilibrium",
    "FertilizerTotals",
    "AmmoniaSpeciation",
    "CalciteCo2Equilibrium",
    "ChMicroProductDose",
    "ChMicroTotals",
    "CalciumSulfateStruviteCompetition",
    "CarbonateCompetition",
    "ChargeBalancedStruviteMixture",
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
    "MixedFertilizerEquilibrium",
    "MilligramsPerLitre",
    "PhPlan",
    "ProductChemistry",
    "NitricAcidTargetPlan",
    "PumpCommand",
    "PhaseAllocation",
    "OrthophosphateSpeciation",
    "StockPlan",
    "StruviteMixtureSpeciation",
    "StockSaltDose",
    "StockTank",
    "StockTankPlan",
    "TemperatureCelsius",
    "TraceEquilibrium",
    "VolumeLitres",
    "alkalinity_meq_per_litre",
    "assert_catalogue_coverage",
    "ammonia_speciation",
    "calcite_co2_reference_values",
    "compose_delivery_plan",
    "calcium_sulfate_struvite_competition",
    "carbonate_competition",
    "chemistry_for_product",
    "calcium_magnesium_phosphate_speciation",
    "hydroxyapatite_hpo4_activity_at_equilibrium",
    "davies_gamma",
    "delivery_report",
    "elemental_contribution",
    "final_solution_recipe",
    "rescore_with_reagent",
    "gap_for",
    "gypsum_reference_values",
    "load_library",
    "make_audit_record",
    "plan_stocks",
    "plan_nitric_acid_target",
    "plan_ph",
    "plan_pump_command",
    "phase_allocation",
    "orthophosphate_speciation",
    "phase_saturation_index",
    "recommend",
    "solve_weights",
    "solve_calcite_co2_equilibrium",
    "solve_fertilizer_equilibrium",
    "solve_mixed_fertilizer_equilibrium",
    "solve_ch_micro_equilibrium",
    "solve_gypsum_equilibrium",
    "solve_charge_balanced_struvite_mixture",
    "struvite_saturation_index",
    "struvite_mixture_speciation",
    "transition_plan",
    "validate_delivery_request",
]
__version__ = "0.2.0"
