# Migrate saved workflows

This guide applies to **0.6.1.dev0**, an unpublished development version. The latest
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
| Nutrient inputs | Zero is a hard zero; omitted targets are incidental. Reject total N and unknown fields. | [File formats](../reference/file-formats.md); tests.test_entry_inputs |
| Objective | Remove nonzero ridge. Incidental ions and dose magnitude do not contribute to fitting loss. | [Python API](../developer/python-api.md); tests.test_unmet_targets |
| Maximums | Supply ammonium and other caps explicitly; omitted data does not select crop limits. | [Python API](../developer/python-api.md#incidental-ions-and-ceilings); tests.test_ammonium_limit |
| Composition | Keep ID-bearing doses and counterions; review assay-only qualifications. | [Inventory](../models/material-inventory.md); tests.test_material_inventory |
| Units | Distinguish final litres, solvent kg, analytical totals and species; reconcile measured water explicitly. | [Basis](../models/concentration-basis.md); tests.test_unit_basis |
| Recipe/reagent | Choose joint mode with its controls or documented legacy mode. Count reagent nutrients once; search exhaustion is unresolved. | [Joint fitting](../developer/joint-problem.md); tests.test_joint_workflow |
| EC | Preserve estimated/partial/unsupported status. A subtotal is not a total, bound or midpoint. | [Conductivity](../developer/conductivity.md); tests.test_irrigation_ec |
| Phases | Replace phase-name exemptions with condition-qualified evidence; saturation is not kinetics. | [Phase decisions](../developer/water-to-delivery.md#saturation-indices-and-acceptance); tests.test_chemistry_acceptance |
| Stocks | Respect separation and solubility applicability; equipment needs can exceed two tanks. | [Assignments](../agronomist/stock-assignments.md); tests.test_stock_planning |
| Delivery/remedies | Structural layouts, missing commands and unevaluated alternatives remain pending. Re-evaluate chosen remedies. | [Delivery](../developer/water-to-delivery.md); tests.test_delivery_plan |
| Acceptance | Recalculate after input/source/quantity changes; acceptance binds the exact result. | [Results](../agronomist/reading-results.md); tests.test_canonical_result |
| Outputs | Retain full-precision evidence; blocked quantities are diagnostic. | [Batch sheet](../grower/batch-sheet.md); tests.test_output_consistency |

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
