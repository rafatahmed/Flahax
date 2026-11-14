"""Bounded search for numerically passing recipes with optional record gating."""

import math

from .delivery_contracts import DeliveryError
from .ratio_recipe import plan_ratio_recipe, _number
from .steiner_context import historical_context


def search_ratio_recipe(
    *,
    strength_range,
    strength_tolerance=1e-5,
    scan_points=33,
    saturation_margin=0.3,
    **recipe_options,
):
    """Scan strength and refine every observed passing-to-failing transition.

    Rounded doses can create discontinuities. Report search coverage and the
    strongest verified candidate found, with no global optimality assertion.
    """
    if not isinstance(strength_range, (list, tuple)) or len(strength_range) != 2:
        raise DeliveryError("invalid_strength_range", "strength_range requires two values")
    low, high = [_number(v, "strength_range") for v in strength_range]
    if low >= high:
        raise DeliveryError("invalid_strength_range", "Strength bounds must be increasing")
    tolerance = _number(strength_tolerance, "strength_tolerance")
    if type(scan_points) is not int or not 3 <= scan_points <= 1001:
        raise DeliveryError("invalid_scan_points", "scan_points must be an integer from 3 to 1001")
    if recipe_options.get("ph_range") is None:
        raise DeliveryError("missing_ph_range", "A strength search requires ph_range")
    if "counted_mmol_l" in recipe_options:
        raise DeliveryError("duplicate_strength", "Choose a fixed strength or a search range")
    saturation_margin = _number(saturation_margin, "saturation_margin", zero=True)
    recipe_options["saturation_margin"] = saturation_margin
    evaluated = {}
    best = None

    def evaluate(strength):
        nonlocal best
        if strength in evaluated:
            return evaluated[strength]["status"]
        try:
            recipe = plan_ratio_recipe(counted_mmol_l=strength, **recipe_options)
        except DeliveryError as exc:
            if exc.code not in (
                "ratio_infeasible",
                "ratio_allocation_infeasible",
                "ratio_water_exceeds_target",
                "ratio_stock_dose_infeasible",
                "ratio_stock_volume_infeasible",
                "nonconvergent",
                "activity_model_out_of_range",
            ):
                raise
            status = "failed" if exc.code.startswith("ratio_") else "incomplete"
            evaluated[strength] = {"status": status, "error": str(exc)}
            return status
        check = recipe.get("uncertainty_verification", recipe["rounded_verification"])
        status = check["status"]
        if recipe_options.get("stock_evidence") is not None and not recipe.get("verified", False):
            if status == "passed":
                status = "failed"
        if recipe_options.get("batch_stability") is not None and not recipe.get("stable", False):
            if status == "passed":
                status = "failed"
        evaluated[strength] = {"status": status}
        if "stability_assessment" in recipe:
            evaluated[strength]["stability_status"] = recipe["stability_assessment"]["status"]
        if "stock_verification" in recipe:
            evaluated[strength]["verification_status"] = recipe["stock_verification"]["status"]
            evaluated[strength]["evidence_failures"] = recipe["stock_verification"]["failures"]
        if "uncertainty_verification" in recipe:
            evaluated[strength]["failed_checks"] = check["failed_checks"]
        if status == "passed" and (best is None or strength > best[0]):
            best = (strength, recipe)
        return status

    grid = [low + (high - low) * i / (scan_points - 1) for i in range(scan_points)]
    for strength in grid:
        evaluate(strength)
    brackets = []
    for left, right in zip(grid, grid[1:]):
        if evaluated[left]["status"] != "passed" or evaluated[right]["status"] != "failed":
            continue
        for _ in range(80):
            if right - left <= tolerance:
                break
            middle = (left + right) / 2
            if not left < middle < right:
                break
            status = evaluate(middle)
            if status == "incomplete":
                break
            if status == "passed":
                left = middle
            else:
                right = middle
        brackets.append(
            {"passing_strength": left, "failing_strength": right, "width": right - left}
        )
    incomplete = any(row["status"] == "incomplete" for row in evaluated.values()) or any(
        bracket["width"] > tolerance for bracket in brackets
    )
    result = {
        "status": "incomplete"
        if incomplete
        else ("found" if best is not None else "no_feasible_candidate_found"),
        "strength_range": [low, high],
        "strength_tolerance": tolerance,
        "saturation_margin": saturation_margin,
        "uncertainty": recipe_options.get("uncertainty"),
        "stock_dosing": recipe_options.get("stock_dosing"),
        "initial_scan_points": scan_points,
        "evaluation_count": len(evaluated),
        "evaluations": [{"strength_mmol_l": x, **row} for x, row in sorted(evaluated.items())],
        "transition_brackets": brackets,
        "search_cap_reached": False,
        "requested_strength_mmol_l": None,
        "recipe": None,
        "verified": False,
        "stable": False,
        "verification_status": "unverified",
        "limiting_phase": None,
        "controlling_ph": None,
        "claim": "Strongest numerically passing rounded candidate found over the stated scan and "
        "transition refinements. Disconnected narrow feasible regions may be missed.",
        "coverage": "Every candidate uses the reported pH grid. Rounding can make "
        "feasibility discontinuous. Strength tolerance applies to refined brackets.",
        "historical_context": historical_context(
            strength_range=[low, high],
            ph_range=recipe_options["ph_range"],
            cation_shares=recipe_options["cation_shares"],
            anion_shares=recipe_options["anion_shares"],
        ),
    }
    if best is None:
        return result
    strength, _ = best
    # Reconstruct again so a cached verdict is not the delivery evidence.
    recipe = plan_ratio_recipe(counted_mmol_l=strength, **recipe_options)
    if (
        recipe.get("uncertainty_verification", recipe["rounded_verification"])["status"]
        != "passed"
    ):
        result["status"] = "incomplete"
        return result
    if recipe_options.get("stock_evidence") is not None and not recipe.get("verified", False):
        result["status"] = "incomplete"
        return result
    if recipe_options.get("batch_stability") is not None and not recipe.get("stable", False):
        result["status"] = "incomplete"
        return result
    result["stable"] = recipe.get("stable", False)
    result["verified"] = recipe.get("verified", False)
    result["verification_status"] = "verified" if result["verified"] else "unverified"
    maxima = recipe.get("uncertainty_verification", recipe["rounded_verification"])["phase_maxima"]
    phase = max(maxima, key=lambda name: maxima[name]["si"])
    result.update(
        requested_strength_mmol_l=strength,
        recipe=recipe,
        search_cap_reached=math.isclose(strength, high, rel_tol=0, abs_tol=0),
        limiting_phase=phase,
        controlling_ph=maxima[phase]["ph"],
    )
    return result
