"""Explicit catalogue-equilibrium to reviewed delivery-plan boundary.

Fixed final solvent mass/volume projection, not automatic dilution or hardware
control. The caller supplies measured initial pH and complete analytical water.
"""
from dataclasses import dataclass
import hashlib
from importlib.resources import files
import math
from typing import Mapping

from .aqueous_model import AcidResult, chemistry
from .delivery_contracts import DeliveryError, validate_product_assay
from .delivery_quantities import FinalSolutionRecipe, MassGrams, VolumeLitres, elemental_contribution, rescore_with_reagent
from .engine import load_library, forward
from .product_conversion import MOLAR_MASS, plan_catalogue_nitric_target


def _number(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DeliveryError('invalid_value', f'{name} must be a finite number')
    if value < 0 or (positive and value == 0):
        raise DeliveryError('out_of_range', f'{name} is outside its permitted range')
    return float(value)


@dataclass(frozen=True)
class EquilibriumPhPlan:
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


def plan_equilibrium_delivery(recipe, *, water_mass_kg, water_totals,
                              water_analysis_id, initial_ph, target_ph, reagent,
                              reagent_channel_id,
                              maximum_reagent_volume, targets,
                              maximum_nutrient_error_percent, temperature_c=25., phases=()):
    """Convert molal HNO3 into assay-qualified mass/volume and rescore nutrients.

    `water_mass_kg` is the explicitly defined final solvent inventory, including
    reagent carrier water; final recipe volume is the make-up volume. No density
    or g/L == g/kg approximation is made. `phases` is the explicit equilibrium
    policy; positive target SI or solid formation prohibits delivery validation.
    """
    if not isinstance(recipe, FinalSolutionRecipe) or not recipe.feasible or not recipe.salts:
        raise DeliveryError('infeasible_recipe', 'a nonempty feasible FinalSolutionRecipe is required')
    water_mass = _number(water_mass_kg, 'water_mass_kg', positive=True)
    initial_ph = _number(initial_ph, 'initial_ph')
    target_ph = _number(target_ph, 'target_ph')
    phases = tuple(phases)
    tolerance = _number(maximum_nutrient_error_percent, 'maximum_nutrient_error_percent')
    if isinstance(temperature_c, bool) or temperature_c != 25:
        raise DeliveryError('temperature_out_of_range', 'equilibrium delivery requires 25 C')
    if not isinstance(water_analysis_id,str) or not water_analysis_id.strip():
        raise DeliveryError('missing_field', 'water_analysis_id is required')
    if not isinstance(reagent_channel_id,str) or not reagent_channel_id.strip():
        raise DeliveryError('missing_field', 'a dedicated reagent_channel_id is required')
    if not isinstance(water_totals,Mapping):
        raise DeliveryError('missing_field', 'complete water_totals are required; use {} for explicitly pure water')
    water = dict(water_totals)
    for basis, amount in water.items():
        if basis not in chemistry()['bases']:
            raise DeliveryError('invalid_totals', f'unknown water component {basis}')
        _number(amount, basis)
    if not isinstance(maximum_reagent_volume,VolumeLitres):
        raise DeliveryError('invalid_type', 'maximum_reagent_volume must be VolumeLitres')
    if not isinstance(targets,Mapping) or not targets:
        raise DeliveryError('missing_field', 'nonempty nutrient targets are required')
    # Validate nutrient symbols/values before the expensive equilibrium solve.
    rescore_with_reagent({},targets,{})
    assay = validate_product_assay(reagent)
    if reagent.get('chemicalFormula') != 'HNO3' or assay['kind'] != 'acid':
        raise DeliveryError('unsupported_reagent', 'explicit HNO3 acid identity is required')
    if set(assay['elements']) != {'N_NO3'} or assay['elements']['N_NO3'] <= 0:
        raise DeliveryError('unsupported_reagent', 'only nitric acid in water with nitrate-N assay is supported')
    if 'densityKgPerL' not in assay:
        raise DeliveryError('missing_measurement', 'reagent densityKgPerL is required')
    fraction = assay['elements']['N_NO3']/100.
    # Nitrogen mass fraction cannot exceed pure HNO3's stoichiometric value.
    if fraction > MOLAR_MASS['N']/63.01284:
        raise DeliveryError('inconsistent_assay', 'nitrate-N assay exceeds pure HNO3')
    density = assay['densityKgPerL']
    normality = density*1e6*fraction/MOLAR_MASS['N']
    if 'normalityMeqPerL' in assay and not math.isclose(assay['normalityMeqPerL'],normality,rel_tol=.01):
        raise DeliveryError('inconsistent_assay', 'normality differs from nitrate-N assay/density by more than 1%')
    library = {p['id']:p for p in load_library()['salts']}
    selected, grams_per_litre, doses = [], [], {}
    for salt in recipe.salts:
        product = library.get(salt.salt_id)
        if product is None or product['name'] != salt.name:
            raise DeliveryError('product_chemistry_mismatch', 'recipe must match both catalogue id and name')
        if not math.isclose(salt.mass.value,salt.dose.value*recipe.final_volume.value,rel_tol=1e-12):
            raise DeliveryError('inconsistent_recipe', 'salt mass, g/L and batch volume disagree')
        selected.append(product)
        grams_per_litre.append(salt.dose.value)
        doses[salt.name]=doses.get(salt.name,0.)+salt.mass.value/water_mass
    result = plan_catalogue_nitric_target(doses,initial_ph,target_ph,water_totals=water,phases=tuple(phases))
    records = {r['name']:r for r in chemistry()['aqueous']}
    total_charge = sum(m*abs(records[n]['charge']) for n,m in result.initial.species.items())
    if abs(result.initial.charge_balance)>max(1e-12,.001*total_charge):
        raise DeliveryError('charge_imbalance', 'initial complete solution exceeds 0.1% charge error; supply missing analytical ions')
    moles = result.nitric_acid_molal*water_mass
    mass = MassGrams(moles*MOLAR_MASS['N']/fraction)
    volume = mass.value/(density*1000.)
    if volume>maximum_reagent_volume.value or volume>recipe.final_volume.value:
        raise DeliveryError('dose_limit_exceeded', 'nitric acid volume exceeds the supplied limit or final volume')
    contribution = elemental_contribution(mass,{'N_NO3':fraction},recipe.final_volume)
    water_ppm = {}
    element_basis = {'Ca+2':'Ca','Mg+2':'Mg','K+':'K','Na+':'Na','Cl-':'Cl',
                     'NO3-':'N_NO3','NH4+':'N_NH4','PO4-3':'P','SO4-2':'S',
                     'Fe+3':'Fe','Fe+2':'Fe','Mn+2':'Mn','Zn+2':'Zn','Cu+2':'Cu',
                     'H3BO3':'B','MoO4-2':'Mo','Ure':'N_UREA'}
    for basis, amount in water.items():
        if basis not in element_basis:
            continue
        ion = element_basis[basis]
        molar_mass = 35.453 if ion=='Cl' else MOLAR_MASS[ion.split('_')[0]]
        value=amount*(2 if basis=='Ure' else 1)*molar_mass*water_mass*1000/recipe.final_volume.value
        water_ppm[ion]=water_ppm.get(ion,0.)+value
    achieved = forward(selected,grams_per_litre,water_ppm)
    loss, rows = rescore_with_reagent(achieved,targets,contribution)
    for row in rows:
        target = row['target']
        if target is not None and ((target == 0 and row['final']>1e-12) or
                                  (row['deltaPct'] is not None and abs(row['deltaPct'])>tolerance)):
            raise DeliveryError('nutrient_tolerance_exceeded',f'final nutrient {row["symbol"]} exceeds the specified tolerance')
    warnings = ['Initial dose only; measure pH after mixing before any correction.']
    if any(v>1e-12 for v in result.target.precipitated.values()) or any(si>1e-7 for si in result.target.saturation_indices.values()):
        warnings.append('Precipitation risk: target has formed solids or positive saturation indices; not valid for delivery approval.')
    audit = {'modelVersion':'minteq-flahax-25c-v1','waterAnalysisId':water_analysis_id,
             'waterMassKg':water_mass,'reagentAssay':assay,'chemicalFormula':'HNO3',
             'reagentChannelId':reagent_channel_id,
             'waterTotalsMolal':water,'initialPh':initial_ph,'targetPh':target_ph,
             'finalVolumeLitres':recipe.final_volume.value,'productDosesGPerKgWater':doses,
             'temperatureC':temperature_c,'phases':list(phases),'maximumNutrientErrorPercent':tolerance,
             'sourceDatabaseSha256':chemistry()['database_sha256'],
             'chemistrySha256':hashlib.sha256(files('flahax').joinpath('data/chemistry_25c.json').read_bytes()).hexdigest(),
             'catalogueSha256':hashlib.sha256(files('flahax').joinpath('data/library.json').read_bytes()).hexdigest()}
    return EquilibriumPhPlan(recipe,water_analysis_id,water_mass,assay['id'],reagent_channel_id,target_ph,result,
                             mass,volume,contribution,loss,tuple(rows),audit,tuple(warnings))
