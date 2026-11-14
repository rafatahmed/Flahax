# Steiner-ratio 10-litre batch: laboratory worksheet

**Blank laboratory record — no measured verification or stability claim.**
Copy this worksheet for each physical batch. Enter measured results only in actual
fields; retain original reports and raw readings. Never copy planned values into
measurement fields. A blank is missing evidence, not zero. Attach extra pages for
replicates, deviations and intermediate observations.

The companion [machine-readable worksheet](../examples/steiner-10-litre-lab-records.json)
contains the fixed recipe request plus blank `stock_evidence` and `batch_stability`
objects. Laboratory notes, signatures and raw readings belong here or in linked
reports, not as extra keys in those strict JSON objects.

## 1. Batch identity and approved design

| Item | Entry |
|---|---|
| Worksheet ID / revision | __________ |
| Physical batch ID / vessel ID | __________ / __________ |
| Operator / independent reviewer | __________ / __________ |
| Preparation start / finish, with timezone | __________ / __________ |
| Laboratory / source-water lot / analysis report | __________ |
| FlahaX version / source revision / request file and hash | __________ |
| Saved numerical result / preparation fingerprint | __________ |
| Actual storage location / vessel material / closure / headspace | __________ |
| Light / temperature control / agitation / aeration conditions | __________ |
| Laboratory SOP / deviations report | __________ |

Use ISO timestamps with a timezone, for example `2026-11-15T09:00:00+03:00`.
Dates entered as `measured_on` must be the timestamp's **UTC date**. Do not predate
measurements or extend certificate validity to make a record pass.

| Design setting | Planned value — not a measurement |
|---|---|
| Final mixed solution | 10.000 L, including all stock doses |
| Final-volume error allowance | ±0.050 L, including bias and filling uncertainty |
| Temperature / water | 25 °C / demineralized; model uses 10 kg water approximation |
| Cation equivalent shares, K:Ca:Mg | 50:30:20 |
| Anion equivalent shares, nitrate:phosphate:sulfate | 5:3:1, phosphate counted on H2PO4 basis |
| Requested strength / rounded nominal counted sum | 1.70947360992432 / approximately 1.709479411 mmol/L |
| Allowed relative share / concentration deviations | 1% / 2% |
| Target pH / complete permitted measured interval | 6.30 / 6.28–6.32 |
| Selected phases / required SI margin | Brushite, Monetite, Hydroxyapatite / 0.30 |
| Stock concentration / delivered-dose bounds | ±0.1% / ±0.02 mL per stock |

This is the previously found numerical candidate, not a new global-maximum claim.
Recalculate this fixed request before use. Actual water chemistry, gas exchange,
temperature, reactive impurities or unaccounted additions can invalidate the modeled
conditions. Steiner's historical 0.13-unit pH discrepancy remains unresolved.

## 2. Planned delivery and actual preparation log

Use six separately identified single-compound stocks. Concentrations below are
active **specified-compound-equivalent g/L**, including the exact hydration state.
They are not elemental g/L and are not uncorrected commercial product masses.

| Formula | Nominal stock g/L | Planned dose mL | Nominal compound g in batch | Actual stock ID | Dispenser ID | Actual setting / delivery mL | Operator / time |
|---|---:|---:|---:|---|---|---|---|
| KH2PO4 | 10.000 | 44.88 | 0.44880 | ____ | ____ | ____ | ____ |
| Ca(NO3)2.4H2O | 10.000 | 36.60 | 0.36600 | ____ | ____ | ____ | ____ |
| MgSO4.7H2O | 10.000 | 13.55 | 0.13550 | ____ | ____ | ____ | ____ |
| Mg(NO3)2.6H2O | 10.000 | 12.40 | 0.12400 | ____ | ____ | ____ | ____ |
| KNO3 | 10.000 | 14.45 | 0.14450 | ____ | ____ | ____ | ____ |
| KOH | 1.000 | 24.70 | 0.02470 | ____ | ____ | ____ | ____ |
| Total stock delivery | — | 146.58 | — | — | — | ____ | ____ |

The compound masses are calculated equivalents, not instructions to weigh these
small masses directly. KOH contributes potassium and must remain in the accounting.
Nominal stock preparation for 1 L would require 10 g active compound (1 g for KOH),
but actual gross mass depends on measured assay and hydration. A 99–100% purity
label and ±0.001 g balance specification do not themselves establish ±0.1% stocks.

Complete a stock preparation record for **each of the six stock IDs**:

| Stock ID / formula | Reagent supplier, lot, hydrate, assay report | Balance ID / calibration / bound g | Tare / gross / net g | Active fraction / correction | Stock vessel ID / contained L / bound L | Prepared at / operator / storage |
|---|---|---|---|---|---|---|
| ____ / KH2PO4 | ____ | ____ | ____ | ____ | ____ | ____ |
| ____ / Ca(NO3)2.4H2O | ____ | ____ | ____ | ____ | ____ | ____ |
| ____ / MgSO4.7H2O | ____ | ____ | ____ | ____ | ____ | ____ |
| ____ / Mg(NO3)2.6H2O | ____ | ____ | ____ | ____ | ____ | ____ |
| ____ / KNO3 | ____ | ____ | ____ | ____ | ____ | ____ |
| ____ / KOH | ____ | ____ | ____ | ____ | ____ | ____ |

Record the actual sequence under the laboratory's applicable preparation SOP:

| Event | Actual record / time / initials |
|---|---|
| Water identity and initial amount; clean final vessel | __________ |
| Each stock delivered into the diluted batch; mixing order and conditions | __________ |
| Mixing complete; temperature before final make-up | __________ |
| Final make-up to calibrated 10 L mark after all stocks | __________ |
| Final mixing / temperature / appearance / baseline sample time | __________ |
| Spills, transfers, extra acid/base/water, dosing departures | __________ |

Do not treat 10 L of water plus stocks as a 10 L batch. Any extra pH reagent must
be included in a revised recipe and matching preparation record; a pH reading alone
cannot account for its nutrients. Do not certify a changed batch using the old
fingerprint. Current software does not independently observe actual dispensing or filling.

## 3. Stock assay and dispenser calibration evidence

Attach measured assay reports for all stocks. KOH alkalinity alone is insufficient
when carbonate or other reactive impurities could be present. The concentration and
impurity declarations below require analytical support, not merely checked boxes.

| Formula / stock ID | Assay record ID | Measured active g/L | Absolute bound g/L | Bias from nominal + bound | Within 0.010 g/L (KOH 0.001)? |
|---|---|---|---|---|---|
| KH2PO4 / ____ | ____ | ____ | ____ | ____ | ____ |
| Ca(NO3)2.4H2O / ____ | ____ | ____ | ____ | ____ | ____ |
| MgSO4.7H2O / ____ | ____ | ____ | ____ | ____ | ____ |
| Mg(NO3)2.6H2O / ____ | ____ | ____ | ____ | ____ | ____ |
| KNO3 / ____ | ____ | ____ | ____ | ____ | ____ |
| KOH / ____ | ____ | ____ | ____ | ____ | ____ |

Assay acceptance: `abs(measured − nominal) + U <= nominal × 0.001`, positive
lower concentration. If this fails, replan explicitly; do not silently substitute
measured concentrations in the old dose instructions.

| Formula / stock ID | Dispenser ID / calibration ID | Covered dose minimum–maximum mL | Maximum absolute bias mL | Additional bound mL | Sum ≤0.020 mL? |
|---|---|---|---|---|---|
| KH2PO4 / ____ | ____ | ____ | ____ | ____ | ____ |
| Ca(NO3)2.4H2O / ____ | ____ | ____ | ____ | ____ | ____ |
| MgSO4.7H2O / ____ | ____ | ____ | ____ | ____ | ____ |
| Mg(NO3)2.6H2O / ____ | ____ | ____ | ____ | ____ | ____ |
| KNO3 / ____ | ____ | ____ | ____ | ____ | ____ |
| KOH / ____ | ____ | ____ | ____ | ____ | ____ |

Calibration must cover the actual rounded dose, actual stock liquid and 25 °C.
Record raw replicate deliveries, reference method, corrections and the justification
for whole-range coverage in the attached report. Isolated endpoints or water-only
calibration do not automatically establish coverage for the stock liquid.

For **each** assay and dispenser calibration, complete this metadata register
(duplicate rows as needed; 12 records minimum):

| Record ID / type / stock ID | Source report / method | Measured on UTC date | Valid until UTC date | Temperature °C | Bounded-error justification / reviewer |
|---|---|---|---|---|---|
| KH2PO4 assay / ____ | ____ | ____ | ____ | ____ | ____ |
| Ca(NO3)2.4H2O assay / ____ | ____ | ____ | ____ | ____ | ____ |
| MgSO4.7H2O assay / ____ | ____ | ____ | ____ | ____ | ____ |
| Mg(NO3)2.6H2O assay / ____ | ____ | ____ | ____ | ____ | ____ |
| KNO3 assay / ____ | ____ | ____ | ____ | ____ | ____ |
| KOH assay / ____ | ____ | ____ | ____ | ____ | ____ |
| KH2PO4 dispenser / ____ | ____ | ____ | ____ | ____ | ____ |
| Ca(NO3)2.4H2O dispenser / ____ | ____ | ____ | ____ | ____ | ____ |
| MgSO4.7H2O dispenser / ____ | ____ | ____ | ____ | ____ | ____ |
| Mg(NO3)2.6H2O dispenser / ____ | ____ | ____ | ____ | ____ | ____ |
| KNO3 dispenser / ____ | ____ | ____ | ____ | ____ | ____ |
| KOH dispenser / ____ | ____ | ____ | ____ | ____ | ____ |

Machine values, only where supported: `uncertainty_basis = total_bound_through_valid_until`;
assay `concentration_basis = specified_compound_equivalent_g_l` and
`reactive_impurities = excluded_by_measurement`; dispenser `coverage = entire_declared_range`.
Map each formula to its distinct stock ID, dispenser ID, assay record ID and
calibration record ID in `stock_evidence.assignments`.

## 4. Final-volume calibration and actual filling

| Required entry | Actual value |
|---|---|
| Vessel ID / calibration record ID | __________ |
| Source report / method / raw calibration readings | __________ |
| Measured on / valid until (UTC dates) | __________ |
| Calibration temperature °C | __________ |
| Nominal contained volume L | 10.000 (target) |
| Measured contained volume L / absolute bound L | __________ / __________ |
| Absolute deviation from 10 L + bound L; must be ≤0.050 | __________ |
| Actual final filling time / temperature / operator / mark check | __________ |
| Baseline remaining volume L / bound L / method and calibration reference | __________ |

Required supported declarations: `capacity_basis = to_contain`,
`application = final_solution_including_stocks`,
`uncertainty_basis = total_bound_through_valid_until`.
The bound must include calibration, filling/meniscus, repeatability, temperature and
drift as applicable. A vessel certificate alone does not prove correct batch filling.

## 5. pH meter and electrode calibration

| Required entry | Actual value |
|---|---|
| Meter ID / electrode ID / calibration record ID | __________ |
| Source / method / raw buffer readings and corrections | __________ |
| Calibrated at (timezone timestamp) / measured on (UTC date) | __________ |
| Valid until UTC date / calibration temperature °C | __________ |
| Declared covered pH minimum / maximum | __________ / __________ |
| Maximum residual absolute bias pH / additional calibration bound pH | __________ / __________ |
| Buffer 1 certificate reference / lot / certified pH at 25 °C | __________ |
| Buffer 2 certificate reference / lot / certified pH at 25 °C | __________ |
| Other buffers / check standards / calibration acceptance | __________ |
| Whole-range coverage and validity justification, including drift | __________ |

At least two distinct referenced buffers must bracket the declared calibration range;
that range must cover 6.28–6.32. Required supported declarations:
`coverage = entire_declared_range`, `uncertainty_basis = total_bound_through_valid_until`.
The present stability gate uses the **same meter, electrode and calibration** for all
observations, applicable and current on assessment day. It does not support a second
calibration midway through the study. Do not claim a seven-day validity unless the
measurement procedure supports it; if unavailable, the current gate cannot qualify
this study. Automatic temperature compensation is not proof of batch temperature.

## 6. Stability protocol and sampling schedule

| Protocol field | Entry / declared choice |
|---|---|
| Protocol ID / source SOP | __________ |
| Storage conditions, temperature, light, aeration, vessel closure | __________ |
| Filter type / lot / pore size µm (positive, ≤0.45) | __________ |
| Dissolved basis | Filtered elemental Ca and total dissolved P |
| Turbidity sample | Representative unfiltered batch |
| Material accounting | No additions; withdrawals count as losses |
| Sampling / preservation / analytical methods and holding-time references | __________ |
| Initial nutrient relative tolerance | 5% (illustrative choice) |
| Turbidity maximum / minimum Ca and P retention | 1 NTU / 95%, including uncertainty |

These are illustrative acceptance choices, not experimentally validated shelf-life
limits. Use one consistent filtration basis. Total dissolved P as elemental P is
not interchangeable with mg/L phosphate or an orthophosphate-only assay. Retain
lab reports identifying preparation/digestion and reporting basis; see the method
reference in [measured stability requirements](measured-batch-stability.md).

| Required time after baseline | Latest allowed time | Planned timestamp | Actual timestamp | Observation ID / sample IDs |
|---|---|---|---|---|
| 0 h | Exactly initial verified pH sample | ____ | ____ | ____ |
| 24 h | 25 h | ____ | ____ | ____ |
| 72 h | 73 h | ____ | ____ | ____ |
| 168 h (7 days) | 169 h | ____ | ____ | ____ |

Record all extra observations too; a failed intermediate result cannot be discarded.
Log withdrawn volume, evaporation, transfers and incidents. No replacement water,
nutrient top-ups or replacement samples are accepted by this material-accounting
protocol. Withdrawals reduce remaining mass and can cause a conservative failure.

## 7. Observation sheet — complete one for every sample time

Copy this section at least four times, one for each scheduled observation.

| Identity and handling | Actual entry |
|---|---|
| Observation ID / required hour / actual elapsed hours | __________ |
| Batch ID / vessel ID / preparation fingerprint | __________ |
| Sampled at (timezone timestamp) / sampler | __________ |
| Sample IDs for unfiltered turbidity / filtered Ca / filtered P | __________ |
| Filtration / preservation / analysis timestamps; analyst / report | __________ |
| Temperature °C / actual storage conditions since previous sample | __________ |
| Withdrawn volume L / cumulative withdrawals L / remaining volume method | __________ |
| Visual appearance / deposits / sediment / unusual events | __________ |

For each metric, attach raw replicates and document the reported result and total
absolute error bound. Units below apply after dilution-factor corrections. Do not
enter below-detection results as zero or infer uncertainty from instrument resolution
alone; obtain a supported interval/report before submission.

| Metric | Result | Absolute bound U | Instrument ID | Calibration reference | Method / source report |
|---|---|---|---|---|---|
| Unfiltered turbidity, NTU | ____ | ____ | ____ | ____ | ____ |
| Dissolved Ca, mg/L elemental Ca | ____ | ____ | ____ | ____ | ____ |
| Total dissolved P, mg/L elemental P | ____ | ____ | ____ | ____ | ____ |
| Remaining batch volume, L | ____ | ____ | ____ | ____ | ____ |

Each metric maps to `value`, `absolute_uncertainty`, `instrument_id`,
`calibration_reference`, `method`, `source`, `uncertainty_basis = total_bounded_error`.
Include applicable calibration, bias, sampling, analytical and dilution contributions.
The software retains references but does not authenticate laboratory certificates.

| Contemporaneous pH record | Actual entry |
|---|---|
| Unique pH measurement record ID / meter ID / electrode ID | __________ |
| Calibration record ID / batch ID / vessel ID | __________ |
| Measured at = this sample timestamp / measured on UTC date | __________ |
| Valid until UTC date / actual measurement temperature °C | __________ |
| Source / method / preparation fingerprint | __________ |
| Indicated pH / additional batch uncertainty (excluding calibration terms) | __________ / __________ |
| Total bound = residual bias + calibration bound + batch bound | __________ |
| Lower pH / upper pH; wholly within 6.28–6.32? | __________ / __________ / __________ |

Required supported pH declarations: `uncertainty_basis = total_bound_through_valid_until`,
`application = final_mixed_batch_no_unaccounted_additions`.
The baseline pH object must exactly match `stock_evidence.batch_ph.measurement`;
later pH records need distinct IDs and their own timestamp. The baseline sample time
is the verified initial pH time; analytical processing may occur later under the
documented sample handling procedure.

## 8. Hand calculations and acceptance record

Use `lower = max(0, result − U)` and `upper = result + U`.
For Ca and P, `mass_lower = concentration_lower × volume_lower` and
`mass_upper = concentration_upper × volume_upper`, in mg.

| Calculation | Baseline | 24 h | 72 h | 168 h |
|---|---|---|---|---|
| Turbidity upper NTU (must be ≤1) | ____ | ____ | ____ | ____ |
| Volume lower / upper L | ____ | ____ | ____ | ____ |
| Ca mass lower / upper mg | ____ | ____ | ____ | ____ |
| P mass lower / upper mg | ____ | ____ | ____ | ____ |
| Ca mass lower / baseline Ca mass upper (must be ≥0.95) | N/A | ____ | ____ | ____ |
| P mass lower / baseline P mass upper (must be ≥0.95) | N/A | ____ | ____ | ____ |
| pH lower / upper (inside 6.28–6.32) | ____ | ____ | ____ | ____ |
| Time window / all observation criteria passed? | ____ | ____ | ____ | ____ |

Baseline targets come from the **recalculated rounded recipe**:
`target_mass_mg = analytical_mmol_l[element] × atomic_mass_mg_per_mmol × 10 L`.
This worksheet's recalculated nominal targets are **Ca 62.116931 mg** and
**P 102.150515 mg** in the full batch (approximately 6.211693 mg/L Ca and
10.215052 mg/L P). These are calculated reference values, not measurements.
Confirm Ca target ____ mg and P target ____ mg from the saved result. Both baseline
mass intervals must lie wholly inside 95–105% of their respective targets. Baseline
volume interval must lie inside 9.950–10.050 L. A depleted baseline cannot establish
stability merely by remaining unchanged. Use mass, not concentration alone: evaporation
can raise concentration while nutrient mass is falling.

| Final review | Entry |
|---|---|
| All assay, dosing, vessel and pH records applicable/current? | __________ |
| Numerical ratios, counted concentration and all three phase checks passed? | __________ |
| Every supplied observation passes, including extra samples? | __________ |
| Complete required schedule and supported uncertainty bounds? | __________ |
| FlahaX `verified` / `stable` / assessment status | __________ |
| Failure details / missing records / corrective actions | __________ |
| Qualified duration / observation start and end | __________ |
| Saved result file / stock records SHA-256 / stability records SHA-256 | __________ |
| Operator signed / date; reviewer signed / date | __________ |

## 9. Transfer records into FlahaX

1. Copy the companion JSON; keep the original blank. Enter real stock assignments,
   assays, dispensers and final-volume records. Remove `batch_ph` temporarily from
   `stock_evidence` and omit `batch_stability` while obtaining the preparation
   specification and `stock_verification.preparation_fingerprint`.
2. Confirm the recalculated rounded doses match Section 2. Prepare and identify the
   physical batch. Complete `batch_ph`, copying the fingerprint from this exact
   recipe. Resubmit the fixed request to assess preparation verification.
3. Complete `batch_stability.assignment`, protocol and each observation. The first
   observation's pH record is an exact copy of the initial measured pH object.
   Store later readings with distinct IDs; include all intermediate observations.
4. Submit the completed fixed request with both evidence objects. Review failures,
   missing times, hashes and qualified duration; archive the request, reports and
   returned result. The unchanged blank template must remain unverified and unstable.

All six stock and calibration records, vessel record, pH calibration and measurement
fields are explicitly present in the JSON. Use the existing CLI's `ratio` command
with JSON on standard input; the JSON is a complete fixed-request shape, not a new search. Searching
again cannot transfer a measured batch's evidence to different doses.

From a checkout in PowerShell, using the checkout's Python environment:

```powershell
$env:PYTHONPATH = "$PWD/src"
Get-Content -Raw examples/steiner-10-litre-lab-records.json | python -m flahax ratio | Set-Content -Encoding utf8 batch-result.json
```

Use your completed copy's path when submitting actual records. This command records
an assessment; it does not turn a blank worksheet into verified evidence.

`verified` means numerical and supplied preparation-record checks passed. `stable`
adds the complete measured study. Neither flag authenticates reports. A seven-day
pass supports only the recorded conditions and observation window, not continuous
clarity between samples, future shelf life, all-nutrient retention or proof of which
mineral formed. No actual preparation or laboratory validation has been performed
by creating this worksheet.
