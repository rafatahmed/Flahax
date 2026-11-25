# Physical validation protocol (draft)

**Draft for independent review.** This is the protocol that issue #41 asks to have reviewed
before any data is collected. It is a design, not a record of work done. Nothing in this
document authorizes laboratory spending, external outreach or experiments; each needs its own
specific approval (see section 10).

FlahaX contract clause Q25 requires measured evidence for any real-mixture predictive accuracy
that is claimed. FlahaX claims none today. This protocol defines what evidence would have to
exist before such a claim could be made, and for which conditions.

## 1. What this protocol can and cannot show

Three kinds of agreement are kept apart in every report and never added together:

| Kind | Question | Where it is already covered |
|---|---|---|
| Model and data uncertainty | How uncertain are the thermodynamic constants, assays and activity model? | Source notes, `docs/site/developer/verification.md` |
| Implementation agreement | Does FlahaX compute what its reference model computes? | Benchmark v1, PHREEQC comparisons |
| Measured physical agreement | Do real solutions behave as predicted? | **This protocol** |

A result may support a claim only for the conditions that were tested: the waters, products,
concentration ranges, pH range and temperature actually measured. No claim extends beyond them.

## 2. Quantities and what would be claimed

Each quantity gets its own acceptance criterion, set before any measurement (section 7).

| ID | Quantity | Measured with | Existing FlahaX support |
|---|---|---|---|
| Q-pH-mix | pH of the mixed solution before any reagent | calibrated pH meter | `stock_evidence.batch_ph`, `docs/measured-batch-ph-records.md` |
| Q-pH-acid | Reagent volume to reach a target pH (titration curve) | burette or calibrated dosing, pH meter | `titration_curve` records, `plan_ph` |
| Q-EC | Electrical conductivity at 25 °C | calibrated conductivity meter | `compare_measured_ec` (reports the difference, no verdict) |
| Q-ion | Final concentration of each target nutrient | ICP-OES or ion chromatography, accredited laboratory | nutrient accounting (already independently reconstructed) |
| Q-stab | Whether a precipitate forms over 24 h at stated conditions | visual and turbidity reading, dated | `docs/measured-batch-stability.md` |

Not in scope: plant response, agronomic benefit, long-term storage, microbial effects, and any
temperature other than the one tested.

## 3. Materials and provenance

- **Reagents.** Analytical grade where an analytical-grade form exists; commercial fertilizer
  grade for the products a grower would actually use. For every lot record: product name,
  supplier, lot number, stated assay, certificate, date opened, and the assay FlahaX was given.
- **Water.** Reverse-osmosis or deionized water, with its measured pH and EC recorded before use.
  A second, hard natural water of fully analyzed composition is added only after the first stage passes.
- **Instruments.** Meter and electrode identity, calibration buffers and their lot and expiry,
  calibration record before each session, temperature probe identity.
- **Records.** Every measurement uses the existing record structure (`record_id`, `source`,
  `method`, `measured_on`, `temperature_c`, `uncertainty_basis`, `meter_id`, `electrode_id`).

## 4. Staged design

Each stage must pass its predefined criteria before the next begins. A failed stage is
published and stops the claim for the conditions it covers.

1. **Stage 0: instrument checks.** pH buffers at the working range and a KCl conductivity
   standard at 25 °C. Establishes measurement uncertainty. No FlahaX prediction is tested.
2. **Stage 1: single salts.** Each fertilizer salt alone in RO water at three concentrations
   (low, mid, high of the intended range). Tests EC and pH of the simplest cases.
3. **Stage 2: two-salt and tank-A/tank-B pairs.** Tests the interactions the planner actually
   separates (calcium with phosphate or sulfate), including a deliberately incompatible pair
   to confirm the model's precipitation warning.
4. **Stage 3: full recipes.** At least three recipes from different crop formulas, made up
   from the FlahaX batch plan exactly as printed. Measure Q-pH-mix, Q-EC, Q-ion and Q-stab.
5. **Stage 4: pH adjustment.** For each Stage 3 recipe, titrate with each planned reagent and
   compare the measured volume for the target pH with the planned volume (Q-pH-acid).
6. **Stage 5: a second water.** Repeat a subset of Stage 3 and Stage 4 in the hard natural water.

## 5. Preparation procedure (fixed in advance)

1. Record room and solution temperature; hold at 25.0 ± 0.5 °C (the model's only temperature).
2. Weigh each product to the planned mass on a balance with recorded calibration; record the
   mass actually weighed, not the mass planned.
3. Dissolve in the order and tank grouping the FlahaX plan prints; stock tanks are diluted
   to final volume with the planned injection ratio, using volumetric glassware of recorded class.
4. Stir for a fixed time, then rest for a fixed time before each reading. Closed vessel (the
   model assumes no CO2 exchange); record any opening.
5. Readings: pH and EC in the same sample, in a fixed order, with the temperature recorded.
6. Replicates: independent preparations, not repeated readings of one preparation (section 7).

## 6. Frozen predictions

Before the first measurement of a stage, a prediction file is produced and sealed:

- FlahaX version and commit, the input files, and their SHA-256 hashes;
- the predicted pH, EC, nutrient concentrations and any precipitation warning;
- the exact planned masses and volumes.

The file is hashed and stored with the date. Predictions are never regenerated after data are
seen. If an input was wrong, the stage is repeated with a new frozen file and the earlier
result stays in the record.

## 7. Replicates, uncertainty and acceptance criteria

These rules are fixed here; the numbers marked **to be set by the reviewer** must be written
into the approved protocol before data collection and cannot change afterwards.

- **Replicates.** At least **n = to be set by the reviewer (proposal: 5)** independent preparations
  per condition.
- **Measurement uncertainty.** An uncertainty budget for each instrument and quantity: calibration
  bias and uncertainty, resolution, temperature, repeatability across replicates. The pH budget
  follows the existing conservative rule in `docs/measured-batch-ph-records.md`
  (bias + calibration uncertainty + batch uncertainty, no root-sum-square reduction).
- **Acceptance rule.** For each quantity, a prediction **agrees** with measurement when
  `|measured − predicted| ≤ model tolerance + expanded measurement uncertainty`, where the model
  tolerance for each quantity is **to be set by the reviewer** (a number with its stated basis)
  before any data exist. Agreement is judged per replicate set, not on averages alone.
- **Reported outcome per quantity:** agrees, disagrees, or inconclusive (uncertainty larger than
  the tolerance). Inconclusive is never reported as agreement.
- **Exclusions.** A replicate is excluded only for a reason on this list, written before data
  collection: calibration failed the post-session check; a recorded procedure deviation (spill,
  wrong mass); instrument fault. Exclusions are published with the reason. Outliers are not
  excluded for being inconvenient.
- **No tuning.** FlahaX constants and defaults are not adjusted to improve agreement during the
  study. Any model change is a new version and restarts the affected stages.

## 8. Claims allowed from the results

A claim names the quantity, the stages passed, the conditions tested and the criteria used, for
example: "pH of full recipes at 25 °C in RO water agrees within X pH units (n = 5, three recipes)".
It never says "FlahaX is accurate". Disagreements, inconclusive stages and unsupported conditions
are published with the same prominence as agreements. The result statement
"No real-mixture predictive accuracy is claimed" is replaced only by a statement scoped this way.

## 9. Independent review and record keeping

- The protocol, with the reviewer's numbers filled in, is reviewed by a person who is not
  the author of FlahaX and who has laboratory experience with nutrient solutions.
- The reviewer's name, date, requested changes and final approval are stored with the protocol.
- All raw observations, instrument records, prediction files, hashes, FlahaX versions and the
  evidence bundle for each stage are kept in a dated folder and verified with the project's
  evidence tooling (the same finalizer that verifies the contract bundles).

## 10. Approvals and costs

This document is a design. The following each need their own specific, written approval from the
project owner before they happen; creating or reading this protocol authorizes none of them:

- laboratory spending, including the accredited ion analysis in Q-ion;
- contacting an external reviewer or laboratory;
- buying reagents or instruments, or running any experiment.

Items to decide before approval: who reviews; which laboratory; the budget; which source water
is used for the second water; the target crops and recipes for Stage 3.

## 11. Known limits of this design

- It tests the conditions chosen, not every water, product or temperature.
- Ion analysis is the costliest part. If it is dropped, Q-ion cannot support a claim, and the
  claim is limited to pH, EC, titration volume and stability.
- Stability over 24 h does not establish stability over weeks.
- A pass supports a scoped claim; it does not turn FlahaX into a dosing instruction.
