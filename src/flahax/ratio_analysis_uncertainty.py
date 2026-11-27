# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Analytical box bounds and disclosed chemistry sampling for commercial
recipes.
"""

from copy import deepcopy
import math
import itertools
import random

from .aqueous_model import solve
from .delivery_contracts import DeliveryError
from .float_sum import float_sum
from .product_conversion import MOLAR_MASS
from .ratio_products import LABELS, VALENCES, reconstruct_products
from .ratio_water import BASIS, account_water


def validate_analysis_uncertainty(options, volume, products, water):
    """Validate a separate, explicit uncertainty contract for material
    inventories.
    """
    elemental = isinstance(options, dict) and options.get("mode") == "water_product_elemental"
    assay_field = "product_element_factors" if elemental else "product_assay_factors"
    required = {
        "mode",
        "weighing_error_g",
        "volume_error_litres",
        "ratio_relative_tolerance",
        "concentration_relative_tolerance",
        "water_relative_error",
        "water_ph_error",
        assay_field,
        "impurity_model",
        "water_mass_model",
        "max_scenarios",
    }
    physical = (
        isinstance(options, dict)
        and options.get("water_mass_model") == "closed_batch_mass_balance"
    )
    if physical:
        required.add("physical_preparation")
    if (
        not isinstance(options, dict)
        or set(options) != required
        or options["mode"] not in ("water_product", "water_product_elemental")
    ):
        raise DeliveryError(
            "invalid_analysis_uncertainty",
            "Supply exactly the uncertainty fields for the selected assay mode",
        )
    for key in required - {
        "mode",
        assay_field,
        "impurity_model",
        "water_mass_model",
        "max_scenarios",
        "physical_preparation",
    }:
        v = options[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise DeliveryError(
                "invalid_analysis_uncertainty", f"{key} must be finite and nonnegative"
            )
    if (
        isinstance(volume, bool)
        or not isinstance(volume, (int, float))
        or not math.isfinite(volume)
        or volume <= 0
    ):
        raise DeliveryError(
            "invalid_analysis_uncertainty", "Final volume must be finite and positive"
        )
    if options["water_relative_error"] > 1 or options["volume_error_litres"] >= volume:
        raise DeliveryError(
            "invalid_analysis_uncertainty",
            "Water concentrations and final volume must remain nonnegative/positive",
        )
    if options["impurity_model"] != "inert" or options["water_mass_model"] not in (
        "scale_with_final_volume",
        "closed_batch_mass_balance",
    ):
        raise DeliveryError(
            "invalid_analysis_uncertainty",
            "Declare inert missing active content and a supported water mass model",
        )
    if type(options["max_scenarios"]) is not int or not 1 <= options["max_scenarios"] <= 4096:
        raise DeliveryError(
            "invalid_analysis_uncertainty", "max_scenarios must be an integer from 1 to 4096"
        )
    if not isinstance(products, list) or not products:
        raise DeliveryError(
            "invalid_analysis_uncertainty",
            "This mode requires explicit commercial product records",
        )
    from .ratio_products import product_sources

    sources = product_sources(products)
    if elemental:
        from .ratio_element_uncertainty import validate_element_factors
        from .ratio_assay_documents import resolve_documented_assays

        options, _ = resolve_documented_assays(options, sources)
        validate_element_factors(sources, options[assay_field])
    if physical:
        from .ratio_physical_uncertainty import validate_physical

        validate_physical(options, sources, water)
    if not elemental:
        names = [p["name"] for p in sources]
        factors = options["product_assay_factors"]
        if (
            not isinstance(factors, dict)
            or set(factors) != set(names)
            or len(names) != len(products)
        ):
            raise DeliveryError(
                "invalid_analysis_uncertainty",
                "Provide assay factors for every product, including pH reagents",
            )
        for pair in factors.values():
            if (
                not isinstance(pair, (list, tuple))
                or len(pair) != 2
                or any(
                    isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                    for v in pair
                )
                or not 0 < pair[0] <= pair[1] <= 1
            ):
                raise DeliveryError(
                    "invalid_analysis_uncertainty", "Assay factors require 0 < low <= high <= 1"
                )
    if isinstance(water, dict):
        measured_ph = water.get("measured_ph")
        if (
            isinstance(measured_ph, bool)
            or not isinstance(measured_ph, (int, float))
            or not math.isfinite(measured_ph)
            or not options["water_ph_error"] <= measured_ph <= 14 - options["water_ph_error"]
        ):
            raise DeliveryError(
                "invalid_analysis_uncertainty", "Source-water pH bounds must stay within 0-14"
            )


def _water_input(recipe):
    report = recipe["water_accounting"]
    if report["source"] == "demineralized":
        return "demineralized"
    result = dict(
        analysis_id=report["analysis_id"],
        totals_mol_kg=deepcopy(report["analytical_totals_mol_kg"]),
        measured_ph=report["measured_ph"],
        temperature_c=25,
        source_water_mass_kg=report["source_water_mass_kg"],
    )
    if report["carbon_source"] == "alkalinity":
        result["alkalinity_eq_per_kg"] = report["alkalinity_eq_per_kg"]
    return result


def _ratio_extreme(groups, nutrient, offset, maximum):
    # A linear-fractional function over independent interval
    # contributions has extrema at endpoints. The zero of max/min(N-rD)
    # finds the bound without enumerating the Cartesian product; each
    # source endpoint is chosen separately.
    low, high = 0.0, 1.0

    def choice(group, r):
        scores = [
            v[nutrient] * VALENCES[nutrient]
            - r * float_sum(v[i] * VALENCES[i] for i in range(offset, offset + 3))
            for v in group[1:]
        ]
        choose = max if maximum else min
        return choose(range(len(scores)), key=scores.__getitem__)

    for _ in range(65):
        mid = (low + high) / 2
        value = 0.0
        for group in groups:
            v = group[1 + choice(group, mid)]
            value += v[nutrient] * VALENCES[nutrient] - mid * float_sum(
                v[i] * VALENCES[i] for i in range(offset, offset + 3)
            )
        if value > 0:
            low = mid
        else:
            high = mid
    ratio = (low + high) / 2
    return 100 * ratio, {g[0]: choice(g, ratio) for g in groups}


def verify_analysis_uncertainty(recipe, options):
    """Bound linear inventory quantities and sample nonlinear chemistry
    without refitting.
    """
    elemental = options["mode"] == "water_product_elemental"
    physical = options["water_mass_model"] == "closed_batch_mass_balance"
    nominal = recipe["rounded_verification"]
    document_evidence = {}
    if elemental:
        from .ratio_assay_documents import resolve_documented_assays

        options, document_evidence = resolve_documented_assays(options, nominal["ingredients"])
    result = dict(
        status="incomplete",
        assumptions=deepcopy(options),
        assay_bound_sources=document_evidence,
        scenario_count=0,
        failed_checks=[],
        phase_maxima={},
        ph_refinement={
            "scenarios": [],
            "total_ph_evaluations": 0,
            "continuous_extrema_proved": False,
        },
        ratio_percent_ranges=None,
        counted_mmol_l_range=None,
        worst_ratio_relative_error=0.0,
        worst_concentration_relative_error=0.0,
        all_scenario_ph_in_range=True,
        ph_failure_example=None,
        continuous_chemistry_extrema_proved=False,
        si_required_below=nominal["si_required_below"],
        coverage=(
            "Analytical inventory bounds cover the declared independent intervals. "
            "Chemistry uses deterministic axes, analytical-extreme witnesses and mixed "
            "corner/interior samples with separate adaptive pH refinement per scenario; unsampled "
            "chemistry extrema are not bounded."
        ),
        qualification=(
            "Product assay scales its entire declared composition, including counterions "
            "and pH reagents. Independent element-assay errors and unknown reactive "
            "impurities are excluded. Source-water mass is fixed; final water mass "
            "scales with volume at the nominal density approximation. Zero-dose products "
            "are not dispensed. No experimental verification or probability claim."
        ),
    )
    if elemental:
        from .ratio_blend_uncertainty import is_blend, bound_evidence

        result["blend_bound_sources"] = {
            row["name"]: bound_evidence(row, options["product_element_factors"][row["name"]])
            for row in nominal["ingredients"]
            if is_blend(options["product_element_factors"][row["name"]])
        }
        result["qualification"] = (
            "Declared elemental assays vary independently; all elements in a product share "
            "its weighing error. Hypothetical assays are reprocessed through the existing "
            "material/charge-reconciliation model; sampled label/chemistry discrepancies "
            "are reported, not erased. Derived analytical nutrients without explicit "
            "bounds are refused in independent-element mode. Disclosed blends can instead "
            "use ingredient fraction bounds with correlated assays and derived counterions. "
            "Single-identity grade scenarios use "
            "separate hypothetical assays; original grade documents remain unchanged. "
            "Factors are supplied explicitly or converted from complete documented bounds. "
            "Documents are not independent measurement verification. "
            "Above-one factors mean above-label elemental content, not purity over 100%; "
            "upper elemental inventories must fit the declared non-solvent mass. "
            "This is not proof of "
            "physically realizable lots or continuous chemistry extrema. Source water "
            "mass is fixed and final water mass scales with final volume. Unknown reactive "
            "impurities and temperature/gas effects remain excluded."
        )
        result["maximum_abs_assay_chemistry_difference_mg_l"] = {}
    if physical:
        result["qualification"] = (
            "Closed-batch mass balance: density times volume gives total batch mass; "
            "declared non-solvent product and source-water mass is subtracted to obtain "
            "final solvent mass. Source-water quantity is shared by all its constituents. "
            "Pure make-up water fills the remaining mass. Solvent fractions and density "
            "are independent supplied intervals, not predicted properties. No evaporation, "
            "gas-transfer mass, reactive impurities or experimental verification is modeled. "
            "Analytical interval bounds retain source correlations; chemistry remains sampled."
        )
    if "stock_delivery" in recipe:
        result["qualification"] += " " + recipe["stock_delivery"]["concentration_basis"]
    if nominal["status"] != "passed":
        result.update(status=nominal["status"], failed_checks=["nominal_recipe"])
        return result
    water = _water_input(recipe)
    sources = nominal["ingredients"]
    volume = recipe["volume_litres"]
    volumes = [volume - options["volume_error_litres"], volume + options["volume_error_litres"]]
    dimensions = {}
    groups = []
    effective = []
    choice_coordinates = {}

    def dimension(name, low, high):
        if low != high:
            dimensions[name] = (low, high)

    if isinstance(water, dict):
        source_mass = water["source_water_mass_kg"]
        for key, value in water["totals_mol_kg"].items():
            low, high = (
                value * (1 - options["water_relative_error"]),
                value * (1 + options["water_relative_error"]),
            )
            name = "water." + key
            dimension(name, low, high)
            vector = [0.0] * 9
            if key in BASIS:
                vector[BASIS.index(key)] = source_mass * 1000
            if key in ("Na+", "Cl-"):
                vector[6 if key == "Na+" else 7] = (
                    source_mass * MOLAR_MASS["Na" if key == "Na+" else "Cl"] * 1000
                )
            if key == "NH4+":
                vector[8] = source_mass * MOLAR_MASS["N"] * 1000
            if not physical:
                groups.append((name, [v * low for v in vector], [v * high for v in vector]))
        if physical:
            from .ratio_physical_uncertainty import water_vertices

            group, coords = water_vertices(water, options, dimension)
            groups.append(group)
            choice_coordinates[group[0]] = coords
        if "alkalinity_eq_per_kg" in water:
            v = water["alkalinity_eq_per_kg"]
            a, b = sorted(
                [
                    v * (1 - options["water_relative_error"]),
                    v * (1 + options["water_relative_error"]),
                ]
            )
            dimension("water.alkalinity", a, b)
        dimension(
            "water.ph",
            water["measured_ph"] - options["water_ph_error"],
            water["measured_ph"] + options["water_ph_error"],
        )
    maximum_solvent = 0.0
    for row in sources:
        from .ratio_product_stocks import product_mass_bounds

        mass_low, mass_high = product_mass_bounds(row, options)
        if mass_low < 0:
            result.update(
                status="failed", failed_checks=["weighing_interval_includes_negative_mass"]
            )
            return result
        if elemental:
            from .ratio_element_uncertainty import product_vertices

            group, coordinates, pair = product_vertices(row, options, dimension)
            groups.append(group)
            choice_coordinates[group[0]] = coordinates
            effective.append(pair)
        else:
            a, b = options["product_assay_factors"][row["name"]]
            low, high = mass_low * a, mass_high * b
            effective.append((low, high))
            name = "product." + row["name"]
            dimension(name, low, high)
            percent = row["inventory"]["nutrient_percent"]
            vector = [percent.get(k, 0) * 10 / MOLAR_MASS[k.split("_")[0]] for k in LABELS]
            vector += [percent.get(k, 0) * 10 for k in ("Na", "Cl", "N_NH4")]
            groups.append((name, [v * low for v in vector], [v * high for v in vector]))
        solvent_high = (
            options["physical_preparation"]["product_solvent_fractions"][row["name"]][1]
            if physical
            else row["solvent_fraction"]
        )
        maximum_solvent += mass_high * solvent_high / 1000
    dimension("volume", *volumes)
    count_low = float_sum(min(float_sum(v[:6]) for v in g[1:]) for g in groups) / volumes[1]
    count_high = float_sum(max(float_sum(v[:6]) for v in g[1:]) for g in groups) / volumes[0]
    result["counted_mmol_l_range"] = [count_low, count_high]
    result["elemental_mg_l_ranges"] = {
        k: [
            float_sum(min(v[i] for v in g[1:]) for g in groups)
            / volumes[1]
            * (MOLAR_MASS[k.split("_")[0]] if i < 6 else 1),
            float_sum(max(v[i] for v in g[1:]) for g in groups)
            / volumes[0]
            * (MOLAR_MASS[k.split("_")[0]] if i < 6 else 1),
        ]
        for i, k in enumerate((*LABELS, "Na", "Cl", "N_NH4"))
    }
    failures = set()
    for k, cap in recipe.get("maximum_concentrations", {}).items():
        if result["elemental_mg_l_ranges"][k][1] > cap:
            failures.add("sodium_chloride_limits" if k in ("Na", "Cl") else "nutrient_limits")
    result["maximum_declared_product_solvent_kg"] = maximum_solvent
    minimum_water_mass = recipe["water_mass_kg"] * volumes[0] / volume
    if physical:
        from .ratio_physical_uncertainty import mass_bounds

        mass_range, makeup_low = mass_bounds(recipe, options, dimension)
        result["final_water_mass_kg_range"] = mass_range
        result["minimum_pure_makeup_water_kg"] = makeup_low
        if makeup_low < 0 or mass_range[0] <= 0:
            result.update(
                status="failed", failed_checks=sorted(failures | {"physical_mass_balance"})
            )
            return result
    elif (
        maximum_solvent + recipe["water_accounting"].get("source_water_mass_kg", 0)
        > minimum_water_mass
    ):
        failures.add("solvent_inventory")
    witnesses = []
    ranges = []
    for offset in (0, 3):
        if (
            float_sum(
                min(
                    float_sum(v[i] * VALENCES[i] for i in range(offset, offset + 3)) for v in g[1:]
                )
                for g in groups
            )
            <= 0
        ):
            result.update(status="failed", failed_checks=["empty_ion_group"])
            return result
        for i in range(offset, offset + 3):
            low, wl = _ratio_extreme(groups, i, offset, False)
            high, wh = _ratio_extreme(groups, i, offset, True)
            ranges.append([low, high])
            witnesses.extend([wl, wh])
    result["ratio_percent_ranges"] = ranges
    for pair, target in zip(ranges, recipe["cation_percent"] + recipe["anion_percent"]):
        error = max(abs(v - target) for v in pair)
        relative = error / target if target else (0.0 if error < 1e-10 else math.inf)
        result["worst_ratio_relative_error"] = max(result["worst_ratio_relative_error"], relative)
        if error > 1e-10 + target * options["ratio_relative_tolerance"]:
            failures.add("nutrient_ratios")
    result["worst_concentration_relative_error"] = max(
        abs(v / recipe["counted_mmol_l"] - 1) for v in (count_low, count_high)
    )
    if (
        result["worst_concentration_relative_error"]
        > options["concentration_relative_tolerance"] + 1e-10
    ):
        failures.add("total_concentration")
    names = list(dimensions)
    points = []
    seen = set()

    def add(coords):
        point = tuple(coords.get(n, 0.5) for n in names)
        if point not in seen:
            seen.add(point)
            points.append(point)

    add({})
    add(dict.fromkeys(names, 0.0))
    add(dict.fromkeys(names, 1.0))
    for name in names:
        add({name: 0.0})
        add({name: 1.0})
    for witness in witnesses:
        coordinates = {}
        for group, index in witness.items():
            if group in choice_coordinates:
                coordinates.update(choice_coordinates[group][index])
            else:
                coordinates[group] = index
        add(coordinates)
    result["dimensions"] = dict(dimensions)
    result["dimension_units"] = {
        name: (
            "grams of commercial product"
            if name.startswith("mass.")
            else "fraction of declared elemental assay"
            if name.startswith("assay.")
            else "ingredient mass fraction of commercial product"
            if name.startswith("ingredient.")
            else "effective grams of declared product"
            if name.startswith("product.")
            else "litres"
            if name == "volume"
            else "kg/L final solution"
            if name == "solution.density"
            else "kg source solvent water"
            if name == "source_water.mass"
            else "solvent mass fraction"
            if name.startswith("solvent.") or name == "source_water.solvent_fraction"
            else "pH"
            if name == "water.ph"
            else "eq/kg source water"
            if name == "water.alkalinity"
            else "mol/kg source water"
        )
        for name in names
    }
    result["corner_count"] = 2 ** len(names)
    result["required_scenarios"] = len(points)
    if len(points) > options["max_scenarios"]:
        result.update(
            failed_checks=sorted(failures | {"insufficient_sampling_budget"}),
            planned_scenarios=len(points),
        )
        return result
    rng = random.Random(1961)
    if 2 ** len(names) + len(points) <= options["max_scenarios"]:
        for corner in itertools.product((0.0, 1.0), repeat=len(names)):
            add(dict(zip(names, corner)))
    else:
        for i in range(options["max_scenarios"] * 4 if names else 0):
            if len(points) >= options["max_scenarios"]:
                break
            add({name: float(rng.randrange(2)) if i % 2 == 0 else rng.random() for name in names})
    result["corners_evaluated"] = float_sum(
        all(v in (0.0, 1.0) for v in point) for point in points
    )
    result["all_corners_evaluated"] = result["corners_evaluated"] == 2 ** len(names)
    result["planned_scenarios"] = len(points)
    result["sampling_seed"] = 1961
    result["reference_charge_mol_kg_range"] = None
    result["inorganic_carbon_mol_kg_range"] = None
    try:
        for index, point in enumerate(points):
            values = {
                name: dimensions[name][0] + x * (dimensions[name][1] - dimensions[name][0])
                for name, x in zip(names, point)
            }
            actual_volume = values.get("volume", volume)
            mass = recipe["water_mass_kg"] * actual_volume / volume
            if physical:
                from .ratio_element_uncertainty import perturb_sources
                from .ratio_physical_uncertainty import scenario_mass

                changed, doses = perturb_sources(sources, options, values)
                mass, actual_source_mass = scenario_mass(
                    changed, doses, options, values, actual_volume
                )
            actual_water = deepcopy(water)
            if isinstance(actual_water, dict):
                if physical:
                    actual_water["source_water_mass_kg"] = actual_source_mass
                for key in actual_water["totals_mol_kg"]:
                    actual_water["totals_mol_kg"][key] = values.get(
                        "water." + key, actual_water["totals_mol_kg"][key]
                    )
                actual_water["measured_ph"] = values.get("water.ph", actual_water["measured_ph"])
                if "alkalinity_eq_per_kg" in actual_water:
                    actual_water["alkalinity_eq_per_kg"] = values.get(
                        "water.alkalinity", actual_water["alkalinity_eq_per_kg"]
                    )
            water_report = account_water(actual_water, actual_volume, mass)
            if elemental:
                from .ratio_element_uncertainty import perturb_sources

                if not physical:
                    changed, doses = perturb_sources(sources, options, values)
                rebuilt = reconstruct_products(
                    changed, doses, water_report, actual_volume, mass, scenario_inventories=True
                )
                for key, difference in rebuilt["analytical_minus_chemistry_mg_l"].items():
                    previous = result["maximum_abs_assay_chemistry_difference_mg_l"].get(key, 0.0)
                    result["maximum_abs_assay_chemistry_difference_mg_l"][key] = max(
                        previous, abs(difference)
                    )
            else:
                doses = [
                    values.get("product." + row["name"], pair[0])
                    for row, pair in zip(sources, effective)
                ]
                rebuilt = reconstruct_products(sources, doses, water_report, actual_volume, mass)
            reference = water_report["reference_charge_mol_kg"]
            for key, value in (
                ("reference_charge_mol_kg_range", reference),
                (
                    "inorganic_carbon_mol_kg_range",
                    rebuilt["aqueous_totals_mol_kg"].get("CO3-2", 0),
                ),
            ):
                result[key] = (
                    [value, value]
                    if result[key] is None
                    else [min(result[key][0], value), max(result[key][1], value)]
                )
            from .ratio_ph_refinement import refine_ph, warm_started

            states, refinement = refine_ph(
                warm_started(
                    lambda ph, start: solve(rebuilt["aqueous_totals_mol_kg"], ph, start=start)
                ),
                nominal.get("base_evaluated_ph", nominal["evaluated_ph"]),
                nominal["selected_phases"],
                result["si_required_below"],
            )
            refinement["scenario"] = index
            refinement["evaluated_ph"] = sorted(states)
            result["ph_refinement"]["scenarios"].append(refinement)
            result["ph_refinement"]["total_ph_evaluations"] += len(states)
            if not refinement["complete"]:
                raise DeliveryError(
                    "ph_refinement_incomplete", "Scenario pH sampling budget exhausted"
                )
            charges = []
            for ph, state in sorted(states.items()):
                charges.append(state.charge_balance - reference)
                for phase in nominal["selected_phases"]:
                    si = state.saturation_indices.get(phase)
                    if si is None or not math.isfinite(si):
                        raise DeliveryError("phase_unavailable", f"Missing finite SI for {phase}")
                    if (
                        phase not in result["phase_maxima"]
                        or si > result["phase_maxima"][phase]["si"]
                    ):
                        result["phase_maxima"][phase] = dict(
                            si=si, ph=ph, scenario=index, inputs=values
                        )
                    if si >= result["si_required_below"]:
                        failures.add("saturation_margin")
            if charges[0] * charges[-1] > 0:
                failures.add("equilibrium_ph")
                result["all_scenario_ph_in_range"] = False
                if result["ph_failure_example"] is None:
                    result["ph_failure_example"] = dict(
                        scenario=index,
                        inputs=values,
                        endpoint_charge_errors_mol_kg=[charges[0], charges[-1]],
                    )
            result["scenario_count"] += 1
    except DeliveryError as exc:
        result.update(
            error={"code": exc.code, "message": str(exc)},
            failed_checks=sorted(failures | {"chemistry_incomplete"}),
        )
        return result
    result.update(status="failed" if failures else "passed", failed_checks=sorted(failures))
    return result
