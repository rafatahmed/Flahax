# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Shared nutrient ledger: form ions plus optional aggregate elemental total N.

Aggregate key ``N`` means elemental N = N_NO3 + N_NH4 + N_UREA from water, salts,
and pH reagents counted once. Form targets stay independent; an aggregate constraint
does not invent a nitrate/ammonium/urea split. Water ion maps must not use bare ``N``
as NO3- mass — that stays an unsupported ion key.
"""

from __future__ import annotations

from collections.abc import Mapping

# Elemental nitrogen forms in the mass balance. Aggregate total N is the key "N".
N_FORMS = ("N_NO3", "N_NH4", "N_UREA")
N_AGGREGATE = "N"
# Absolute mg/L agreement between stated forms and aggregate N.
_N_CONSISTENCY_ABS = 1e-6
# Match engine.TOLERANCE_PCT for aggregate/form target assessment.
_DEFAULT_TOLERANCE_PCT = 1.0


def elemental_nitrogen(totals: Mapping[str, float]) -> float:
    """Elemental total N (mg/L) as the sum of N_NO3 + N_NH4 + N_UREA.

    Ignores an aggregate ``N`` key on ``totals`` so forms are never double-counted.
    """
    return sum(float(totals.get(form) or 0.0) for form in N_FORMS)


def merge_nutrient_totals(*sources: Mapping[str, float]) -> dict[str, float]:
    """Sum nutrient maps (water, salt assay delivery, reagents) once per form key.

    Aggregate ``N`` keys in sources are ignored; derive total N with
    :func:`elemental_nitrogen` after merging.
    """
    merged: dict[str, float] = {}
    for source in sources:
        for symbol, raw in source.items():
            if symbol == N_AGGREGATE:
                continue
            merged[symbol] = merged.get(symbol, 0.0) + float(raw or 0.0)
    return merged


def nitrogen_form_sum(profile: Mapping[str, float]) -> float:
    """Sum of nitrogen form keys present on a profile (absent forms contribute nothing)."""
    return sum(float(profile[form]) for form in N_FORMS if form in profile)


def forms_agree_with_aggregate(profile: Mapping[str, float]) -> bool:
    """True when aggregate N is absent, forms are absent, or stated forms sum to N."""
    if N_AGGREGATE not in profile:
        return True
    if not any(form in profile for form in N_FORMS):
        return True
    return abs(nitrogen_form_sum(profile) - float(profile[N_AGGREGATE])) <= _N_CONSISTENCY_ABS


def is_water_ion_profile(label: str) -> bool:
    """Water ion maps reject bare N; targets/limits/achieved may carry aggregate N."""
    text = str(label or "")
    if text == "water" or text.endswith(".ions"):
        return True
    lowered = text.lower().replace("_", "")
    return "wateranalysis" in lowered and "ion" in lowered


def assess_nitrogen_constraints(
    totals: Mapping[str, float],
    targets: Mapping[str, float] | None = None,
    maxima: Mapping[str, float] | None = None,
    *,
    tolerance_pct: float = _DEFAULT_TOLERANCE_PCT,
) -> dict:
    """Compare form and optional aggregate elemental N constraints to achieved totals.

    Does not invent form splits. Aggregate ``N`` is judged against
    :func:`elemental_nitrogen` of ``totals``. Explicit form targets and maxima stay
    independent rows. ``withinTolerance`` is true when every listed nitrogen
    constraint is satisfied.
    """
    targets = dict(targets or {})
    maxima = dict(maxima or {})
    forms = {form: float(totals.get(form) or 0.0) for form in N_FORMS}
    achieved_n = elemental_nitrogen(totals)
    violations: list[dict] = []

    def _target_ok(final: float, target: float) -> bool:
        if target == 0:
            return final <= 0.0
        if target < 0:
            return False
        return abs((final - target) / target) * 100.0 <= tolerance_pct

    aggregate_target = targets.get(N_AGGREGATE)
    if aggregate_target is not None:
        if not _target_ok(achieved_n, float(aggregate_target)):
            delta = None
            if float(aggregate_target) > 0:
                delta = ((achieved_n - float(aggregate_target)) / float(aggregate_target)) * 100.0
            violations.append(
                {
                    "symbol": N_AGGREGATE,
                    "kind": "target",
                    "ppm": achieved_n,
                    "limitPpm": float(aggregate_target),
                    "deltaPct": delta,
                }
            )

    form_targets = {form: float(targets[form]) for form in N_FORMS if form in targets}
    for form, target in form_targets.items():
        final = forms[form]
        if not _target_ok(final, target):
            delta = None if target <= 0 else ((final - target) / target) * 100.0
            violations.append(
                {
                    "symbol": form,
                    "kind": "target",
                    "ppm": final,
                    "limitPpm": target,
                    "deltaPct": delta,
                }
            )

    if N_AGGREGATE in maxima:
        limit = float(maxima[N_AGGREGATE])
        if achieved_n > limit:
            violations.append(
                {
                    "symbol": N_AGGREGATE,
                    "kind": "maximum",
                    "ppm": achieved_n,
                    "limitPpm": limit,
                    "deltaPct": None,
                }
            )
    for form in N_FORMS:
        if form not in maxima:
            continue
        limit = float(maxima[form])
        if forms[form] > limit:
            violations.append(
                {
                    "symbol": form,
                    "kind": "maximum",
                    "ppm": forms[form],
                    "limitPpm": limit,
                    "deltaPct": None,
                }
            )

    return {
        "elementalNitrogen": achieved_n,
        "forms": forms,
        "aggregateTarget": None if aggregate_target is None else float(aggregate_target),
        "formTargets": form_targets,
        "violations": violations,
        "withinTolerance": not violations,
    }
