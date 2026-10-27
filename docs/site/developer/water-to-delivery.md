# Water, nutrient targets and acid selection

Released in 0.3.1; measured-pH water balancing added in 0.4.0. This workflow
plans; it does not operate equipment or certify agronomic suitability.

## Separate inputs and separate acceptance

Crop targets and source-water contributions are nutrient concentrations in
mg/L of final working solution. For the pepper example, Ca target 104 minus
water contribution 20 gives an 84 mg/L fertilizer gap. Neither number is an
alkalinity measurement. `water={}` explicitly declares zero nutrient
contributions; omitting water is an error.

A zero nutrient target means no intentional requirement, not a prohibition on
counterions present in real fertilizers. `recommend` and `solve_weights` retain
their positive-target fit calculation and report additional fields:

- `incidentalContributions`: zero/omitted-target nutrients, actual ppm and review status.
- `limitViolations`: final ppm exceeding caller-supplied absolute maxima.
- `requiresReview`: incidental additions without a declared maximum.

Percentage deviation from zero remains `None`, not infinity or a fabricated
percentage. An explicit `maximum_concentrations={'N_NH4': 0}` does prohibit
ammonium. Without that maximum, incidental ammonium is reported for separate
assessment; the package does not invent a safe threshold or call it harmless.
The optimizer's existing objective is unchanged; maxima are post-solve checks,
not a new constrained optimization algorithm. A rejected recipe is not proof
that every alternative recipe is infeasible.

With the supplied pepper targets, twelve selected catalogue products and
water Ca 20 mg/L, the regression recipe has approximately 4.845193 mg/L NH4-N
and 0.047919 mg/L Na. Positive targets fit within 1%, but these incidental
amounts require review. These are catalogue-assay calculations, not a dosing
authorization. Since the 2026-10-18 catalogue correction, `Phosphoric Acid (75%)`
lists 23.706035% P (a 75% w/w aqueous product, dosed by product mass) and
Mg Nitrate is Mg(NO3)2·6H2O theory; the actual grade of each product still
requires confirmation before physical use.
See [traceable materials](../agronomist/formula-and-products.md) for supplying that grade or lot.

## Public orchestration

```python
from flahax import load_library, plan_fertilizer_workflow

library = {p['name']: p for p in load_library()['salts']}
result = plan_fertilizer_workflow(
    [library['Calcium Nitrate (ag grade)']],
    targets={'Ca': 104, 'N_NO3': 84 * 14.4 / 19, 'N_NH4': 0},
    water={'Ca': 20}, target_ph=6.5,
)
assert result.nutrient_gap['Ca'] == 84
assert result.stages['formulation'].status == 'requires_review'
assert result.stages['chemistry'].status == 'needs_input'
```

Each `WorkflowStage` exposes `status`, `value`, `required_inputs`, `error_code`
and `message`. Status is `calculated`, `requires_review`, `needs_input` or
`blocked`. A calculated stage is not a validated hardware delivery plan.
Earlier calculated stages remain available when a later stage is blocked.

`final_volume=VolumeLitres(...)` enables batch conversion. Additional keyword
configurations are mappings:

| Configuration | Required entries | Meaning |
|---|---|---|
| `equilibrium` | `water_totals`, `water_mass_kg`, `water_analysis_id`, `complete_analysis`, `carbon_boundary`, `temperature_c`, `phases` | Complete fixed-valence analytical component totals in mol/kg-water; explicit final solvent inventory, 25 C, closed carbon, explicit phase list ; optional `measured_ph` (with `alkalinity_eq_per_kg`, `balance_ion`, `maximum_imbalance_percent`) speciates the water at its measured pH and closes the charge on one ion instead of solving pH from charge balance |
| `acids` | `products`, `maximum_nutrient_error_percent`, `maximum_reagent_volume_litres` | Evaluate single-acid candidates; optional `preferred_product_id` forbids automatic fallback |
| `ph_adjustment` | `products`, `maximum_reagent_volume_litres` | Plan the recipe and its pH reagent together, acid or base, with the reagent's nutrients counted as supply (see below); optional `preferred_product_id` |
| `nitric` | `reagent`, `reagent_channel_id`, `maximum_reagent_volume`, `maximum_nutrient_error_percent` | Existing assay-qualified HNO3 delivery adapter; volume is `VolumeLitres` |
| `titration` | `water_analysis`, `curve`, `reagent`, `maximum_reagent_volume` | Existing matched-record measured-curve API; optional positive-target tolerance defaults to 1% |
| `stocks` | `injection_ratio`, `tanks`, `compatibility_rules`, `solubility_limits`, `temperature` | Existing typed stock planner, with sourced records and temperature-qualified limits |

`maximum_concentrations` is a separate top-level mapping of nutrient symbol to
maximum final mg/L. Checks include reagent nutrient contributions. Stock
compatibility calculations remain possible for an unapproved formulation;
they do not approve that formulation. A measured water titration curve is not
a measurement of the final fertilizer mixture; post-mix verification remains
mandatory. Nitric equilibrium plans with unreviewed incidental additions
cannot pass `validated_equilibrium` delivery composition.

## Measured-pH water balancing

**Two inventories, two uses (#84).** Nutrient targets and maximum
concentrations are always decided on the laboratory analysis after blending,
plus everything added (products and pH reagent), at the final volume. The
charge-balanced composition is an input to the chemistry only: pH, speciation,
saturation, EC and the reagent dose. Closing the charge on chloride or sodium is
a modelling step, not a corrected measurement, so it can never pass or fail a
limit. When it would change a limit decision, the plan asks for review and says
so; a laboratory-basis exceedance always blocks.

`balance_water_analysis(totals, measured_ph=..., alkalinity_eq_per_kg=None,
balance_ion='Cl-', maximum_imbalance_percent=5, phases=(), temperature_c=25,
analysis_id=None, balance_ion_uncertainty_percent=None, fixed=(),
below_detection=None)` speciates a laboratory analysis at its measured pH.

- **Zero, not measured, below detection.** A component given as 0 is a measured
  zero and is held fixed; an omitted component is not measured.
  `below_detection` records detection limits (mol/kg); those components enter
  the chemistry as 0 and are never adjusted. Inorganic carbon comes from
  `totals['CO3-2']` (0 for water measured carbon-free) or from titrated
  alkalinity (carbonate alkalinity: each carbon species counts 2 x C - H+
  relative to H2CO3, plus OH- - H+), never both; carbon not reported at all is
  `missing_carbon`.
- **Balance first.** If the composition's charge closes at the measured pH within
  `CLOSURE_TOLERANCE` (0.0001 % of its total ionic charge, a numerical
  tolerance), it is used unchanged (`reconciliation='unchanged'`) and no balance
  ion is needed: a chloride-free water does not fail because the default
  balance ion is chloride. Passing the 5 % screen does not make an analysis
  balanced.
- **Otherwise, explicit and bounded.** An imbalance above
  `maximum_imbalance_percent` is rejected (`charge_imbalance_exceeded`). The
  rest is closed on `balance_ion` (`Cl-` or `Na+`), as PHREEQC's `charge`
  option does, only if that ion is measured, positive and not fixed
  (`fixed_balance_ion`, `missing_balance_ion`). When the default `Cl-` is not
  measured, zero or below detection, only positive, nonfixed directly supplied carbon
  may use the legacy model-only fallback (`closed_on_alkalinity`). Titrated alkalinity,
  fixed carbon and carbon measured zero are held fixed. A measured titration without
  a suitable balance ion requires further input; no other ion is tried. With
  `balance_ion_uncertainty_percent` the adjustment must lie within that stated
  measurement uncertainty (`reconciled`, else `reconciliation_out_of_bounds`).
  Without it the closure is an assumption (`assumed`): the workflow's chemistry
  stage, and every plan built on it, is `requires_review` with the reason.
- **The record.** `analytical_totals` keeps the analysis as entered,
  `totals` the model; `balance_ion`, `balance_adjustment_molal`,
  `imbalance_percent`, `reconciliation`, `fixed`, `below_detection` and
  `analysis_id` record what was done. `diluted(fraction)` blends it with
  ion-free water: both inventories scale and the blend's chemistry is
  recomputed; the source's measured pH stays as metadata. Blending two real
  waters needs both analyses and is not supported.

In `plan_fertilizer_workflow`, either pass the laboratory totals with
`measured_ph` (and optional `alkalinity_eq_per_kg`, `balance_ion`,
`balance_ion_uncertainty_percent`, `fixed`, `below_detection`) in the
`equilibrium` record, or pass a prepared `water_balance` record (for example a
diluted blend) instead of `water_totals`. The `water` mg/L must be the
laboratory analysis; the balanced model's mg/L, or `water_balance` together with
`measured_ph` or with different `water_totals`, is rejected. The result's
`water_basis` lists laboratory and modelled water side by side and every limit
the balancing alone would flip. `plan_equilibrium_delivery` takes
`analytical_water_totals` (or a `BalancedWaterAnalysis` as `water_totals`): its
nutrient rows and limits use the analysis, its dose the chemistry. A plain
mapping without it keeps its previous meaning.

Why: calculated pH from charge balance alone is extremely sensitive to
analytical error in brackish water. For Shomar et al. (2024) station 104
(measured pH 7.80), charge balance alone gives pH 3.8. Matching the measured
pH needs 9.5% less chloride, and after that a further 0.5% change in chloride
still moves the calculated pH by about 0.45 units. Routine analyses carry
errors of that size, so only the measured pH can anchor the water.

## Calculated pH and model boundary

`calculate_equilibrium_ph(totals, complete_analysis=True,
carbon_boundary='closed', phases=[], temperature_c=25)` solves charge balance
using the existing coupled aqueous solver. It does not infer missing chloride,
carbon, alkalinity, oxidation states or balancing salts. Completeness is the
caller's declaration, not an inference from the nutrient list. Complete water
totals must also agree with the independently supplied water nutrient ppm on
the declared mass/volume basis. Catalogue identity, formula and assay must
match before the chemistry stage converts fertilizer doses.

The 25 C reaction set, Davies ionic-strength bound, phase allocation and
convergence errors remain enforced. `phases=[]` means aqueous-only modelling,
not proof that precipitation is impossible. Solids, or supersaturation of a
phase that forms readily at feed conditions, prevent acid-plan acceptance; see
[saturation indices and acceptance](#saturation-indices-and-acceptance). Calculated pH is restricted to [0,14], with a
charge residual of at most 1e-12 mol-charge/kg-water. The present complete
mixed reference is checked within 0.01 pH units at initial and acidified states.

Solvent mass and final volume are explicit fixed-final-inventory quantities;
include reagent carrier water in that inventory. Do not interpret them as
an arbitrary initial tank mass followed by unaccounted dilution. Gas exchange,
redox evolution, temperatures other than 25 C and concentrated-stock activity
models are not added here.

USGS documents concentration units and `pH ... charge` in the
[PHREEQC SOLUTION reference](https://water.usgs.gov/water-resources/software/PHREEQC/documentation/phreeqc3-html/phreeqc3-48.htm).
That charge-balance method does not make a nutrient-only water table complete.

## Acid candidates

The standard `plan_fertilizer_workflow` accepts **HNO3 and H3PO4 only**.
The lower-level `plan_acid_options` retains aqueous HNO3, H3PO4, H2SO4 and
C6H8O7 support for compatibility with existing scientific fixtures; sulfuric
and citric acids are not offered by the standard site workflow.
Each record supplies `id`, `source`, `revision`, `recordedAt`,
`chemicalFormula`, `massFraction` (pure acid/product mass, 0–1) and
`densityKgPerL`. Hydrated citric solids must first be represented by a defined
aqueous stock; no density or purity is guessed.

Demand is solved against the same mixed model by adding conserved nitrate,
phosphate, sulfate or citrate respectively. Citric acid is not inorganic
carbon, and its complexes remain part of the model. Commercial mass/volume
and nitrate-N/P/S additions are calculated and rescored against the crop
targets. Candidates may be accepted, rejected or require incidental review.
Only accepted candidates can be selected. Automatic ranking minimizes final
nutrient loss, with input order breaking ties; this is not a recommendation
that the lowest-loss acid is operationally or agronomically best. No acid
blending, cost optimization, handling protocol or autonomous dosing is added.

## Recipe and pH reagent together

The `acids` stage evaluates an acid against a recipe that already meets every
target, so the acid's own nitrate, phosphorus or sulfur pushes the recipe past
its targets and the plan is rejected. `ph_adjustment` plans them together:

1. The recipe is fitted without pH reagents. Acids (nitric, phosphoric,
   sulfuric, citric) are not offered as nutrient salts here: phosphoric acid
   chosen as a P source drove five shipped formulas to pH 3.0-3.4 in RO water.
2. The mixed feed is speciated at its calculated pH. Below the target it needs
   a base; above it, an acid. Products of the other direction are reported as
   `not_applicable`.
3. For each applicable product, the dose that brings the mixed feed to the
   target pH is solved on the same equilibrium model. Its nutrients (N from
   nitric acid, P from phosphoric acid, K from the bases) are counted as supply,
   like the water's, and the recipe is fitted again. This repeats until the
   recipe and the dose agree; if the recipe switches products between nearby
   doses, the two bracketing product recipes are blended. Charge balance is solved
   on each actual mixture; pH values are never interpolated. A trial that crosses
   to the opposite reagent direction bounds the search but cannot be returned as
   a plan. The final dose is independently recalculated, and nutrient rows, limits,
   source attribution and unmet-target diagnostics are rebuilt from that recipe.
   A missing charge bracket or dose disagreement reports nonconvergence.
4. Every candidate reports its dose (mol/kg water, product grams and, with a
   density, litres), nutrient contribution, recipe and target-pH state, even
   when it is rejected. A plan is selected only from accepted candidates, by
   lowest final nutrient loss.

This search is not a global joint-optimization certificate. Recipe selection can
change when the nutrient objective changes; an acid-only inventory may become
inapplicable if the new unadjusted recipe needs a base. Existing targets and
maximum concentrations remain unchanged.

A recipe that misses a target still gets a pH plan: the miss stays in the
recipe's `unmetTargets`. Bases are added as K+ with implicit hydroxide (KOH),
or with inorganic carbon (KHCO3, K2CO3) under the closed carbon boundary.
`catalogue_ph_reagents()` returns sourced records for the catalogue's three
pH-up products (Potassium Hydroxide (45% solution), Potassium Bicarbonate,
Potassium Carbonate); acids are supplied by the user with the assay and density
from the supplier's certificate. A plan is rejected when its target state has
solids, unresolved SI sign, or supersaturation without applicable evidence
(next section).

## Saturation indices and acceptance

A positive saturation index is a thermodynamic finding, not a precipitation rate.
No phase name grants an exemption. Supersaturation without matching reviewed
kinetic/redox evidence prevents approval, including Hydroxylapatite, Goethite,
MnHPO4 and Vivianite. The MnHPO4 measurement/source chain remains unverified;
that is not proof that measurements or precipitation do not exist.

`assess_saturation` reports `thermodynamic`, `applicability`, `solids`, and
`invalid_solids` separately. The existing SI comparison guard is numerical only.
An SI interval touching zero has `uncertain_sign` and prevents approval; a
caller-supplied SI uncertainty half-width can widen that interval but cannot
remove the guard. It is not a kinetic allowance or a certified model-error bound.
Any positive allocated solid prevents approval, even below the old reporting
cutoff or when the reported SI is negative. Invalid SI/allocation data fail closed.
Negative infinity denotes an absent-reactant index, not a finite uncertainty interval.

The optional `conditions` and `evidence` mappings support explicit applicability
review. A phase-specific evidence record must contain `phase`, `source`,
`review_id`, `reviewed=True`, `decision="review_only"` and a `conditions` envelope.
It must specify temperature (C), pH, ionic strength (mol/kg water), holding time
(hours), redox and solution-matrix identity. Numeric envelopes are inclusive
pairs; categorical conditions must match exactly. All additional conditions in
the record must match too. State pH and ionic strength take precedence over
caller values. Missing, unreviewed or out-of-envelope evidence cannot exempt a
phase. These are caller-reviewed evidence records, not automatically verified
source claims. No physical applicability envelopes ship with FlahaX.

Matching evidence permits review only: `mixing_approved` remains false. The
public workflows use the conservative default and do not infer holding time,
redox, matrix identity or evidence from a phase name. Mathematical completion
requires testing these decisions, not waiting for future physical experiments.
Iron(II) has a fixed oxidation state in this model; its advisory does not invent
an oxidation half-life or guarantee which real solids will form.

## Reproducible evidence

`tests/test_water_workflow.py` covers water subtraction, incidental review and
explicit maxima, calculated pH against the existing mixed PHREEQC reference,
synthetic end-to-end stock/acid planning and rejection boundaries.
`tests/test_acid_reference.py` checks four additional independent acid cases,
charge balance, component conservation, hashes and live replay.

Captures are under `tests/fixtures/phreeqc/acid_selection/{HNO3,H3PO4,H2SO4,C6H8O7}`.
Each contains input, full output, screen output, selected output and expected
JSON with hashes/provenance/tolerances. These are synthetic NaCl-background
references, not validation of every possible real-water acid combination.
Dose tolerance is 3% relative plus 1e-9 mol/kg-water, pH tolerance 0.01, and
PHREEQC charge error must not exceed 0.1%. The existing database and all prior
product/phase/failure captures are preserved.

Generate review candidates using
`python tools/acid_selection_evidence.py --output NEW_DIRECTORY`.
The destination must be new and outside the immutable historical fixture tree;
existing captures and their comparison budgets are never replaced by this command.
It uses the pinned external 3.8.6-17100 installation and temporarily merges
unchanged `minteq.v4.dat` with the existing chelate and phase extensions. No
executable or merged database is checked in.

(local-validation-2026-09-28)=
## Historical validation

Dated development checks are preserved in the
[planning validation history](../evidence/planning-validation-history.md#water-to-delivery-validation).
They record those runs only and do not establish current release validation.

See [total alkalinity and carbon inference](../models/total-alkalinity.md) for the
qualified inorganic proton reference and distinct water JSON titration field.


## Size channels and reconcile delivery

Use `size_injection_requirements` with final batch litres, or concurrently active
area in m2 times gross depth in mm, plus duration in hours. Specify each channel's
final-litres-per-stock-litre ratio and actual available prepared stock litres.
For a 120 L batch over two hours, ratios 100, 200 and 400 require 1.2, 0.6 and
0.3 L respectively; their additive carrier remainder is 117.9 L. Per-channel
flows are 0.6, 0.3 and 0.15 L/h. These numbers follow direct division and summation,
not empirical equipment performance.

Transfer each required channel volume to `plan_pump_command` using its own
calibration and inventory. Include every fertilizer channel and the separately
planned reagent channel once. A pump command's runtime is litres divided by
calibrated litres/minute. Reconcile the resulting commands with
`compose_delivery_plan` before advancing the draft.

A final-volume ratio is not a motive-water injector setting. Common-carrier
percentages use the shared carrier remainder; serial devices see different local
flows. Manufacturer operating curves, pressure differential, turndown and stock
properties remain necessary to select hardware. No contact-time, contraction or
hydraulic mixing model is supplied, and no equipment is operated.


## Canonical calculation and export identity

`plan_fertilizer_workflow` retains a `canonical_result`: an immutable JSON snapshot
of normalized inputs, complete stage values (including selected and rejected
candidates), package version and SHA-256 fingerprints of packaged Python/JSON
model sources. Its `result_id` identifies that exact calculation content.
`to_dict()` returns a detached copy. Changing the workflow after calculation or
supplying different product records to `summarize_batch` raises
`canonical_result_mismatch`; rerun the calculation with the intended inputs.

The summary retains `calculation_identity` with the calculation ID and input,
source, weighed-recipe and actual-state fingerprints. An unavailable state has
no state fingerprint. `export_identity` binds all final export fields. Batch
metadata is added before final export sealing. Report-time tank ratios, temperatures
and display metadata belong to the export identity; the calculation ID identifies
the preceding workflow snapshot. HTML, sheets and terminal views
check bound exports and reject later edits. The same calculation reference
appears in reports, sheets and the plain terminal summary. These hashes establish
content identity, not authenticity, independent review or scientific validity.

Legacy manually assembled workflows have `legacy_unverified` identity and cannot
claim a bound calculation. Synthetic presentation fixtures explicitly remove their
calculation identity; they are not production acceptance evidence. A stored export
can still be rendered on a newer installation: its identity describes its retained
calculation, whereas a live workflow rejects model-source changes before reporting.

The `statuses` mapping preserves independent formulation, chemistry, phase, pH,
EC, stock, delivery, physical and overall qualifications. Numerical convergence is
`not_reported` because the legacy recommendation does not expose a convergence
certificate; feasibility is not substituted for one. Delivery and physical
validation remain `not_validated`. Overall blocking retains the existing precedence;
no successful stage promotes an unrelated unsupported stage to success.


## Evaluate remedies without changing the original plan

Pass `remedy_options` and an explicit `max_remedy_evaluations` budget to
`plan_fertilizer_workflow`. The default budget is 20 workflow evaluations.
Each option has a unique `id`, `kind` and `changes` mapping:

- `catalogue`: `changes.products` is a bundle of product records to add to the
  supplied pool. `available: true` confirms the whole bundle is available.
  All products are fitted together, retaining permissions, targets and maxima.
  Changed assays need new record IDs; an existing record cannot be overwritten.
- `treatment`: `changes.water` supplies the treated nutrient analysis and
  `changes.equilibrium` supplies its equilibrium configuration. `evidence.source`
  and `evidence.revision` identify the supplied analysis. No removal efficiency,
  water composition or treatment performance is invented. Missing chemistry
  inputs remain unresolved even when nutrient constraints improve.
- `equipment`: `changes.stocks` supplies the complete stock-planning configuration.
  Tank capacity, separation, solubility and mixture-model qualification are
  rechecked. Additional tanks alone do not establish mixture compatibility.

```python
workflow = plan_fertilizer_workflow(
    available_products, targets, measured_water, target_ph,
    final_volume=VolumeLitres(100),
    remedy_options=[{
        "id": "available-bundle", "kind": "catalogue", "available": True,
        "changes": {"products": additional_available_products},
    }],
    max_remedy_evaluations=5,
)
```

`workflow.remedies.requirements` provides a next action for every unmet nutrient,
violated maximum and unfinished stage. Scoped structural proofs remain attached;
failed numerical searches never become global impossibility claims. The original
recipe and water are retained. Explicitly rerun with the chosen inputs to adopt a
scenario; there is no automatic replacement or external action.

Each option reports `potential_remedy`, `not_evaluated`, `evaluation_failed`,
`evaluated_no_resolution` or `evaluated_candidate`. An evaluated candidate resolves
at least one baseline requirement; it can still introduce or retain other issues.
Inspect `resolved_requirements`, `introduced_requirements` and
`remaining_requirements`, plus the immutable candidate `snapshot` and
`calculation_id`. These results do not imply delivery or physical approval.

The search covers only the supplied scenarios and product bundles. It does not
combine separate options automatically, enumerate the whole market, prove a
minimum-cost equipment solution or select a manufacturer model. Budget skips and
conditional options make `search_incomplete` explicit. `declared_options_evaluated`
only means the supplied scenarios were attempted, not that a solution exists.

The JSON `workflow` command accepts the same option fields. Its equipment options
use the existing stock JSON shape (`final_litres_per_stock_litre`, `temperature_c`
and tanks with `id`/`capacity_litres`). Python callers use the typed stock values.


## Exact-result acceptance and saved-state schemas

`flahax.result_acceptance.accept_result(summary, actor=..., reason=...)` records
explicit consent to the exact proposal in a bound summary. It does not change
calculation statuses or waive any guard. Actor and reason are explicit caller
inputs; attribution is not authenticated. A blocked zero/hard limit stays blocked,
an unassessed EC stays unassessed, and physical validation stays separate.

The schema-version-1 acceptance record contains `scope=exact_result_proposal`,
`actor`, `reason`, a timezone-qualified `recorded_at`, `result_id` and
`export_sha256`. `verify_acceptance` rejects changed doses, inputs, state, evidence,
source identity or export metadata, including a modified export that was resealed.
Recalculation requires fresh explicit acceptance if its content differs. Hashes
identify content; they do not establish authenticity or scientific validity.

`save_result(summary, acceptance=None)` builds an archive with `schema_version=1`,
`payload={summary, acceptance}` and the payload `sha256`. Saving alone creates no
consent. `load_result` validates both the archive and its nested identities and
returns a detached payload. `Store.save('results', name, archive)` and
`Store.load('results', name)` validate the same contract. Use
`batch_cli.render_saved_result(archive)` to validate before rendering an archived
result. Historical results preserve their historical source identities; rendering
is not recalculation against the current engine.

New saved mix sessions retain their answer fields and add `saved_state` with
`schema_version=1`, `inputs_sha256`, named-item `references` fingerprints and
package `sources` fingerprints. Execution rejects changed answers, referenced
water/formula/product/reagent files or model sources. Unknown schema versions and
malformed metadata fail explicitly. Both terminal interfaces use the shared store
and option conversion; neither grants consent automatically.

### Migrating saved sessions

Legacy answer-only sessions remain readable and rerun using current inputs. They
have no asserted historical provenance or result consent. Legacy `accepted` or
`acceptance` fields are rejected on ordinary load: they cannot become approval of
another result. No files in the user's home are migrated automatically.

After reviewing the answers and current referenced records, call
`mix_store.migrate_session(store, old_answers)` to obtain a new bound session,
then save it under a reviewed name with `store.save('sessions', name, migrated)`.
Migration discards old consent and old fingerprints; it captures current inputs,
not reconstructed history. The original dictionary/file is unchanged. Rerun the
calculation and review the new result before creating any new acceptance record.
