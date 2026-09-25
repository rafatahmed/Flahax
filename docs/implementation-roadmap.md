# FlahaX Delivery System: Trackable Implementation Roadmap

## Purpose

This roadmap turns the delivery-control design into independently reviewable work. The target is an optional delivery-planning capability that converts a feasible FlahaX working-solution recipe into compatible stock-tank, pH, and pump plans without weakening the existing nutrient solver.

**Status key:** `[ ]` not started · `[-]` active · `[x]` accepted · `[!]` blocked or decision required.

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

P2, P3, and P4 may be developed in parallel after P0/P1. P5 must not begin until all three are accepted. P7 is deliberately last.

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

### P2 — Stock-tank compatibility and equilibrium model `[-]`

**Objective:** produce safe, explainable A/B/acid stock plans before modelling detailed equilibria.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P2.1 | Product compatibility graph `[x]` | Tests reject supplied separation-rule conflicts; rule provenance is reported |
| P2.2 | Per-product, temperature-bounded solubility-limit records `[x]` | Missing source/range fails; boundary and safety-margin tests |
| P2.3 | Tank-assignment constraint solver `[x]` | Deterministic assignment or explicit infeasibility explanation |
| P2.4 | Stock concentration and capacity calculation `[x]` | Hand-checked 1:100 examples; no tank overfill |
| P2.5 | Reference-model verification `[-]` | Dependency-free PHREEQC fixture harness, carbonate/calcium canary, and gypsum/anhydrite Example 2 fixture checked in; mixed nutrient-stock fixture family remains |
| P2.6 | Activity/speciation saturation model `[-]` | Carbonate/calcium and pure-water calcium/sulfate Davies kernels pass PHREEQC fixtures; phosphate/magnesium and mixed-fertilizer phases remain |
| P2.7 | Full fertilizer-chemistry data model `[-]` | Ca/Mg/phosphate PHREEQC 3.8.9 fixture, fixed-pH complexation kernel, and hydroxyapatite `SI=0` activity boundary added; precipitation extent, full activity model, and broader mixtures remain |

**Exit condition:** every selected salt has exactly one compatible storage channel, no limit/capacity is exceeded, and the plan names the rule that accepted or rejected each assignment.

**Decision gate G2:** select a published thermodynamic database and an activity model appropriate to the intended ionic-strength range. The current rule table is not the long-term scientific authority.

### P3 — pH and alkalinity equilibrium model `[-]`

**Objective:** calculate a bounded initial reagent dose from measured buffering, then require measurement-based verification.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P3.1 | Alkalinity normalization (`mg/L as CaCO3` to `meq/L`) `[x]` | Unit-tested conversion using 50.043 mg/meq; P3 dose remains based on a water-specific titration curve rather than a generic residual-alkalinity assumption. |
| P3.2 | Titration-curve record and interpolation `[x]` | Optional site-calibration path with monotonicity, endpoint, matched-record, and extrapolation-rejection tests |
| P3.3 | Acid/base dose plan `[x]` | Dimensional dose calculation; density, normality, and endpoint guardrails |
| P3.4 | Reagent addition feedback into nutrient balance `[x]` | Re-scored nutrient addition is included in every plan |
| P3.5 | Post-mix verification protocol `[x]` | Required-measurement flag and documented operator protocol |
| P3.6 | Aqueous-equilibrium target-pH solver `[-]` | First internal open-CO₂ carbonate/calcium pH kernel passes the PHREEQC canary fixture; reagent mole-balance and fertilizer species remain |
| P3.7 | Fertilizer acid/base species coverage `[-]` | PHREEQC-sourced 25 °C orthophosphate and ammonium/ammonia distributions added with mass-balance/domain guards; coupled mixed-ion pH solve and broader nitrogen coverage remain |

**Exit condition:** the plan returns an initial dose, explicit validity range, nutrient contribution, and a required post-mix measurement; it never presents pH as exactly predicted.

**Decision gate G3:** choose the gas boundary (closed total inorganic carbon or specified CO2 partial pressure), activity model, thermodynamic database, and allowed reagent stoichiometry. These are mathematical model inputs, not laboratory work.

### P4 — Pump calibration and dosing planner `[ ]`

**Objective:** convert a validated stock volume into bounded, auditable pump commands without controlling hardware.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P4.1 | Calibration record with date, stock density, test temperature, mean flow, variation, and valid range | Invalid/stale calibration rejection tests |
| P4.2 | Volume-to-runtime calculation | Hand-calculated fixtures; `t = V / q` verified |
| P4.3 | First-order uncertainty calculation | `u(V)^2 = t^2u(q)^2 + q^2u(t)^2` fixtures |
| P4.4 | Command safety envelope | Reject zero/negative flow, dry-tank, excessive dose, uncalibrated channel, and out-of-range runtime |
| P4.5 | Hardware-neutral command and verification interfaces | Test doubles demonstrate no device I/O occurs in package code |

**Exit condition:** a command includes requested volume, runtime, calibration provenance, uncertainty, and conditions that prohibit execution.

### P5 — Composed delivery plan `[ ]`

**Objective:** combine accepted subsystems into one atomic, reviewable plan.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P5.1 | `DeliveryPlan` aggregate with recipe, stocks, pH plan, commands, warnings, and audit record | Schema snapshot tests |
| P5.2 | Cross-stage constraint evaluation | Acid addition, stock constraints, tank capacity, and pump bounds evaluated together |
| P5.3 | Approval state machine | `draft -> validated -> operator-approved -> executed/verified`; no implicit approval |
| P5.4 | Human-readable report | Lists assumptions, inputs, equations, warnings, rejected options, and required measurements |

**Exit condition:** a complete plan is either `validated` with all evidence or `blocked` with actionable reasons. Partial values must never look executable.

### P6 — Simulation, verification, and release evidence `[ ]`

**Objective:** prove the planner before any external integration.

| ID | Deliverable | Acceptance evidence |
|---|---|---|
| P6.1 | Golden test fixtures | Pepper plus at least one high-alkalinity and one incompatibility case |
| P6.2 | Property tests | Non-negative mass/volume, unit consistency, constraint preservation, deterministic plans |
| P6.3 | Sensitivity tests | Water alkalinity, temperature, assay, injector ratio, and pump-rate perturbations produce bounded/visible effects |
| P6.4 | Reference-equivalence evidence set | Golden activities, species, saturation indices, pH/reagent amount, and numerical-tolerance comparison against the cited solver |
| P6.5 | Release checklist | Documentation, API stability, regression suite, safety review, version/citation update |

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
| Must have | P0, P1 | Prevents unsafe assumptions and protects the existing package contract |
| Must have | P2 | Solves the immediate physical stock-tank safety problem conservatively |
| Must have before automation | P3, P4, P5, P6 | pH and hardware decisions require calibrated, verifiable evidence |
| Later / optional | P7 | External application integration must not drive core chemistry design |
| Explicitly deferred | Full PHREEQC runtime integration; autonomous recirculating ion correction; cost optimization; pump actuation | The reference-equivalence harness comes first; runtime coupling needs a separate dependency and architecture decision |

## Metrics and release gates

| Metric | Target before operational use |
|---|---|
| Existing solver regression | 100% of current tests pass unchanged |
| Planning calculation tests | 100% pass, including all rejection and boundary cases |
| Mass balance | Per-ion conservation within documented numeric tolerance |
| Stock plan | 0 unproven compatibility assignments; all concentrations under validated limits |
| pH plan | Valid titration curve and post-mix measurement required for every accepted plan |
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

## Next action

**Current next action:** couple the checked-in nitrogen/struvite mixture's phosphate, ammonium, magnesium, and counter-ion mass balances into a fixed-pH mixed-ion speciation fixture. Full fertilizer chemistry advances family-by-family only with sourced thermodynamic data and fixture equivalence.
