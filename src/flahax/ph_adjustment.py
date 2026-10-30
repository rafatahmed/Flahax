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
from .composition import ATOMIC, fitted_targets
from .delivery_contracts import DeliveryError
from .engine import (
    PH_REAGENT,
    load_library,
    recommend,
    score,
    forward,
    _report,
    _diagnose,
    _charge_report,
    total_n_report,
)
from .nutrient_acceptance import assess_incidental, assessed_limits, name_sources
from .requirement_fit import PH_TOLERANCE, met  # a pH within 1e-4 is met (G25)
from .root_finding import shrink_bracket
from .product_conversion import component_nutrient_masses, material_inventory
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
    joint_result: dict | None = None


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
    unadjusted_state: object | None = None

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
    joint=None,
    water_components=None,
):
    """Fit the recipe and its pH reagent together; one candidate per offered product.

    mix(recommendation) returns the mixed state (water and products, before any
    reagent) at its calculated pH. Explicit joint configuration supplies controls,
    final solvent mass, reagent solvent fractions and mass caps; optional starting
    points are checked as search seeds. water_components supplies the declared
    final-basis water inventory. Joint mode evaluates every offered reagent and
    independently calculates final pH. Legacy mode retains directional fitting,
    with bounded zero-reagent recovery when no matching direction is offered.
    A candidate's quantities and unresolved numerical status remain inspectable.
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
    # Every refit uses the nitrogen rows recommend fitted (D1, G24); the joint search holds the
    # ammonium allowance recommend applied as a declared maximum (G23).
    targets = fitted_targets(targets)
    joint_maxima = assessed_limits(maximum_concentrations, unadjusted)
    base_state = mix(unadjusted)
    if abs(base_state.ph - target_ph) <= PH_TOLERANCE:
        direction = 'none'
    else:
        direction = 'base' if target_ph > base_state.ph else 'acid'
    candidates = []
    for product in products:
        identity, formula = product.get('id'), product.get('chemicalFormula')
        zero_failure = None
        try:
            fraction, density = _check_product(product)
            reagent_direction, components, molar_mass, _ = REAGENTS[formula]
            nutrients = component_nutrient_masses(components)
            if joint is not None:
                from .joint_workflow import joint_candidate

                candidates.append(
                    joint_candidate(
                        pool,
                        targets,
                        water,
                        target_ph,
                        product,
                        unadjusted,
                        mix,
                        mass,
                        volume,
                        cap,
                        phases,
                        joint_maxima,
                        water_components,
                        joint,
                    )
                )
                continue
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
                if (
                    water_components is not None
                    and not phases
                    and not any(
                        REAGENTS.get(p.get('chemicalFormula'), ('unknown',))[0] == direction
                        for p in products
                    )
                ):
                    from .joint_workflow import joint_candidate

                    try:
                        candidates.append(
                            joint_candidate(
                                pool,
                                targets,
                                water,
                                target_ph,
                                product,
                                unadjusted,
                                mix,
                                mass,
                                volume,
                                cap,
                                phases,
                                joint_maxima,
                                water_components,
                            )
                        )
                    except DeliveryError as exc:
                        if exc.code not in (
                            'joint_search_incomplete',
                            'joint_verification_failed',
                        ):
                            raise
                        zero_failure = dict(
                            status='search_incomplete',
                            accepted=False,
                            globalOptimalityProven=False,
                            reason=str(exc),
                        )
                    else:
                        continue
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
                        joint_result=zero_failure,
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
                    joint_result=(
                        dict(
                            status='search_incomplete',
                            accepted=False,
                            globalOptimalityProven=False,
                            reason=str(exc),
                        )
                        if joint is not None
                        else None
                    ),
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
        float(target_ph),
        base_state.ph,
        direction,
        tuple(candidates),
        selected,
        policy,
        unadjusted,
        unadjusted_state=base_state,
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


def _blend_recipe(pool, targets, supply, endpoints, weight, maxima):
    """Conserve product doses and rebuild assessments for a convex recipe blend.

    Incidental nutrients are assessed against the same limits as the endpoint recipes,
    including the ammonium allowance they report (G23), and total N is recomputed from the
    rebuilt rows (water, products and the reagent's supply).
    """
    maxima = assessed_limits(maxima, endpoints[0])
    by_id = {p['id']: p for p in pool}
    entries = {s['id']: s for r in endpoints for s in r['salts']}
    doses = {}
    for recipe, factor in zip(endpoints, (1 - weight, weight)):
        for salt in recipe['salts']:
            doses[salt['id']] = doses.get(salt['id'], 0.0) + factor * salt['gramsPerLitre']
    salts = [dict(entries[key], gramsPerLitre=g) for key, g in doses.items() if g > 0]
    grams = [doses.get(p['id'], 0.0) for p in pool]
    loss, rows = score(forward(pool, grams, supply), targets)
    result = dict(
        endpoints[0],
        salts=salts,
        saltIds=[s['id'] for s in salts],
        grams=grams,
        rows=rows,
        loss=loss,
    )
    warnings = [
        w for w in result['warnings'] if not w.startswith('Fit includes formula counterion')
    ]
    result.update(_report(rows, grams, warnings, maxima))
    result['totalN'] = total_n_report(rows, targets)
    name_sources(result, salts, pool, supply)
    result['unmetTargets'] = _diagnose(
        pool,
        targets,
        supply,
        rows,
        maxima,
        frozenset(s for s, v in maxima.items() if v > 0),
        False,
    )
    result['materialInventory'] = [
        dict(
            recordId=s['id'],
            name=s['name'],
            gramsPerLitre=s['gramsPerLitre'],
            **material_inventory(by_id[s['id']]),
        )
        for s in salts
    ]
    _charge_report(result)
    selected = {s['id'] for s in salts}
    result['excluded'] = [e for e in result['excluded'] if e.get('id') not in selected]
    result['requirementConflicts'] = [
        dict(symbol=s, reason='target_above_maximum', targetPpm=t, maximumPpm=maxima[s])
        for s, t in targets.items()
        if s in maxima and t > maxima[s]
    ] + [
        dict(symbol=s, reason='water_above_maximum', waterPpm=supply[s], maximumPpm=limit)
        for s, limit in (maxima | {s: 0 for s, t in targets.items() if t == 0}).items()
        if (not met(0.0, supply.get(s, 0)) if targets.get(s) == 0 else supply.get(s, 0) > limit)
    ]
    if result['requirementConflicts']:
        result['feasible'] = False
    if 'substitutionSearch' in result:
        result['substitutionSearch'] = dict(
            result['substitutionSearch'],
            status='candidate_found' if result['feasible'] else 'search_incomplete',
            method='convex blend of searched endpoint recipes; no global search certificate',
            attemptedProductIds=[
                [salt['id'] for salt in endpoint['salts']] for endpoint in endpoints
            ],
        )
    return result


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
    products between nearby doses). A direction-crossing trial bounds the search
    but cannot be returned as a plan. At a product switch, blend the bracketing
    product doses and solve charge balance on the actual mixture. This preserves
    nonnegative mass accounting; it is not a global joint-optimality certificate.
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
            try:
                dose, target = reagent_dose(
                    mixed.totals, mixed.ph, target_ph, formula, phases=phases, initial=mixed
                )
            except DeliveryError as exc:
                if exc.code != 'wrong_reagent_direction' or assumed == 0:
                    raise
                # This trial bounds the search but cannot be emitted as a plan.
                dose, target = 0.0, None
            cache[assumed] = (dose, recommendation, mixed, target)
        return cache[assumed]

    def gap(assumed):
        return evaluate(assumed)[0] - assumed

    def settled(assumed):
        dose, _, _, target = evaluate(assumed)
        return target is not None and abs(dose - assumed) <= DOSE_TOLERANCE * max(dose, 1e-12)

    assumed = 0.0
    for _ in range(4):
        if settled(assumed) or evaluate(assumed)[3] is None:
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
        low, high = shrink_bracket(
            gap,
            low,
            gap(low),
            high,
            gap(high),
            relative=DOSE_TOLERANCE,
            accept=lambda x, g_x, lo, hi: settled(x),
            max_steps=60,
        )
        assumed = min(
            (x for x in cache if evaluate(x)[3] is not None),
            key=lambda x: abs(gap(x)) / max(evaluate(x)[0], 1e-12),
        )
    dose, recommendation, mixed, target = evaluate(assumed)
    if not settled(assumed):
        # A product switch makes the optimizer's selection discontinuous. Blend
        # the two bracketing recipes, not their pH values: mass contributions are
        # affine, but chemistry must be solved on each trial mixture.
        ends = [evaluate(x)[1] for x in (low, high)]
        blended = {}

        def at(weight):
            if weight not in blended:
                assumed_dose = low * (1 - weight) + high * weight
                supply = dict(water)
                for ion, mg in contribution(assumed_dose).items():
                    supply[ion] = supply.get(ion, 0.0) + mg
                recipe = _blend_recipe(pool, targets, supply, ends, weight, maximum_concentrations)
                state = mix(recipe)
                amended = dict(state.totals)
                for basis, n in REAGENTS[formula][1].items():
                    amended[basis] = amended.get(basis, 0.0) + n * assumed_dose
                target_state = solve(amended, target_ph, phases=phases, start=state)
                blended[weight] = (assumed_dose, recipe, state, target_state)
            return blended[weight]

        def charge_gap(weight):
            _, _, state, target_state = at(weight)
            return target_state.charge_balance - state.charge_balance

        g_left, g_right = charge_gap(0.0), charge_gap(1.0)
        if g_left != 0 and g_right != 0 and (g_left > 0) == (g_right > 0):
            raise DeliveryError('nonconvergent', 'recipe blend does not bracket charge balance')
        left, right = shrink_bracket(charge_gap, 0.0, g_left, 1.0, g_right, width=2.0**-40)
        assumed_dose, recommendation, mixed, _ = at((left + right) / 2)
        dose, target = reagent_dose(
            mixed.totals, mixed.ph, target_ph, formula, phases=phases, initial=mixed
        )
        if abs(dose - assumed_dose) > DOSE_TOLERANCE * max(dose, 1e-12):
            raise DeliveryError('nonconvergent', 'blended recipe and reagent dose disagree')
        # Recompute every assessment at the actual dose, including diagnostic rows.
        supply = dict(water)
        for ion, mg in contribution(dose).items():
            supply[ion] = supply.get(ion, 0.0) + mg
        recommendation = _blend_recipe(
            pool, targets, supply, [recommendation] * 2, 0.0, maximum_concentrations
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
    """Reagent records for the catalogue's sourced pH products (#75), ready for plan_coupled_ph.

    The packaged catalogue lists potassium hydroxide, bicarbonate and carbonate to raise
    the pH and phosphoric and nitric acid to lower it. A record you supply from your own
    supplier certificate (assay and density) is evaluated beside them.
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


def make_joint_problem(salts, reagent, targets, water, *, reagent_solvent_fraction, **conditions):
    """Compile a fixed-target contract from supplied nutrient and reagent records.

    conditions supplies the explicit water components, final solvent mass/volume,
    target pH, reference charge and reagent mass cap required by JointProblem.
    Reagent solvent fraction is declared separately; assay remainder is not water.
    This compiler does not run the sequential or joint optimizer. Fertilizer carrier
    or hydrate solvent is not inferred; use explicit JointSource records when needed.
    """
    from .joint_problem import JointSource, JointProblem, _number

    reagent_solvent_fraction = _number(reagent_solvent_fraction, "reagent solvent fraction")
    if len(nutrient_salts(salts)) != len(salts):
        raise DeliveryError('invalid_role', 'pH reagents cannot also be fertilizer variables')
    fraction, density = _check_product(reagent)
    _, components, molar_mass, nutrients = REAGENTS[reagent['chemicalFormula']]
    if reagent_solvent_fraction + fraction > 1:
        raise DeliveryError('inconsistent_assay', 'active and solvent fractions exceed one')
    sources = []
    for salt in salts:
        inventory = material_inventory(salt)
        sources.append(
            JointSource(
                salt['id'],
                {k: v / 100 for k, v in inventory['nutrient_percent'].items()},
                inventory['components_moles_per_gram'],
            )
        )
    active = JointSource(
        reagent['id'],
        {k: fraction * g / molar_mass for k, g in nutrients.items()},
        {k: fraction * n / molar_mass for k, n in components.items()},
        solvent_fraction=reagent_solvent_fraction,
        density_kg_per_litre=density,
    )
    if isinstance(targets, Mapping):
        targets = fitted_targets(targets)  # nitrogen rows as recommend fits them (D1, G24)
    return JointProblem(tuple(sources), active, targets, water, **conditions)
