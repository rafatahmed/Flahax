# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Bounded preparation scenarios for rounded six-ingredient recipes."""

import itertools
import math

from .aqueous_model import solve
from .composition import ATOMIC, parse_formula
from .delivery_contracts import DeliveryError
from .ratio_verification import BASIS, ELEMENTS, VALENCES
from .ratio_products import LABELS
from .product_conversion import MOLAR_MASS


def validate_uncertainty(options, volume, *, stock_mode=False):
    """Require explicit finite preparation bounds and acceptance
    tolerances.
    """
    required = {
        "weighing_error_g",
        "purity_fraction",
        "volume_error_litres",
        "ratio_relative_tolerance",
        "concentration_relative_tolerance",
        "impurity_model",
    }
    if stock_mode:
        required -= {"weighing_error_g", "purity_fraction"}
    if not isinstance(options, dict) or set(options) != required:
        raise DeliveryError(
            "invalid_uncertainty",
            "Supply exactly the preparation uncertainty fields for this mode",
        )
    for key in required - {"purity_fraction", "impurity_model"}:
        value = options[key]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise DeliveryError("invalid_uncertainty", f"{key} must be finite and nonnegative")
    purity = options.get("purity_fraction", [1, 1])
    if (
        not isinstance(purity, (list, tuple))
        or len(purity) != 2
        or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in purity
        )
        or not 0 < purity[0] <= purity[1] <= 1
    ):
        raise DeliveryError(
            "invalid_uncertainty", "Purity bounds must satisfy 0 < low <= high <= 1"
        )
    if (
        isinstance(volume, bool)
        or not isinstance(volume, (int, float))
        or not math.isfinite(volume)
        or volume <= options["volume_error_litres"]
    ):
        raise DeliveryError("invalid_uncertainty", "Volume must stay positive under uncertainty")
    if options["impurity_model"] != "inert":
        raise DeliveryError(
            "invalid_uncertainty", "Only chemically inert missing assay fraction is supported"
        )


def verify_uncertainty(recipe, options, *, effective_bounds=None):
    """Evaluate effective-dose interval corners at both volume bounds
    and the pH grid.

    Dose/purity products have exact endpoint bounds. Nonlinear chemistry
    is sampled at corners; this does not prove extrema over the
    continuous uncertainty box.
    """
    nominal = recipe["rounded_verification"]
    result = {
        "status": "failed",
        "assumptions": dict(options),
        "phase_maxima": {},
        "ph_refinement": {
            "scenarios": [],
            "total_ph_evaluations": 0,
            "continuous_extrema_proved": False,
        },
        "scenario_count": 0,
        "planned_scenarios": 0,
        "failed_checks": [],
        "ratio_percent_ranges": None,
        "counted_mmol_l_range": None,
        "elemental_mg_l_ranges": {},
        "all_scenario_ph_in_range": None,
        "ph_failure_example": None,
        "worst_ratio_relative_error": 0.0,
        "worst_concentration_relative_error": 0.0,
        "coverage": "Independent effective-dose corners and volume endpoints at every nominal pH "
        "grid point. Chemistry interiors are not bounded; no probabilistic confidence claim.",
        "water_model": "Water mass scales with volume using the nominal density approximation.",
        "impurity_qualification": "Inactive assay fraction is inert. Carbonate in KOH, reactive "
        "impurities, hydrate errors, gas exchange and temperature uncertainty are excluded.",
        "si_required_below": nominal["si_required_below"],
    }
    if nominal["status"] != "passed":
        result["status"] = nominal["status"]
        result["failed_checks"] = ["nominal_recipe"]
        return result
    error = options.get("weighing_error_g", 0)
    low_purity, high_purity = options.get("purity_fraction", [1, 1])
    bounds, vectors = [], []
    for row in nominal["ingredients"]:
        if row["grams"] < error:
            result["failed_checks"] = ["weighing_interval_includes_negative_mass"]
            return result
        bounds.append(
            sorted({(row["grams"] - error) * low_purity, (row["grams"] + error) * high_purity})
        )
        atoms = parse_formula(row["formula"])["atoms"]
        mw = sum(ATOMIC[e] * n for e, n in atoms.items())
        vectors.append([1000 * atoms.get(e, 0) / mw for e in ELEMENTS])
    if effective_bounds is not None:
        bounds = effective_bounds
        result["stock_specification"] = recipe["stock_delivery"]["specification"]
        result["verification_scope"] = recipe["stock_delivery"]["verification_scope"]
    volume_error = options["volume_error_litres"]
    volumes = sorted(
        {recipe["volume_litres"] - volume_error, recipe["volume_litres"] + volume_error}
    )
    result["planned_scenarios"] = math.prod(map(len, bounds)) * len(volumes)
    target_ratios = recipe["cation_percent"] + recipe["anion_percent"]
    ranges = [[math.inf, -math.inf] for _ in range(6)]
    concentration_range = [math.inf, -math.inf]
    failures = set()
    result["all_scenario_ph_in_range"] = True
    try:
        for doses in itertools.product(*bounds):
            batch = [sum(d * vector[i] for d, vector in zip(doses, vectors)) for i in range(6)]
            eq = [a * z for a, z in zip(batch, VALENCES)]
            if not sum(eq[:3]) or not sum(eq[3:]):
                result["failed_checks"] = ["empty_ion_group"]
                return result
            ratios = [100 * v / sum(eq[:3]) for v in eq[:3]] + [
                100 * v / sum(eq[3:]) for v in eq[3:]
            ]
            for i, (actual, target) in enumerate(zip(ratios, target_ratios)):
                ranges[i] = [min(ranges[i][0], actual), max(ranges[i][1], actual)]
                relative = (
                    abs(actual - target) / target if target else (0 if actual == 0 else math.inf)
                )
                result["worst_ratio_relative_error"] = max(
                    result["worst_ratio_relative_error"], relative
                )
                if abs(actual - target) > 1e-10 + options["ratio_relative_tolerance"] * target:
                    failures.add("nutrient_ratios")
            for volume in volumes:
                concentration = sum(batch) / volume
                concentration_range = [
                    min(concentration_range[0], concentration),
                    max(concentration_range[1], concentration),
                ]
                relative = abs(concentration / recipe["counted_mmol_l"] - 1)
                result["worst_concentration_relative_error"] = max(
                    result["worst_concentration_relative_error"], relative
                )
                if relative > options["concentration_relative_tolerance"] + 1e-10:
                    failures.add("total_concentration")
                water_mass = recipe["water_mass_kg"] * volume / recipe["volume_litres"]
                elemental = {
                    k: batch[i] / volume * MOLAR_MASS[k.split("_")[0]]
                    for i, k in enumerate(LABELS)
                }
                for key, value in elemental.items():
                    prior = result["elemental_mg_l_ranges"].get(key, [value, value])
                    result["elemental_mg_l_ranges"][key] = [
                        min(prior[0], value),
                        max(prior[1], value),
                    ]
                for key, cap in recipe.get("maximum_concentrations", {}).items():
                    if elemental.get(key, 0) > cap:
                        failures.add(
                            "sodium_chloride_limits" if key in ("Na", "Cl") else "nutrient_limits"
                        )
                totals = dict(zip(BASIS, [a / 1000 / water_mass for a in batch]))
                from .ratio_ph_refinement import refine_ph

                states, refinement = refine_ph(
                    lambda ph: solve(totals, ph),
                    nominal.get("base_evaluated_ph", nominal["evaluated_ph"]),
                    nominal["selected_phases"],
                    nominal["si_required_below"],
                )
                refinement["scenario"] = result["scenario_count"]
                refinement["evaluated_ph"] = sorted(states)
                result["ph_refinement"]["scenarios"].append(refinement)
                result["ph_refinement"]["total_ph_evaluations"] += len(states)
                if not refinement["complete"]:
                    raise DeliveryError(
                        "ph_refinement_incomplete", "Scenario pH sampling budget exhausted"
                    )
                charges = []
                for ph, state in sorted(states.items()):
                    charges.append(state.charge_balance)
                    for phase in nominal["selected_phases"]:
                        si = state.saturation_indices.get(phase)
                        if si is None or not math.isfinite(si):
                            raise DeliveryError(
                                "phase_unavailable", f"Missing finite SI for {phase}"
                            )
                        old = result["phase_maxima"].get(phase)
                        if old is None or si > old["si"]:
                            result["phase_maxima"][phase] = {
                                "si": si,
                                "ph": ph,
                                "effective_grams": list(doses),
                                "volume_litres": volume,
                            }
                        if si >= nominal["si_required_below"]:
                            failures.add("saturation_margin")
                if charges[0] * charges[-1] > 0:
                    result["all_scenario_ph_in_range"] = False
                    failures.add("equilibrium_ph")
                    if result["ph_failure_example"] is None:
                        result["ph_failure_example"] = {
                            "effective_grams": list(doses),
                            "volume_litres": volume,
                            "endpoint_charge_residuals": [charges[0], charges[-1]],
                        }
                result["scenario_count"] += 1
    except DeliveryError as exc:
        result["status"] = "incomplete"
        result["error"] = {"code": exc.code, "message": str(exc)}
        return result
    result["ratio_percent_ranges"] = ranges
    result["counted_mmol_l_range"] = concentration_range
    result["failed_checks"] = sorted(failures)
    result["status"] = "failed" if failures else "passed"
    return result
