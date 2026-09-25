"""Conservative, data-driven stock-tank planning for a final FlahaX recipe.

The planner does not infer chemistry from a product name. Every product needs
a supplied temperature-qualified solubility limit, and any co-storage ban must
come from a versioned compatibility-rule record.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
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
    salt_id: str
    name: str
    concentration: GramsPerLitre


@dataclass(frozen=True, slots=True)
class StockTankPlan:
    tank: StockTank
    stock_volume: VolumeLitres
    salts: tuple[StockSaltDose, ...]


@dataclass(frozen=True, slots=True)
class StockPlan:
    """A compatible, capacity-checked plan without any hardware command."""

    recipe: FinalSolutionRecipe
    injection_ratio: InjectionRatio
    temperature: TemperatureCelsius
    tanks: tuple[StockTankPlan, ...]
    compatibility_rule_ids: tuple[str, ...]
    solubility_limit_ids: tuple[str, ...]


def _validated_tanks(tanks: Iterable[StockTank]) -> tuple[StockTank, ...]:
    try:
        clean = tuple(tanks)
    except TypeError as exc:
        raise DeliveryError("invalid_type", "tanks must be an iterable of StockTank values") from exc
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


def plan_stocks(
    recipe: FinalSolutionRecipe,
    injection_ratio: InjectionRatio,
    tanks: Iterable[StockTank],
    compatibility_rules: Iterable[Mapping[str, Any]],
    solubility_limits: Iterable[Mapping[str, Any]],
    temperature: TemperatureCelsius,
) -> StockPlan:
    """Assign a feasible recipe to compatible concentrated-stock tanks.

    Stock concentration is ``final_g_per_litre * injection_ratio`` and each
    used tank holds ``final_volume / injection_ratio``. The planner chooses the
    first deterministic assignment using the fewest tanks, then tank-id order.
    """
    if not isinstance(recipe, FinalSolutionRecipe):
        raise DeliveryError("invalid_type", "recipe must be a FinalSolutionRecipe value")
    if not recipe.feasible:
        raise DeliveryError("infeasible_recipe", "an infeasible nutrient recipe cannot produce a stock plan")
    if not isinstance(injection_ratio, InjectionRatio):
        raise DeliveryError("invalid_type", "injection_ratio must be an InjectionRatio value")
    if not isinstance(temperature, TemperatureCelsius):
        raise DeliveryError("invalid_type", "temperature must be a TemperatureCelsius value")
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
        return StockPlan(recipe, injection_ratio, temperature, (), tuple(rule["id"] for rule in rules), ())

    selected: tuple[int, ...] | None = None
    for count in range(1, len(usable_tanks) + 1):
        for assignment in product(range(count), repeat=len(prepared)):
            groups = [[] for _ in range(count)]
            for index, tank_index in enumerate(assignment):
                groups[tank_index].append(prepared[index][0].salt_id)
            if _compatible(groups, rules):
                selected = assignment
                break
        if selected is not None:
            break
    if selected is None:
        raise DeliveryError("no_stock_assignment", "no compatible assignment exists for the supplied tanks and rules")

    groups: list[list[tuple[Any, GramsPerLitre, str]]] = [[] for _ in range(max(selected) + 1)]
    for item, tank_index in zip(prepared, selected):
        groups[tank_index].append(item)
    plan_tanks = []
    used_limit_ids = []
    for index, group in enumerate(groups):
        if not group:
            continue
        plan_tanks.append(
            StockTankPlan(
                usable_tanks[index],
                stock_volume,
                tuple(StockSaltDose(salt.salt_id, salt.name, concentration) for salt, concentration, _limit_id in group),
            )
        )
        used_limit_ids.extend(limit_id for _salt, _concentration, limit_id in group)
    return StockPlan(
        recipe,
        injection_ratio,
        temperature,
        tuple(plan_tanks),
        tuple(rule["id"] for rule in rules),
        tuple(used_limit_ids),
    )
