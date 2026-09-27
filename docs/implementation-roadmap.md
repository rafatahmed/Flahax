# FlahaX Package: Trackable Implementation Roadmap

## Purpose

This roadmap tracks package capabilities and their evidence, not deployment or hardware control. FlahaX's dependency-free nutrient formulation API and CLI remain the core product. Optional chemistry and delivery-planning APIs extend a feasible working-solution recipe without weakening that existing contract. FlahaFAST is a later consumer of the package, not a prerequisite for its usefulness or release.

**Status key:** `[ ]` not started · `[-]` active · `[x]` accepted · `[!]` blocked or decision required.

`[x]` means implemented and numerically verified within the documented boundary. It does not mean commercial-product certification, independent scientific approval, or permission to operate equipment. Section status includes any newly identified integration work; completed rows retain their evidence.

## Package audit baseline — 2026-09-27

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

P2/P3/P4 have bounded numerical implementations. The measured-curve P5 composition is implemented; the newly tracked equilibrium-result bridge must pass its own end-to-end checks before that path is called composed. P6 package hardening and G6 review precede operational advertising. P7 remains deliberately last and optional.

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

### P5 — Composed delivery plan `[-]`

**Objective:** combine accepted subsystems into one atomic, reviewable plan.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P5.1 | `DeliveryPlan` aggregate with recipe, stocks, pH plan, commands, warnings, and audit record `[x]` | Aggregate rejects partial validation and requires an audit model version; complete lifecycle fixture is checked in |
| P5.2 | Cross-stage constraint evaluation `[x]` | Recipe/stock identity and complete pH/pump composition fixture are tested |
| P5.3 | Approval state machine `[x]` | Explicit state transitions; no implicit approval |
| P5.4 | Human-readable report `[x]` | State, volume, stock, pump, pH, audit, and warning report implemented |
| P5.5 | Catalogue-equilibrium result to composed delivery adapter `[ ]` | Explicit g/L-to-g/kg-water conversion; water mass and reagent assay/density; molal HNO3 to bounded mass/volume; nitrate feedback and recipe rescoring; source/model hashes; missing-data and out-of-domain rejection; one integration test from recipe through reviewed delivery plan |

P5.1–P5.4 remain accepted for the measured-curve path. P5.5 is an audit-discovered integration gap, not a claim that the P2/P3 numerical solver failed. It must retain both planning modes explicitly rather than silently substituting one for the other.

**Exit condition:** a complete plan is either `validated` with all evidence or `blocked` with actionable reasons. Partial values must never look executable.

### P6 — Simulation, verification, and release evidence `[-]`

**Objective:** prove the planner before any external integration.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P6.1 | Golden test fixtures `[x]` | Pepper plus high-alkalinity and incompatible-calcium/phosphate cases pass dependency-free |
| P6.2 | Property tests `[x]` | Deterministic stock/volume conservation invariant passes |
| P6.3 | Sensitivity tests `[x]` | Measured-curve demand, assay, temperature validity, injector ratio, and pump-rate perturbations produce bounded or explicitly rejected effects |
| P6.4 | Reference-equivalence evidence set `[x]` | Full species, activities, phase amounts and target-pH/nitric-dose evidence passes for the bounded mixed-product model; P2/P3 golden suite and live replay are recorded in release evidence |
| P6.5 | Release checklist `[x]` | In-repo release evidence and external-gate checklist are checked in; independent review remains G6 |
| P6.6 | Installed-distribution and public API verification `[ ]` | Build wheel/sdist; install in a clean environment outside the source tree; verify bundled `chemistry_25c.json`/library, public imports, CLI, catalogue solve and target-pH examples; document return-type changes and supported Python versions; no PHREEQC runtime dependency |
| P6.7 | Reproducible live-reference validation job `[ ]` | Provision pinned PHREEQC outside the package; verify database/executable hashes; run every golden case with zero skips; retain logs; ordinary dependency-free tests must still work without PHREEQC |
| P6.8 | Independent scientific and bench/site acceptance `[ ]` | Named reviewer, reviewed ligand activity/concentration and stereoisomer assumptions, lot/water records, predeclared uncertainty/tolerances, measured pH and precipitation observations, investigated deviations, dated sign-off; satisfies G6 |

**Decision gate G6:** an independent reviewer signs off on test and bench evidence before the planner is advertised for operational use.

### P7 — Optional FlahaFAST integration `[ ]`

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
| Preserve / regression protect | P0–P4, P5.1–P5.4, P6.1–P6.5 | Accepted bounded capabilities; retain core formulation behavior and all chemistry evidence |
| Next package increment | P6.6, P6.7 | Prove the distributed package and make live reference verification repeatable, rather than relying only on a source checkout |
| Next integration increment | P5.5 | Bridge verified equilibrium results to the existing composed delivery API with explicit units, assay and audit semantics |
| Required for operational claims | P6.8 / G6 | Numerical agreement alone cannot establish scientific calibration or site safety |
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
| Bench validation | Measured versus predicted results within pre-approved tolerances, with deviations investigated |
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

1. **Review and merge the current branch by pull request.** Review core API compatibility, source-profile limitations and all preserved fixture evidence; require repository CI. Opening the PR is not approval to merge or publish a release. Do not regenerate or discard passing fixtures merely to make a review smaller.
2. **P6.6/P6.7 — package verification.** Add clean-distribution smoke tests, public Python/CLI examples and a pinned live-reference validation job. Exit when the installable package and source checkout agree, supported Python CI passes, and the live evidence has zero skips. Do not publish to PyPI as part of this work without separate release authorization.
3. **P5.5 — explicit equilibrium delivery bridge.** Specify the return-type/units contract, implement reagent assay and density conversion plus recipe rescoring, then test one complete catalogue-dose-to-delivery path and every missing-input rejection. Preserve the existing measured-curve path.
4. **P6.8/G6 — independent review and bench/site evidence.** Assign scientific and operations reviewers; agree the protocol and tolerances before measurement; record discrepancies and sign-off. Prepare the review dossier alongside package hardening, but do not mark the gate accepted without external evidence.
5. **P7 — optional read-only integration.** Only after those gates, expose a versioned package boundary behind a default-off flag. No pump control, deployments, credential changes or external data writes are authorized by this roadmap.

**Suggested next task:** “Complete P6.6/P6.7 package verification: clean wheel/sdist installation, public chemistry API and CLI smoke tests, supported Python CI, and reproducible pinned PHREEQC live replay. Preserve all golden and diagnostic evidence; do not alter the frozen product chemistry, publish a release, or implement external integration.”
