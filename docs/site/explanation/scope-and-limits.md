# Scope and limits

FlahaX helps growers and agronomists turn crop-feed targets, source-water analyses and
available products into a practical batch recipe. It formulates candidates, accounts for
fertilizer and pH-reagent contributions, and reports the finished feed and preparation
checks. The user reviews the result and chooses how to proceed.

## Supported workflows

| Goal | Required inputs | Supported operation and output |
|---|---|---|
| Calculate a finished-feed recipe | Nutrient targets, water contributions, available fertilizer records, target pH and offered reagents | Fertilizer and reagent quantities, achieved nutrients, residuals and calculated chemistry where supported |
| Revise feed targets from observations | A crop/system baseline, explicit corrections and irrigation EC; dated sample and guide values when using root-zone feedback | Auditable Sonneveld A–D targets and a preview bound to grower approval |
| Find an alternative recipe | Declared additional products, constraints and a search budget | Evaluated candidates and the best verified alternative found within that search |
| Verify rounded preparation | Final volume, stock strengths, rounding increments, tolerances, uncertainty and nutrient ceilings | Rounded dry weights, separate stock volumes, reagent dose, nutrient bounds and sampled pH |
| Plan concentrate delivery | Recipe, tank equipment, separation rules and applicable solubility evidence | Tank assignments, quantities and unresolved preparation qualifications |
| Review and repeat a calculation | TUI, batch or Python inputs; saved session or exported evidence | Reproducible inputs, calculation identity, batch sheet, report and JSON summary |

The ordinary TUI interview plans nutrient tanks and a separate reagent channel. The
Sonneveld profile path can verify direct preparation of a stated final volume with separate
product stocks. The available tank count and compatibility constraints determine which
concentrate layouts can be prepared. Missing mixture evidence remains visible for review.

Root-zone samples inform an explicitly approved feed adjustment. The grower or agronomist
chooses the correction and evaluates the crop response. Season-long crop management,
automatic control of recirculation or drainage, and operation of pumps or valves are outside
the supported workflow.

## What a passing result establishes

Each result retains the checks and assumptions actually used. Numerical target acceptance,
the configured rounded-preparation tolerance and crop suitability are separate decisions.
The [calculation guide](how-a-recipe-is-calculated.md) explains the tolerance values.
A bounded search reports its evaluated scope, and a budget-limited result can leave other
recipes unexplored.

Rounded preparation uses the stated uncertainty inputs. Nutrient bounds, sampled pH and
nominal saturation screening have the coverage described in that result. An unmeasured
supplier assay or equipment error still needs qualification. Root-zone approval binds the
reviewed feed design and does not certify physical preparation.

## Chemistry model conditions

- 25 °C, with Davies activity coefficients, for dilute solutions (ionic strength up to
  0.1 mol/kg water). Concentrated stock tanks are outside the model.
- Product oxidation states and the selected carbon condition are explicit. The worked
  Appendix I feed uses closed analytical inorganic carbon and fixed final solvent mass.
- Concentration and solvent-mass assumptions appear with the result. The common dilute
  approximation takes 1 L of finished solution as 1 kg of solvent water.
- Speciation and saturation indices support a thermodynamic phase assessment. Precipitation
  rates and what will form during actual mixing require physical evidence.
- Checked against pinned PHREEQC 3.8.6 (USGS) for every catalogue product, phase and acid case;
  see the [PHREEQC reference fixtures](../models/reference-fixtures.md) and the
  [coverage matrix](../models/chemistry-coverage-matrix.md).

## Preparation and measurement

| Check | Calculation and evidence | Physical qualification |
|---|---|---|
| Nutrient delivery | Water, fertilizer and reagent accounting with declared rounding and uncertainty | Actual water and product assays, scale and dispenser accuracy, finished-feed analysis |
| pH and EC | Modeled pH and estimated conductivity with reported applicability and bounds | Measurements after mixing under the actual temperature and gas-exchange conditions |
| Stock assignment | Separation rules, single-product solubility records and supplied mixture evidence | Dissolution, stability and compatibility at the actual grades, concentrations and temperature |
| Feed suitability | Targets, guide comparisons and approved corrections | Crop response and subsequent root-zone measurements |

FlahaX's aqueous model covers dilute feed. Concentrated mixtures need evidence applicable
to the stock conditions, supplied through the [stock qualification workflow](../agronomist/stock-assignments.md).
Single-product solubility data alone leaves a shared stock mixture unqualified.
Products without applicable data are identified in the result.

User-declared nutrient maxima apply as supplied. When no ammonium requirement is declared,
the default recipe fit additionally applies its reported incidental-ammonium allowance.
Review the limits actually used before selecting a candidate.

## Validation status and review actions

FlahaX has computational reference and software-test evidence. Laboratory and field
validation remain open under the [physical validation programme](../evidence/physical-validation-protocol.md).
The author's [computational assessment](../evidence/computational-review.md) records its scope
and provenance.

Read review notes for missing measurements, unsupported chemistry and stock qualifications.
For a blocked preparation, resolve the recorded input, equipment or constraint issue and
recalculate. Record measured pH and EC with the batch sheet, and obtain individual nutrient
analysis when checking the delivered composition.

The full-screen TUI supports the tested console interactions described in
[Run a batch](../grower/run-a-batch.md). The line-by-line interface is available through
`flahax mix --plain` when the console cannot support full-screen operation.

See the [changelog](../changelog.md) for dated changes and the
[migration guide](../start/migration.md) before replaying older saved workflows.
