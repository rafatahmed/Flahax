# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Verify rounded ratio recipes on a disclosed grid of imposed pH
values.
"""

import math

from .aqueous_model import solve
from .composition import ATOMIC, parse_formula
from .delivery_contracts import DeliveryError
from .float_sum import float_sum
from .root_finding import shrink_bracket

PHASE_ALIASES = {
    "Brushite": "CaHPO4:2H2O",
    "Monetite": "CaHPO4",
    "Hydroxyapatite": "Hydroxylapatite",
    "CaHPO4:2H2O": "CaHPO4:2H2O",
    "CaHPO4": "CaHPO4",
    "Hydroxylapatite": "Hydroxylapatite",
}
DEFAULT_PHASES = ("CaHPO4:2H2O", "CaHPO4", "Hydroxylapatite")
BASIS = ("K+", "Ca+2", "Mg+2", "NO3-", "PO4-3", "SO4-2")
NUTRIENTS = ("K", "Ca", "Mg", "NO3", "P", "SO4")
ELEMENTS = ("K", "Ca", "Mg", "N", "P", "S")
VALENCES = (1, 2, 2, 1, 1, 2)
GRID_SPACING = 0.001
ROUNDING_RELATIVE_TOLERANCE = 0.001
# Numerical guard around zero; a negative index must exceed this margin.
SI_GUARD = 1e-7


def verification_options(ph, ph_range, selected_phases, mass_decimals):
    """Validate the requested interval, mineral names and mass
    precision.
    """
    if not isinstance(ph_range, (list, tuple)) or len(ph_range) != 2:
        raise DeliveryError("invalid_ph_range", "ph_range requires two pH values")
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in ph_range
    ):
        raise DeliveryError("invalid_ph_range", "pH endpoints must be finite numbers")
    low, high = ph_range
    if not 0 <= low <= ph <= high <= 14:
        raise DeliveryError("invalid_ph_range", "pH range must contain target pH within 0 to 14")
    if type(mass_decimals) is not int or not 0 <= mass_decimals <= 8:
        raise DeliveryError("invalid_rounding", "mass_decimals must be an integer from 0 to 8")
    phases = DEFAULT_PHASES if selected_phases is None else selected_phases
    if not isinstance(phases, (list, tuple)) or not phases:
        raise DeliveryError("invalid_phases", "Select at least one mineral")
    if any(not isinstance(p, str) or p not in PHASE_ALIASES for p in phases):
        raise DeliveryError(
            "invalid_phases", "Supported phases are brushite, monetite and hydroxyapatite"
        )
    return tuple(dict.fromkeys(PHASE_ALIASES[p] for p in phases))


def verify_rounded_recipe(
    recipe, ph_range, phases, mass_decimals, saturation_margin=0.0, *, delivered_grams=None
):
    """Reconstruct delivered masses and return sampled saturation and
    fit checks.
    """
    water = recipe.get("water_accounting", {})
    amounts = [water.get("nutrients_mmol_l", {}).get(n, 0.0) for n in NUTRIENTS]
    reference_charge = water.get("reference_charge_mol_kg", 0.0)
    if recipe.get("product_inventory"):
        from .ratio_products import reconstruct_products

        grams = (
            [round(row["grams"], mass_decimals) for row in recipe["ingredients"]]
            if delivered_grams is None
            else delivered_grams
        )
        rebuilt = reconstruct_products(
            recipe["ingredients"], grams, water, recipe["volume_litres"], recipe["water_mass_kg"]
        )
        ingredients = rebuilt["ingredients"]
        analytical = rebuilt["analytical_mmol_l"]
        amounts = [analytical[n] for n in NUTRIENTS]
        totals = rebuilt["aqueous_totals_mol_kg"]
        elemental = rebuilt["elemental_mg_l"]
        solvent_ok = rebuilt["solvent_inventory_passed"]
    else:
        ingredients = []
        for index, row in enumerate(recipe["ingredients"]):
            grams = (
                round(row["grams"], mass_decimals)
                if delivered_grams is None
                else delivered_grams[index]
            )
            atoms = parse_formula(row["formula"])["atoms"]
            molar_mass = float_sum(ATOMIC[e] * n for e, n in atoms.items())
            mmol_l = grams / molar_mass * 1000 / recipe["volume_litres"]
            amounts = [v + mmol_l * atoms.get(e, 0) for v, e in zip(amounts, ELEMENTS)]
            ingredients.append({"formula": row["formula"], "grams": grams})
        analytical = dict(zip(NUTRIENTS, amounts))
        totals = {
            k: v * recipe["volume_litres"] / recipe["water_mass_kg"] / 1000
            for k, v in zip(BASIS, amounts)
        }
        totals.update(water.get("background_totals_mol_kg", {}))
        from .ratio_products import elemental_from_totals

        elemental = elemental_from_totals(totals, recipe["volume_litres"], recipe["water_mass_kg"])
        solvent_ok = True
    from .ratio_products import limit_assessment

    limits = limit_assessment(elemental, recipe.get("maximum_concentrations", {}))
    errors = {key: analytical[key] - target for key, target in recipe["analytical_mmol_l"].items()}
    rounding_ok = all(
        abs(errors[key]) <= 1e-10 + ROUNDING_RELATIVE_TOLERANCE * abs(target)
        for key, target in recipe["analytical_mmol_l"].items()
    )
    equivalents = [v * z for v, z in zip(amounts, VALENCES)]
    low, high = ph_range
    count = max(1, math.ceil((high - low) / GRID_SPACING))
    grid = sorted(
        {low + (high - low) * i / count for i in range(1, count)}
        | {low, high, recipe["target_ph"]}
    )
    result = {
        "status": "incomplete",
        "elemental_mg_l": elemental,
        "limit_assessment": limits,
        "solvent_inventory_passed": solvent_ok,
        "ph_range": list(ph_range),
        "selected_phases": list(phases),
        "mass_decimals": mass_decimals if delivered_grams is None else None,
        "delivery_basis": "rounded_grams" if delivered_grams is None else "rounded_stock_doses",
        "ingredients": ingredients,
        "analytical_mmol_l": analytical,
        "aqueous_totals_mol_kg": totals,
        "reference_charge_mol_kg": reference_charge,
        "counted_mmol_l": float_sum(amounts),
        "nutrient_errors_mmol_l": errors,
        "rounding_relative_tolerance": ROUNDING_RELATIVE_TOLERANCE,
        "rounding_within_tolerance": rounding_ok,
        "cation_percent": [100 * v / float_sum(equivalents[:3]) for v in equivalents[:3]]
        if float_sum(equivalents[:3])
        else None,
        "anion_percent": [100 * v / float_sum(equivalents[3:]) for v in equivalents[3:]]
        if float_sum(equivalents[3:])
        else None,
        "evaluated_ph": [],
        "base_evaluated_ph": list(grid),
        "max_grid_spacing": max((b - a for a, b in zip(grid, grid[1:])), default=0),
        "coverage": "Endpoints, target and interior grid; maximum spacing 0.001 pH. "
        "This sampled check supplies no mathematical bound between grid points.",
        "chemical_scenario": "Fixed rounded analytical totals at imposed pH. Off-target "
        "charge residuals are reported. Acid/base additions and gas "
        "exchange would require their own material accounting.",
        "saturation_margin": saturation_margin,
        "si_required_below": -saturation_margin - SI_GUARD,
        "maximum_activity_product_fraction": 10 ** (-saturation_margin),
        "margin_qualification": "Engineering allowance in the pinned reaction convention; "
        "not a measured bound on weighing, purity, temperature or model uncertainty.",
        "phase_maxima": {},
        "charge_residuals_mol_kg": [],
        "rounded_ph": None,
        "rounded_ph_in_range": False,
    }
    states = {}
    try:
        from .ratio_ph_refinement import refine_ph

        states, result["ph_refinement"] = refine_ph(
            lambda ph: solve(totals, ph), grid, phases, result["si_required_below"]
        )
        result["coverage"] += (
            " Adaptive refinement resolves observed peaks and crossings to 1e-5 pH locally; "
            "no continuous bound is proved."
        )
        for ph, state in sorted(states.items()):
            result["evaluated_ph"].append(ph)
            result["charge_residuals_mol_kg"].append(state.charge_balance)
            for phase in phases:
                value = state.saturation_indices.get(phase)
                if value is None or not math.isfinite(value):
                    raise DeliveryError("phase_unavailable", f"Missing finite SI for {phase}")
                previous = result["phase_maxima"].get(phase)
                if previous is None or value > previous["si"]:
                    result["phase_maxima"][phase] = {"si": value, "ph": ph}
        if not result["ph_refinement"]["complete"]:
            raise DeliveryError(
                "ph_refinement_incomplete", "Adaptive pH sampling budget exhausted"
            )
        result["target_ph_saturation_indices"] = {
            phase: states[recipe["target_ph"]].saturation_indices[phase] for phase in phases
        }
        a, b = (
            states[low].charge_balance - reference_charge,
            states[high].charge_balance - reference_charge,
        )
        if a * b <= 0:
            left, right = shrink_bracket(
                lambda ph: solve(totals, ph).charge_balance - reference_charge,
                low,
                a,
                high,
                b,
                width=1e-9,
            )
            result["rounded_ph"] = (left + right) / 2
            result["rounded_ph_in_range"] = True
    except DeliveryError as exc:
        result["error"] = {"code": exc.code, "message": str(exc)}
        return result
    saturated = [
        phase
        for phase, row in result["phase_maxima"].items()
        if row["si"] >= result["si_required_below"]
    ]
    result["failed_phases"] = saturated
    result["status"] = (
        "passed"
        if rounding_ok
        and result["rounded_ph_in_range"]
        and not saturated
        and limits["passed"]
        and solvent_ok
        else "failed"
    )
    return result
