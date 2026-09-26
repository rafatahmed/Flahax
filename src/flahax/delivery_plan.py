"""Atomic, reviewable composition of recipe, stock, pH, and pump plans."""
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Iterable, Mapping, Any
from .delivery_contracts import DeliveryError
from .delivery_quantities import FinalSolutionRecipe, VolumeLitres
from .ph_planning import PhPlan
from .pump_planning import PumpCommand
from .stock_planning import StockPlan

PLAN_STATES = frozenset({"draft", "validated", "operator-approved", "executed", "verified", "blocked"})
_TRANSITIONS = {"draft": {"validated", "blocked"}, "validated": {"operator-approved", "blocked"}, "operator-approved": {"executed", "blocked"}, "executed": {"verified", "blocked"}, "verified": set(), "blocked": set()}

@dataclass(frozen=True, slots=True)
class DeliveryPlan:
    recipe: FinalSolutionRecipe; stocks: StockPlan; ph_plan: PhPlan | None; commands: tuple[PumpCommand, ...]
    audit_record: dict[str, Any]; warnings: tuple[str, ...]; state: str = "draft"

def compose_delivery_plan(recipe: FinalSolutionRecipe, stocks: StockPlan, ph_plan: PhPlan | None, commands: Iterable[PumpCommand], audit_record: Mapping[str, Any], warnings: Iterable[str] = ()) -> DeliveryPlan:
    if not isinstance(recipe, FinalSolutionRecipe) or not isinstance(stocks, StockPlan): raise DeliveryError("invalid_type", "recipe and stocks must be planning values")
    if stocks.recipe != recipe: raise DeliveryError("cross_stage_constraint", "stock plan recipe does not match delivery recipe")
    if ph_plan is not None and not isinstance(ph_plan, PhPlan): raise DeliveryError("invalid_type", "ph_plan must be a PhPlan or None")
    clean_commands=tuple(commands)
    if any(not isinstance(x,PumpCommand) for x in clean_commands): raise DeliveryError("invalid_type", "commands must contain PumpCommand values")
    if not isinstance(audit_record, Mapping) or not audit_record:
        raise DeliveryError("missing_field", "audit_record is required")
    if not isinstance(audit_record.get("modelVersion"), str) or not audit_record["modelVersion"].strip():
        raise DeliveryError("missing_field", "audit_record.modelVersion is required")
    if not recipe.feasible or not stocks.tanks: raise DeliveryError("cross_stage_constraint", "a feasible recipe and non-empty stock plan are required")
    return DeliveryPlan(recipe,stocks,ph_plan,clean_commands,dict(audit_record),tuple(str(x) for x in warnings))

def transition_plan(plan: DeliveryPlan, target: str) -> DeliveryPlan:
    if not isinstance(plan,DeliveryPlan): raise DeliveryError("invalid_type", "plan must be a DeliveryPlan")
    if target not in PLAN_STATES or target not in _TRANSITIONS[plan.state]: raise DeliveryError("invalid_plan_transition", f"cannot transition {plan.state} to {target}")
    if target == "validated" and (plan.ph_plan is None or not plan.commands):
        raise DeliveryError("incomplete_plan", "validated plan needs pH plan and pump commands")
    if target == "operator-approved" and any(c.requires_operator_verification for c in plan.commands):
        # The explicit transition is the approval; commands remain verification-required at execution.
        pass
    return replace(plan,state=target)

def delivery_report(plan: DeliveryPlan) -> str:
    if not isinstance(plan,DeliveryPlan): raise DeliveryError("invalid_type", "plan must be a DeliveryPlan")
    lines=[f"FlahaX delivery plan: {plan.state}",f"Final volume: {plan.recipe.final_volume.value:g} L",f"Stock tanks: {len(plan.stocks.tanks)}",f"Pump commands: {len(plan.commands)}",f"Audit model: {plan.audit_record.get('modelVersion','unspecified')}"]
    if plan.ph_plan: lines.append(f"pH target: {plan.ph_plan.target_ph:g}; post-mix measurement required")
    lines.extend(f"Warning: {warning}" for warning in plan.warnings)
    return "\n".join(lines)
