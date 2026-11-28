# Migrate saved workflows

This guide covers upgrading **from 0.7.0 to 0.7.1** (first section) and **from 0.6.0 to 0.7.0**
(the table after it). 0.7.1 is prepared but not published; the latest publication recorded in
[release evidence](../evidence/release-evidence.md) is 0.7.0. Historical tests and benchmark
downloads describe their own revisions.

## Recalculate before accepting

1. Preserve original inputs, reports, product IDs, source revisions and acceptance records.
   Do not edit a saved result to make it pass.
2. Check the installed version and [strict file contracts](../reference/file-formats.md).
   Use explicit products, supported nutrient symbols and finite quantities.
3. Recalculate with the intended sources. Review independent statuses, limits, residuals,
   warnings and search qualifications.
4. Compare quantities by product ID and analytical basis. Equivalent optima can use
   different products; a smaller loss alone does not establish correctness.
5. Review stock and delivery requirements. Accept only the exact new result after its gates
   pass. Legacy unbound summaries cannot inherit acceptance.

No migration step operates equipment. Mathematical verification and physical validation
remain separate; field evidence is not invented to complete software work.

## From 0.7.0 to 0.7.1

Recalculate every saved recipe: a default recipe can differ. The [0.7.1 release
notes](https://github.com/rafatahmed/Flahax/blob/main/docs/releases/0.7.1.md) explain each change.

| Area | Migration action | Check |
|---|---|---|
| Ammonium | An absent or zero `N_NH4` is no requirement and no maximum, so a default recipe may use ammonium nitrate and reports its NH4-N. To keep the 0.7.0 behavior pass `max_ammonium_fraction=0.10`. | [Python API](../developer/python-api.md#incidental-ions-and-ceilings); tests.test_ammonium_limit |
| Total nitrogen | `N` is accepted as a target, alone or with forms; with a declared nitrate and a positive ammonium it must equal their sum (absent urea is zero) or the input is refused. Remove workarounds that dropped `N`. | [File formats](../reference/file-formats.md); tests.test_entry_inputs |
| Ranges and pH | Optional `deviation_ranges`, `--range-percent`, `--range`, `--require-ranges`, and a `target_ph` interval (`--ph-min`, `--ph-max`). Nothing changes unless you pass them. | [Water to delivery](../developer/water-to-delivery.md); tests.test_deviation_ranges |
| Stocks and solubility | `plan_stocks` no longer raises `missing_solubility_limit`: read `StockPlan.unverified` and `StockPlan.qualification`; a product without a limit at the tank temperature approves nothing. A solubility-limit record may state a `basis`. | [Assignments](../agronomist/stock-assignments.md); tests.test_stock_planning |
| Equipment | `--available-tanks`, `--tank-capacity` and `--fit-equipment` are new; the stock assignment may use more than two tanks (`tanks.tanks`). | [Assignments](../agronomist/stock-assignments.md); tests.test_equipment_input |
| Saved results | A saved result carries `supplied_inputs`; a recalculation reports `saved_input_differences`. Do not reuse an acceptance after an input differs. | [Results](../agronomist/reading-results.md); tests.test_saved_inputs |
| Product names | Two products with the same exact name are refused as `ambiguous_product_name`; rename one or use catalogue ids. | tests.test_entry_inputs |
| Numbers | A numeric string is no longer coerced in delivery contracts; pass numbers. A concentration above 2,000,000 mg/L, or a boolean, is an `InputError`; a maximum is not capped. A water file needs a finite `measured_ph`. | tests.test_edge_case_corpus |
| Solver errors | Messages gain a bracketed suffix (stage, iterations, residual) and `DeliveryError.details`. `solve` and `nitric_target` raise `DeliveryError`, not `TypeError`, for non-numbers. Match error codes, or the start of a message. | tests.test_convergence_diagnostics |
| Delivery plans | Composition refuses a pH plan, pump command or stock plan whose fields contradict each other (`cross_stage_constraint`). Plans built by the planners are unaffected. | [Delivery quantities](../developer/delivery-quantities.md); tests.test_composed_plan_rejections |
| Stage statuses | A workflow stage has one of five statuses: `calculated`, `requires_review`, `needs_input`, `blocked`, `not_calculated`. A stage made with any other status is refused (`STAGE_STATUSES` in `flahax.fertilizer_workflow`); map your own statuses to these. | [Water to delivery](../developer/water-to-delivery.md); tests.test_status_vocabulary |
| Numeric review tool | `tools/check_numeric_review.py` prints `fully_classified` and `scientifically_qualified` as separate outcomes and no longer prints one `valid` flag. A script that read `valid` must read both; a complete classification is not scientific qualification. | tests.test_numeric_review |
| Moved names | Import `run_batch` and `BatchOptions` from `flahax.batch_request`, the water reader from `flahax.water_input`, `read_json` and `number` from `flahax.inputs`, nitrogen rules from `flahax.nitrogen`, report helpers from `batch_summary`, `report_html`, `result_wording`, `report_format`; sixteen former `_helpers` lost their underscore. Names exported from `flahax` and all commands are unchanged. `validate_profile` no longer takes `total_n`; use `validate_targets`. | [Python API](../developer/python-api.md) |

## From 0.6.0 to 0.7.0: changes to account for

The table lists the 0.7.0 contracts as they were published; the 0.7.1 section above supersedes
its total-nitrogen and ammonium rows.

| Area | Migration action | Contract and executable check |
|---|---|---|
| Nutrient inputs | Explicit zero is a hard zero except absent/zero N_NH4 (no requirement); absent N_UREA is zero. Other omitted targets are incidental. Reject unknown fields. 0.7.0 also rejected total N; 0.7.1 accepts it (see above). | [File formats](../reference/file-formats.md); tests.test_entry_inputs |
| Objective | Remove nonzero ridge. Incidental ions and dose magnitude do not contribute to fitting loss. | [Python API](../developer/python-api.md); tests.test_unmet_targets |
| Maximums | In 0.7.0 the default incidental NH4 allowance was min(10% of target N, 1.5 mmol/L); in 0.7.1 it is opt-in through max_ammonium_fraction. An explicit NH4 maximum replaces it. Supply other caps explicitly. | [Python API](../developer/python-api.md#incidental-ions-and-ceilings); tests.test_ammonium_limit |
| Composition | Keep ID-bearing doses and counterions; review assay-only qualifications. | [Inventory](../models/material-inventory.md); tests.test_material_inventory |
| Units | Distinguish final litres, solvent kg, analytical totals and species; reconcile measured water explicitly. | [Basis](../models/concentration-basis.md); tests.test_unit_basis |
| Recipe/reagent | Choose joint mode with its controls or documented legacy mode. Count reagent nutrients once; search exhaustion is unresolved. | [Joint fitting](../developer/joint-problem.md); tests.test_joint_workflow |
| EC | `partial` and the assay and phosphate-fit refusals are gone: read `status` (`estimated` or `range`) and `ec25_range_ms_cm`; there is no midpoint. | [Conductivity](../developer/conductivity.md); tests.test_irrigation_ec |
| Phases | Phase evidence inputs and `blocks` are gone: read `risk` and `information`; saturation is not kinetics. | [Phase decisions](../developer/water-to-delivery.md#saturation-indices-and-acceptance); tests.test_chemistry_acceptance |
| Stocks | Respect separation and solubility applicability; equipment needs can exceed two tanks. | [Assignments](../agronomist/stock-assignments.md); tests.test_stock_planning |
| Delivery/remedies | Structural layouts, missing commands and unevaluated alternatives remain pending. Re-evaluate chosen remedies. | [Delivery](../developer/water-to-delivery.md); tests.test_delivery_plan |
| Acceptance | Recalculate after input/source/quantity changes; acceptance binds the exact result. | [Results](../agronomist/reading-results.md); tests.test_canonical_result |
| Outputs | Retain full-precision evidence; blocked quantities are diagnostic. | [Batch sheet](../grower/batch-sheet.md); tests.test_output_consistency |

## Sonneveld profiles and rounded preparation

1. Preserve the old source profile and session. Review the baseline, corrections,
   source-water basis, offered products and pH reagents in the new profile.
2. Import with `flahax mix --sonneveld-batch FILE`. Review the A-D targets before
   approving the dated root-zone sample and explicitly chosen feed correction.
   A changed observation/design needs a new approval; no crop response is inferred.
3. Supply product-stock strength, carrier, dry/stock/reagent rounding and uncertainty
   in the documented units. Choose nutrient ceilings/reserves explicitly. The 5%
   sodium reserve and tolerances in Appendix I are example inputs, not defaults
   that make every crop or product suitable.
4. Review the rounded delivered recipe, nutrient intervals, pH and preparation
   qualifications. A broader bounded search reports the best verified candidate
   found, not a global optimum or permission to use unavailable products.
5. Save under a new session name. The embedded profile supports repeat after
   removing the original import file; input/source/candidate guards still apply.
   A legacy session missing reagent availability requires `--review-reagents`
   and a new name. That review cannot waive other source/input drift checks.

See [exact file contracts](../reference/file-formats.md), the
[grower walkthrough](../grower/sonneveld-walkthrough.md) and the
[Appendix I calculations](../agronomist/sonneveld-appendix-i.md).
Package 0.7.0 is separate from the existing schema and model/source versions.
All 135 old package export names remain, but changed arguments/statuses and
acceptance bindings require review. No old result is automatically accepted.

## Executable migration check

This synthetic nutrient calculation demonstrates zero versus omitted targets. It does not
establish a usable crop formula, complete chemistry or physical validation.

```python
from flahax import load_library, recommend

product = next(p for p in load_library()["salts"] if p["formula"] == "KNO3")
allowed = recommend([product], {"K": 10})
forbidden = recommend([product], {"K": 10, "N_NO3": 0})
assert allowed["feasible"]
assert not forbidden["feasible"]
assert forbidden["unmetTargets"]
```

## Find and reproduce the documentation

- **Tutorial:** [first recipe](first-recipe.md), runnable from the installed package.
- **How-to:** this guide and [batch from files](../agronomist/batch-command.md).
- **Reference:** [generated API](../reference/api.md), [generated CLI](../reference/cli.md),
  and [file contracts](../reference/file-formats.md).
- **Explanation:** [calculation stages](../explanation/how-a-recipe-is-calculated.md)
  and [scope](../explanation/scope-and-limits.md).

Current-site Python fences run in isolated temporary directories. Signature summaries,
schema sketches and caller-owned-record templates are labeled separately; they are not
standalone programs. Complete synthetic repository scenarios run through tests.test_examples;
the README and nine packaged-manual examples run through tests.test_release_hygiene.

Existing old site URLs remain redirected. Historical audits, benchmarks and publication
records are retained. Documentation checks do not establish clean-package, full-coverage,
hosted-platform or live-reference acceptance of a future release.


## Removed agronomic presets and advice

The five University of Florida tomato presets are no longer shipped. Calls by
those preset names fail lookup; choose an explicitly reviewed target file instead.
Existing user-saved targets remain user inputs and are not silently rewritten.
Feed-pH range warnings and the residual-bicarbonate buffer warning are removed.
Calculated pH, bicarbonate inventories, explicit nutrient limits, and chemical
model applicability checks remain available. Crop suitability is not inferred
from software regression tests or extension guidance.
