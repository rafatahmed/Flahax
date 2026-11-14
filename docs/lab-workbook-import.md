# Import the completed Steiner laboratory workbook

`flahax lab-import` reads the [Excel template](../examples/steiner-10-litre-lab-worksheet.xlsx),
maps recorded inputs to the existing evidence schemas, and runs the fixed-ratio
recipe calculation, rounded stock delivery, preparation uncertainty, selected-mineral
saturation checks, measured pH gate and longitudinal stability assessment.
Excel and third-party spreadsheet libraries are not required to import the file.

This is a deliberately narrow adapter for the existing six-stock, 10 L recipe at
pH 6.30 with verification over 6.28–6.32. It does not generalize the solver, create a
laboratory information system, or turn a calculated boundary into experimental evidence.

## Before preparing the batch

1. Make a copy of the Excel template for the named physical batch.
2. Fill `Batch!B6:B7` (batch and vessel IDs), all yellow inputs in **Stock assays**
   and **Dispensers**, and the final-volume block `Calibration!B6:B18`.
3. Save and close the workbook, then run:

```powershell
python -m flahax lab-import completed-batch.xlsx --prepare --output preparation-report.json
```

For a source checkout, first set `$env:PYTHONPATH = "$PWD/src"`.
The installed console equivalent is `flahax lab-import ...`.

The preparation report recomputes the numerical recipe and checks stock and vessel
records. Read its failures before proceeding. Copy the returned
`stock_verification.preparation_fingerprint` into **Batch!B8**. This is the one
identity handoff required before preparing the batch, not manual evidence-to-JSON
copying. The command never rewrites the workbook or silently assigns a fingerprint
to an already measured preparation. Preparation mode always leaves `verified` and
`stable` false because no measured batch pH or stability series is assessed yet.

## After preparing and observing the batch

Complete the batch/protocol inputs, pH calibration, actual delivery log, observations
and corresponding laboratory provenance rows. Save the workbook and run:

```powershell
python -m flahax lab-import completed-batch.xlsx --output verification-report.json
```

No manual JSON construction is needed. The report is the full existing FlahaX result,
including numerical checks, stock verification, measured pH, per-observation
stability checks, missing sampling times, `verified`, `stable` and qualified duration.
It also contains `workbook_import` with source-file SHA-256, import schema, actual
UTC assessment time and supplementary handling/withdrawal/raw-report references.
The existing gates retain their own evidence snapshots and hashes.

| Exit status | Meaning |
|---|---|
| 0 | Full verification and stability passed; in `--prepare` mode, numerical and stock/vessel checks passed |
| 1 | Workbook imported, but required verification or stability checks did not pass |
| 2 | Invalid/incomplete workbook, unsupported input/layout, or file/report error |

An incomplete study can still be imported once its baseline and prerequisite
records exist. It remains `stable: false` and reports the missing 24, 72 or 168 h
observations. A blank template returns `invalid_workbook`, `verified: false`,
`stable: false` and input-cell locations requiring completion.

## What is read and what is recalculated

| Workbook area | Imported information |
|---|---|
| Batch B6:B8 | Physical batch, vessel and previously obtained preparation fingerprint |
| Batch B9:B11 | Recorded assessment timestamp, operator and reviewer; not a replacement for current UTC validity checks |
| Batch B14:B22 | Preparation/protocol declarations, storage, filter pore size and protocol source |
| Stock assays D6:O11 | Six stock identities, assays, bounds, dates, sources and applicability declarations |
| Dispensers D6:P11 | Assigned devices, calibration ranges, bias, uncertainty and provenance |
| Calibration B6:B18 | Final-volume calibration and vessel identity |
| Calibration B26:B39, B41:B42, D41:D42 | Meter/electrode calibration, validity, bounds and buffer references |
| Observations A6:V17 | All populated sample rows, measured pH, turbidity, Ca/P, volume, uncertainty and handling |
| Measurement records D6:H53, J6:J53 | Four supporting metric records for each of the 12 observation slots |
| Preparation K6:K11 | Actual logged rounded delivery instructions; must match this recipe exactly |

Preparation notes are retained as supplementary provenance. The raw reports behind
those notes and the stock/measurement certificates are not independently authenticated.
Shared batch/vessel/fingerprint and meter/electrode identities are copied into the
individual schema records. The first observation's pH record becomes the initial
batch-pH evidence and is reused exactly in the baseline stability observation.

**Excel PASS/FAIL cells, cached formula results, Batch B12:B13's earlier numerical
claim and the workbook's manual assessment date do not authorize verification.**
FlahaX recomputes the numerical checks and uses the current UTC date/time for record
validity. A saved PASS cannot override expired calibration, a wrong fingerprint or
new failing measurements. Excel's workbook-acceptance label is not the product's
`verified` or `stable` result.

## Input contract

- Use the distributed seven-sheet layout and literal values in measured input cells.
  Formulas in those cells are rejected even when they contain plausible cached values.
  Derived workbook cells remain formulas and are ignored as evidence.
- Dates and timestamps are numeric Excel dates in the template's **1900 date system**,
  interpreted as UTC. Date-only fields must not include a time. Text dates, the 1904
  date system, blank numeric bounds, booleans in numeric cells and nonfinite values
  are rejected. Zero uncertainty must be entered explicitly and supported by the method.
- Keep all design settings and nominal concentrations/doses unchanged. The import
  contract identifies this fixed recipe, not arbitrary edited spreadsheets. The
  specified six salts and KOH potassium contribution remain in the recalculated recipe.
- `Preparation!K6:K11` records delivery of the exact planned rounded instructions.
  A different delivered amount requires explicit replanning and a matching batch
  record. It is not silently substituted or absorbed into another uncertainty term.
- Enter supported `YES` declarations only when the linked measurement reports justify
  them. Incomplete or contradictory declarations block import.
- Use at most 12 observation slots and include every recorded observation, including
  intermediate failures. Supporting records without their observation are rejected.
  Additional observations outside the supported rows are not silently discarded.
- Retention uses remaining **mass**, not just concentration: concentration and volume
  intervals are multiplied, then current lower mass is divided by baseline upper mass.
  The 1 NTU, 95% retention, baseline ±5% and sampling-window choices remain illustrative.
- No Excel formulas/macros are executed. Macro/external-link workbooks and excessive
  ZIP/XML payloads are rejected. Preserve the original completed file as evidence.

The workbook remains an input form. FlahaX's existing JSON interface remains available
for larger studies or explicitly modeled alternative recipes. This adapter does not
resolve Steiner's historical pH discrepancy or demonstrate practical hydroxyapatite
control. Those remain scientific and experimental questions.
