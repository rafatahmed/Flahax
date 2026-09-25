"""Titration-bounded pH planning for a prepared final nutrient solution.

This module calculates an initial acid/base dose from a measured curve. It
never operates equipment and always marks post-mix measurement as required.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .delivery_contracts import (
    DeliveryError,
    validate_product_assay,
    validate_titration_curve,
    validate_water_analysis,
)
from .delivery_quantities import (
    MassGrams,
    MilliEquivalentsPerLitre,
    MilligramsPerLitre,
    VolumeLitres,
    elemental_contribution,
    rescore_with_reagent,
)

CA_CO3_MG_PER_MEQ = 50.043


def alkalinity_meq_per_litre(value: MilligramsPerLitre) -> MilliEquivalentsPerLitre:
    """Convert alkalinity reported as mg/L as CaCO3 into meq/L."""
    if not isinstance(value, MilligramsPerLitre):
        raise DeliveryError("invalid_type", "alkalinity must be a MilligramsPerLitre value")
    return MilliEquivalentsPerLitre(value.value / CA_CO3_MG_PER_MEQ)


@dataclass(frozen=True, slots=True)
class PhPlan:
    """A bounded initial pH-adjustment plan with re-scored nutrient balance."""

    water_analysis_id: str
    titration_curve_id: str
    reagent_id: str
    direction: str
    target_ph: float
    source_alkalinity: MilliEquivalentsPerLitre
    demand: MilliEquivalentsPerLitre
    reagent_volume_litres: float
    reagent_mass: MassGrams
    nutrient_contribution: dict[str, MilligramsPerLitre]
    loss: float
    rows: tuple[dict, ...]
    post_mix_measurement_required: bool = True


def _target_ph(value: Any) -> float:
    if isinstance(value, bool):
        raise DeliveryError("invalid_type", "target_ph must be a number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DeliveryError("invalid_type", "target_ph must be a number") from exc
    if result < 0 or result > 14:
        raise DeliveryError("out_of_range", "target_ph must be between 0 and 14")
    return result


def _interpolate_demand(points: list[dict], target_ph: float) -> tuple[float, str]:
    p_hs = [point["pH"] for point in points]
    lower, upper = min(p_hs), max(p_hs)
    if target_ph < lower or target_ph > upper:
        raise DeliveryError(
            "outside_titration_range",
            f"target pH {target_ph:g} is outside measured range {lower:g}–{upper:g}",
        )
    direction = "base" if p_hs[-1] > p_hs[0] else "acid"
    for left, right in zip(points, points[1:]):
        p0, p1 = left["pH"], right["pH"]
        if min(p0, p1) <= target_ph <= max(p0, p1):
            if target_ph == p0:
                return left["demandMeqPerL"], direction
            if target_ph == p1:
                return right["demandMeqPerL"], direction
            fraction = (target_ph - p0) / (p1 - p0)
            return left["demandMeqPerL"] + fraction * (
                right["demandMeqPerL"] - left["demandMeqPerL"]
            ), direction
    raise DeliveryError("invalid_value", "titrationCurve does not bracket target pH")


def plan_ph(
    water_analysis: Mapping[str, Any],
    titration_curve: Mapping[str, Any],
    reagent: Mapping[str, Any],
    target_ph: float,
    final_volume: VolumeLitres,
    maximum_reagent_volume: VolumeLitres,
    achieved: Mapping[str, Any],
    targets: Mapping[str, Any],
) -> PhPlan:
    """Calculate a bounded initial dose and re-score its nutrient addition.

    The source water must include measured pH and alkalinity. The measured
    curve, not a generic acid formula, determines the dose at the target pH.
    """
    if not isinstance(final_volume, VolumeLitres):
        raise DeliveryError("invalid_type", "final_volume must be a VolumeLitres value")
    if not isinstance(maximum_reagent_volume, VolumeLitres):
        raise DeliveryError("invalid_type", "maximum_reagent_volume must be a VolumeLitres value")
    water = validate_water_analysis(water_analysis)
    curve = validate_titration_curve(titration_curve)
    product = validate_product_assay(reagent)
    p_h = _target_ph(target_ph)
    if "pH" not in water or "alkalinityMgLAsCaCO3" not in water:
        raise DeliveryError("missing_measurement", "water analysis needs measured pH and alkalinity")
    alkalinity = alkalinity_meq_per_litre(MilligramsPerLitre(water["alkalinityMgLAsCaCO3"]))
    if curve["waterAnalysisId"] != water["id"]:
        raise DeliveryError("mismatched_record", "titration curve does not belong to this water analysis")
    if curve["reagentId"] != product["id"]:
        raise DeliveryError("mismatched_record", "titration curve does not belong to this reagent")
    if product["kind"] not in {"acid", "base"}:
        raise DeliveryError("invalid_value", "pH reagent must be an acid or base product")
    if "densityKgPerL" not in product or "normalityMeqPerL" not in product:
        raise DeliveryError(
            "missing_measurement", "pH reagent needs densityKgPerL and normalityMeqPerL",
        )
    demand_value, direction = _interpolate_demand(curve["points"], p_h)
    if product["kind"] != direction:
        raise DeliveryError(
            "mismatched_record", f"titration curve describes a {direction} dose, not {product['kind']}",
        )
    demand = MilliEquivalentsPerLitre(demand_value)
    total_meq = demand.value * final_volume.value
    reagent_volume = total_meq / product["normalityMeqPerL"]
    if reagent_volume > maximum_reagent_volume.value:
        raise DeliveryError(
            "dose_limit_exceeded",
            f"calculated reagent volume {reagent_volume:g} L exceeds the {maximum_reagent_volume.value:g} L limit",
        )
    reagent_mass = MassGrams(reagent_volume * product["densityKgPerL"] * 1000.0)
    fractions = {symbol: percent / 100.0 for symbol, percent in product["elements"].items()}
    contribution = elemental_contribution(reagent_mass, fractions, final_volume)
    loss, rows = rescore_with_reagent(achieved, targets, contribution)
    return PhPlan(
        water["id"],
        curve["id"],
        product["id"],
        direction,
        p_h,
        alkalinity,
        demand,
        reagent_volume,
        reagent_mass,
        contribution,
        loss,
        tuple(rows),
    )
