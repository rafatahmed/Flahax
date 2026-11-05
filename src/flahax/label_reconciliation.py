# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""A product label reconciled with its compound's charges (decision G5, option a, 2026-10-31).

A label states guaranteed minimums, not exact stoichiometry: potassium nitrate 13-0-46
(13.0 % N, 38.2 % K) carries more potassium charge than nitrate charge. Chemistry uses the
label amounts as declared, except the charge that does not balance: it is taken from the
excess side's declared ions in proportion to each ion's charge contribution and reported as
not assigned to an ion. A label that balances is used unchanged. The nutrient fit keeps the
label.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .composition import ATOMIC
from .material_chemistry import COMPLEXES, ION_TABLE, NUTRIENT_CHARGES

_N_FORMS = ('N_NO3', 'N_NH4', 'N_UREA')
_SUBSCRIPTS = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')
# Hydroxide is the proton deficit the charge balance closes (material_chemistry._IMPLICIT).
_IMPLICIT = frozenset({'OH-'})


@dataclass(frozen=True)
class LabelReconciliation:
    """``unassigned_percent``: the declared surplus (% w/w) no ion carries; ``imbalance_percent``:
    100 x net charge / total charge of the declared ions; ``basis``: how it was taken."""

    unassigned_percent: dict
    imbalance_percent: float
    basis: str


def _mean_charges(ion_forms: Mapping) -> dict:
    """Mean charge per nutrient atom over the compound's ions."""
    totals: dict = {}
    for ion, count in ion_forms.items():
        if ion in NUTRIENT_CHARGES:
            nutrient, charge = NUTRIENT_CHARGES[ion]
            weighted, atoms = totals.get(nutrient, (0.0, 0.0))
            totals[nutrient] = (weighted + charge * count, atoms + count)
    return {nutrient: weighted / atoms for nutrient, (weighted, atoms) in totals.items()}


def _unstated(ion: str, declared) -> bool:
    """A charged ion whose nutrient the label does not state: it closes the balance."""
    if ion in COMPLEXES:
        return COMPLEXES[ion][1] not in declared
    if ion in _IMPLICIT or ion not in ION_TABLE or ION_TABLE[ion][1] == 0:
        return False
    return ION_TABLE[ion][2] not in declared


def reconcile_label(identity: Mapping, elements: Mapping) -> LabelReconciliation | None:
    """The charge of a label that its compound's ions cannot balance; None for a blend.

    A blend (no formula or no theoretical analysis) has no defined compound to balance against.
    """
    if not identity.get('formula') or not identity.get('theoretical_analysis'):
        return None
    return charge_surplus(identity['ion_forms'], elements)


def charge_surplus(ion_forms: Mapping, elements: Mapping) -> LabelReconciliation:
    """The declared charge that the compound's ions (ion -> count) cannot balance.

    Each declared nutrient carries moles = % / atomic mass times its ions' mean charge per atom.
    The net charge is taken from the side in excess, from each declared ion in proportion to its
    charge contribution. A label leaving a charged ion unstated (Mn-EDTA's sodium, a carbonate)
    or stating one side only (KOH, an acid, urea) is closed by that ion: nothing is unassigned.
    The balance is exact: a net charge that is not exactly zero in floating point is reported.
    """
    # A stated zero is declared: a calcium nitrate label with N 0 leaves all its Ca unbalanced.
    declared = {key: float(value) for key, value in elements.items()}
    if any(_unstated(ion, declared) for ion in ion_forms):
        return LabelReconciliation({}, 0.0, 'an unstated ion closes the charge balance')
    charges = _mean_charges(ion_forms)
    equivalents = {
        key: charges[key] * value / ATOMIC['N' if key in _N_FORMS else key]
        for key, value in declared.items()
        if charges.get(key)
    }
    signs = {charges[key] > 0 for key in equivalents}
    if signs != {True, False}:
        return LabelReconciliation({}, 0.0, 'one side of the charge is not declared')
    net = sum(equivalents.values())
    if not net:
        return LabelReconciliation({}, 0.0, 'the declared charges balance')
    imbalance = 100.0 * net / sum(abs(eq) for eq in equivalents.values())
    excess = {key: eq for key, eq in equivalents.items() if eq * net > 0}
    # Each excess ion gives up net x (its share of the excess charge); in mass that is the
    # same fraction, net / excess charge, of its declared %.
    share = net / sum(excess.values())
    word = 'cations' if net > 0 else 'anions'
    return LabelReconciliation(
        {key: share * declared[key] for key in excess},
        imbalance,
        f"charge surplus of the label's {word}, taken in proportion to charge",
    )


def _identity(record: Mapping) -> Mapping | None:
    from .materials import load_identities  # deferred: materials imports this lazily

    grade = record.get('grade')
    identity_id = record.get('identityId') or (
        grade.get('identity_id')
        if isinstance(grade, Mapping) and grade.get('composition', 'single') == 'single'
        else None
    )
    return load_identities().get(identity_id) if identity_id else None


def chemistry_elements(record: Mapping, ion_forms: Mapping) -> dict:
    """The analysis chemistry uses: the label without the charge its ions cannot balance.

    ``ion_forms`` are the material's ions (its chemistry profile). A record whose identity is a
    blend keeps its label.
    """
    elements = dict(record['elements'])
    identity = _identity(record)
    if identity is not None and reconcile_label(identity, elements) is None:
        return elements
    unassigned = charge_surplus(ion_forms, elements).unassigned_percent
    return {key: value - unassigned.get(key, 0.0) for key, value in elements.items()}


def _formula(formula: str) -> str:
    """KNO3 -> KNO₃: counts after an element or a bracket are subscripts; '.' is '·'."""
    out, count = [], False
    for char in formula:
        count = char.isdigit() and (count or bool(out) and (out[-1].isalpha() or out[-1] == ')'))
        out.append(char.translate(_SUBSCRIPTS) if count else '·' if char == '.' else char)
    return ''.join(out)


def label_note(identity: Mapping, elements: Mapping) -> str | None:
    """The grower's note on a label; None when no surplus shows at two decimals.

    The full values stay in ``reconcile_label``.
    """
    result = reconcile_label(identity, elements)
    if result is None:
        return (
            f'{identity["name"]} has no defined compound: its label analysis is used as declared'
        )
    shown = [
        f'{value:.2f} % {key}'
        for key, value in sorted(result.unassigned_percent.items(), key=lambda kv: -kv[1])
        if round(value, 2)
    ]
    if not shown:
        return None
    return (
        f'label analysis differs from {_formula(identity["formula"])}: '
        f'{", ".join(shown)} not assigned to an ion'
    )
