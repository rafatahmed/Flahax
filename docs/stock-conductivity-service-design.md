# Stock conductivity service (design, not implemented)

Status: proposal for owner review. No code in this repository implements it. Nothing here is a measured result, an independent scientific review or an approval to ship; every accuracy figure below is either quoted from a stated source, marked as a placeholder for the owner to decide, or marked as unknown.

## 1. Purpose

FlahaX should be the single source of conductivity predictions for fertilizer stock solutions and their dilutions, so that consumers (first: FlahaFAST) do not carry their own conductivity model. The service answers one question:

> For these salts made up to this volume at this temperature, what EC should a meter read on the solution as made and on a 1:N dilution of it, how uncertain is that, and is it inside the range where the model has been validated?

It is a prediction and verification aid. It does not set equipment, choose injection ratios or replace the nutrient balance (see [conductivity](conductivity.md), which keeps the same line).

## 2. Why now: the gap this closes

| Existing piece | What it does | Limit |
|---|---|---|
| `calculated_ec.py` (manufacturer-anchor screening) | EC of the dilute irrigation solution from brochure anchors | Refuses concentrated stocks, acid, unknown products and loadings above 1 g/L; no uncertainty |
| `conductivity.py` / `plan_ec_delivery` | Interpolates measured EC grids per recipe, source and tank | Needs measured profiles per recipe; none ship; never extrapolates |
| Equilibrium kernel (Davies) | Speciation including pairs and chelates | Activity model is sound to about 0.5 mol/kg; produces no conductivity |
| [development-status.md](development-status.md), next work item 3 | Names this work | "Specify and validate a full-mixture conductivity model and a concentrated-stock model, retaining unsupported results until qualified" |

**Consumer observation (motivation, not evidence).** FlahaFAST has been using a limiting-law conductivity model (per-ion mobility times `exp(-0.7025 * sqrt(I) * z^1.5)`) derived from HydroBuddy. Checked against commonly tabulated KCl conductivity standards at 25 C, it read low by about 4 % at 0.01 mol/L, 6 % at 0.02, 10 % at 0.05, 15 % at 0.1 and 51 % at 1 mol/L (reference values 1.413, 2.767, 6.668, 12.85 and 111.9 mS/cm). Those reference values were taken from memory of standard tables and **must be re-sourced from a primary citation before they are used as evidence** (section 8). The shape of the error, not its exact size, is the reason for this work: a limiting-law mobility factor is too severe at stock strength, and real mixtures add ion pairing, viscosity and complexation.

Growers also measure stocks diluted, because many meters stop near 20 mS/cm. The service therefore predicts at **a list of dilutions**, not only at stock strength.

## 3. Scope

In scope for the first usable version (stage C1, section 9):

- EC at 25 C of a made-up solution and of 1:N dilutions of it, for common macronutrient salts, in the dilute-to-moderate range the model is validated for.
- An explicit validity envelope and a smallest trusted dilution.
- A way to compare stored measurements with predictions, without storing anything in FlahaX.

Out of scope (any of these returns `not_supported`, never a guess):

- Setpoints, pump or injection control, hardware.
- Acid- or base-adjusted solutions, until separately modelled (the existing equilibrium work covers pH planning; conductivity after reaction is a later stage).
- Chelates and trace mixes in stage C1 (decision D4).
- Temperatures outside the validated range.
- Any claim of accuracy beyond the validated range.

## 4. Interface

FlahaFAST already consumes FlahaX as a child process: one JSON object on standard input, one on standard output, with its own timeout and a default-off feature flag ([consumer boundary](../INTEGRATION.md)). The service keeps that pattern: `python -m flahax conductivity` (alias `flahax conductivity`), plus a Python function with the same contract. The installed package is the only dependency.

Contract files (JSON Schema draft 2020-12), with examples that validate against them:

- Request: [stock-conductivity-v1.request.schema.json](schemas/stock-conductivity-v1.request.schema.json)
- Response: [stock-conductivity-v1.response.schema.json](schemas/stock-conductivity-v1.response.schema.json)
- Examples: [schemas/examples/](schemas/examples/) (the "synthetic" example shows shape only and carries no real numbers)

### 4.1 Operations

| `operation` | Purpose | Reads | Writes |
|---|---|---|---|
| `predict` | EC of each channel at each dilution, with uncertainty and validity | The request | Nothing |
| `describe_model` | Supported elements, temperature range, validated ionic strength, limits, what is and is not supported | Nothing | Nothing |
| `reference_check` | The model's gap against its packaged reference data | Packaged reference sets | Nothing |
| `evaluate_measurements` | Compare supplied meter readings with predictions; descriptive statistics only | The request | Nothing |

The service is stateless and deterministic: the same request and model version give the same response byte for byte (no clock, no randomness). It never stores measurements and never changes a parameter because of them. Calibrating or revising the model is a deliberate change in this repository with its own evidence (decision D6).

### 4.2 `predict` request (summary; the schema is authoritative)

| Field | Type | Rules |
|---|---|---|
| `schemaVersion` | `"1"` | Required |
| `operation` | `"predict"` | Required |
| `temperature_c` | number | Required; -5 to 80 accepted by the schema, but only the validated range returns estimates |
| `channels[]` | 1-8 objects | `id`, `volume_l` (> 0, the **final** volume the salts are made up to, not added to), `salts[]` (1-64) |
| `salts[]` | objects | `id`, `name`, optional `formula`, `grams` (>= 0), optional `purity` (percent assay), `elements` (symbol to percent by mass; FlahaX symbols including `N_NO3`, `N_NH4`) |
| `dilutions[]` | 1-16 unique integers, 1 to 100000 | `1` is the solution as made; `N` means one part solution in N parts total |
| `water` | optional | `elements` in mg/L (used only for the final irrigation solution), `ec_ms_cm` used only as a consistency check, never to replace composition |
| `options` | optional | `include_diagnostics`, `include_speciation` (both default false) |

The service converts grams in a final volume to water mass and molality itself (density and partial volumes are model concerns, and matter at 100x stock where "salts take up space"). Callers do not convert units.

### 4.3 `predict` response (summary)

Per channel and per dilution:

| Field | Meaning |
|---|---|
| `status` | `estimated`, `not_supported` or `needs_input` |
| `reason` | Required unless `estimated`: `no_validated_model`, `ionic_strength_outside_validated_range`, `temperature_outside_validated_range`, `unknown_ion`, `unsupported_chemistry`, `composition_incomplete`, `precipitation_expected`, `water_ec_inconsistent` |
| `ec_ms_cm_25` | EC at 25 C, **unrounded**; present only when `estimated` |
| `ec_ms_cm_at_temperature` | EC at the requested temperature |
| `uncertainty` | `value_ms_cm`, `relative` and `basis` (`validated_range`, `reference_fit` or `unknown`); `unknown` is never zero |
| `validity` | `in_range`, `ionic_strength_mol_kg`, `max_validated_ionic_strength_mol_kg`, `minimum_trusted_dilution` (smallest whole dilution, not below the one asked, at which the model is validated; `null` if none) |
| `diagnostics` | Optional: density, water mass, contribution by species, species molalities |
| `warnings` | Free-text notes; never the only carrier of a limit |

Top level: `model` (`id`, `version`, `profile`, `validation_status`), `inputHash` (hash of the canonical request, for consumers that store a prediction), `ok`. `validation_status: "unvalidated"` means no number from this model may be shown as a prediction; until stage C1 exits, every point is `not_supported` with `no_validated_model` (the `predict.response.not-supported.json` example).

### 4.4 Errors and exit status

- Exit status 0 with `ok: true` even when individual points are `not_supported`: that is an answer, not a failure.
- Exit status 2 with `ok: false` and `error` (`code`, `message`, JSON-pointer `path`) when the request is refused: `invalid_json`, `invalid_schema_version`, `invalid_type`, `invalid_value`, `unknown_operation`, `limit_exceeded`, `unknown_channel`, `internal_error`.
- Consumers must check both the exit status and `ok`; a non-empty `results` is never implied by exit status 0 alone (the same rule the existing CLI states for `feasible`).

### 4.5 Versioning

`schemaVersion` changes only for breaking changes to field names, meaning or units. `model.version` changes whenever any returned number could change; consumers store it with each prediction. Adding optional response fields is not breaking. Removing or reinterpreting a `reason` code is.

## 5. Model design

The model is built in layers so that each layer can be validated and, if necessary, replaced without touching the others.

1. **Composition to solution.** Salts, purity and elemental percentages to moles of each ion and to water mass per litre of final solution (density model). Unknown elements or incomplete charge balance give `composition_incomplete` / `unknown_ion`.
2. **Speciation.** Free ions and ion pairs from the existing equilibrium kernel, within the range its activity model supports. Precipitation expected at the stated strength gives `precipitation_expected` and no estimate for that point.
3. **High-strength activities (decision D2).** Beyond about 0.5 mol/kg the Davies activity model is not adequate. Candidate routes, to be chosen by evidence, not preference:
   - (a) Pitzer-type parameters from the PHREEQC database already used for verification, for the major ions;
   - (b) per-salt empirical conductivity curves (Casteel-Amis form) anchored on handbook data, with a stated mixing rule;
   - (c) stop at the validated dilute range and return `not_supported` above it (the stage C1 position).
4. **Mobility and conductivity.** Specific conductivity as the sum over free ions of ionic strength-dependent molar conductivity times molality and density, with a published form for the ionic-strength dependence, not the limiting-law factor alone (decision D3). Ion pairs and chelates contribute only where a mobility is justified; otherwise they remove charge carriers and are reported in diagnostics.
5. **Temperature.** Compensation to and from 25 C within a stated range, with the form and its error recorded; outside the range `temperature_outside_validated_range`.
6. **Validity envelope and uncertainty.** The maximum validated ionic strength, the supported chemistry, the temperature range, and a relative uncertainty by region, all set by the validation evidence (section 8), never by the implementer's judgement. `minimum_trusted_dilution` is computed against this envelope.

Design rules carried over from the existing EC work: never multiply a dilute EC by a concentration ratio, never add A and B conductivities, never report an estimate without a basis, and never let a missing product disappear into a falsely complete total.

## 6. Decisions needed (owner)

| Id | Decision | Why it matters |
|---|---|---|
| D1 | Accuracy target and range, for example "within X % up to a Y-times stock" | Sets the acceptance criteria in section 8 and the route in D2. **Placeholder: not decided.** |
| D2 | High-strength route: Pitzer, per-salt curves, or stay dilute-only | Largest effort difference; determines whether stock-strength estimates exist at all |
| D3 | Form of the mobility-vs-ionic-strength law | Needs published support; affects every number |
| D4 | First-version chemistry: chelates (EDTA) and trace mixes in or out | The pepper and tomato recipes in use contain iron and trace chelates |
| D5 | Temperature range for the first version | Growers measure at greenhouse temperatures, not only 25 C |
| D6 | Whether measurements may ever revise the model, and who reviews that | Keeps the service stateless and the evidence auditable |
| D7 | Reference data owner and measurement protocol for real stocks | Real measurements are the long pole under any model |

## 7. Consumer integration (FlahaFAST), for information

This repository does not implement the consumer ([INTEGRATION.md](../INTEGRATION.md)). The intended use, to be built and tested in the consumer's own project:

- A default-off adapter alongside the existing recommendation adapter, with its own timeout and error handling.
- If the service is disabled, errors, or returns `not_supported`, the consumer keeps its existing behaviour (compare a measured sample at the dilution it was measured, within the consumer's own trust limits).
- If the service returns a validated range, the consumer may use `minimum_trusted_dilution` and show uncertainty, and replaces its own conductivity code rather than running two models.
- The consumer stores `model.id`, `model.version`, `schemaVersion` and `inputHash` with each prediction, so a stored prediction can be reproduced and is never silently recomputed with a newer model.

## 8. Validation and evidence plan

Evidence tiers, in the order they are needed:

| Tier | Data | Used for | Status |
|---|---|---|---|
| E1 | Single-salt conductivity vs concentration to saturation (KCl, KNO3, Ca(NO3)2, MgSO4, KH2PO4, K2SO4, NH4NO3, (NH4)2SO4, others as supported) from handbook or primary literature, with citations and temperature | Mobility law, high-strength route, `reference_check` | To be sourced and cited; the KCl values in section 2 are provisional |
| E2 | Binary and ternary mixtures of E1 salts | Mixing behaviour, ion pairing | To be sourced |
| E3 | Measured real stocks (the owner's A/B recipes) at several dilutions and temperatures, with meter calibration records | Final acceptance, uncertainty by region | Not available; protocol is decision D7 |
| E4 | Measurements collected by consumers (via `evaluate_measurements`) | Monitoring drift and finding gaps; never silent recalibration | Optional, later |

Rules:

- Reference values keep their citation, temperature and uncertainty in the repository; unsourced numbers are not committed as evidence.
- Acceptance criteria are written down from D1 **before** the model is tuned, and tuning data are kept separate from acceptance data.
- Outcomes are recorded as measured, including failures. A model that misses its target ships as `unvalidated` with every point `not_supported`.

### Test plan

Contract tests (stage C0, before any chemistry):

1. The request and response schemas are valid JSON Schema and every packaged example validates (and the "synthetic" example is rejected if its `validation_status` claims validation without a real profile).
2. Refusal table: dilution 0, 1.5, 100001, duplicates; empty channels; missing temperature; negative grams; percent over 100; malformed symbols; unknown operation; wrong `schemaVersion`; extra fields; oversize lists. Each returns the documented `error.code` and `path` with exit status 2.
3. `describe_model` returns capabilities that match what `predict` actually accepts (generated from the same constants).
4. Determinism: identical requests give identical bytes; `inputHash` is independent of key order and stable across platforms.
5. `not_supported` points never contain an EC number; `estimated` points always contain uncertainty and validity.
6. CLI behaviour: JSON in/out, exit status 0 for answers including `not_supported`, 2 for refusals, no output on stderr for normal operation.

Model tests (stage C1 onward):

7. Reference reproduction: every E1/E2 point within its stated tolerance; the report from `reference_check` equals the stored fixture.
8. Property tests inside the validated range: EC increases with added salt; EC at dilution N is consistent with the model at the corresponding concentration (no scaling of a dilute EC by N); charge balance holds; zero salts give water only.
9. Boundary tests: just inside and just outside the validated ionic strength and temperature return `estimated` and `not_supported` respectively, with the documented `reason`; `minimum_trusted_dilution` is the smallest whole dilution that qualifies (and `null` when none does).
10. Failure injection: unknown ion, incomplete composition, precipitation expected, water EC inconsistent with supplied composition.
11. Regression fixtures for the owner's real recipes once E3 exists, recorded with provenance.
12. `evaluate_measurements`: statistics are computed only over points the model supports; nothing is stored; calling it twice gives the same result.

Repository checks (existing practice): the `API_REFERENCE.md` generation check, release hygiene tests, `compileall`, `git diff --check`, the PHREEQC-required test run, and the distribution verification described in [documentation maintenance](documentation-maintenance.md) and [CONTRIBUTING](../CONTRIBUTING.md).

## 9. Stages

| Stage | Delivers | Exit criteria |
|---|---|---|
| C0 | Contract only: schemas, examples, CLI skeleton that validates input and returns `not_supported` / `no_validated_model` for every point; `describe_model` reports `unvalidated`; contract tests 1-6 | Consumers can integrate and test against a real process that never returns a false number |
| C1 | Dilute-range speciation conductivity for E1/E2 salts within the validated ionic strength and temperature range; `reference_check`; `minimum_trusted_dilution`; model tests 7-10 | D1 criteria met on E1/E2 and a small E3 set, recorded as measured |
| C2 | Stock-strength route chosen under D2, with its own acceptance data | Acceptance met or the route is dropped and stock strength stays `not_supported` |
| C3 | Chelates and trace mixes (D4), acid-adjusted solutions as a separately specified increment | Own evidence and tests |
| C4 | `evaluate_measurements` against consumer-collected data, with drift reporting | A reviewed process for any model revision (D6) |

A stage that does not meet its exit criteria does not ship its numbers; the previous stage's behaviour stays.

## 10. Risks

- Real stock measurements are scarce and slow to collect; every model choice depends on them.
- Mixed-fertilizer stocks (calcium with phosphate or sulfate, chelates) are the hardest case and the one growers care about.
- A confident-looking number from an unvalidated route is worse than none: hence `validation_status`, `uncertainty.basis` and the rule that `not_supported` carries no number.
- Per-process start-up cost: one request should cover all channels and dilutions, and the consumer's timeout should be measured against a realistic request before relying on it.
