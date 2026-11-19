# Migrate saved workflows

This guide applies to the **0.7.0 release**, upgrading from 0.6.0
or an intermediate development checkout. No 0.7.0 package upload is claimed. The latest
publication recorded in [release evidence](../evidence/release-evidence.md) is 0.6.0.
Historical tests and benchmark downloads describe their own revisions.

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

## Changes to account for

| Area | Migration action | Contract and executable check |
|---|---|---|
| Nutrient inputs | Explicit zero is a hard zero except absent/zero N_NH4 (no requirement); absent N_UREA is zero. Other omitted targets are incidental. Reject total N and unknown fields. | [File formats](../reference/file-formats.md); tests.test_entry_inputs |
| Objective | Remove nonzero ridge. Incidental ions and dose magnitude do not contribute to fitting loss. | [Python API](../developer/python-api.md); tests.test_unmet_targets |
| Maximums | Default incidental NH4 allowance is min(10% of target N, 1.5 mmol/L). An explicit NH4 maximum replaces it; max_ammonium_fraction=None disables it. Supply other caps explicitly. | [Python API](../developer/python-api.md#incidental-ions-and-ceilings); tests.test_ammonium_limit |
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
