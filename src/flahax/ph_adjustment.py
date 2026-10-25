# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""pH adjustment planned together with the recipe (#74, #75, #76, #77).

A reagent that corrects pH also supplies nutrients: nitric acid adds nitrate-N,
phosphoric acid P, sulfuric acid S, potassium hydroxide and carbonates K. Planned
one after the other, the recipe already meets every target and the reagent then
overshoots it, so no plan is acceptable (#74). Here the reagent's nutrients are
counted as supply, like the water's, and the recipe is fitted again until the
dose and the recipe agree. Acids are pH reagents in this mode and are not offered
to the nutrient fit as salts (#76), and a recipe that misses a target is still
given a pH plan (#77). The dose itself is the same equilibrium solve for acids and
bases: the reagent's anion (acid) or cation (base) is added at the target pH until
the solution is electrically neutral again.
"""

from dataclasses import dataclass
import math
from collections.abc import Callable, Mapping, Sequence

from .aqueous_model import AqueousResult, solve
from .composition import ATOMIC
from .delivery_contracts import DeliveryError
from .engine import PH_REAGENT, TOLERANCE_PCT, load_library, recommend, score
from .nutrient_acceptance import assess_incidental, assessed_limits
from .root_finding import shrink_bracket
from .product_conversion import component_nutrient_masses
from .saturation_policy import assess_saturation, describe

_K, _C, _O, _H = ATOMIC['K'], ATOMIC['C'], ATOMIC['O'], ATOMIC['H']

# formula -> (direction, basis moles added per mole of reagent, g/mol, nutrient g per mole of
# reagent)
REAGENTS = {
    'HNO3': ('acid', {'NO3-': 1}, 63.01284, {'N_NO3': 14.0067}),
    'H3PO4': ('acid', {'PO4-3': 1}, 97.995182, {'P': 30.973762}),
    'H2SO4': ('acid', {'SO4-2': 1}, 98.07848, {'S': 32.06}),
    'C6H8O7': ('acid', {'Citrate-3': 1}, 192.12352, {}),
    'KOH': ('base', {'K+': 1}, _K + _O + _H, {'K': _K}),
    'KHCO3': ('base', {'K+': 1, 'CO3-2': 1}, _K + _H + _C + 3 * _O, {'K': _K}),
    'K2CO3': ('base', {'K+': 2, 'CO3-2': 1}, 2 * _K + _C + 3 * _O, {'K': 2 * _K}),
}
# Change in pH below which no reagent is planned.
PH_TOLERANCE = 1e-3
# The recipe and its reagent dose agree when they differ by less than this fraction.
DOSE_TOLERANCE = 1e-4


def reagent_dose(totals, initial_ph, target_ph, formula, *, phases=(), initial=None):
    """Moles of reagent per kg water that bring an electroneutral solution to target_ph.

    Returns (dose_molal, state at target_ph). The reagent is neutral, so the
    solution's residual charge at the new pH must equal its residual at the initial
    pH; the dose adds the reagent's conserved ions (an acid's anion, a base's K+ and
    carbonate) with its protons or hydroxide implicit.
    """
    if formula not in REAGENTS:
        raise DeliveryError('unsupported_reagent', 'supported identities: ' + ', '.join(REAGENTS))
    direction, adds, _, _ = REAGENTS[formula]
    initial = initial or solve(totals, initial_ph, phases=phases)
    if target_ph == initial_ph:
        return 0.0, initial
    if (target_ph > initial_ph) != (direction == 'base'):
        needed = 'base' if target_ph > initial_ph else 'acid'
        raise DeliveryError('wrong_reagent_direction', f'target requires {needed}, not {formula}')
    # An acid's added anion lowers the residual charge at the target pH; a base's cation raises it.
    sign = 1.0 if direction == 'acid' else -1.0
    last = [initial]

    def at(dose):
        amended = dict(totals)
        for basis, n in adds.items():
            amended[basis] = amended.get(basis, 0) + n * dose
        last[0] = solve(amended, target_ph, phases=phases, start=last[0])  # warm start, #61
        return last[0]

    def gap(dose):
        return sign * (at(dose).charge_balance - initial.charge_balance)

    target = at(0.0)
    g_low = sign * (target.charge_balance - initial.charge_balance)
    if g_low < -1e-12:
        raise DeliveryError(
            'wrong_reagent_direction',
            f'target requires the opposite reagent to {formula} ' 'under this phase policy',
        )
    low, high = 0.0, 1e-6
    for _ in range(32):
        g_high = gap(high)
        if g_high <= 0:
            break
        low, g_low = high, g_high
        high *= 2
    else:
        raise DeliveryError('nonconvergent', 'reagent demand could not be bracketed')
    # Same final width as 40 bisection steps from [0, high].
    low, high = shrink_bracket(gap, low, g_low, high, g_high, width=high * 2.0**-40)
    dose = (low + high) / 2
    return dose, at(dose)


@dataclass(frozen=True)
class PhCandidate:
    """One pH reagent tried in one direction: its dose, reagent amount, nutrient contribution and
    solved solutions, or why it was not usable.
    """

    product_id: str
    formula: str
    direction: str
    status: str
    dose_molal: float | None = None
    reagent_mass_g: float | None = None
    reagent_volume_litres: float | None = None
    nutrient_contribution: dict | None = None
    recommendation: dict | None = None
    mixed: AqueousResult | None = None
    target: AqueousResult | None = None
    iterations: int = 0
    loss: float | None = None
    error_code: str | None = None
    message: str | None = None
    product_record: dict | None = None
    saturation: dict | None = None


@dataclass(frozen=True)
class PhAdjustmentPlan:
    """Every pH reagent tried and the selected one; the pH must still be measured after mixing."""

    target_ph: float
    unadjusted_ph: float
    direction: str
    candidates: tuple
    selected_product_id: str | None
    selection_policy: str
    unadjusted_recommendation: dict | None = None
    post_mix_measurement_required: bool = True

    @property
    def selected(self):
        """The selected candidate, or None."""
        return next((c for c in self.candidates if c.product_id == self.selected_product_id), None)


def _positive(value, name):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise DeliveryError('invalid_value', f'{name} must be finite and positive')
    return float(value)


def _check_product(product):
    if not isinstance(product, Mapping):
        raise DeliveryError('invalid_type', 'reagent products must be mappings')
    for key in ('id', 'source', 'revision', 'recordedAt'):
        if not isinstance(product.get(key), str) or not product[key].strip():
            raise DeliveryError('missing_field', f'reagent product {key} is required')
    if product.get('chemicalFormula') not in REAGENTS:
        raise DeliveryError('unsupported_reagent', 'supported identities: ' + ', '.join(REAGENTS))
    fraction = _positive(product.get('massFraction'), 'massFraction')
    if fraction > 1:
        raise DeliveryError('inconsistent_assay', 'massFraction cannot exceed one')
    density = product.get('densityKgPerL')
    if density is not None:
        density = _positive(density, 'densityKgPerL')
    return fraction, density


def nutrient_salts(salts):
    """Products the coupled plan offers to the nutrient fit: no pH reagents and no acids (#76)."""
    acids = {formula for formula, (direction, *_rest) in REAGENTS.items() if direction == 'acid'}
    return [
        s
        for s in salts
        if s.get('role') != PH_REAGENT and str(s.get('formula') or '') not in acids
    ]


def plan_coupled_ph(
    salts,
    targets,
    water,
    target_ph,
    *,
    products,
    mix: Callable[[dict], AqueousResult],
    water_mass_kg,
    final_volume_litres,
    maximum_reagent_volume_litres,
    preferred_product_id=None,
    phases=(),
    maximum_concentrations=None,
):
    """Fit the recipe and its pH reagent together; one candidate per offered product.

    mix(recommendation) returns the mixed state (water and products, before any
    reagent) at its calculated pH. Candidates whose direction does not fit the feed
    are reported as not applicable. A candidate's dose is reported even when it is
    rejected, so the reason and the amount are both visible.
    """
    mass = _positive(water_mass_kg, 'water_mass_kg')
    volume = _positive(final_volume_litres, 'final_volume_litres')
    cap = _positive(maximum_reagent_volume_litres, 'maximum_reagent_volume_litres')
    if not isinstance(products, (list, tuple)) or not products:
        raise DeliveryError('missing_field', 'sourced pH reagent product records are required')
    identifiers = [p.get('id') if isinstance(p, Mapping) else None for p in products]
    if any(not isinstance(i, str) or not i.strip() for i in identifiers) or len(
        set(identifiers)
    ) != len(identifiers):
        raise DeliveryError('invalid_value', 'reagent product IDs must be unique nonempty strings')
    if preferred_product_id is not None and preferred_product_id not in identifiers:
        raise DeliveryError(
            'unknown_product', 'requested reagent product is not in the supplied list'
        )
    if isinstance(phases, (str, bytes)) or not isinstance(phases, Sequence):
        raise DeliveryError('invalid_type', 'phases must be an explicit sequence')
    phases = tuple(phases)
    pool = nutrient_salts(salts)
    unadjusted = recommend(pool, targets, water, maximum_concentrations=maximum_concentrations)
    base_state = mix(unadjusted)
    if abs(base_state.ph - target_ph) <= PH_TOLERANCE:
        direction = 'none'
    else:
        direction = 'base' if target_ph > base_state.ph else 'acid'
    candidates = []
    for product in products:
        identity, formula = product.get('id'), product.get('chemicalFormula')
        try:
            fraction, density = _check_product(product)
            reagent_direction, components, molar_mass, _ = REAGENTS[formula]
            nutrients = component_nutrient_masses(components)
            if direction == 'none':
                # No reagent, but the same final acceptance as every dosed candidate (#84).
                status, code, message, saturation = _judge(
                    unadjusted, base_state, maximum_concentrations, accepted='not_needed'
                )
                candidates.append(
                    PhCandidate(
                        identity,
                        formula,
                        reagent_direction,
                        status,
                        0.0,
                        0.0,
                        0.0 if density else None,
                        {},
                        unadjusted,
                        base_state,
                        base_state,
                        loss=_loss(unadjusted),
                        error_code=code,
                        message=message,
                        product_record=dict(product),
                        saturation=saturation,
                    )
                )
                continue
            if reagent_direction != direction:
                candidates.append(
                    PhCandidate(
                        identity,
                        formula,
                        reagent_direction,
                        'not_applicable',
                        error_code='wrong_reagent_direction',
                        message=f'the feed mixes at pH {base_state.ph:.2f} and must be '
                        f'{"raised" if direction == "base" else "lowered"} to {target_ph:g}',
                        product_record=dict(product),
                    )
                )
                continue
            candidates.append(
                _couple(
                    pool,
                    targets,
                    water,
                    target_ph,
                    product,
                    fraction,
                    density,
                    molar_mass,
                    nutrients,
                    mix,
                    mass,
                    volume,
                    cap,
                    phases,
                    maximum_concentrations,
                )
            )
        except DeliveryError as exc:
            candidates.append(
                PhCandidate(
                    identity,
                    formula,
                    REAGENTS.get(formula, ('unknown',))[0],
                    'rejected',
                    error_code=exc.code,
                    message=str(exc),
                    product_record=dict(product) if isinstance(product, Mapping) else None,
                )
            )
    # Accepted plans first; a plan with review-only findings (#78) is usable after review.
    usable = [
        c
        for c in candidates
        if c.status in ('accepted', 'not_needed', 'requires_review')
        and (preferred_product_id is None or c.product_id == preferred_product_id)
    ]
    selected = (
        min(
            usable,
            key=lambda c: (c.status == 'requires_review', c.loss, identifiers.index(c.product_id)),
        ).product_id
        if usable
        else None
    )
    policy = (
        'explicit user choice; no fallback'
        if preferred_product_id is not None
        else 'lowest final nutrient loss; input order breaks ties'
    )
    return PhAdjustmentPlan(
        float(target_ph), base_state.ph, direction, tuple(candidates), selected, policy, unadjusted
    )


def _loss(recommendation):
    return sum(
        (row['deltaPct'] / 100) ** 2
        for row in recommendation['rows']
        if row['deltaPct'] is not None
    )


def _judge(recommendation, target, maximum_concentrations, over_dose=False, accepted='accepted'):
    """Final acceptance of one candidate: dose, hard limits, then saturation; review never
    outranks a rejection."""
    incidental = assess_incidental(
        recommendation['rows'], assessed_limits(maximum_concentrations, recommendation)
    )
    saturation = assess_saturation(target)
    if over_dose:
        return (
            'rejected',
            'dose_limit_exceeded',
            'dose exceeds the reagent volume limit or solvent inventory',
            saturation,
        )
    if incidental['limitViolations']:
        return (
            'rejected',
            'nutrient_limit_exceeded',
            'the plan exceeds an explicit nutrient maximum',
            saturation,
        )
    if saturation['blocks']:
        return (
            'rejected',
            'precipitation_risk',
            'precipitation risk at the target pH: ' + '; '.join(describe(saturation)),
            saturation,
        )
    if incidental['requiresReview'] or saturation['review'] or saturation['advisories']:
        findings = describe(saturation) + saturation['advisories']
        return (
            'requires_review',
            None,
            '; '.join(findings) if findings else 'incidental nutrient contributions need review',
            saturation,
        )
    return accepted, None, None, saturation


def _couple(
    pool,
    targets,
    water,
    target_ph,
    product,
    fraction,
    density,
    molar_mass,
    nutrients,
    mix,
    mass,
    volume,
    cap,
    phases,
    maximum_concentrations,
):
    """Find the reagent dose the recipe fitted for that dose's nutrients actually needs.

    F(d) is the dose required by the recipe fitted with supply water + reagent(d).
    A few fixed-point steps settle most feeds; otherwise the root of F(d) - d is
    bracketed (the fixed-point step can oscillate, and the recipe can switch
    products between nearby doses). Where a switch leaves no exact root, the plan
    takes the nearer side and rescores the nutrients at the dose that recipe needs.
    """
    formula, identity = product['chemicalFormula'], product['id']
    cache = {}

    def contribution(dose):
        return {ion: dose * mass * grams * 1000 / volume for ion, grams in nutrients.items()}

    def evaluate(assumed):
        if assumed not in cache:
            supply = dict(water)
            for ion, mg in contribution(assumed).items():
                supply[ion] = supply.get(ion, 0.0) + mg
            recommendation = recommend(
                pool, targets, supply, maximum_concentrations=maximum_concentrations
            )
            mixed = mix(recommendation)
            dose, target = reagent_dose(
                mixed.totals, mixed.ph, target_ph, formula, phases=phases, initial=mixed
            )
            cache[assumed] = (dose, recommendation, mixed, target)
        return cache[assumed]

    def gap(assumed):
        return evaluate(assumed)[0] - assumed

    def settled(assumed):
        dose = evaluate(assumed)[0]
        return abs(dose - assumed) <= DOSE_TOLERANCE * max(dose, 1e-12)

    assumed = 0.0
    for _ in range(4):
        if settled(assumed):
            break
        assumed = evaluate(assumed)[0]
    if not settled(assumed):
        below = [x for x in cache if gap(x) > 0]
        above = [x for x in cache if gap(x) < 0]
        high = min(above) if above else max(cache) * 2 or 1e-6
        for _ in range(30):
            if gap(high) < 0:
                break
            high *= 2
        else:
            raise DeliveryError(
                'nonconvergent', f'{formula} dose could not be bracketed against the recipe'
            )
        low = max([x for x in below if x < high], default=0.0)
        shrink_bracket(
            gap,
            low,
            gap(low),
            high,
            gap(high),
            relative=DOSE_TOLERANCE,
            accept=lambda x, g_x, lo, hi: settled(x),
            max_steps=60,
        )
        assumed = min(cache, key=lambda x: abs(gap(x)) / max(evaluate(x)[0], 1e-12))
    dose, recommendation, mixed, target = evaluate(assumed)
    if not settled(assumed):
        # The recipe switches products between nearby doses: rescore it at the dose it needs.
        achieved = {row['symbol']: row['final'] for row in recommendation['rows']}
        for ion, mg in contribution(dose).items():
            achieved[ion] = achieved.get(ion, 0.0) + mg - contribution(assumed).get(ion, 0.0)
        loss, rows = score(achieved, targets)
        recommendation = dict(
            recommendation,
            rows=rows,
            loss=loss,
            feasible=all(
                abs(r['deltaPct']) <= TOLERANCE_PCT for r in rows if r['deltaPct'] is not None
            )
            and not recommendation.get('limitViolations'),
        )
    grams = dose * mass * molar_mass / fraction
    litres = grams / (1000 * density) if density else None
    over_dose = (litres is not None and (litres > cap or litres > volume)) or grams * (
        1 - fraction
    ) > mass * 1000
    status, code, message, saturation = _judge(
        recommendation, target, maximum_concentrations, over_dose
    )
    return PhCandidate(
        identity,
        formula,
        REAGENTS[formula][0],
        status,
        dose,
        grams,
        litres,
        contribution(dose),
        recommendation,
        mixed,
        target,
        len(cache),
        _loss(recommendation),
        code,
        message,
        dict(product),
        saturation,
    )


def catalogue_ph_reagents():
    """Reagent records for the catalogue's sourced pH-up products (#75), ready for plan_coupled_ph.

    Acids are not in the catalogue as reagent grades: supply your own nitric or
    phosphoric acid record (assay and density from the supplier certificate).
    """
    records = []
    for salt in load_library()['salts']:
        if salt.get('role') != PH_REAGENT:
            continue
        source = salt.get('source') or {}
        records.append(
            {
                'id': salt['id'],
                'name': salt['name'],
                'chemicalFormula': salt['formula'],
                'massFraction': salt.get('massFraction', 1.0),
                'densityKgPerL': salt.get('densityKgPerL'),
                'source': source.get('title') or 'FlahaX catalogue',
                'revision': salt['analysisBasis'],
                'recordedAt': source.get('entered') or 'catalogue',
            }
        )
    return records
