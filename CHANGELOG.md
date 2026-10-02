# Changelog

## 0.3.1 - Unreleased

- Ship a complete generated public API inventory, expand the manual to seven executable examples, and check documentation drift in source and installed-package tests. Clarify product-dose mapping after recommendation filtering, stage statuses and unpublished-version installation.

- Clarify every pepper product's candidate Tank A/B/acid destination or unresolved status; display actual contents of synthetic stock examples, preserve recipe mass and prevent interpreting recipe acid as an additional pH dose.
- Document current capability limits and next steps; preserve supplied manufacturer PDFs locally while excluding them from versioned/package artifacts and retaining reviewed source hashes.

- Add interactive/JSON workflow, EC-screening and injector-sizing CLI commands; retain the legacy stdin contract. Require explicit source water and restrict standard workflow acids to nitric/phosphoric, preserving lower-level scientific references.
- Review four supplied fertilizer PDFs; add exact-SQM-brand pre-acid EC screening with unknown accuracy and unsupported-stock boundaries, plus channel volume/flow requirements for pump, venturi and Dosatron sizing. No fabricated equipment model selection.

- Add an offline HTML capability report with accessible SVG charts, explicit units and nutrient/chemistry/acid/EC/injection tables; keep synthetic evidence and missing-input statuses visible.

- Add recipe-calibrated EC25 estimation for separate concentrated stock tanks and combined irrigation solution, explicit meter-TDS conversion, and recipe-preserving injection/pump planning. Missing calibration never yields a fabricated EC value; no real calibration dataset or universal concentrated-stock predictor is claimed.

- Add runnable `examples/` capability scenarios and a combined JSON/Markdown report, with explicit synthetic-data boundaries and regression coverage; include examples in source distributions.

- Separate zero-target incidental nutrients from positive-target fit and explicit maximum concentrations; preserve real catalogue materials.
- Add explicit source-water-to-formulation orchestration, complete-analysis calculated pH, measured-curve/stock delegation and single-acid candidate planning for nitric, phosphoric, sulfuric and citric acids.
- Add four charge-balanced PHREEQC acid references with hashes, conservation/equivalence tests and live replay. These development APIs are not in the published 0.3.0 artifacts; see `docs/water-to-delivery.md` for assumptions and input requirements.

## 0.3.0 — 2026-09-27

### Added

- One bounded mixed aqueous model for all 28 catalogue product conversions, with preserved PHREEQC product, phase and nitric-acid reference evidence.
- Assay-qualified equilibrium-to-delivery planning: explicit water mass, reagent density, nitrate contribution, nutrient rescoring and source hashes.
- Dedicated acid-channel checks and rejection of target supersaturation/formed solids during delivery validation.
- Isolated wheel/sdist verification, hash-pinned external PHREEQC provisioning and a required live-reference CI job.
- A self-contained user manual shipped inside both wheel and source distribution, with tested Python examples.

### Fixed and clarified

- Identical initial/target pH returns exactly zero nitric acid.
- CLI examples supply the required salts array; historical chemistry notes are archived separately.
- Test calibration dates are deterministic; real runtime calibration expiry remains enforced.
- FlahaFAST integration belongs to the separate FlahaFAST project.

### Compatibility and limits

- Core `recommend` and CLI input contracts remain unchanged; no required third-party runtime dependencies.
- Public nitric-target functions return `AcidResult`; use `EquilibriumPhPlan` for reagent-volume planning. Earlier reduced-model fixtures retain explicitly named legacy solvers.
- The chemistry boundary is 25 °C, Davies I <= 0.1 mol/kg water, fixed product oxidation states and closed analytical inorganic carbon. No universal solubility, laboratory validation or equipment-control claim.
- Delivery record schema version `0.1` and chemistry model identifiers are independent of package version `0.3.0` and are not automatically renumbered.
- Hosted checks are blocked by account billing. The owner explicitly approved publication based on verified local evidence; the exception does not mark hosted checks as passed. PyPI confirms wheel and source-distribution publication on 2026-09-27; hosted verification remains outstanding.

## 0.2.0

Existing package baseline for fertilizer formulation. Earlier chemistry and planning development history remains in Git and the archived documentation; this changelog does not retroactively claim those developments were in the published 0.2.0 artifact.
