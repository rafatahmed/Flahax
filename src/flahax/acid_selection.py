"""Evaluate user-supplied acid products against the same mixed equilibrium model.

No fertilizer target is interpreted as a water-quality measurement. Acid product
purity, density and provenance are explicit; formulations are never silently
relaxed to accommodate nutrient-bearing acid additions.
"""
from dataclasses import dataclass
import math
from collections.abc import Mapping, Sequence

from .aqueous_model import solve, chemistry
from .delivery_contracts import DeliveryError
from .delivery_quantities import rescore_with_reagent, MilligramsPerLitre
from .nutrient_acceptance import assess_incidental

# Pure, anhydrous acid identities; commercial aqueous products supply their own
# mass fraction/density. Hydrated citric solids require a separately defined stock.
ACIDS = {
    'HNO3': ('NO3-', 63.01284, {'N_NO3': 14.0067}),
    'H3PO4': ('PO4-3', 97.995182, {'P': 30.973762}),
    'H2SO4': ('SO4-2', 98.07848, {'S': 32.06}),
    'C6H8O7': ('Citrate-3', 192.12352, {}),
}


@dataclass(frozen=True)
class AcidCandidate:
    product_id: str
    formula: str
    status: str
    dose_molal: float | None = None
    reagent_mass_g: float | None = None
    reagent_volume_litres: float | None = None
    nutrient_contribution: dict | None = None
    rows: tuple = ()
    loss: float | None = None
    target: object = None
    error_code: str | None = None
    message: str | None = None
    product_record: dict | None = None
    incidental_assessment: dict | None = None


@dataclass(frozen=True)
class AcidSelection:
    candidates: tuple
    selected_product_id: str | None
    selection_policy: str
    post_mix_measurement_required: bool = True


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise DeliveryError('invalid_value', f'{name} must be finite and positive')
    return float(value)


def plan_acid_options(totals, initial_ph, target_ph, *, products, water_mass_kg,
                      final_volume_litres, achieved, targets,
                      maximum_nutrient_error_percent, maximum_reagent_volume_litres,
                      preferred_product_id=None, phases=(), maximum_concentrations=None):
    """Rank accepted single-acid plans by nutrient loss, or respect an explicit ID.

    Products: id, source, revision, recordedAt, chemicalFormula, massFraction
    (pure acid mass / aqueous product mass), densityKgPerL. No acid blending,
    cost optimization, dosing execution or open-CO2 prediction is performed.
    """
    mass = _positive(water_mass_kg, 'water_mass_kg')
    volume = _positive(final_volume_litres, 'final_volume_litres')
    cap = _positive(maximum_reagent_volume_litres, 'maximum_reagent_volume_litres')
    tolerance = _positive(maximum_nutrient_error_percent, 'maximum_nutrient_error_percent')
    for ph in (initial_ph, target_ph):
        if isinstance(ph, bool) or not isinstance(ph, (int, float)) or not math.isfinite(ph) or not 0 <= ph <= 14:
            raise DeliveryError('out_of_range', 'pH must be finite in [0,14]')
    rescore_with_reagent(achieved, targets, {})
    if not targets:
        raise DeliveryError('missing_field', 'nutrient targets are required')
    if not isinstance(products, (list, tuple)) or not products:
        raise DeliveryError('missing_field', 'sourced aqueous acid product records are required')
    identifiers = [p.get('id') if isinstance(p, Mapping) else None for p in products]
    if any(not isinstance(i, str) or not i.strip() for i in identifiers) or len(set(identifiers)) != len(identifiers):
        raise DeliveryError('invalid_value', 'acid product IDs must be unique nonempty strings')
    if preferred_product_id is not None and preferred_product_id not in identifiers:
        raise DeliveryError('unknown_product', 'requested acid product is not in the supplied list')
    if isinstance(phases, (str, bytes)) or not isinstance(phases, Sequence):
        raise DeliveryError('invalid_type', 'phases must be an explicit sequence')
    phases = tuple(phases)
    initial = solve(totals, initial_ph, phases=phases)
    records = {r['name']: r for r in chemistry()['aqueous']}
    absolute_charge = sum(abs(records[n]['charge']) * value for n, value in initial.species.items())
    if abs(initial.charge_balance) > max(1e-12, .001 * absolute_charge):
        raise DeliveryError('charge_imbalance', 'initial mixed solution must be charge balanced')
    candidates = []
    for product in products:
        identity = product['id']
        formula = product.get('chemicalFormula')
        try:
            for key in ('source', 'revision', 'recordedAt'):
                if not isinstance(product.get(key), str) or not product[key].strip():
                    raise DeliveryError('missing_field', f'acid product {key} is required')
            if formula not in ACIDS:
                raise DeliveryError('unsupported_reagent', 'supported identities: HNO3, H3PO4, H2SO4, C6H8O7')
            fraction = _positive(product.get('massFraction'), 'massFraction')
            density = _positive(product.get('densityKgPerL'), 'densityKgPerL')
            if fraction > 1:
                raise DeliveryError('inconsistent_assay', 'massFraction cannot exceed one')
            if target_ph > initial_ph:
                raise DeliveryError('wrong_reagent_direction', 'acid selection cannot satisfy a base requirement')
            basis, molar_mass, nutrients = ACIDS[formula]

            def at(dose):
                amended = dict(totals)
                amended[basis] = amended.get(basis, 0) + dose
                return solve(amended, target_ph, phases=phases)

            dose = 0.
            target = initial if target_ph == initial_ph else at(0.)
            if target_ph != initial_ph:
                if target.charge_balance < initial.charge_balance - 1e-12:
                    raise DeliveryError('wrong_reagent_direction', 'target requires base under this phase policy')
                low, high = 0., 1e-6
                for _ in range(32):
                    if at(high).charge_balance <= initial.charge_balance:
                        break
                    high *= 2
                else:
                    raise DeliveryError('nonconvergent', 'acid demand could not be bracketed')
                for _ in range(40):
                    middle = (low + high) / 2
                    if at(middle).charge_balance > initial.charge_balance:
                        low = middle
                    else:
                        high = middle
                dose = (low + high) / 2
                target = at(dose)
            grams = dose * mass * molar_mass / fraction
            litres = grams / (1000 * density)
            if litres > cap or litres > volume or grams * (1 - fraction) > mass * 1000:
                raise DeliveryError('dose_limit_exceeded', 'dose exceeds volume or final solvent inventory')
            contribution = {ion: dose * mass * molar * 1000 / volume for ion, molar in nutrients.items()}
            loss, rows = rescore_with_reagent(achieved, targets,
                                             {ion: MilligramsPerLitre(value) for ion, value in contribution.items()})
            for row in rows:
                if row['deltaPct'] is not None and abs(row['deltaPct']) > tolerance:
                    raise DeliveryError('nutrient_tolerance_exceeded', f'acid plan violates {row["symbol"]} target')
            assessment = assess_incidental(rows, maximum_concentrations)
            if assessment['limitViolations']:
                raise DeliveryError('nutrient_limit_exceeded', 'acid plan exceeds an explicit nutrient maximum')
            if any(v > 1e-12 for v in target.precipitated.values()) or any(si > 1e-7 for si in target.saturation_indices.values()):
                raise DeliveryError('precipitation_risk', 'target solids or positive SI prohibit acid-plan acceptance')
            candidates.append(AcidCandidate(identity, formula, 'requires_review' if assessment['requiresReview'] else 'accepted',
                                           dose, grams, litres, contribution, tuple(rows), loss, target,
                                           product_record=dict(product), incidental_assessment=assessment))
        except DeliveryError as exc:
            candidates.append(AcidCandidate(identity, formula, 'rejected', error_code=exc.code,
                                           message=str(exc), product_record=dict(product)))
    accepted = [c for c in candidates if c.status == 'accepted' and
                (preferred_product_id is None or c.product_id == preferred_product_id)]
    selected = min(accepted, key=lambda c: (c.loss, identifiers.index(c.product_id))).product_id if accepted else None
    policy = 'explicit user choice; no fallback' if preferred_product_id is not None else 'lowest final nutrient loss; input order breaks ties'
    return AcidSelection(tuple(candidates), selected, policy)
