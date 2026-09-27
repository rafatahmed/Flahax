# FlahaX Package: Trackable Implementation Roadmap

## Purpose

This roadmap tracks package capabilities and their evidence, not deployment or hardware control. FlahaX's dependency-free nutrient formulation API and CLI remain the core product. Optional chemistry and delivery-planning APIs extend a feasible working-solution recipe without weakening that existing contract. FlahaFAST is a later consumer of the package, not a prerequisite for its usefulness or release.

**Status key:** `[ ]` not started · `[-]` active · `[x]` accepted · `[!]` blocked or decision required.

`[x]` means implemented and numerically verified within the documented boundary. It does not mean commercial-product certification, independent scientific approval, or permission to operate equipment. Section status includes any newly identified integration work; completed rows retain their evidence.

## Package audit baseline — 2026-09-27

This section preserves the pre-increment audit. See the continuation below for the current implementation and verification status; its identified P5.5 and local packaging gaps are now addressed.

Audited against chemistry closure commit `20c41c43f785940c5045276bb47925159a119bca`, package version `0.2.0`, runtime modules, tests and checked-in workflows. The closure records 100 passing tests with live PHREEQC, 10 product/target and 11 phase fixture families. [Release evidence](release-evidence.md), [exact chemistry coverage](chemistry-coverage-matrix.md), [source assumptions](sources/flahax-chelate-thermodynamic-profile.md) and [reproduction instructions](reference-fixtures.md) are the acceptance record, not a claim that all future work is finished.

| Audited area | What the package actually provides | Evidence / outstanding boundary |
|---|---|---|
| Core formulation | `recommend`, `solve_weights`, catalogue data and CLI; no required runtime dependencies | `tests/test_pepper.py`, `test_library.py`, `test_guards.py`; `pyproject.toml` |
| P0/P1 contracts and units | Planning records, errors, audit metadata, grams/L recipe and elemental contribution adapters | `tests/test_delivery_contracts.py`, `test_delivery_quantities.py` |
| P2 stock planning | Assignment and concentration checks against **caller-supplied** sourced rules/limits | `tests/test_stock_planning.py`; not a bundled, experimentally certified limit for every catalogue product |
| P2/P3 chemistry | Catalogue g/kg-water totals feed one bounded mixed solve and nitric-acid calculation | `tests/test_chemistry_acceptance.py`, `test_product_phreeqc.py`; 25 C, I <= 0.1 mol/kgw, fixed oxidation states |
| P3/P5 composition | `plan_ph` returns measured-curve `PhPlan`; `compose_delivery_plan` accepts that type | `tests/test_ph_planning.py`, `test_delivery_plan.py`; the equilibrium `AcidResult` is not yet a drop-in composed delivery plan |
| P4 commands | Calibrated, bounded planning values and explicit verification flags | `tests/test_pump_planning.py`; no pump I/O |
| P6 CI / packaging | Ubuntu CI installs editable package and tests Python 3.11–3.13; release workflow builds distributions | `.github/workflows/test.yml`, `publish.yml`; live PHREEQC is not provisioned in CI, and installed-wheel chemistry smoke coverage is not yet established |
| Operational release / P7 | Prototype planning boundary; no external adapter | G6 independent scientific and bench/site approval remains open; P7 is optional and unimplemented |

### Audit conclusions

- Preserve P2.5/P2.7/P3.7 numerical acceptance; do not reopen the frozen chelate boundary or replace source provenance with agreement between two solvers.
- Do not equate g/L recipes with g/kg-water equilibrium input. An explicit water-mass conversion and assay/density inputs are required for composition.
- A nitrate-conserving `AcidResult` is not yet an assay-qualified reagent-volume plan with recipe rescoring. P3.4's existing acceptance applies to the measured-curve path.
- Stock-rule acceptance does not imply all concentrated stocks lie in the dilute Davies domain. Domain rejection remains mandatory; caller-supplied compatibility/solubility evidence stays necessary.
- A green generic CI run can skip the live PHREEQC test. Numerical-reference acceptance requires a separate recorded zero-skip live run with the pinned database/executable.

## Operating assumptions

### Verification continuation — 2026-09-27

P5.5 now provides the explicit catalogue-equilibrium delivery adapter. The complete Python 3.13 suite passes **107 tests with zero skips**, including pinned live PHREEQC. Clean wheel and sdist installs pass outside the checkout on Python 3.13 and were also exercised on Python 3.14. Fresh hash-pinned PHREEQC provisioning succeeds outside the repository. [Package verification](package-verification.md) documents commands, inputs, units and public return types.

P6.6/P6.7 remain active until the supported Python 3.11–3.13 hosted jobs actually pass; the previously observed GitHub account billing lock prevented execution. Local success is not hosted-CI acceptance.

At the project owner's request, G6 for this **planning-package release** uses computational evidence without laboratory work. **Assessor: Rafat Al Khashan.** The [computational assessment](computational-review.md) records passing numerical evidence and its limits, not an independent human review, fabricated signature or operational certification. Physical validation is not a prerequisite for this bounded computational assessment. No hardware or external integration is authorized by this amendment.

1. FlahaX remains a Python package with no required third-party runtime dependencies.
2. The current `recommend` output—grams per litre of final working solution—remains the canonical nutrient recipe.
3. The first release produces plans and validations only. It does not operate pumps, write a database, deploy services, or make unattended pH corrections.
4. All chemical inputs are product- and site-specific. The system must fail explicitly when a required assay, temperature range, water-analysis value, or calibration record is absent.
5. A future FlahaFAST connection remains optional and feature-flagged. The package must be fully testable without FlahaFAST.

## Definition of done

A work package is complete only when its stated acceptance evidence exists, its unit/integration tests pass, its public types and errors are documented, and its backwards-compatibility impact is reviewed. “It calculates a number” is not sufficient evidence for a chemical or control feature.

## Delivery sequence

```text
P0 boundaries/data contracts
        |
        +--> P1 units + recipe invariants
        |        |
        |        +--> P2 stock-tank planner ----+
        |        |                              |
        |        +--> P3 pH/alkalinity planner -+--> P5 composed delivery plan
        |                                       |
        +--> P4 pump calibration planner -------+
                                                 |
                                                 +--> P6 simulation/verification
                                                          |
                                                          +--> P7 optional FlahaFAST adapter
```

P2/P3/P4 have bounded numerical implementations. Both measured-curve and equilibrium P5 composition now have end-to-end tests. P6 hosted validation remains open. G6's amended computational scope does not authorize operational advertising. P7 remains deliberately last and optional.

## Work packages

### P0 — Scope, safety, and data contracts `[x]`

**Objective:** freeze the boundaries before implementation.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P0.1 | Public planning-scope statement and non-goals `[x]` | Reviewed documentation; explicit no-hardware/no-database boundary |
| P0.2 | Versioned schemas for water analysis, product assay, compatibility rule, solubility limit, titration curve, and pump calibration `[x]` | Valid and invalid JSON fixtures; schema validation tests |
| P0.3 | Error taxonomy `[x]` | Stable error codes for missing, ambiguous, incompatible, out-of-range, and unsafe input |
| P0.4 | Audit-record schema `[x]` | A complete plan can identify all input records and model versions used |

**Decision gate G0:** batch preparation is the implemented P0 planning scope. Proportional injection remains deferred and rejected until its operating model, calibration requirements, and safety envelope are formally approved.

### P1 — Units, invariants, and recipe interface `[x]`

**Objective:** make every calculation dimensionally explicit and preserve the existing solver contract.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P1.1 | Immutable value objects for mass, volume, concentration, time, temperature, flow, ratio, and equivalents `[x]` | Conversion and invalid-unit tests |
| P1.2 | Adapter from `recommend` result to a final-solution recipe `[x]` | Round-trip fixture; grams/L and ppm mass conservation tests |
| P1.3 | Reagent nutrient-contribution calculation `[x]` | Known elemental contribution and re-scored final-recipe tests |
| P1.4 | Tolerance and rounding policy `[x]` | No rounding before constraint checks; documented output precision |

**Exit condition:** a recipe containing salts plus a reagent addition conserves mass and either remains within configured nutrient tolerance or is rejected.

### P2 — Stock-tank compatibility and equilibrium model `[x]`

**Objective:** provide explainable A/B/acid stock assignment and separately bounded mixed-equilibrium checks, without treating a dilute solution model as unrestricted stock certification.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P2.1 | Product compatibility graph `[x]` | Tests reject supplied separation-rule conflicts; rule provenance is reported |
| P2.2 | Per-product, temperature-bounded solubility-limit record support `[x]` | Caller supplies sourced records; missing source/range fails and boundary/safety-margin tests pass. This is not complete certified catalogue limit data. |
| P2.3 | Tank-assignment constraint solver `[x]` | Deterministic assignment or explicit infeasibility explanation |
| P2.4 | Stock concentration and capacity calculation `[x]` | Hand-checked 1:100 examples; no tank overfill |
| P2.5 | Reference-model verification `[x]` | PHREEQC 3.8.6 pinned MINTEQ + extensions: 10 product/target families, 11 phase families, raw outputs, hashes, tolerances and live replay; `tests/test_product_phreeqc.py` |
| P2.6 | Activity/speciation saturation model `[x]` | Coupled macro/trace/ligand solver reports mass-balanced species and named phase indices at 25 °C through `I <= 0.1 mol/kgw`; outside-domain stocks are rejected |
| P2.7 | Full fertilizer-chemistry data model `[x]` | All 28 catalogue conversions feed one 197-entry/28-phase mass-action model; alias/source coverage matrix and `tests/test_chemistry_acceptance.py`; frozen Fe-only Dtp/Edd boundary |

**Exit condition:** every selected salt has exactly one compatible storage channel, no limit/capacity is exceeded, and the plan names the rule that accepted or rejected each assignment.

**Decision gate G2:** the unified 25 C reference is PHREEQC 3.8.6 `minteq.v4.dat` plus the checked-in, source-documented FlahaX extensions. Runtime Davies is restricted to `I <= 0.1 mol/kgw`. The [coverage matrix](chemistry-coverage-matrix.md) identifies exact native aliases, extension gaps, reactions and sources. Acceptance is numerical verification of this bounded selected model, not commercial-lot or bench certification.

### P3 — pH and alkalinity equilibrium model `[x]`

**Objective:** calculate a bounded initial reagent dose from measured buffering, then require measurement-based verification.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P3.1 | Alkalinity normalization (`mg/L as CaCO3` to `meq/L`) `[x]` | Unit-tested 50.043 mg/meq conversion for measured-curve planning; separate equilibrium APIs use complete analytical totals and measured initial pH, not a generic residual-alkalinity formula |
| P3.2 | Titration-curve record and interpolation `[x]` | Optional site-calibration path with monotonicity, endpoint, matched-record, and extrapolation-rejection tests |
| P3.3 | Acid/base dose plan `[x]` | Dimensional dose calculation; density, normality, and endpoint guardrails |
| P3.4 | Reagent addition feedback into nutrient balance `[x]` | Measured-curve `PhPlan` includes reagent assay contribution and rescoring. Equilibrium `AcidResult` conserves added nitrate; its delivery/recipe adapter is tracked under P5.5. |
| P3.5 | Post-mix verification protocol `[x]` | Required-measurement flag and documented operator protocol |
| P3.6 | Aqueous-equilibrium target-pH solver `[x]` | Closed-carbon, 25 °C nitric-acid solver passes its stated PHREEQC target-pH/reagent fixture tolerance |
| P3.7 | Fertilizer acid/base species coverage `[x]` | Macro + trace + ligand protonation and added nitrate use the same coupled solver; actual-product target agrees with nitrate titration and corrected Fix_H+; measurement flag and charge/component conservation tested |

**Exit condition:** the plan returns an initial dose, explicit validity range, nutrient contribution, and a required post-mix measurement; it never presents pH as exactly predicted.

**Decision gate G3:** closed analytical inorganic carbon, fixed product oxidation states, 25 C, and HNO3 define the target-pH scope, including the frozen catalogue chelates. Corrected PHREEQC Amm decoupling enforces the same nitrogen boundary; failed inputs and their full error text are preserved. Open-CO2 and alternate strong acids/bases remain separate future capabilities.

### P4 — Pump calibration and dosing planner `[x]`

**Objective:** convert a validated stock volume into bounded, auditable pump commands without controlling hardware.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P4.1 | Calibration record with date, stock density, test temperature, mean flow, variation, and valid range `[x]` | Required fields, invalid-range checks, non-zero density, and a 30-day default calibration-age policy are tested |
| P4.2 | Volume-to-runtime calculation `[x]` | Hand-calculated `t = V / q` fixture verified |
| P4.3 | First-order uncertainty calculation `[x]` | Flow/runtime uncertainty equation fixture verified |
| P4.4 | Command safety envelope `[x]` | Rejects dry tank, invalid flow, zero density, stale calibration, and out-of-range volume |
| P4.5 | Hardware-neutral command and verification interfaces `[x]` | Planning value only; no device I/O in package code |

**Exit condition:** a command includes requested volume, runtime, calibration provenance, uncertainty, and conditions that prohibit execution.

### P5 — Composed delivery plan `[x]`

**Objective:** combine accepted subsystems into one atomic, reviewable plan.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P5.1 | `DeliveryPlan` aggregate with recipe, stocks, pH plan, commands, warnings, and audit record `[x]` | Aggregate rejects partial validation and requires an audit model version; complete lifecycle fixture is checked in |
| P5.2 | Cross-stage constraint evaluation `[x]` | Recipe/stock identity and complete pH/pump composition fixture are tested |
| P5.3 | Approval state machine `[x]` | Explicit state transitions; no implicit approval |
| P5.4 | Human-readable report `[x]` | State, volume, stock, pump, pH, audit, and warning report implemented |
| P5.5 | Catalogue-equilibrium result to composed delivery adapter `[x]` | `src/flahax/equilibrium_delivery.py`, `tests/test_equilibrium_delivery.py`: explicit water-mass conversion, assayed HNO3 mass/volume, nitrate rescoring, source hashes, dedicated acid channel, rejection guards, PHREEQC target agreement and recipe-to-reviewed-plan integration; `docs/package-verification.md` |

P5.1–P5.4 remain accepted for the measured-curve path. P5.5 closes the integration gap with a distinct `EquilibriumPhPlan`; it preserves the existing `PhPlan` and low-level `AcidResult` contracts. The caller supplies fixed final solvent mass and final make-up volume; the model does not silently simulate dynamic dilution. Supersaturation or formed solids block delivery validation.

**Exit condition:** a complete plan is either `validated` with all evidence or `blocked` with actionable reasons. Partial values must never look executable.

### P6 — Simulation, verification, and release evidence `[-]`

**Objective:** prove the planner before any external integration.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P6.1 | Golden test fixtures `[x]` | Pepper plus high-alkalinity and incompatible-calcium/phosphate cases pass dependency-free |
| P6.2 | Property tests `[x]` | Deterministic stock/volume conservation invariant passes |
| P6.3 | Sensitivity tests `[x]` | Measured-curve demand, assay, temperature validity, injector ratio, and pump-rate perturbations produce bounded or explicitly rejected effects |
| P6.4 | Reference-equivalence evidence set `[x]` | Full species, activities, phase amounts and target-pH/nitric-dose evidence passes for the bounded mixed-product model; P2/P3 golden suite and live replay are recorded in release evidence |
| P6.5 | Release checklist `[x]` | In-repo release evidence and outstanding hosted-CI gate; G6 scope amendment is explicit |
| P6.6 | Installed-distribution and public API verification `[-]` | `tools/verify_distribution.py` passes isolated wheel/sdist imports, data hashes, exports, CLI and numerical delivery checks on Python 3.13; earlier Python 3.14 checks also pass. Supported-version hosted matrix still unverified. |
| P6.7 | Reproducible live-reference validation job `[-]` | `tools/provision_phreeqc.ps1` fresh pinned extraction passes; full local suite runs live with zero skips. Workflow retains logs and requires reference availability; `tests/test_live_reference_policy.py` tests fail-not-skip policy. Hosted job still unverified. |
| P6.8 | Computational assessment under owner-amended scope `[x]` | `docs/computational-review.md`, `docs/release-evidence.md`; named assessor Rafat Al Khashan; numerical conservation, convergence, reference equivalence, units and guards pass. No laboratory or independent-review claim. This status records numerical acceptance, not a fabricated personal signature. |

**Decision gate G6 (owner-amended 2026-09-27):** computational evidence assesses the bounded planning package without laboratory work. Assessor: **Rafat Al Khashan**. The assessment is not independent scientific certification or permission for operational dosing. Hosted release checks remain a separate, open gate.

### P7 — FlahaFAST integration (external project; not a package release gate)

**Ownership:** the project owner assigns this work to the separate FlahaFAST project. The following requirements are a handoff outline, not in-repository implementation or a prerequisite for FlahaX release.

**Objective:** expose an already-validated plan without changing the existing user flow by default.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P7.1 | Feature flag, default off | Existing workflow regression passes with flag off |
| P7.2 | Read-only plan request/response boundary | Schema contract tests and non-zero error handling |
| P7.3 | Review screen | Shows plan, uncertainties, warnings, and manual approval; never auto-accepts |
| P7.4 | Snapshot/audit linkage | Saves the plan and evidence IDs only after explicit acceptance |

**Exit condition:** the integration cannot write a recipe, trigger hardware, or alter a saved run without explicit future authorization.

## Prioritised backlog

| Priority | IDs | Why now |
|---|---|---|
| Preserve / regression protect | P0–P5, P6.1–P6.5, P6.8 | Accepted bounded capabilities and computational assessment; retain core formulation behavior and all chemistry evidence |
| Outstanding package verification | P6.6, P6.7 | Observe successful supported-version and live-reference hosted jobs; implementations and local evidence are present |
| Separate operational boundary | Physical validation | Not required for the owner-amended computational release; numerical agreement still cannot establish site safety |
| Later / optional | P7 | Begin only after the package interface and relevant release gates are accepted; no implicit FlahaFAST writes |
| Explicitly deferred | Full PHREEQC runtime integration; autonomous recirculating ion correction; cost optimization; pump actuation | The reference-equivalence harness comes first; runtime coupling needs a separate dependency and architecture decision |

## Metrics and release gates

| Metric | Target before operational use |
|---|---|
| Existing solver regression | Preserve core formulation behavior; changes to scientific baselines require documented source/model reasons and retained historical evidence |
| Planning calculation tests | 100% pass, including all rejection and boundary cases |
| Mass balance | Per-ion conservation within documented numeric tolerance |
| Stock plan | 0 unproven compatibility assignments; all concentrations under validated limits |
| pH plan | Measured-curve path requires a matched valid curve; equilibrium path requires complete bounded chemistry inputs and assay-qualified delivery conversion before composition. Both require post-mix measurement. |
| Package distribution | Clean installed wheel/sdist includes chemistry data, exports and working examples without source-tree imports or PHREEQC runtime dependency |
| Reference validation | Golden tests pass independently of PHREEQC; release evidence additionally includes a zero-skip pinned live replay |
| Pump plan | Current calibration, bounded uncertainty, and no command outside valid range |
| Physical validation (operational claims only) | Outside this computational release; any future operational claims need separately authorized measurement evidence |
| Safety | Every unsafe or incomplete input produces a blocked plan and a clear reason |

## Risk register

| Risk | Early warning | Mitigation | Owner required |
|---|---|---|---|
| Incomplete model input | Missing alkalinity, temperature, ions, gas boundary, or thermodynamic database | Block equilibrium solve; request the missing referenced input | Agronomy/operations |
| Product data differs from assay | Unverified label, lot change, oxide/element ambiguity | Versioned certificate/assay record; reject ambiguous units | Procurement/agronomy |
| Stock precipitation | Positive saturation index or phase constraint breach | Activity/speciation solve and named phase constraints | Chemistry/model owner |
| Pump drift | Delivered-volume deviation | Scheduled calibration and command bounds | Operations |
| Sensor drift | pH/EC inconsistency or stale calibration | Calibration schedule; reject stale data; independent spot checks | Operations |
| False confidence from EC | EC matches but modelled ion balance differs | Activity/speciation reference regression and elemental mass-balance review | Model owner |
| Scope creep into actuator control | Requests to auto-dose before evidence exists | Keep package planning-only; require a separate safety authorization | Product owner |

## Next execution plan

1. **Finish hosted P6.6/P6.7 acceptance.** The implementation and local checks are present. An authorized account owner must resolve the observed GitHub billing lock; then observe successful Python 3.11–3.13 distribution jobs and required live-reference replay. Do not mark blocked jobs as passed or publish to PyPI.
2. **Review this package increment.** Preserve both pH planning modes, explicit solvent/assay units and all golden/diagnostic evidence. Record review against the computational assessment attributed to Rafat Al Khashan; do not fabricate independent or experimental approval.
3. **Release preparation and review.** Audit package/API compatibility, documentation and distribution contents; require successful hosted checks before merging. Publication and a new version/tag require separate release authorization.
4. **P7 — external handoff.** Any FlahaFAST integration is implemented in the separate FlahaFAST project, not here. See `INTEGRATION.md` for the package boundary.

**Suggested next task:** “Once the account owner restores GitHub Actions, run and inspect the supported Python matrix and pinned live-reference workflow. Record actual outcomes before closing P6.6/P6.7. Then finish package release review; hand any P7 implementation to the separate FlahaFAST project.”
