# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Conservative, data-driven stock-tank planning for a final FlahaX recipe.

The planner does not infer chemistry from a product name. Every product needs
a supplied temperature-qualified solubility limit, and any co-storage ban must
come from a versioned compatibility-rule record.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import product
import math
from typing import Any, Iterable, Mapping

from .delivery_contracts import (
    DeliveryError,
    validate_compatibility_rule,
    validate_solubility_limit,
)
from .delivery_quantities import (
    FinalSolutionRecipe,
    GramsPerLitre,
    InjectionRatio,
    TemperatureCelsius,
    VolumeLitres,
)


@dataclass(frozen=True, slots=True)
class StockTank:
    """A physical tank available for a prepared stock solution."""

    tank_id: str
    capacity: VolumeLitres

    def __post_init__(self) -> None:
        if not isinstance(self.tank_id, str) or not self.tank_id.strip():
            raise DeliveryError("invalid_value", "stock tank id must be a non-empty string")
        if not isinstance(self.capacity, VolumeLitres):
            raise DeliveryError("invalid_type", "stock tank capacity must be a VolumeLitres value")
        object.__setattr__(self, "tank_id", self.tank_id.strip())


@dataclass(frozen=True, slots=True)
class StockSaltDose:
    """One fertilizer's concentration in a stock tank."""

    salt_id: str
    name: str
    concentration: GramsPerLitre


@dataclass(frozen=True, slots=True)
class StockTankPlan:
    """One stock tank: its volume and the fertilizers dissolved in it."""

    tank: StockTank
    stock_volume: VolumeLitres
    salts: tuple[StockSaltDose, ...]


@dataclass(frozen=True, slots=True)
class StockPlan:
    """A capacity-checked assignment with explicit mixture qualification and search status."""

    recipe: FinalSolutionRecipe
    injection_ratio: InjectionRatio
    temperature: TemperatureCelsius
    tanks: tuple[StockTankPlan, ...]
    compatibility_rule_ids: tuple[str, ...]
    solubility_limit_ids: tuple[str, ...]
    mixture_approved: bool = False
    status: str = 'requires_review'
    mixture_assessments: tuple[dict, ...] = ()
    assignments_evaluated: int = 0
    search_complete: bool = True


def _validated_tanks(tanks: Iterable[StockTank]) -> tuple[StockTank, ...]:
    try:
        clean = tuple(tanks)
    except TypeError as exc:
        raise DeliveryError(
            "invalid_type", "tanks must be an iterable of StockTank values"
        ) from exc
    if not clean:
        raise DeliveryError("missing_field", "at least one stock tank is required")
    ids = set()
    for tank in clean:
        if not isinstance(tank, StockTank):
            raise DeliveryError("invalid_type", "tanks must contain StockTank values")
        if tank.tank_id in ids:
            raise DeliveryError("invalid_value", f"stock tanks repeat {tank.tank_id}")
        ids.add(tank.tank_id)
    return tuple(sorted(clean, key=lambda tank: tank.tank_id))


def _limits_at_temperature(
    limits: Iterable[Mapping[str, Any]], temperature: TemperatureCelsius
) -> dict[str, dict]:
    usable: dict[str, dict] = {}
    for raw in limits:
        limit = validate_solubility_limit(raw)
        if limit["temperatureMinC"] <= temperature.value <= limit["temperatureMaxC"]:
            current = usable.get(limit["productId"])
            if current is None or limit["maxGramsPerLitre"] < current["maxGramsPerLitre"]:
                usable[limit["productId"]] = limit
    return usable


def _compatible(groups: list[list[str]], rules: tuple[dict, ...]) -> bool:
    for group in groups:
        members = set(group)
        for rule in rules:
            # A "separate" rule with multiple listed products means no two of
            # that group may be co-stored in the same concentrated tank.
            if len(members.intersection(rule["productIds"])) >= 2:
                return False
    return True


def _assess_mixture(tank, temperature, model):
    """Validate caller model evidence against this exact stock and its domain."""
    if model is None:
        return dict(status='not_supported', reason='no qualified mixture model')
    raw = model(tank, temperature)
    if not isinstance(raw, Mapping):
        raise DeliveryError('invalid_mixture_result', 'mixture model must return a mapping')
    result = dict(raw)
    if result.get('status') not in ('compatible', 'incompatible', 'not_supported'):
        raise DeliveryError('invalid_mixture_result', 'unknown mixture model status')
    if result['status'] != 'compatible':
        return result
    required = ('model_id', 'source', 'revision', 'review_id')
    if result.get('reviewed') is not True or any(
        not isinstance(result.get(k), str) or not result[k].strip() for k in required
    ):
        return dict(status='not_supported', reason='unreviewed mixture model')
    ids = result.get('product_ids')
    if not isinstance(ids, (tuple, list)) or sorted(ids) != sorted(s.salt_id for s in tank.salts):
        return dict(status='not_supported', reason='product or grade identity mismatch')
    if result.get('evaluated_concentrations_g_per_l') != {
        s.salt_id: s.concentration.value for s in tank.salts
    }:
        return dict(status='not_supported', reason='mixture input concentrations do not match')
    if result.get('basis') != 'g_per_l_stock_solution':
        return dict(status='not_supported', reason='unsupported mixture concentration basis')
    keys = (
        'temperature_min_c',
        'temperature_max_c',
        'ionic_strength',
        'ionic_strength_max',
        'total_concentration_max_g_per_l',
    )
    if any(
        isinstance(result.get(k), bool)
        or not isinstance(result.get(k), (int, float))
        or not math.isfinite(result[k])
        for k in keys
    ):
        raise DeliveryError('invalid_mixture_result', 'model bounds must be finite numbers')
    if not (
        result['temperature_min_c'] <= temperature.value <= result['temperature_max_c']
        and 0 <= result['ionic_strength'] <= result['ionic_strength_max']
        and sum(s.concentration.value for s in tank.salts)
        <= result['total_concentration_max_g_per_l']
    ):
        return dict(
            status='not_supported',
            reason='stock outside reviewed model domain',
            model_id=result['model_id'],
        )
    if result.get('mass_balance_verified') is not True:
        return dict(status='not_supported', reason='mixture mass balance not verified')
    return result


def plan_stocks(
    recipe: FinalSolutionRecipe,
    injection_ratio: InjectionRatio,
    tanks: Iterable[StockTank],
    compatibility_rules: Iterable[Mapping[str, Any]],
    solubility_limits: Iterable[Mapping[str, Any]],
    temperature: TemperatureCelsius,
    *,
    mixture_model=None,
    max_assignments=100000,
) -> StockPlan:
    """Assign a feasible recipe to compatible concentrated-stock tanks.

    Stock concentration is ``final_g_per_litre * injection_ratio`` and each
    used tank holds ``final_volume / injection_ratio``. The planner chooses the
    first qualified assignment using the fewest tanks, then tank-id order.
    Without a reviewed mixture model, return a structural requires_review plan,
    never mixing approval. The callable receives (StockTankPlan, temperature)
    and must report matched product IDs, basis, source, review and domain bounds.
    Search evaluates alternatives after mixture rejection; exhaustion is explicit.
    """
    if not isinstance(recipe, FinalSolutionRecipe):
        raise DeliveryError("invalid_type", "recipe must be a FinalSolutionRecipe value")
    if not recipe.feasible:
        raise DeliveryError(
            "infeasible_recipe", "an infeasible nutrient recipe cannot produce a stock plan"
        )
    if not isinstance(injection_ratio, InjectionRatio):
        raise DeliveryError("invalid_type", "injection_ratio must be an InjectionRatio value")
    if not isinstance(temperature, TemperatureCelsius):
        raise DeliveryError("invalid_type", "temperature must be a TemperatureCelsius value")
    if mixture_model is not None and not callable(mixture_model):
        raise DeliveryError('invalid_type', 'mixture_model must be callable')
    if type(max_assignments) is not int or max_assignments < 1:
        raise DeliveryError('invalid_value', 'max_assignments must be a positive integer')
    clean_tanks = _validated_tanks(tanks)
    rules = tuple(validate_compatibility_rule(item) for item in compatibility_rules)
    limits = _limits_at_temperature(solubility_limits, temperature)
    stock_volume = VolumeLitres(recipe.final_volume.value / injection_ratio.value)

    prepared = []
    for salt in recipe.salts:
        limit = limits.get(salt.salt_id)
        if limit is None:
            raise DeliveryError(
                "missing_solubility_limit",
                f"{salt.salt_id} has no solubility limit at {temperature.value:g} °C",
            )
        concentration = GramsPerLitre(salt.dose.value * injection_ratio.value)
        if concentration.value > limit["maxGramsPerLitre"]:
            raise DeliveryError(
                "solubility_exceeded",
                f"{salt.salt_id} needs {concentration.value:g} g/L stock, above its "
                f"{limit['maxGramsPerLitre']:g} g/L limit",
            )
        prepared.append((salt, concentration, limit["id"]))

    usable_tanks = tuple(tank for tank in clean_tanks if tank.capacity.value >= stock_volume.value)
    if not usable_tanks:
        raise DeliveryError(
            "capacity_exceeded",
            f"every tank is smaller than the required {stock_volume.value:g} L stock volume",
        )
    if not prepared:
        return StockPlan(
            recipe, injection_ratio, temperature, (), tuple(rule["id"] for rule in rules), ()
        )

    fallback = None
    evaluated = 0
    for count in range(1, len(usable_tanks) + 1):
        for assignment in product(range(count), repeat=len(prepared)):
            evaluated += 1
            if evaluated > max_assignments:
                if fallback is not None:
                    return replace(
                        fallback, search_complete=False, assignments_evaluated=max_assignments
                    )
                raise DeliveryError('stock_search_limit', 'assignment search budget exhausted')
            if len(set(assignment)) != count:
                continue
            groups = [[] for _ in range(count)]
            for index, tank_index in enumerate(assignment):
                groups[tank_index].append(prepared[index])
            if not _compatible([[s.salt_id for s, _, _ in g] for g in groups], rules):
                continue
            built = tuple(
                StockTankPlan(
                    usable_tanks[i],
                    stock_volume,
                    tuple(StockSaltDose(s.salt_id, s.name, c) for s, c, _ in g),
                )
                for i, g in enumerate(groups)
            )
            assessments = tuple(_assess_mixture(t, temperature, mixture_model) for t in built)
            approved = all(a['status'] == 'compatible' for a in assessments)
            candidate = StockPlan(
                recipe,
                injection_ratio,
                temperature,
                built,
                tuple(r['id'] for r in rules),
                tuple(limit_id for g in groups for _, _, limit_id in g),
                approved,
                'qualified' if approved else 'requires_review',
                assessments,
                evaluated,
            )
            if approved:
                return candidate
            if not any(a['status'] == 'incompatible' for a in assessments) and fallback is None:
                fallback = candidate
            if mixture_model is None:
                return candidate  # alternatives cannot create missing model evidence
    if fallback is not None:
        return replace(fallback, assignments_evaluated=evaluated)
    raise DeliveryError(
        'no_stock_assignment',
        'no assignment satisfies the supplied equipment, separations and model',
    )
