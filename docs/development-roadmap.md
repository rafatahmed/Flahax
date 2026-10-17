# FlahaX development roadmap

Updated 2026-10-17. Status: proposed priorities, not scheduled releases. The
published baseline is [0.4.0](https://pypi.org/project/flahax/0.4.0/)
(Apache-2.0, measured-pH water balancing).
The [implementation ledger](implementation-roadmap.md) retains P0–P7
acceptance and historical audits.

Site planning ([site planning](site-planning.md), [source review](source-sheet-review.md)),
the water-to-delivery workflow and the EC/injection planner shipped in 0.3.1.
General concentrated A/B EC, acid-adjusted full-recipe conductivity and
manufacturer-qualified equipment model selection remain open; brochure anchors
do not close these gaps.

## Assumptions and baseline

FlahaX remains a dependency-free Python planning library and CLI. Preserve the existing `recommend` contract, explicit g/L versus g/kg-water boundaries, model identifiers, source hashes and error semantics. FlahaFAST integration is owned by its separate project. No dates, staffing or expansion of the chemical domain have been agreed.

The repository already implements catalogue conversion, coupled equilibrium, measured-curve and nitric-acid pH planning, stocks, pump-planning values and composed delivery plans. It has golden PHREEQC evidence, failure reproducers and isolated distribution checks. Hardening should extend these assets instead of replacing them with a new solver or removing older exported compatibility APIs.

Hosted acceptance P6.6/P6.7 is closed: Python 3.11–3.13 jobs and the pinned live PHREEQC replay pass on `main` (first on `2e257d5`, run `38967066279`). The 0.4.0 candidate passes 162 local tests with live PHREEQC. From 0.4.0, publication runs the same checks inside the [hardened release workflow](publishing.md).

## Milestones and acceptance

The [water-to-delivery](water-to-delivery.md) workflow (0.3.1) does not
authorize a commercial dose from an incomplete water analysis. 0.4.0 anchors
source water at its measured pH; a field evaluation against measured pH, acid
demand and laboratory nutrient analyses is planned
([publication drafts](publication/README.md)). The
[EC/injection planner](conductivity.md) still lacks real calibration packs and
hold-out validation; synthetic interpolation tests are not physical accuracy
evidence. Automatic EC-setpoint dosing and a universal concentrated-stock
conductivity model are not claimed.

Version labels below are proposals. Assign an owner before starting each milestone; publish only after review and explicit release authorization.

| Order / candidate | Work and code anchors | Acceptance before completion | Suggested accountable role |
|---|---|---|---|
| M1 / 0.3.1 — done | Close P6.6/P6.7; `.github/workflows/test.yml`, `tools/verify_distribution.py`; reconcile release records | Successful Python 3.11–3.13 hosted distribution jobs and required pinned PHREEQC replay for the reviewed revision; retain run URLs, artifact hashes and actual skip counts; fresh PyPI install verification recorded | Maintainer; account owner for billing |
| M2 / 0.3.x | Expand input and numerical robustness in `aqueous_model.py`, `product_conversion.py`, `equilibrium_delivery.py` and planning contracts | Reproducible edge-case corpus; finite-input rejection, conservation, phase complementarity and convergence checks; failure cases return documented errors; existing golden tolerances and source provenance preserved | Numerical/model maintainer |
| M3 / 0.5.0 candidate | Stabilize consumer contracts, diagnostics and repeatable reports; `delivery_contracts.py`, `delivery_plan.py`, public exports | Documented serialization/version policy, round-trip and invalid-record tests, stable error codes and migration notes; compatibility tests for existing API/CLI examples | API maintainer |
| M4 / later minor releases | Choose one validated capability extension from the opportunity table | Approved scope and source data first; independent reference cases and rejection boundaries; documented compatibility and performance impact | Product owner with model reviewer |

M1 is complete: hosted checks passed on `main` at `2e257d5` (run `38967066279`; see the [0.3.1 release audit](release-evidence.md#031-release-audit---2026-10-17)) and 0.3.1 was verified by a fresh PyPI installation. 0.4.0 added measured-pH balancing outside these milestones. M2 can progress in parallel. M3 depends on agreed contracts; M4 chemistry changes depend on M2 regression coverage and their own scientific evidence. No future release inherits the 0.3.0 CI exception automatically.

## Hardening backlog

| Priority / ID | Concrete next increment | Evidence required |
|---|---|---|
| Done H1 | Hosted jobs failing on an account restriction | Resolved for 0.3.1: passing jobs with supported-version artifact checks and zero-skip reference replay |
| P1 H2 | Extend tests for NaN/infinity, negative/zero values, unknown ions, pH endpoints, I near 0.1, temperature rejection and extreme assay/volume inputs | Parameterized public-entry-point cases assert documented results/errors; no incidental traceback or plausible-looking invalid plan |
| P1 H3 | Exercise phase onset, disappearance, near-zero totals, competing phases and difficult Newton/active-set cases | Seeded generated cases; component residuals within declared tolerances, nonnegative solids and phase complementarity; retain minimized failures |
| P1 H4 | Improve convergence diagnostics around the existing iteration limits and line search | Failures identify stage, iteration count and residual without changing successful return contracts; deterministic regression cases |
| P1 H5 | Expand composed-plan rejection tests across mismatched record IDs, assay changes, stale calibration, acid-channel conflicts and altered recipe/stock data | Complete measured-curve and equilibrium paths reject inconsistent evidence and preserve atomic validation |
| P2 H6 | Establish benchmark baselines for formulation, mixed equilibrium and nitric-target planning | Fixed representative fixtures, machine/Python metadata, median and tail timing plus iteration counts; agree budgets after measurement, then compare changes |
| P2 H7 | Add development-only lint/type checks incrementally around public contracts and numerical code | Reviewed annotations/check configuration, clean selected modules and full regression pass; no new mandatory runtime dependency |
| P2 H8 | Release supply chain. Done for 0.4.0: tag/version guard, no re-upload, tests and live replay before build, reviewer-gated Trusted Publishing, protected `main`. Actions are pinned by full commit SHA (version in a trailing comment) and `.github/dependabot.yml` opens monthly update PRs; pins take effect for tags created after the change. Open: record or pin build-tool versions (`build`, `twine`) | Reviewed build-tool pinning policy and artifact provenance; distribution verification still passes |

These are test and review targets, not claims that the inspected code is defective. Existing tests already cover many guards; each increment should document the additional cases it contributes. Do not loosen scientific tolerances merely to make a new test pass.

## Development opportunities

| Opportunity | User value | Prerequisite and bounded first deliverable |
|---|---|---|
| Explainable formulation and infeasibility | Helps users understand missed targets and excluded salts | Report existing objective, residuals and exclusion reasons without changing `recommend` defaults; golden examples for feasible and infeasible targets |
| Versioned product/stock evidence packs | Reduces repeated caller data entry | Licensed, sourced assay and temperature-qualified compatibility/solubility records, with provenance and missing-data rejection; computational acceptance does not certify commercial lots |
| Uncertainty and sensitivity reports | Shows how assay, water or calibration variation changes a plan | Explicit input intervals and assumptions; compare against hand-checkable perturbations; distinguish sensitivity ranges from statistical confidence |
| Batch/scenario comparison | Compares water analyses or candidate recipes reproducibly | Stable serialization and benchmark baseline first; deterministic reports with units, warnings and source/model identifiers |
| Cost-aware formulation | Evaluates price versus nutrient fit | Versioned caller-supplied prices and availability, explicit objective tradeoffs and infeasibility tests; opt-in API preserves default results |
| Additional acids/bases, temperatures or gas boundaries | Serves more planning scenarios | Separate model proposal, thermodynamic sources, elemental/charge balances and independent reference fixtures for each extension; never extrapolate the current HNO3/25 °C/closed-carbon model silently |
| Optional FlahaFAST adapter | Makes package plans reviewable in the application | Package contract tests first; application-owned feature flag and explicit persistence approval; no application implementation in this roadmap increment |

Prioritize explainability and evidence packs before expanding the chemical domain. Their likely value is inferred from the current caller-supplied data burden and API boundaries; customer demand and effort have not yet been measured. Autonomous dosing and unrestricted concentrated-stock chemistry require separate scope and validation decisions.

## Working and release policy

Use phase-, issue-, stage- or release-based branch names under the
[development conventions](../CONTRIBUTING.md). See [current status](development-status.md)
for the release in preparation.

Keep one focused branch per increment. Delete merged branches only after checking for unique commits and active worktrees. Preserve source-backed scientific captures, failed-reference reproducers and released-artifact evidence; ignored build outputs and environments are not automatically disposable.

For each increment, record its owner, acceptance cases, dependency, compatibility impact and validation outcome. Run relevant tests plus the full suite for numerical/contract changes. Run isolated wheel/sdist checks when packaging, exported APIs or shipped assets change. Preserve real skipped-test counts and distinguish local results from hosted results.

Before the next release, require the [publishing checklist](publishing.md), reviewed changelog, supported-version evidence and explicit publication approval. Keep package, record-schema and chemistry-model versions independent. Broader operational claims require separately authorized measurement evidence.

## First three work items

1. Prepare the field-trial protocol inputs (water analyses with measured pH and alkalinity) and record build-tool versions (H8).
2. Add H2/H3 cases around current numerical boundaries, including measured-pH balancing near its imbalance limit, and retain every reproducible failure before changing solver behavior.
3. Specify M3 serialization and error contracts, then select an explainability increment with a concrete user example (for example, why the best mass balance can be chemically wrong).
