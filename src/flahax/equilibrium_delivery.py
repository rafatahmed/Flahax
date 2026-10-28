# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Explicit catalogue-equilibrium to reviewed delivery-plan boundary.

Fixed final solvent mass/volume projection, not automatic dilution or hardware
control. The caller supplies measured initial pH and complete analytical water.
"""

from dataclasses import dataclass
import hashlib
from importlib.resources import files
import math
from typing import Mapping

from .saturation_policy import assess_saturation
from .aqueous_model import AcidResult, chemistry
from .delivery_contracts import DeliveryError, validate_product_assay
from .delivery_quantities import (
    FinalSolutionRecipe,
    MassGrams,
    VolumeLitres,
    elemental_contribution,
    rescore_with_reagent,
)
from .engine import load_library, forward
from .materials import IDENTITIES_SHA256, material_audit_entry, resolve_material
from .product_conversion import MOLAR_MASS, plan_catalogue_nitric_target
from .nutrient_acceptance import assess_incidental
from .measured_water import BalancedWaterAnalysis, nutrient_mg_per_litre


def _number(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DeliveryError('invalid_value', f'{name} must be a finite number')
    if value < 0 or (positive and value == 0):
        raise DeliveryError('out_of_range', f'{name} is outside its permitted range')
    return float(value)


@dataclass(frozen=True)
class EquilibriumPhPlan:
    """An acid dose for the target pH, solved by equilibrium for one recipe and water, with the
    reagent amount, nutrient contribution, audit and warnings.
    """

    recipe: FinalSolutionRecipe
    water_analysis_id: str
    water_mass_kg: float
    reagent_id: str
    reagent_channel_id: str
    target_ph: float
    equilibrium: AcidResult
    reagent_mass: MassGrams
    reagent_volume_litres: float
    nutrient_contribution: dict
    loss: float
    rows: tuple
    audit: dict
    warnings: tuple[str, ...]
    post_mix_measurement_required: bool = True
    mode: str = 'catalogue-equilibrium-nitric'
    incidental_assessment: dict | None = None


def plan_equilibrium_delivery(
    recipe,
    *,
    water_mass_kg,
    water_totals,
    water_analysis_id,
    initial_ph,
    target_ph,
    reagent,
    reagent_channel_id,
    maximum_reagent_volume,
    targets,
    maximum_nutrient_error_percent,
    temperature_c=25.0,
    phases=(),
    maximum_concentrations=None,
    analytical_water_totals=None,
):
    """Convert molal HNO3 into assay-qualified mass/volume and rescore nutrients.

    `water_mass_kg` is the explicitly defined final solvent inventory, including
    reagent carrier water; final recipe volume is the make-up volume. No density
    or g/L == g/kg approximation is made. `phases` is the explicit equilibrium
    policy; positive target SI or solid formation prohibits delivery validation.

    `water_totals` drive the acid dose. Nutrient rows, target deviations and
    maximum concentrations use `analytical_water_totals`, the laboratory analysis
    (#84). Pass a `BalancedWaterAnalysis` as `water_totals` and both come from it;
    a plain mapping without `analytical_water_totals` is taken as the analysis
    itself, as before.
    """
    if not isinstance(recipe, FinalSolutionRecipe) or not recipe.feasible or not recipe.salts:
        raise DeliveryError(
            'infeasible_recipe', 'a nonempty feasible FinalSolutionRecipe is required'
        )
    water_mass = _number(water_mass_kg, 'water_mass_kg', positive=True)
    initial_ph = _number(initial_ph, 'initial_ph')
    target_ph = _number(target_ph, 'target_ph')
    phases = tuple(phases)
    tolerance = _number(maximum_nutrient_error_percent, 'maximum_nutrient_error_percent')
    if isinstance(temperature_c, bool) or temperature_c != 25:
        raise DeliveryError('temperature_out_of_range', 'equilibrium delivery requires 25 C')
    if not isinstance(water_analysis_id, str) or not water_analysis_id.strip():
        raise DeliveryError('missing_field', 'water_analysis_id is required')
    if not isinstance(reagent_channel_id, str) or not reagent_channel_id.strip():
        raise DeliveryError('missing_field', 'a dedicated reagent_channel_id is required')
    if isinstance(water_totals, BalancedWaterAnalysis):
        # A balanced record carries its own laboratory analysis: never substitute the model for it.
        if (
            analytical_water_totals is not None
            and dict(analytical_water_totals) != water_totals.analytical_totals
        ):
            raise DeliveryError(
                'contradictory_water_inputs',
                'analytical_water_totals differ from the balanced record\'s analytical totals',
            )
        analytical_water_totals = water_totals.analytical_totals
        water_totals = water_totals.totals
    if not isinstance(water_totals, Mapping):
        raise DeliveryError(
            'missing_field', 'complete water_totals are required; use {} for explicitly pure water'
        )
    water = dict(water_totals)
    if analytical_water_totals is None:
        analytical = dict(water)
    elif not isinstance(analytical_water_totals, Mapping):
        raise DeliveryError('invalid_type', 'analytical_water_totals must be a mapping')
    else:
        analytical = dict(analytical_water_totals)
    for inventory in (water, analytical):
        for basis, amount in inventory.items():
            if basis not in chemistry()['bases']:
                raise DeliveryError('invalid_totals', f'unknown water component {basis}')
            _number(amount, basis)
    if not isinstance(maximum_reagent_volume, VolumeLitres):
        raise DeliveryError('invalid_type', 'maximum_reagent_volume must be VolumeLitres')
    if not isinstance(targets, Mapping) or not targets:
        raise DeliveryError('missing_field', 'nonempty nutrient targets are required')
    # Validate nutrient symbols/values before the expensive equilibrium solve.
    rescore_with_reagent({}, targets, {})
    assay = validate_product_assay(reagent)
    if reagent.get('chemicalFormula') != 'HNO3' or assay['kind'] != 'acid':
        raise DeliveryError('unsupported_reagent', 'explicit HNO3 acid identity is required')
    if set(assay['elements']) != {'N_NO3'} or assay['elements']['N_NO3'] <= 0:
        raise DeliveryError(
            'unsupported_reagent', 'only nitric acid in water with nitrate-N assay is supported'
        )
    if 'densityKgPerL' not in assay:
        raise DeliveryError('missing_measurement', 'reagent densityKgPerL is required')
    fraction = assay['elements']['N_NO3'] / 100.0
    # Nitrogen mass fraction cannot exceed pure HNO3's stoichiometric value.
    if fraction > MOLAR_MASS['N'] / 63.01284:
        raise DeliveryError('inconsistent_assay', 'nitrate-N assay exceeds pure HNO3')
    density = assay['densityKgPerL']
    normality = density * 1e6 * fraction / MOLAR_MASS['N']
    if 'normalityMeqPerL' in assay and not math.isclose(
        assay['normalityMeqPerL'], normality, rel_tol=0.01
    ):
        raise DeliveryError(
            'inconsistent_assay', 'normality differs from nitrate-N assay/density by more than 1%'
        )
    library = {p['id']: p for p in load_library()['salts']}
    selected, grams_per_litre, doses = [], [], {}
    for salt in recipe.salts:
        product = library.get(salt.salt_id)
        if product is None or product['name'] != salt.name:
            raise DeliveryError(
                'product_chemistry_mismatch', 'recipe must match both catalogue id and name'
            )
        if not math.isclose(
            salt.mass.value, salt.dose.value * recipe.final_volume.value, rel_tol=1e-12
        ):
            raise DeliveryError('inconsistent_recipe', 'salt mass, g/L and batch volume disagree')
        selected.append(product)
        grams_per_litre.append(salt.dose.value)
        doses[salt.name] = doses.get(salt.name, 0.0) + salt.mass.value / water_mass
    result = plan_catalogue_nitric_target(
        doses, initial_ph, target_ph, water_totals=water, phases=tuple(phases)
    )
    records = {r['name']: r for r in chemistry()['aqueous']}
    total_charge = sum(m * abs(records[n]['charge']) for n, m in result.initial.species.items())
    if abs(result.initial.charge_balance) > max(1e-12, 0.001 * total_charge):
        raise DeliveryError(
            'charge_imbalance',
            'initial complete solution exceeds 0.1% charge error; supply missing analytical ions',
        )
    moles = result.nitric_acid_molal * water_mass
    mass = MassGrams(moles * MOLAR_MASS['N'] / fraction)
    volume = mass.value / (density * 1000.0)
    if volume > maximum_reagent_volume.value or volume > recipe.final_volume.value:
        raise DeliveryError(
            'dose_limit_exceeded', 'nitric acid volume exceeds the supplied limit or final volume'
        )
    contribution = elemental_contribution(mass, {'N_NO3': fraction}, recipe.final_volume)
    # Nutrient accounting on the laboratory analysis; the dose above used the chemistry inventory.
    water_ppm = nutrient_mg_per_litre(analytical, water_mass, recipe.final_volume.value)
    achieved = forward(selected, grams_per_litre, water_ppm)
    loss, rows = rescore_with_reagent(achieved, targets, contribution)
    for row in rows:
        target = row['target']
        if target is not None and row['deltaPct'] is not None and abs(row['deltaPct']) > tolerance:
            raise DeliveryError(
                'nutrient_tolerance_exceeded',
                f'final nutrient {row["symbol"]} exceeds the specified tolerance',
            )
    assessment = assess_incidental(rows, maximum_concentrations)
    if assessment['limitViolations']:
        raise DeliveryError(
            'nutrient_limit_exceeded', 'final composition exceeds an explicit nutrient maximum'
        )
    warnings = ['Initial dose only; measure pH after mixing before any correction.']
    if assessment['requiresReview']:
        warnings.append(
            'Incidental nutrient additions require review or explicit maximum-concentration '
            'limits.'
        )
    saturation = assess_saturation(result.target)
    if saturation['blocks']:
        warnings.append(
            'Precipitation risk: target has formed solids or positive saturation indices; not '
            'valid for delivery approval.'
        )
    warnings += [
        f'Review: {p} SI {si:.2f}. {reason} Sources: {sources}'
        for p, si, reason, sources in saturation['review']
    ]
    warnings += saturation['advisories']
    residual_bicarbonate = 1000 * result.target.species.get('HCO3-', 0.0)
    audit = {
        'modelVersion': 'minteq-flahax-25c-v1',
        'waterAnalysisId': water_analysis_id,
        'waterMassKg': water_mass,
        'reagentAssay': assay,
        'chemicalFormula': 'HNO3',
        'reagentChannelId': reagent_channel_id,
        'waterTotalsMolal': water,
        'analyticalWaterTotalsMolal': analytical,
        'nutrientBasis': 'laboratory analysis' if analytical != water else 'supplied water totals',
        'initialPh': initial_ph,
        'targetPh': target_ph,
        'finalVolumeLitres': recipe.final_volume.value,
        'productDosesGPerKgWater': doses,
        'temperatureC': temperature_c,
        'phases': list(phases),
        'maximumNutrientErrorPercent': tolerance,
        'maximumConcentrationsPpm': dict(maximum_concentrations or {}),
        'residualBicarbonateMmolPerKg': residual_bicarbonate,
        'sourceDatabaseSha256': chemistry()['database_sha256'],
        'chemistrySha256': hashlib.sha256(
            files('flahax').joinpath('data/chemistry_25c.json').read_bytes()
        ).hexdigest(),
        'catalogueSha256': hashlib.sha256(
            files('flahax').joinpath('data/library.json').read_bytes()
        ).hexdigest(),
        'identitiesSha256': IDENTITIES_SHA256,
        'materials': {name: material_audit_entry(resolve_material(name)) for name in doses},
    }
    return EquilibriumPhPlan(
        recipe,
        water_analysis_id,
        water_mass,
        assay['id'],
        reagent_channel_id,
        target_ph,
        result,
        mass,
        volume,
        contribution,
        loss,
        tuple(rows),
        audit,
        tuple(warnings),
        incidental_assessment=assessment,
    )
