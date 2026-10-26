# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""FlahaX: choose salt weights that minimize formulation Δ%."""

__all__ = [
    "solve_joint_problem",
    "JointSource",
    "JointProblem",
    "make_joint_problem",
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
    "ProductAnalyticalTotals",
    "material_inventory",
    "component_nutrient_masses",
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
    "SolventBasis",
    "alkalinity_meq_per_litre",
    "assert_catalogue_coverage",
    "ammonia_speciation",
    "calcite_co2_reference_values",
    "compose_delivery_plan",
    "calcium_sulfate_struvite_competition",
    "carbonate_competition",
    "chemistry_for_product",
    "convert_catalogue_product_dose",
    "convert_product_dose",
    "calcium_magnesium_phosphate_speciation",
    "hydroxyapatite_hpo4_activity_at_equilibrium",
    "davies_gamma",
    "delivery_report",
    "elemental_contribution",
    "final_solution_recipe",
    "rescore_with_reagent",
    "rescore_weighed_recipe",
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
    "solve_catalogue_product_doses",
    "solve_gypsum_equilibrium",
    "solve_charge_balanced_struvite_mixture",
    "struvite_saturation_index",
    "struvite_mixture_speciation",
    "transition_plan",
    "validate_delivery_request",
    "EquilibriumPhPlan",
    "plan_equilibrium_delivery",
    "AqueousResult",
    "AcidResult",
    "catalogue_dose_totals",
    "plan_catalogue_nitric_target",
    "material_chemistry",
    "calculate_equilibrium_ph",
    "FertilizerWorkflow",
    "WorkflowStage",
    "plan_fertilizer_workflow",
    "AcidCandidate",
    "AcidSelection",
    "plan_acid_options",
    "PhAdjustmentPlan",
    "PhCandidate",
    "catalogue_ph_reagents",
    "plan_coupled_ph",
    "reagent_dose",
    "ConcentrateTank",
    "TankGrouping",
    "TankProduct",
    "default_compatibility_rules",
    "group_tanks",
    "render_batch_sheet",
    "render_report",
    "summarize_batch",
    "ECPrediction",
    "ECDeliveryPlan",
    "water_ec25",
    "ec_recipe_key",
    "plan_ec_delivery",
    "estimate_manufacturer_ec",
    "size_injection_requirements",
    "BalancedWaterAnalysis",
    "balance_water_analysis",
    "carbonate_alkalinity",
    "total_alkalinity",
    "IrrigationECResult",
    "DeclaredPureWater",
    "calculate_irrigation_ec",
    "calculate_irrigation_ec_from_plan",
    "calculate_ec_from_totals",
    "compare_measured_ec",
    "assay_charge_residual",
    "calculate_irrigation_ec_band",
    "DocumentReference",
    "Grade",
    "Lot",
    "ResolvedMaterial",
    "make_grade",
    "make_lot",
    "resolve_material",
    "nutrient_band",
    "load_identities",
    "identity_for_product",
]
__version__ = "0.6.1.dev0"

from .composition import InputError
from .competition import (
    CalciumSulfateStruviteCompetition,
    CarbonateCompetition,
    calcium_sulfate_struvite_competition,
    carbonate_competition,
)
from .ammonia import AmmoniaSpeciation, ammonia_speciation
from .delivery_contracts import DeliveryError, make_audit_record, validate_delivery_request
from .fertilizer_equilibrium import (
    FertilizerEquilibrium,
    FertilizerTotals,
    NitricAcidTargetPlan,
    plan_nitric_acid_target,
    solve_fertilizer_equilibrium,
)
from .delivery_plan import DeliveryPlan, compose_delivery_plan, delivery_report, transition_plan
from .delivery_quantities import (
    SolventBasis,
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
    rescore_weighed_recipe,
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
from .struvite_mixture import (
    ChargeBalancedStruviteMixture,
    StruviteMixtureSpeciation,
    solve_charge_balanced_struvite_mixture,
    struvite_mixture_speciation,
)
from .thermodynamics import MineralPhase, phase_saturation_index
from .trace_equilibrium import (
    ChMicroProductDose,
    ChMicroTotals,
    TraceEquilibrium,
    solve_ch_micro_equilibrium,
)
from .catalogue_chemistry import ProductChemistry, assert_catalogue_coverage, chemistry_for_product
from .product_conversion import (
    ProductAnalyticalTotals,
    material_inventory,
    component_nutrient_masses,
    convert_catalogue_product_dose,
    convert_product_dose,
    solve_catalogue_product_doses,
    catalogue_dose_totals,
    plan_catalogue_nitric_target,
)
from .material_chemistry import material_chemistry
from .aqueous_model import AqueousResult, AcidResult
from .mixed_equilibrium import MixedFertilizerEquilibrium, solve_mixed_fertilizer_equilibrium
from .equilibrium_delivery import EquilibriumPhPlan, plan_equilibrium_delivery
from .calculated_ph import calculate_equilibrium_ph
from .fertilizer_workflow import FertilizerWorkflow, WorkflowStage, plan_fertilizer_workflow
from .acid_selection import AcidCandidate, AcidSelection, plan_acid_options
from .ph_adjustment import (
    PhAdjustmentPlan,
    PhCandidate,
    catalogue_ph_reagents,
    plan_coupled_ph,
    reagent_dose,
)
from .tank_grouping import (
    ConcentrateTank,
    TankGrouping,
    TankProduct,
    default_compatibility_rules,
    group_tanks,
)
from .grower_report import render_batch_sheet, render_report, summarize_batch
from .conductivity import ECPrediction, ECDeliveryPlan, water_ec25, ec_recipe_key, plan_ec_delivery
from .calculated_ec import estimate_manufacturer_ec
from .injector_sizing import size_injection_requirements
from .measured_water import (
    BalancedWaterAnalysis,
    balance_water_analysis,
    carbonate_alkalinity,
    total_alkalinity,
)
from .irrigation_ec import (
    IrrigationECResult,
    DeclaredPureWater,
    calculate_irrigation_ec,
    calculate_irrigation_ec_from_plan,
    calculate_ec_from_totals,
    compare_measured_ec,
    assay_charge_residual,
    calculate_irrigation_ec_band,
)
from .materials import (
    DocumentReference,
    Grade,
    Lot,
    ResolvedMaterial,
    make_grade,
    make_lot,
    resolve_material,
    nutrient_band,
    load_identities,
    identity_for_product,
)

from .joint_problem import JointSource, JointProblem
from .ph_adjustment import make_joint_problem

from .joint_solver import solve_joint_problem
