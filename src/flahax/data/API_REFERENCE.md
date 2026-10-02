# FlahaX 0.3.1 - Public API reference

Generated from `flahax.__all__`, runtime signatures and source docstrings.
Do not edit this inventory by hand. Regenerate with
`PYTHONPATH=src python tools/generate_api_reference.py` (PowerShell:
`$env:PYTHONPATH="src"; python tools/generate_api_reference.py`).

Start with the [User Manual](USER_GUIDE.md) for units, complete examples,
input provenance, errors and scientific limits. This inventory is not a
substitute for the linked workflow contracts or a claim of field validation.

## Choosing an entry point

| Task | Entry point | Contract |
|---|---|---|
| Nutrient fit | `recommend`, `solve_weights` | Elemental mg/L in; product g/L out |
| Staged site workflow | `plan_fertilizer_workflow` | Explicit water; inspect every stage status |
| One mixed chemistry solve | `solve_catalogue_product_doses` | Product g/kg water; fixed pH |
| Calculated pH | `calculate_equilibrium_ph` | Complete analytical mol/kg-water totals |
| Nitric reagent volume | `plan_equilibrium_delivery` | Final solvent mass, assay and density |
| Standard acid candidates | `plan_acid_options` | Workflow restricts to nitric/phosphoric |
| Stock compatibility | `plan_stocks` | Sourced rules and solubility limits required |
| Measured titration | `plan_ph` | Matching measured curve, not inferred water chemistry |
| Approximate EC | `estimate_manufacturer_ec` | Restricted pre-acid irrigation screening |
| Calibrated EC | `plan_ec_delivery` | Matching measured profiles |
| Injector requirements | `size_injection_requirements` | Volume/flow only, not model selection |
| Calibrated delivery | `plan_pump_command`, `compose_delivery_plan` | Planning only; no hardware I/O |

## Compatibility and error handling

Only the names listed here are the top-level import surface. Submodule
helpers are not automatically public contracts. Legacy single-system kernels
remain available for compatibility and reference tests; do not combine their
independent results as a substitute for the coupled mixed solver.
Signatures show keyword-only arguments after `*`; omitted defaults do not
supply missing measured chemistry. Handle `InputError` and `DeliveryError`
as described in the manual. A returned result is not necessarily an approved
plan: inspect feasibility, stage status, residuals and warnings.

## flahax.acid_selection

### `AcidCandidate`

```text
AcidCandidate(product_id: str, formula: str, status: str, dose_molal: float | None = None, reagent_mass_g: float | None = None, reagent_volume_litres: float | None = None, nutrient_contribution: dict | None = None, rows: tuple = (), loss: float | None = None, target: object = None, error_code: str | None = None, message: str | None = None, product_record: dict | None = None, incidental_assessment: dict | None = None) -> None
```

Record fields: `product_id`, `formula`, `status`, `dose_molal`, `reagent_mass_g`, `reagent_volume_litres`, `nutrient_contribution`, `rows`, `loss`, `target`, `error_code`, `message`, `product_record`, `incidental_assessment`.

Source module: `flahax.acid_selection`. Import with `from flahax import AcidCandidate`.

### `AcidSelection`

```text
AcidSelection(candidates: tuple, selected_product_id: str | None, selection_policy: str, post_mix_measurement_required: bool = True) -> None
```

Record fields: `candidates`, `selected_product_id`, `selection_policy`, `post_mix_measurement_required`.

Source module: `flahax.acid_selection`. Import with `from flahax import AcidSelection`.

### `plan_acid_options`

```text
plan_acid_options(totals, initial_ph, target_ph, *, products, water_mass_kg, final_volume_litres, achieved, targets, maximum_nutrient_error_percent, maximum_reagent_volume_litres, preferred_product_id=None, phases=(), maximum_concentrations=None)
```

Rank accepted single-acid plans by nutrient loss, or respect an explicit ID.

Products: id, source, revision, recordedAt, chemicalFormula, massFraction
(pure acid mass / aqueous product mass), densityKgPerL. No acid blending,
cost optimization, dosing execution or open-CO2 prediction is performed.

Source module: `flahax.acid_selection`. Import with `from flahax import plan_acid_options`.

## flahax.ammonia

### `AmmoniaSpeciation`

```text
AmmoniaSpeciation(total_ammoniacal_nitrogen_molal: 'float', ph: 'float', ionic_strength: 'float', ammonium_molal: 'float', ammonia_molal: 'float', ammonium_activity: 'float') -> None
```

Record fields: `total_ammoniacal_nitrogen_molal`, `ph`, `ionic_strength`, `ammonium_molal`, `ammonia_molal`, `ammonium_activity`.

Source module: `flahax.ammonia`. Import with `from flahax import AmmoniaSpeciation`.

### `ammonia_speciation`

```text
ammonia_speciation(total_ammoniacal_nitrogen_molal: 'float', ph: 'float', ionic_strength: 'float') -> 'AmmoniaSpeciation'
```

Split analytical NHx between NH4+ and neutral NH3 at fixed pH/I.

Source module: `flahax.ammonia`. Import with `from flahax import ammonia_speciation`.

## flahax.aqueous_model

### `AcidResult`

```text
AcidResult(initial: flahax.aqueous_model.AqueousResult, target: flahax.aqueous_model.AqueousResult, nitric_acid_molal: float, post_mix_measurement_required: bool = True) -> None
```

Record fields: `initial`, `target`, `nitric_acid_molal`, `post_mix_measurement_required`.

Source module: `flahax.aqueous_model`. Import with `from flahax import AcidResult`.

### `AqueousResult`

```text
AqueousResult(totals: dict, ph: float, ionic_strength: float, species: dict, activities: dict, saturation_indices: dict, precipitated: dict, residuals: dict, iterations: int, charge_balance: float, water_activity: float) -> None
```

Record fields: `totals`, `ph`, `ionic_strength`, `species`, `activities`, `saturation_indices`, `precipitated`, `residuals`, `iterations`, `charge_balance`, `water_activity`.

Source module: `flahax.aqueous_model`. Import with `from flahax import AqueousResult`.

## flahax.calculated_ec

### `estimate_manufacturer_ec`

```text
estimate_manufacturer_ec(doses_g_per_litre, *, water_ec_ms_cm=None, water_tds_ppm=None, tds_factor=None, temperature_c=25, channel='irrigation', acid_added=False)
```

Approximate EC25 = source-water EC25 + sum(dose * brochure anchor).

A no-new-measurements, pre-acid screening estimate. Linearity/additivity
are assumptions, not manufacturer validation. A total fertilizer loading
cap of 1 g/L is a conservative software policy, NOT a validated range.
No uncertainty bound or model for concentrated A/B stocks is asserted.
Unknown products never disappear into a falsely complete total.

Source module: `flahax.calculated_ec`. Import with `from flahax import estimate_manufacturer_ec`.

## flahax.calculated_ph

### `calculate_equilibrium_ph`

```text
calculate_equilibrium_ph(totals, *, complete_analysis, carbon_boundary, phases, temperature_c=25.0)
```

Return AqueousResult at zero net charge within the existing Davies domain.

Completeness is a caller declaration of analytical coverage, not a claim
that the software can identify absent laboratory measurements. A nutrient
table alone is not a complete analysis. Charge adjustment changes only pH.

Source module: `flahax.calculated_ph`. Import with `from flahax import calculate_equilibrium_ph`.

## flahax.catalogue_chemistry

### `ProductChemistry`

```text
ProductChemistry(name: 'str', family: 'str', components: 'tuple[str, ...]', source_profile: 'str', temperature_c: 'float' = 25.0) -> None
```

Source-versioned chemical identity; not a nutrient-assay replacement.

Record fields: `name`, `family`, `components`, `source_profile`, `temperature_c`.

Source module: `flahax.catalogue_chemistry`. Import with `from flahax import ProductChemistry`.

### `assert_catalogue_coverage`

```text
assert_catalogue_coverage(products: 'list[Mapping[str, object]]') -> 'None'
```

Require exact one-to-one coverage of the package fertilizer catalogue.

Source module: `flahax.catalogue_chemistry`. Import with `from flahax import assert_catalogue_coverage`.

### `chemistry_for_product`

```text
chemistry_for_product(name: 'str') -> 'ProductChemistry'
```

Return a product's explicit equilibrium identity or fail closed.

Source module: `flahax.catalogue_chemistry`. Import with `from flahax import chemistry_for_product`.

## flahax.competition

### `CalciumSulfateStruviteCompetition`

```text
CalciumSulfateStruviteCompetition(gypsum_si: 'float', struvite_si: 'float') -> None
```

Record fields: `gypsum_si`, `struvite_si`.

Source module: `flahax.competition`. Import with `from flahax import CalciumSulfateStruviteCompetition`.

### `CarbonateCompetition`

```text
CarbonateCompetition(calcite_si: 'float', gypsum_si: 'float', struvite_si: 'float') -> None
```

Record fields: `calcite_si`, `gypsum_si`, `struvite_si`.

Source module: `flahax.competition`. Import with `from flahax import CarbonateCompetition`.

### `calcium_sulfate_struvite_competition`

```text
calcium_sulfate_struvite_competition(calcium_activity: 'float', sulfate_activity: 'float', magnesium_activity: 'float', ammonium_activity: 'float', phosphate_activity: 'float') -> 'CalciumSulfateStruviteCompetition'
```

Compare gypsum and struvite SI at supplied free-ion activities.

Source module: `flahax.competition`. Import with `from flahax import calcium_sulfate_struvite_competition`.

### `carbonate_competition`

```text
carbonate_competition(calcium_activity: 'float', carbonate_activity: 'float', sulfate_activity: 'float', magnesium_activity: 'float', ammonium_activity: 'float', phosphate_activity: 'float') -> 'CarbonateCompetition'
```

Compare calcite, gypsum, and struvite SI from free-ion activities.

Source module: `flahax.competition`. Import with `from flahax import carbonate_competition`.

## flahax.composition

### `InputError`

The caller passed a profile or a salt the balance cannot use.

Source module: `flahax.composition`. Import with `from flahax import InputError`.

## flahax.conductivity

### `ECDeliveryPlan`

```text
ECDeliveryPlan(water_ec_ms_cm: float, predictions: dict, injections: dict, pump_commands: tuple, audit: dict, warnings: tuple = <factory>, post_mix_measurement_required: bool = True) -> None
```

Record fields: `water_ec_ms_cm`, `predictions`, `injections`, `pump_commands`, `audit`, `warnings`, `post_mix_measurement_required`.

Source module: `flahax.conductivity`. Import with `from flahax import ECDeliveryPlan`.

### `ECPrediction`

```text
ECPrediction(status: str, ec_ms_cm: float | None = None, profile_id: str | None = None, profile_sha256: str | None = None, error_code: str | None = None, message: str | None = None, uncertainty_ms_cm: float | None = None) -> None
```

Record fields: `status`, `ec_ms_cm`, `profile_id`, `profile_sha256`, `error_code`, `message`, `uncertainty_ms_cm`.

Source module: `flahax.conductivity`. Import with `from flahax import ECPrediction`.

### `ec_recipe_key`

```text
ec_recipe_key(stocks, channel='irrigation', *, reagent_doses_g_per_l=None)
```

Bind calibration to dose, identity, shipped assays and separate reagents.

Changing a product, dose or included reagent requires a new profile. Caller
provenance must additionally identify commercial grades/lots and protocol.

Source module: `flahax.conductivity`. Import with `from flahax import ec_recipe_key`.

### `plan_ec_delivery`

```text
plan_ec_delivery(stocks, *, profiles, water_source_id, water_ec_ms_cm=None, water_tds_ppm=None, tds_factor=None, reference_temperature_c=25, reagent_doses_g_per_l=None, pump_calibrations=None, available_volumes=None, as_of=None)
```

Estimate each stock and the combined final solution independently.

The configured source must be represented by the profiles, even if another
source has the same EC. Calibration strength 1 is the stock-plan recipe in
g/L of final solution; stock strength is the physical injection ratio.
Pump plans are optional and require all used tank calibrations/inventories.

Source module: `flahax.conductivity`. Import with `from flahax import plan_ec_delivery`.

### `water_ec25`

```text
water_ec25(*, ec_ms_cm=None, tds_ppm=None, tds_factor=None)
```

TDS is a meter-equivalent value: ppm = factor * EC in microS/cm.

No conversion of gravimetrically measured dissolved-solids mass is implied.

Source module: `flahax.conductivity`. Import with `from flahax import water_ec25`.

## flahax.delivery_contracts

### `DeliveryError`

```text
DeliveryError(code: 'str', message: 'str')
```

A delivery-planning input failure with a stable machine-readable code.

Source module: `flahax.delivery_contracts`. Import with `from flahax import DeliveryError`.

### `make_audit_record`

```text
make_audit_record(request: 'dict', *, model_version: 'str') -> 'dict'
```

Return a deterministic audit record for a validated delivery request.

Source module: `flahax.delivery_contracts`. Import with `from flahax import make_audit_record`.

### `validate_delivery_request`

```text
validate_delivery_request(payload: 'Any') -> 'dict'
```

Validate the P0 batch-planning request envelope and its referenced records.

Source module: `flahax.delivery_contracts`. Import with `from flahax import validate_delivery_request`.

## flahax.delivery_plan

### `DeliveryPlan`

```text
DeliveryPlan(recipe: 'FinalSolutionRecipe', stocks: 'StockPlan', ph_plan: 'PhPlan | EquilibriumPhPlan | None', commands: 'tuple[PumpCommand, ...]', audit_record: 'dict[str, Any]', warnings: 'tuple[str, ...]', state: 'str' = 'draft') -> None
```

Record fields: `recipe`, `stocks`, `ph_plan`, `commands`, `audit_record`, `warnings`, `state`.

Source module: `flahax.delivery_plan`. Import with `from flahax import DeliveryPlan`.

### `compose_delivery_plan`

```text
compose_delivery_plan(recipe: 'FinalSolutionRecipe', stocks: 'StockPlan', ph_plan: 'PhPlan | EquilibriumPhPlan | None', commands: 'Iterable[PumpCommand]', audit_record: 'Mapping[str, Any]', warnings: 'Iterable[str]' = ()) -> 'DeliveryPlan'
```

Source module: `flahax.delivery_plan`. Import with `from flahax import compose_delivery_plan`.

### `delivery_report`

```text
delivery_report(plan: 'DeliveryPlan') -> 'str'
```

Source module: `flahax.delivery_plan`. Import with `from flahax import delivery_report`.

### `transition_plan`

```text
transition_plan(plan: 'DeliveryPlan', target: 'str') -> 'DeliveryPlan'
```

Source module: `flahax.delivery_plan`. Import with `from flahax import transition_plan`.

## flahax.delivery_quantities

### `DurationMinutes`

```text
DurationMinutes(value: 'float') -> None
```

Record fields: `value`.

Source module: `flahax.delivery_quantities`. Import with `from flahax import DurationMinutes`.

### `FinalSolutionRecipe`

```text
FinalSolutionRecipe(final_volume: 'VolumeLitres', feasible: 'bool', salts: 'tuple[SaltDose, ...]') -> None
```

A recommendation expressed for a concrete final batch volume.

Record fields: `final_volume`, `feasible`, `salts`.

Source module: `flahax.delivery_quantities`. Import with `from flahax import FinalSolutionRecipe`.

### `FlowLitresPerMinute`

```text
FlowLitresPerMinute(value: 'float') -> None
```

Record fields: `value`.

Source module: `flahax.delivery_quantities`. Import with `from flahax import FlowLitresPerMinute`.

### `GramsPerLitre`

```text
GramsPerLitre(value: 'float') -> None
```

Record fields: `value`.

Source module: `flahax.delivery_quantities`. Import with `from flahax import GramsPerLitre`.

### `InjectionRatio`

```text
InjectionRatio(value: 'float') -> None
```

Final-solution litres produced per one litre of injected stock.

Record fields: `value`.

Source module: `flahax.delivery_quantities`. Import with `from flahax import InjectionRatio`.

### `MassGrams`

```text
MassGrams(value: 'float') -> None
```

Record fields: `value`.

Source module: `flahax.delivery_quantities`. Import with `from flahax import MassGrams`.

### `MilliEquivalentsPerLitre`

```text
MilliEquivalentsPerLitre(value: 'float') -> None
```

Record fields: `value`.

Source module: `flahax.delivery_quantities`. Import with `from flahax import MilliEquivalentsPerLitre`.

### `MilligramsPerLitre`

```text
MilligramsPerLitre(value: 'float') -> None
```

Record fields: `value`.

Source module: `flahax.delivery_quantities`. Import with `from flahax import MilligramsPerLitre`.

### `TemperatureCelsius`

```text
TemperatureCelsius(value: 'float') -> None
```

Record fields: `value`.

Source module: `flahax.delivery_quantities`. Import with `from flahax import TemperatureCelsius`.

### `VolumeLitres`

```text
VolumeLitres(value: 'float') -> None
```

Record fields: `value`.

Source module: `flahax.delivery_quantities`. Import with `from flahax import VolumeLitres`.

### `elemental_contribution`

```text
elemental_contribution(reagent_mass: 'MassGrams', elemental_mass_fractions: 'Mapping[str, Any]', final_volume: 'VolumeLitres') -> 'dict[str, MilligramsPerLitre]'
```

Convert a reagent's elemental mass fractions into final ppm additions.

Source module: `flahax.delivery_quantities`. Import with `from flahax import elemental_contribution`.

### `final_solution_recipe`

```text
final_solution_recipe(recommendation: 'Mapping[str, Any]', final_volume: 'VolumeLitres') -> 'FinalSolutionRecipe'
```

Adapt a FlahaX recommendation to exact salt masses for a final batch.

The function consumes only ``result['salts']`` and retains its feasibility
flag. It does not reinterpret the solver's nutrient balance or round doses.

Source module: `flahax.delivery_quantities`. Import with `from flahax import final_solution_recipe`.

### `rescore_with_reagent`

```text
rescore_with_reagent(achieved: 'Mapping[str, Any]', targets: 'Mapping[str, Any]', contribution: 'Mapping[str, MilligramsPerLitre]') -> 'tuple[float, list[dict]]'
```

Add a reagent's ppm contribution and score the resulting ion balance.

Source module: `flahax.delivery_quantities`. Import with `from flahax import rescore_with_reagent`.

## flahax.engine

### `gap_for`

```text
gap_for(targets: 'dict', water: 'dict | None' = None) -> 'dict'
```

Return target minus water in elemental mg/L, without clipping deficits.

Missing water concentrations default to zero in this low-level helper.
Water-only symbols have a None gap; negative gaps mean water exceeds the
target, not that fertilizer can remove the excess. Invalid nutrient maps
raise InputError. This is nutrient accounting, not an acid/base analysis.

Source module: `flahax.engine`. Import with `from flahax import gap_for`.

### `load_library`

```text
load_library() -> 'dict'
```

Salt library, water profiles, and crop formulas shipped with the package.

Source module: `flahax.engine`. Import with `from flahax import load_library`.

### `recommend`

```text
recommend(library: 'list[dict]', targets: 'dict', water: 'dict | None' = None, *, allow_ions: 'frozenset[str] | set[str] | None' = None, allow_carbonates: 'bool' = False, ridge: 'float' = 0.02) -> 'dict'
```

Select eligible products and fit non-negative product g/L.

Args:
    library: Product records with id, name, formula and elemental mass
        percentages in elements. Use load_library()['salts'] deliberately.
    targets: Required nonempty elemental mg/L map; nitrogen forms are
        separate N_NO3, N_NH4 and N_UREA keys, not generic total N.
    water: Source-water elemental mg/L; omitted entries default to zero.
    allow_ions: Explicit exceptions to the default restricted-ion filter.
    allow_carbonates: Permit carbonate products in nutrient fitting only;
        this does not establish dissolution or stock compatibility.
    ridge: L2 dose penalty, not a limit on the number of products.

Returns:
    Dictionary containing identity-bearing salts with gramsPerLitre,
    nutrient rows, feasibility, incidental review, warnings and exclusions.
    The raw grams vector follows the internal eligible/recovered product
    order, NOT necessarily the original library order. Use salts for
    product-to-dose mapping. Feasible is positive-target fit within 1%,
    not chemical, stock or operational approval.

Raises:
    InputError: Invalid targets/water or no eligible products. Inspect
        exclusions and warnings for skipped or recovered candidates.

Source module: `flahax.engine`. Import with `from flahax import recommend`.

### `solve_weights`

```text
solve_weights(salts: 'list[dict]', targets: 'dict', water: 'dict | None' = None, ridge: 'float' = 0.0) -> 'dict'
```

Non-negative grams per litre minimizing squared Δ%.

Source module: `flahax.engine`. Import with `from flahax import solve_weights`.

## flahax.equilibrium

### `CalciteCo2Equilibrium`

```text
CalciteCo2Equilibrium(ph: 'float', ionic_strength: 'float', calcium_molal: 'float', bicarbonate_molal: 'float', carbonate_molal: 'float', co2_molal: 'float', si_calcite: 'float', si_co2_gas: 'float') -> None
```

Open-CO2 calcite equilibrium at 25 °C, using the Davies model.

Record fields: `ph`, `ionic_strength`, `calcium_molal`, `bicarbonate_molal`, `carbonate_molal`, `co2_molal`, `si_calcite`, `si_co2_gas`.

Source module: `flahax.equilibrium`. Import with `from flahax import CalciteCo2Equilibrium`.

### `GypsumEquilibrium`

```text
GypsumEquilibrium(ionic_strength: 'float', free_calcium_molal: 'float', free_sulfate_molal: 'float', calcium_sulfate_molal: 'float', total_calcium_molal: 'float', total_sulfate_molal: 'float', si_gypsum: 'float', si_anhydrite: 'float') -> None
```

Pure-water gypsum equilibrium at 25 °C using Davies activities.

The supported aqueous species are free ``Ca+2`` and ``SO4-2`` plus the
neutral ``CaSO4`` ion pair. It does not include HSO4-, Mg, phosphate,
background electrolyte, or temperature correction.

Record fields: `ionic_strength`, `free_calcium_molal`, `free_sulfate_molal`, `calcium_sulfate_molal`, `total_calcium_molal`, `total_sulfate_molal`, `si_gypsum`, `si_anhydrite`.

Source module: `flahax.equilibrium`. Import with `from flahax import GypsumEquilibrium`.

### `calcite_co2_reference_values`

```text
calcite_co2_reference_values(result: 'CalciteCo2Equilibrium') -> 'dict[str, float]'
```

Map the supported kernel result to PHREEQC-fixture output names.

Source module: `flahax.equilibrium`. Import with `from flahax import calcite_co2_reference_values`.

### `davies_gamma`

```text
davies_gamma(charge: 'int', ionic_strength: 'float') -> 'float'
```

Activity coefficient from the Davies equation at 25 °C.

Source module: `flahax.equilibrium`. Import with `from flahax import davies_gamma`.

### `gypsum_reference_values`

```text
gypsum_reference_values(result: 'GypsumEquilibrium') -> 'dict[str, float]'
```

Map the supported gypsum kernel result to fixture output names.

Source module: `flahax.equilibrium`. Import with `from flahax import gypsum_reference_values`.

### `solve_calcite_co2_equilibrium`

```text
solve_calcite_co2_equilibrium(log_pco2: 'float', temperature_c: 'float' = 25.0) -> 'CalciteCo2Equilibrium'
```

Solve open-CO2 calcite equilibrium with charge balance and Davies activities.

Supported domain is exactly 25 °C. The equations are mass action for CO2,
carbonic acid, water, and calcite; electroneutrality; and iterative ionic
strength/activity-coefficient consistency. It deliberately excludes ion
pairing and all other phases, so it is a reference-tested kernel rather
than a general replacement for PHREEQC.

Source module: `flahax.equilibrium`. Import with `from flahax import solve_calcite_co2_equilibrium`.

### `solve_gypsum_equilibrium`

```text
solve_gypsum_equilibrium(temperature_c: 'float' = 25.0) -> 'GypsumEquilibrium'
```

Solve gypsum-saturated pure water at 25 °C.

For the dissolution reaction ``Gypsum = Ca+2 + SO4-2 + 2 H2O``, this
solves ``a_Ca * a_SO4 = 10**logK``. Electroneutrality gives equal free
calcium and sulfate molalities; their divalent charge gives
``I = 4 m_free``. The neutral complex obeys
``m_CaSO4 = 10**logBeta * a_Ca * a_SO4`` and contributes to totals but
not ionic strength. Anhydrite is evaluated at the same ion activity
product. This is deliberately a pure-water, 25 °C kernel.

Source module: `flahax.equilibrium`. Import with `from flahax import solve_gypsum_equilibrium`.

## flahax.equilibrium_delivery

### `EquilibriumPhPlan`

```text
EquilibriumPhPlan(recipe: flahax.delivery_quantities.FinalSolutionRecipe, water_analysis_id: str, water_mass_kg: float, reagent_id: str, reagent_channel_id: str, target_ph: float, equilibrium: flahax.aqueous_model.AcidResult, reagent_mass: flahax.delivery_quantities.MassGrams, reagent_volume_litres: float, nutrient_contribution: dict, loss: float, rows: tuple, audit: dict, warnings: tuple[str, ...], post_mix_measurement_required: bool = True, mode: str = 'catalogue-equilibrium-nitric', incidental_assessment: dict | None = None) -> None
```

Record fields: `recipe`, `water_analysis_id`, `water_mass_kg`, `reagent_id`, `reagent_channel_id`, `target_ph`, `equilibrium`, `reagent_mass`, `reagent_volume_litres`, `nutrient_contribution`, `loss`, `rows`, `audit`, `warnings`, `post_mix_measurement_required`, `mode`, `incidental_assessment`.

Source module: `flahax.equilibrium_delivery`. Import with `from flahax import EquilibriumPhPlan`.

### `plan_equilibrium_delivery`

```text
plan_equilibrium_delivery(recipe, *, water_mass_kg, water_totals, water_analysis_id, initial_ph, target_ph, reagent, reagent_channel_id, maximum_reagent_volume, targets, maximum_nutrient_error_percent, temperature_c=25.0, phases=(), maximum_concentrations=None)
```

Convert molal HNO3 into assay-qualified mass/volume and rescore nutrients.

`water_mass_kg` is the explicitly defined final solvent inventory, including
reagent carrier water; final recipe volume is the make-up volume. No density
or g/L == g/kg approximation is made. `phases` is the explicit equilibrium
policy; positive target SI or solid formation prohibits delivery validation.

Source module: `flahax.equilibrium_delivery`. Import with `from flahax import plan_equilibrium_delivery`.

## flahax.fertilizer_equilibrium

### `FertilizerEquilibrium`

```text
FertilizerEquilibrium(totals: 'FertilizerTotals', ph: 'float', ionic_strength: 'float', species: 'Mapping[str, float]', activities: 'Mapping[str, float]', saturation_indices: 'Mapping[str, float]', phase_allocations: 'tuple[PhaseAllocation, ...]') -> None
```

Species, activities, saturation indices, and equilibrium allocations.

Record fields: `totals`, `ph`, `ionic_strength`, `species`, `activities`, `saturation_indices`, `phase_allocations`.

Source module: `flahax.fertilizer_equilibrium`. Import with `from flahax import FertilizerEquilibrium`.

### `FertilizerTotals`

```text
FertilizerTotals(calcium: 'float' = 0.0, magnesium: 'float' = 0.0, phosphate: 'float' = 0.0, carbonate: 'float' = 0.0, sulfate: 'float' = 0.0, ammonium: 'float' = 0.0, nitrate: 'float' = 0.0, potassium: 'float' = 0.0, sodium: 'float' = 0.0, chloride: 'float' = 0.0) -> None
```

Analytical molal totals for the supported 25 °C aqueous system.

Record fields: `calcium`, `magnesium`, `phosphate`, `carbonate`, `sulfate`, `ammonium`, `nitrate`, `potassium`, `sodium`, `chloride`.

Source module: `flahax.fertilizer_equilibrium`. Import with `from flahax import FertilizerTotals`.

### `NitricAcidTargetPlan`

```text
NitricAcidTargetPlan(initial: 'FertilizerEquilibrium', target: 'FertilizerEquilibrium', nitric_acid_molal: 'float') -> None
```

Closed-carbon initial acid requirement at a requested target pH.

Record fields: `initial`, `target`, `nitric_acid_molal`.

Source module: `flahax.fertilizer_equilibrium`. Import with `from flahax import NitricAcidTargetPlan`.

### `plan_nitric_acid_target`

```text
plan_nitric_acid_target(totals, initial_ph, target_ph, *, trace_totals=None)
```

Nitric acid adds conserved nitrate in the full mixed aqueous model.

Source module: `flahax.fertilizer_equilibrium`. Import with `from flahax import plan_nitric_acid_target`.

### `solve_fertilizer_equilibrium`

```text
solve_fertilizer_equilibrium(totals, ph, *, allow_precipitation=True)
```

Public macro entry point; uses the same model as product/mixed solves.

Source module: `flahax.fertilizer_equilibrium`. Import with `from flahax import solve_fertilizer_equilibrium`.

## flahax.fertilizer_workflow

### `FertilizerWorkflow`

```text
FertilizerWorkflow(recommendation: dict, water: dict, nutrient_gap: dict, target_ph: float, stages: dict = <factory>, post_mix_measurement_required: bool = True) -> None
```

Record fields: `recommendation`, `water`, `nutrient_gap`, `target_ph`, `stages`, `post_mix_measurement_required`.

Source module: `flahax.fertilizer_workflow`. Import with `from flahax import FertilizerWorkflow`.

### `WorkflowStage`

```text
WorkflowStage(status: str, value: object = None, required_inputs: tuple = (), error_code: str | None = None, message: str | None = None) -> None
```

Record fields: `status`, `value`, `required_inputs`, `error_code`, `message`.

Source module: `flahax.fertilizer_workflow`. Import with `from flahax import WorkflowStage`.

### `plan_fertilizer_workflow`

```text
plan_fertilizer_workflow(salts, targets, water, target_ph, *, final_volume=None, equilibrium=None, nitric=None, titration=None, stocks=None, acids=None, maximum_concentrations=None)
```

Run available stages; expose missing inputs and rejected stages separately.

Water nutrient mg/L is mandatory ({} explicitly denotes zero nutrients).
It is never silently promoted to a complete acid/base analysis. Optional
configurations are mappings documented in docs/water-to-delivery.md.
No stage performs external writes, mixing or equipment operation.

Source module: `flahax.fertilizer_workflow`. Import with `from flahax import plan_fertilizer_workflow`.

## flahax.injector_sizing

### `size_injection_requirements`

```text
size_injection_requirements(*, duration_hours, channels, equipment_type, final_volume_litres=None, active_area_m2=None, gross_depth_mm=None)
```

Use final batch volume OR active irrigated area * gross depth.

Channel fields: final_litres_per_stock_litre, available_stock_litres.
Ratios use FINAL volume, not motive-water volume; output both definitions.
One mm over one m2 is one litre. Area is the concurrently irrigated zone,
not necessarily the whole farm. Gross depth already includes losses.

Source module: `flahax.injector_sizing`. Import with `from flahax import size_injection_requirements`.

## flahax.mixed_equilibrium

### `MixedFertilizerEquilibrium`

```text
MixedFertilizerEquilibrium(macro: flahax.fertilizer_equilibrium.FertilizerEquilibrium, trace: flahax.trace_equilibrium.TraceEquilibrium | None, ionic_strength: float, iterations: int, aqueous: flahax.aqueous_model.AqueousResult) -> None
```

Record fields: `macro`, `trace`, `ionic_strength`, `iterations`, `aqueous`.

Source module: `flahax.mixed_equilibrium`. Import with `from flahax import MixedFertilizerEquilibrium`.

### `solve_mixed_fertilizer_equilibrium`

```text
solve_mixed_fertilizer_equilibrium(totals, ph, *, trace_totals=None, allow_precipitation=True)
```

Source module: `flahax.mixed_equilibrium`. Import with `from flahax import solve_mixed_fertilizer_equilibrium`.

## flahax.ph_planning

### `PhPlan`

```text
PhPlan(water_analysis_id: 'str', titration_curve_id: 'str', reagent_id: 'str', direction: 'str', target_ph: 'float', source_alkalinity: 'MilliEquivalentsPerLitre', demand: 'MilliEquivalentsPerLitre', reagent_volume_litres: 'float', reagent_mass: 'MassGrams', nutrient_contribution: 'dict[str, MilligramsPerLitre]', loss: 'float', rows: 'tuple[dict, ...]', post_mix_measurement_required: 'bool' = True) -> None
```

A bounded initial pH-adjustment plan with re-scored nutrient balance.

Record fields: `water_analysis_id`, `titration_curve_id`, `reagent_id`, `direction`, `target_ph`, `source_alkalinity`, `demand`, `reagent_volume_litres`, `reagent_mass`, `nutrient_contribution`, `loss`, `rows`, `post_mix_measurement_required`.

Source module: `flahax.ph_planning`. Import with `from flahax import PhPlan`.

### `alkalinity_meq_per_litre`

```text
alkalinity_meq_per_litre(value: 'MilligramsPerLitre') -> 'MilliEquivalentsPerLitre'
```

Convert alkalinity reported as mg/L as CaCO3 into meq/L.

Source module: `flahax.ph_planning`. Import with `from flahax import alkalinity_meq_per_litre`.

### `plan_ph`

```text
plan_ph(water_analysis: 'Mapping[str, Any]', titration_curve: 'Mapping[str, Any]', reagent: 'Mapping[str, Any]', target_ph: 'float', final_volume: 'VolumeLitres', maximum_reagent_volume: 'VolumeLitres', achieved: 'Mapping[str, Any]', targets: 'Mapping[str, Any]') -> 'PhPlan'
```

Calculate a bounded initial dose and re-score its nutrient addition.

The source water must include measured pH and alkalinity. The measured
curve, not a generic acid formula, determines the dose at the target pH.

Source module: `flahax.ph_planning`. Import with `from flahax import plan_ph`.

## flahax.phase_allocation

### `PhaseAllocation`

```text
PhaseAllocation(phase: 'str', initial_moles: 'float', final_moles: 'float', delta_moles: 'float') -> None
```

Record fields: `phase`, `initial_moles`, `final_moles`, `delta_moles`.

Source module: `flahax.phase_allocation`. Import with `from flahax import PhaseAllocation`.

### `phase_allocation`

```text
phase_allocation(phase: 'str', initial_moles: 'float', final_moles: 'float') -> 'PhaseAllocation'
```

Record a phase result; positive delta means dissolution to aqueous phase.

Source module: `flahax.phase_allocation`. Import with `from flahax import phase_allocation`.

## flahax.phosphate

### `OrthophosphateSpeciation`

```text
OrthophosphateSpeciation(total_phosphate_molal: 'float', ph: 'float', ionic_strength: 'float', po4_molal: 'float', hpo4_molal: 'float', h2po4_molal: 'float', h3po4_molal: 'float', po4_activity: 'float', hpo4_activity: 'float', h2po4_activity: 'float', h3po4_activity: 'float') -> None
```

Uncomplexed phosphate species at a specified pH and ionic strength.

Record fields: `total_phosphate_molal`, `ph`, `ionic_strength`, `po4_molal`, `hpo4_molal`, `h2po4_molal`, `h3po4_molal`, `po4_activity`, `hpo4_activity`, `h2po4_activity`, `h3po4_activity`.

Source module: `flahax.phosphate`. Import with `from flahax import OrthophosphateSpeciation`.

### `orthophosphate_speciation`

```text
orthophosphate_speciation(total_phosphate_molal: 'float', ph: 'float', ionic_strength: 'float') -> 'OrthophosphateSpeciation'
```

Distribute total uncomplexed orthophosphate among four protonation states.

The calculation uses ``a_H = 10**(-pH)`` and the PHREEQC mass-action
reactions ``PO4-3 + nH+ = H_nPO4``. Davies coefficients convert activity
to molality. The declared domain is 0 <= ionic strength <= 0.1 mol/kgw;
outside it, this reduced Davies model is deliberately rejected.

Source module: `flahax.phosphate`. Import with `from flahax import orthophosphate_speciation`.

## flahax.phosphate_complexes

### `CalciumMagnesiumPhosphateSpeciation`

```text
CalciumMagnesiumPhosphateSpeciation(calcium_molal: 'float', magnesium_molal: 'float', phosphate_molal: 'float', sodium_molal: 'float', ph: 'float', ionic_strength: 'float', free_calcium_molal: 'float', free_magnesium_molal: 'float', free_phosphate_molal: 'float', hpo4_molal: 'float', h2po4_molal: 'float', calcium_hpo4_molal: 'float', magnesium_hpo4_molal: 'float', hydroxyapatite_si: 'float') -> None
```

Species and hydroxyapatite SI for a fixed-pH, fixed-I solution.

Record fields: `calcium_molal`, `magnesium_molal`, `phosphate_molal`, `sodium_molal`, `ph`, `ionic_strength`, `free_calcium_molal`, `free_magnesium_molal`, `free_phosphate_molal`, `hpo4_molal`, `h2po4_molal`, `calcium_hpo4_molal`, `magnesium_hpo4_molal`, `hydroxyapatite_si`.

Source module: `flahax.phosphate_complexes`. Import with `from flahax import CalciumMagnesiumPhosphateSpeciation`.

### `calcium_magnesium_phosphate_speciation`

```text
calcium_magnesium_phosphate_speciation(calcium_molal: 'float', magnesium_molal: 'float', phosphate_molal: 'float', sodium_molal: 'float', ph: 'float', ionic_strength: 'float') -> 'CalciumMagnesiumPhosphateSpeciation'
```

Solve source-defined Ca/Mg phosphate complexes at fixed pH and I.

The model is limited to 25 °C and I <= 0.1 mol/kgw. It includes the
phosphate acid forms, Ca/Mg phosphate complexes, and NaHPO4-; it does not
solve charge balance, pH, ionic strength, precipitation, or other ligands.

Source module: `flahax.phosphate_complexes`. Import with `from flahax import calcium_magnesium_phosphate_speciation`.

### `hydroxyapatite_hpo4_activity_at_equilibrium`

```text
hydroxyapatite_hpo4_activity_at_equilibrium(calcium_activity: 'float', ph: 'float') -> 'float'
```

Return the HPO4-2 activity at SI(Hydroxyapatite) = 0.

Uses the `phreeqc.dat` reaction
``Hydroxyapatite + 4H+ = 5Ca+2 + 3HPO4-2 + H2O``.
It is a thermodynamic boundary, not a precipitation-kinetics prediction.

Source module: `flahax.phosphate_complexes`. Import with `from flahax import hydroxyapatite_hpo4_activity_at_equilibrium`.

## flahax.product_conversion

### `ProductAnalyticalTotals`

```text
ProductAnalyticalTotals(chemistry: 'ProductChemistry', dose_g_per_kg_water: 'float', totals: 'Mapping[str, float]', counterions: 'Mapping[str, float]', ligands: 'Mapping[str, float]', inert_mass_fraction: 'float') -> None
```

Molal analytical components arising from a stated g/kg-water dose.

Record fields: `chemistry`, `dose_g_per_kg_water`, `totals`, `counterions`, `ligands`, `inert_mass_fraction`.

Source module: `flahax.product_conversion`. Import with `from flahax import ProductAnalyticalTotals`.

### `catalogue_dose_totals`

```text
catalogue_dose_totals(doses: 'Mapping[str, float]')
```

Convert every assayed catalogue element into one conserved basis.

Hydration water/inert carrier is outside mol/kg *water* totals. Iron sulfate
retains Fe(II); declared iron chelates retain Fe(III). Urea stays neutral and
unhydrolysed. Rounded product assays do not establish unassayed counterions.

Source module: `flahax.product_conversion`. Import with `from flahax import catalogue_dose_totals`.

### `convert_catalogue_product_dose`

```text
convert_catalogue_product_dose(product: 'Mapping[str, object]', dose_g_per_kg_water: 'float') -> 'ProductAnalyticalTotals'
```

Catalogue adapter. Equilibrium callers should retain the returned profile.

Source module: `flahax.product_conversion`. Import with `from flahax import convert_catalogue_product_dose`.

### `convert_product_dose`

```text
convert_product_dose(product: 'Mapping[str, object]', chemistry: 'ProductChemistry', dose_g_per_kg_water: 'float') -> 'ProductAnalyticalTotals'
```

Convert a library assay using an explicit chemistry profile.

Assays are elemental mass fractions.  Counterions/ligands are declared by
the chemical family; unassayed remainder is retained as inert carrier.

Source module: `flahax.product_conversion`. Import with `from flahax import convert_product_dose`.

### `plan_catalogue_nitric_target`

```text
plan_catalogue_nitric_target(doses, initial_ph, target_ph, *, water_totals=None, phases=())
```

Source module: `flahax.product_conversion`. Import with `from flahax import plan_catalogue_nitric_target`.

### `solve_catalogue_product_doses`

```text
solve_catalogue_product_doses(doses: 'Mapping[str, float]', ph: 'float', *, water_totals=None, allow_precipitation=True)
```

Solve the actual catalogue doses and stated water through one model.

Source module: `flahax.product_conversion`. Import with `from flahax import solve_catalogue_product_doses`.

## flahax.pump_planning

### `PumpCommand`

```text
PumpCommand(calibration_id: 'str', channel_id: 'str', requested_volume: 'VolumeLitres', runtime: 'DurationMinutes', volume_uncertainty: 'VolumeLitres', requires_operator_verification: 'bool' = True) -> None
```

Record fields: `calibration_id`, `channel_id`, `requested_volume`, `runtime`, `volume_uncertainty`, `requires_operator_verification`.

Source module: `flahax.pump_planning`. Import with `from flahax import PumpCommand`.

### `plan_pump_command`

```text
plan_pump_command(calibration: 'Mapping[str, Any]', requested_volume: 'VolumeLitres', available_volume: 'VolumeLitres', runtime_standard_deviation_minutes: 'float' = 0.01, *, as_of: 'datetime | None' = None, max_calibration_age_days: 'float' = 30.0) -> 'PumpCommand'
```

Calculate a bounded command; this function performs no device I/O.

Source module: `flahax.pump_planning`. Import with `from flahax import plan_pump_command`.

## flahax.stock_planning

### `StockPlan`

```text
StockPlan(recipe: 'FinalSolutionRecipe', injection_ratio: 'InjectionRatio', temperature: 'TemperatureCelsius', tanks: 'tuple[StockTankPlan, ...]', compatibility_rule_ids: 'tuple[str, ...]', solubility_limit_ids: 'tuple[str, ...]') -> None
```

A compatible, capacity-checked plan without any hardware command.

Record fields: `recipe`, `injection_ratio`, `temperature`, `tanks`, `compatibility_rule_ids`, `solubility_limit_ids`.

Source module: `flahax.stock_planning`. Import with `from flahax import StockPlan`.

### `StockSaltDose`

```text
StockSaltDose(salt_id: 'str', name: 'str', concentration: 'GramsPerLitre') -> None
```

Record fields: `salt_id`, `name`, `concentration`.

Source module: `flahax.stock_planning`. Import with `from flahax import StockSaltDose`.

### `StockTank`

```text
StockTank(tank_id: 'str', capacity: 'VolumeLitres') -> None
```

A physical tank available for a prepared stock solution.

Record fields: `tank_id`, `capacity`.

Source module: `flahax.stock_planning`. Import with `from flahax import StockTank`.

### `StockTankPlan`

```text
StockTankPlan(tank: 'StockTank', stock_volume: 'VolumeLitres', salts: 'tuple[StockSaltDose, ...]') -> None
```

Record fields: `tank`, `stock_volume`, `salts`.

Source module: `flahax.stock_planning`. Import with `from flahax import StockTankPlan`.

### `plan_stocks`

```text
plan_stocks(recipe: 'FinalSolutionRecipe', injection_ratio: 'InjectionRatio', tanks: 'Iterable[StockTank]', compatibility_rules: 'Iterable[Mapping[str, Any]]', solubility_limits: 'Iterable[Mapping[str, Any]]', temperature: 'TemperatureCelsius') -> 'StockPlan'
```

Assign a feasible recipe to compatible concentrated-stock tanks.

Stock concentration is ``final_g_per_litre * injection_ratio`` and each
used tank holds ``final_volume / injection_ratio``. The planner chooses the
first deterministic assignment using the fewest tanks, then tank-id order.

Source module: `flahax.stock_planning`. Import with `from flahax import plan_stocks`.

## flahax.struvite

### `struvite_saturation_index`

```text
struvite_saturation_index(magnesium_activity: 'float', ammonium_activity: 'float', phosphate_activity: 'float') -> 'float'
```

Return SI for MgNH4PO4:6H2O; inputs must be free-ion activities.

Source module: `flahax.struvite`. Import with `from flahax import struvite_saturation_index`.

## flahax.struvite_mixture

### `ChargeBalancedStruviteMixture`

```text
ChargeBalancedStruviteMixture(ph: 'float', ionic_strength: 'float', charge_residual: 'float', mixture: 'StruviteMixtureSpeciation', gypsum_si: 'float | None' = None, free_calcium_molal: 'float' = 0.0, free_sulfate_molal: 'float' = 0.0, calcium_sulfate_molal: 'float' = 0.0) -> None
```

Record fields: `ph`, `ionic_strength`, `charge_residual`, `mixture`, `gypsum_si`, `free_calcium_molal`, `free_sulfate_molal`, `calcium_sulfate_molal`.

Source module: `flahax.struvite_mixture`. Import with `from flahax import ChargeBalancedStruviteMixture`.

### `StruviteMixtureSpeciation`

```text
StruviteMixtureSpeciation(magnesium_molal: 'float', ammoniacal_nitrogen_molal: 'float', phosphate_molal: 'float', sodium_molal: 'float', ph: 'float', ionic_strength: 'float', free_magnesium_molal: 'float', ammonium_molal: 'float', free_phosphate_molal: 'float', struvite_si: 'float') -> None
```

Record fields: `magnesium_molal`, `ammoniacal_nitrogen_molal`, `phosphate_molal`, `sodium_molal`, `ph`, `ionic_strength`, `free_magnesium_molal`, `ammonium_molal`, `free_phosphate_molal`, `struvite_si`.

Source module: `flahax.struvite_mixture`. Import with `from flahax import StruviteMixtureSpeciation`.

### `solve_charge_balanced_struvite_mixture`

```text
solve_charge_balanced_struvite_mixture(magnesium_molal: 'float', ammoniacal_nitrogen_molal: 'float', phosphate_molal: 'float', sodium_molal: 'float', chloride_molal: 'float', calcium_molal: 'float' = 0.0, sulfate_molal: 'float' = 0.0) -> 'ChargeBalancedStruviteMixture'
```

Solve pH/I for the reduced Mg/NHx/P/Na/Cl aqueous system.

This is not a complete fertilizer-water solver: calcium, sulfate,
carbonate, other counter-ions, and solid precipitation are excluded.

Source module: `flahax.struvite_mixture`. Import with `from flahax import solve_charge_balanced_struvite_mixture`.

### `struvite_mixture_speciation`

```text
struvite_mixture_speciation(magnesium_molal: 'float', ammoniacal_nitrogen_molal: 'float', phosphate_molal: 'float', sodium_molal: 'float', ph: 'float', ionic_strength: 'float') -> 'StruviteMixtureSpeciation'
```

Solve Mg/P and NHx mass balances at supplied pH and ionic strength.

Source module: `flahax.struvite_mixture`. Import with `from flahax import struvite_mixture_speciation`.

## flahax.thermodynamics

### `MineralPhase`

```text
MineralPhase(name: 'str', dissolved_species: 'Mapping[str, float]', log_k: 'float', database: 'str', temperature_c: 'float') -> None
```

A dissolution phase with log K for one named database and temperature.

Record fields: `name`, `dissolved_species`, `log_k`, `database`, `temperature_c`.

Source module: `flahax.thermodynamics`. Import with `from flahax import MineralPhase`.

### `phase_saturation_index`

```text
phase_saturation_index(phase: 'MineralPhase', activities: 'Mapping[str, float]') -> 'float'
```

Return SI = log10(IAP) - log K from explicitly supplied activities.

Source module: `flahax.thermodynamics`. Import with `from flahax import phase_saturation_index`.

## flahax.trace_equilibrium

### `ChMicroProductDose`

```text
ChMicroProductDose(product_g_per_kg_water: 'float') -> None
```

Declared CH-micro assay converted from g product per kg water.

Product identity (declared by the project owner): Fe-EDTA, Mn-EDTA,
Zn-EDTA, Cu-EDTA, borax, and sodium molybdate.  One EDTA ligand per
chelated metal is an exact stoichiometric consequence of those names.

Record fields: `product_g_per_kg_water`.

Source module: `flahax.trace_equilibrium`. Import with `from flahax import ChMicroProductDose`.

### `ChMicroTotals`

```text
ChMicroTotals(iron: 'float' = 0.0, manganese: 'float' = 0.0, zinc: 'float' = 0.0, copper: 'float' = 0.0, edta: 'float' = 0.0, dtpa: 'float' = 0.0, eddha: 'float' = 0.0, citrate: 'float' = 0.0, boron: 'float' = 0.0, molybdate: 'float' = 0.0, calcium: 'float' = 0.0, magnesium: 'float' = 0.0) -> None
```

Analytical molal totals for the declared CH-micro components.

Record fields: `iron`, `manganese`, `zinc`, `copper`, `edta`, `dtpa`, `eddha`, `citrate`, `boron`, `molybdate`, `calcium`, `magnesium`.

Source module: `flahax.trace_equilibrium`. Import with `from flahax import ChMicroTotals`.

### `TraceEquilibrium`

```text
TraceEquilibrium(totals: 'ChMicroTotals', ph: 'float', ionic_strength: 'float', species: 'Mapping[str, float]', activities: 'Mapping[str, float]') -> None
```

Mass-balanced EDTA competition and B/Mo acid-base species at fixed pH.

Record fields: `totals`, `ph`, `ionic_strength`, `species`, `activities`.

Source module: `flahax.trace_equilibrium`. Import with `from flahax import TraceEquilibrium`.

### `solve_ch_micro_equilibrium`

```text
solve_ch_micro_equilibrium(totals: 'ChMicroTotals', ph: 'float', ionic_strength: 'float') -> 'TraceEquilibrium'
```

Fixed-I view of the same simultaneous aqueous mass-action model.

Source module: `flahax.trace_equilibrium`. Import with `from flahax import solve_ch_micro_equilibrium`.
