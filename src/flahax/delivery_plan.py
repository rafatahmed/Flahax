# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Atomic, reviewable composition of recipe, stock, pH, and pump plans."""

from __future__ import annotations
from dataclasses import dataclass, replace
import math
from typing import Iterable, Mapping, Any
from .saturation_policy import assess_saturation
from .delivery_contracts import DeliveryError
from .delivery_quantities import FinalSolutionRecipe
from .ph_planning import PhPlan
from .equilibrium_delivery import EquilibriumPhPlan
from .pump_planning import PumpCommand
from .stock_planning import StockPlan

PLAN_STATES = frozenset(
    {"draft", "validated", "operator-approved", "executed", "verified", "blocked"}
)
_TRANSITIONS = {
    "draft": {"validated", "blocked"},
    "validated": {"operator-approved", "blocked"},
    "operator-approved": {"executed", "blocked"},
    "executed": {"verified", "blocked"},
    "verified": set(),
    "blocked": set(),
}


@dataclass(frozen=True, slots=True)
class DeliveryPlan:
    """A recipe, its stock tanks, pH plan and pump commands, with the audit record, warnings and
    its approval state (``draft`` first).
    """

    recipe: FinalSolutionRecipe
    stocks: StockPlan
    ph_plan: PhPlan | EquilibriumPhPlan | None
    commands: tuple[PumpCommand, ...]
    audit_record: dict[str, Any]
    warnings: tuple[str, ...]
    state: str = "draft"


def _check_delivery_balance(recipe, stocks, ph_plan, commands, *, complete):
    """Check additive batch-volume bookkeeping and unrounded product identities."""

    def matches(actual, expected, *, absolute=1e-12):
        # Preserve command-volume tolerance; product mass has no absolute floor.
        return (
            math.isfinite(actual)
            and math.isfinite(expected)
            and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=absolute)
        )

    def fail(message):
        raise DeliveryError('cross_stage_constraint', message)

    expected = {}
    masses = {}
    for tank in stocks.tanks:
        channel = tank.tank.tank_id
        if channel in expected:
            fail('stock channels must be unique')
        volume = tank.stock_volume.value
        if volume > tank.tank.capacity.value or not matches(
            volume, recipe.final_volume.value / stocks.injection_ratio.value
        ):
            fail('stock volume must match ratio and fit tank capacity')
        expected[channel] = volume
        for salt in tank.salts:
            if salt.salt_id in masses:
                fail('each product must occur in exactly one stock')
            masses[salt.salt_id] = salt.concentration.value * volume
    recipe_masses = {salt.salt_id: salt.mass.value for salt in recipe.salts}
    if len(recipe_masses) != len(recipe.salts) or set(masses) != set(recipe_masses):
        fail('stock products must match recipe products exactly')
    for salt in recipe.salts:
        if not matches(masses[salt.salt_id], salt.mass.value, absolute=0.0) or not matches(
            salt.dose.value * recipe.final_volume.value, salt.mass.value, absolute=0.0
        ):
            fail('stock and final-solution product masses differ')
    if ph_plan is not None:
        if isinstance(ph_plan, PhPlan) and ph_plan.final_volume != recipe.final_volume:
            fail('titration plan must retain the matching final volume')
        channel = ph_plan.reagent_channel_id
        if not isinstance(channel, str) or not channel.strip() or channel in expected:
            fail('reagent needs a distinct nonempty channel')
        volume = ph_plan.reagent_volume_litres
        if not math.isfinite(volume) or volume < 0:
            fail('reagent volume must be finite and non-negative')
        if volume > 0:
            expected[channel] = volume
    total = sum(expected.values())
    if not math.isfinite(total) or total >= recipe.final_volume.value:
        fail('combined stocks and reagent must leave positive carrier volume')
    seen = set()
    for command in commands:
        if command.channel_id in seen or command.channel_id not in expected:
            fail('duplicate or unknown delivery channel')
        seen.add(command.channel_id)
        if not matches(command.requested_volume.value, expected[command.channel_id]):
            fail('command volume differs from planned channel volume')
    if complete and seen != set(expected):
        raise DeliveryError('incomplete_plan', 'every stock and reagent needs one command')
    return recipe.final_volume.value - total


def compose_delivery_plan(
    recipe: FinalSolutionRecipe,
    stocks: StockPlan,
    ph_plan: PhPlan | EquilibriumPhPlan | None,
    commands: Iterable[PumpCommand],
    audit_record: Mapping[str, Any],
    warnings: Iterable[str] = (),
) -> DeliveryPlan:
    """A draft DeliveryPlan after checking that every stage plans the same recipe; raises
    DeliveryError when a stage does not match.
    """
    if not isinstance(recipe, FinalSolutionRecipe) or not isinstance(stocks, StockPlan):
        raise DeliveryError("invalid_type", "recipe and stocks must be planning values")
    if stocks.recipe != recipe:
        raise DeliveryError(
            "cross_stage_constraint", "stock plan recipe does not match delivery recipe"
        )
    if ph_plan is not None and not isinstance(ph_plan, (PhPlan, EquilibriumPhPlan)):
        raise DeliveryError("invalid_type", "ph_plan must be PhPlan, EquilibriumPhPlan or None")
    if isinstance(ph_plan, EquilibriumPhPlan) and ph_plan.recipe != recipe:
        raise DeliveryError(
            'cross_stage_constraint', 'equilibrium plan recipe does not match delivery recipe'
        )
    clean_commands = tuple(commands)
    if any(not isinstance(x, PumpCommand) for x in clean_commands):
        raise DeliveryError("invalid_type", "commands must contain PumpCommand values")
    if not isinstance(audit_record, Mapping) or not audit_record:
        raise DeliveryError("missing_field", "audit_record is required")
    if (
        not isinstance(audit_record.get("modelVersion"), str)
        or not audit_record["modelVersion"].strip()
    ):
        raise DeliveryError("missing_field", "audit_record.modelVersion is required")
    if not recipe.feasible or not stocks.tanks:
        raise DeliveryError(
            "cross_stage_constraint", "a feasible recipe and non-empty stock plan are required"
        )
    _check_delivery_balance(recipe, stocks, ph_plan, clean_commands, complete=False)
    audit = dict(audit_record)
    combined_warnings = tuple(str(x) for x in warnings)
    if isinstance(ph_plan, EquilibriumPhPlan):
        acid_commands = [c for c in clean_commands if c.channel_id == ph_plan.reagent_channel_id]
        if ph_plan.reagent_volume_litres > 0 and len(acid_commands) != 1:
            raise DeliveryError(
                'cross_stage_constraint', 'one acid command must match the planned reagent'
            )
        if 'equilibrium' in audit and audit['equilibrium'] != ph_plan.audit:
            raise DeliveryError(
                'cross_stage_constraint', 'equilibrium audit metadata differs from the plan'
            )
        audit['equilibrium'] = ph_plan.audit
        combined_warnings += ph_plan.warnings
    return DeliveryPlan(recipe, stocks, ph_plan, clean_commands, audit, combined_warnings)


def transition_plan(plan: DeliveryPlan, target: str) -> DeliveryPlan:
    """The plan moved to ``target`` state; raises DeliveryError when the move is not allowed or a
    validated plan lacks its pH plan, commands or clean equilibrium.
    """
    if not isinstance(plan, DeliveryPlan):
        raise DeliveryError("invalid_type", "plan must be a DeliveryPlan")
    if target not in PLAN_STATES or target not in _TRANSITIONS[plan.state]:
        raise DeliveryError(
            "invalid_plan_transition", f"cannot transition {plan.state} to {target}"
        )
    if target == "validated" and (plan.ph_plan is None or not plan.commands):
        raise DeliveryError("incomplete_plan", "validated plan needs pH plan and pump commands")
    if target == 'validated' and not plan.stocks.mixture_approved:
        raise DeliveryError(
            'unqualified_stock_mixture', 'stock mixtures require qualified model evidence'
        )
    if target != 'blocked':
        # Revalidate even manually constructed/replaced values before advancing state.
        compose_delivery_plan(
            plan.recipe, plan.stocks, plan.ph_plan, plan.commands, plan.audit_record
        )
        _check_delivery_balance(
            plan.recipe, plan.stocks, plan.ph_plan, plan.commands, complete=True
        )
    if target == 'validated' and isinstance(plan.ph_plan, EquilibriumPhPlan):
        result = plan.ph_plan.equilibrium.target
        # A phase name or operator acknowledgement cannot establish applicability.
        if assess_saturation(result)['blocks']:
            raise DeliveryError(
                'precipitation_risk',
                'equilibrium target cannot be approved with solids or positive SI',
            )
        if (
            plan.ph_plan.incidental_assessment
            and plan.ph_plan.incidental_assessment['requiresReview']
        ):
            raise DeliveryError(
                'incidental_review_required',
                'incidental nutrient contributions need explicit limits before validation',
            )
    if target == "operator-approved" and any(
        c.requires_operator_verification for c in plan.commands
    ):
        # The explicit transition is the approval; commands remain verification-required at
        # execution.
        pass
    return replace(plan, state=target)


def delivery_report(plan: DeliveryPlan) -> str:
    """A short plain-text summary of the plan: state, volume, tanks, pump commands, pH target and
    warnings.
    """
    if not isinstance(plan, DeliveryPlan):
        raise DeliveryError("invalid_type", "plan must be a DeliveryPlan")
    lines = [
        f"FlahaX delivery plan: {plan.state}",
        f"Final volume: {plan.recipe.final_volume.value:g} L",
        f"Stock tanks: {len(plan.stocks.tanks)}",
        f"Pump commands: {len(plan.commands)}",
        f"Audit model: {plan.audit_record.get('modelVersion', 'unspecified')}",
    ]
    carrier = _check_delivery_balance(
        plan.recipe, plan.stocks, plan.ph_plan, plan.commands, complete=False
    )
    lines.append(f"Carrier remainder (additive-volume accounting): {carrier:g} L")
    lines.append("Contact time, hydraulic mixing and volume contraction are not modeled.")
    if plan.ph_plan:
        lines.append(f"pH target: {plan.ph_plan.target_ph:g}; post-mix measurement required")
    lines.extend(f"Warning: {warning}" for warning in plan.warnings)
    return "\n".join(lines)
