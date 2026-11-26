# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""The nitrogen rules in one place: the three forms, the total-N target and its
fitted rows, the optional ammonium allowance and the total-N report (decisions
D1 and D2, ADR 0001)."""

import math

from .composition import InputError, validate_targets


NITROGEN_FORMS = ("N_NO3", "N_NH4", "N_UREA")


# A declared total and the sum of its forms agree within this relative
# amount (decimal input such as 150 against 100 + 30 + 20).
TOTAL_NITROGEN_TOLERANCE = 1e-6


def nitrogen_rows(targets) -> dict:
    """The nitrogen requirements fitted for a formula (decisions D1 and
    D2, gates G23 and G24).

    Each form is its own requirement on the elemental-N basis: N_NO3 as
    declared, N_UREA as declared or 0 when absent (a declared zero, with
    no allowance), and N_NH4 only when it is declared above 0. An absent
    or zero N_NH4 is no ammonium requirement at all: no row and no ban.
    A formula that declares no nitrogen form has no nitrogen rows.

    Total N ("N", elemental mg/L) is a target too. Alone it is one row
    over the sum of the three forms and imposes no form split; the urea
    safeguard still holds, so urea products stay out unless urea is
    declared. Total N is nitrate + ammonium + urea, and urea that is not
    asked for is a zero requirement, not an unknown. So a declared
    nitrate and a positive ammonium determine the total (urea is
    declared or zero): the forms are scored once and the declared total
    must agree with their sum. An explicit zero N_NH4 asks for nothing
    (decision G24), so it does not determine the total. When the forms
    leave the total open, both are scored (the overlap is reported by
    total_n_report) and no other form target is invented. A total below
    the declared forms, or a total that disagrees with forms that
    determine it, raises InputError before any fitting.
    """
    total = targets.get("N")
    if total is None and not any(form in targets for form in NITROGEN_FORMS):
        return {}
    determined = "N_NO3" in targets and targets.get("N_NH4", 0) > 0
    if total is not None:
        declared = total_nitrogen(targets)
        slack = TOTAL_NITROGEN_TOLERANCE * max(abs(total), 1.0)
        if determined and abs(total - declared) > slack:
            raise InputError(
                f"targets declare total N {total:g} mg/L but N_NO3 + N_NH4 + N_UREA = "
                f"{declared:g} mg/L; declare either the total or consistent forms"
            )
        if declared - total > slack:
            raise InputError(
                f"targets declare nitrogen forms summing to {declared:g} mg/L, which "
                f"exceed the declared total N of {total:g} mg/L"
            )
    rows = {}
    if total is not None and not determined and total > 0:
        rows["N"] = total
    if "N_NO3" in targets:
        rows["N_NO3"] = targets["N_NO3"]
    if targets.get("N_NH4", 0) > 0:
        rows["N_NH4"] = targets["N_NH4"]
    rows["N_UREA"] = targets.get("N_UREA", 0)
    if total == 0 and "N_NO3" not in targets:
        rows["N_NO3"] = 0  # a declared zero total admits no nitrate product either
    return rows


def fitted_targets(targets) -> dict:
    """The targets as fitted: other nutrients unchanged, nitrogen as
    ``nitrogen_rows``.

    A zero N_NH4 is dropped (no requirement, no ban) and an absent
    N_UREA becomes a declared zero whenever any nitrogen form is
    declared.
    """
    nitrogen = nitrogen_rows(targets)
    fitted = {
        s: v for s, v in targets.items() if (s not in NITROGEN_FORMS and s != "N") or s in nitrogen
    }
    fitted.update(nitrogen)
    return fitted


def total_nitrogen(profile) -> float:
    """Elemental N summed over the three forms (N_NO3 + N_NH4 + N_UREA),
    in the profile's units.
    """
    return math.fsum(float(profile.get(form) or 0.0) for form in NITROGEN_FORMS)


def target_total_nitrogen(targets) -> float:
    """Total N a formula asks for: the declared total when the targets
    carry one, otherwise the sum of the declared forms.
    """
    if targets.get("N") is not None:
        return float(targets["N"])
    return total_nitrogen(targets)


# Ammonium allowance (G23): when a formula declares no NH4-N requirement
# (absent or 0), incidental NH4-N may reach min(10% of total target N,
# 1.5 mmol/L NH4 = 21.01 mg/L N). Dutch soilless practice: NH4 at 5-15%
# of total N with at most 1-1.5 mmol/L (Van der Lugt et al. 2016
# handbook, after De Kreij, Voogt et al.).
AMMONIUM_FRACTION = 0.10


AMMONIUM_CAP_MG_PER_L = 1.5 * 14.0067


AMMONIUM_BASIS = "Dutch soilless practice (De Kreij, Voogt et al.)"


def ammonium_allowance(targets: dict, maxima: dict, fraction: float | None) -> dict | None:
    """The ammonium allowance (G23) for fitted targets, added to maxima
    as N_NH4.

    It applies when the targets have no NH4-N requirement and no N_NH4
    maximum is stated: min(fraction x total target N,
    AMMONIUM_CAP_MG_PER_L). None adds no maximum.
    """
    if fraction is None:
        return None
    if (
        isinstance(fraction, bool)
        or not isinstance(fraction, (int, float))
        or not 0 <= fraction <= 1
    ):
        raise InputError("max_ammonium_fraction must be a number in [0, 1]")
    total_n = target_total_nitrogen(targets)
    # A positive N_NH4 target keeps its own row; absent or 0 gets the
    # allowance (G23).
    if total_n <= 0 or "N_NH4" in targets or "N_NH4" in maxima:
        return None
    limit = min(fraction * total_n, AMMONIUM_CAP_MG_PER_L)
    maxima["N_NH4"] = limit
    return {
        "mgPerL": limit,
        "fractionOfTotalN": fraction,
        "absoluteCapMgPerL": AMMONIUM_CAP_MG_PER_L,
        "basis": AMMONIUM_BASIS,
    }


def ammonium_allowance_preset(targets: dict, fraction: float = AMMONIUM_FRACTION) -> dict | None:
    """The optional ammonium allowance preset for ``targets``, as a
    disclosed record, without applying it.

    Returns the same record ``ammoniumLimit`` carries (mgPerL,
    fractionOfTotalN, absoluteCapMgPerL, basis), or None when the
    targets already state NH4-N or have no nitrogen. To apply it, pass
    ``max_ammonium_fraction=fraction`` to ``recommend`` or declare
    ``maximum_concentrations={'N_NH4': record['mgPerL']}``.
    """
    return ammonium_allowance(
        fitted_targets(validate_targets(dict(targets), "targets")), {}, fraction
    )


def total_n_report(rows: list[dict], targets: dict) -> dict:
    """Total N as the sum of the three forms in the final rows (water,
    products and any reagent), against the declared total or the sum of
    the declared forms (D1, D2). The target is None when neither a form
    nor a total is declared. fitted is True when the total is its own
    row; overlapForms then lists the forms scored beside it (the urea
    safeguard's zero is not an overlap).
    """
    declared = "N" in targets or any(form in targets for form in NITROGEN_FORMS)
    target = target_total_nitrogen(targets) if declared else None
    final = total_nitrogen({row["symbol"]: row["final"] for row in rows})
    fitted = "N" in targets
    return {
        "target": target,
        "final": final,
        "deltaPct": 100.0 * (final - target) / target if target else None,
        "unit": "mg/L as N",
        "forms": list(NITROGEN_FORMS),
        "fitted": fitted,
        "overlapForms": [
            form
            for form in NITROGEN_FORMS
            if fitted and form in targets and (form != "N_UREA" or targets[form] > 0)
        ],
    }
