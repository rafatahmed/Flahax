# Changelog

## 0.3.0 — 2026-09-27, publication authorized

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
- Hosted checks are blocked by account billing. The owner explicitly approved publication based on verified local evidence; the exception does not mark hosted checks as passed. Upload success is recorded separately after verification.

## 0.2.0

Existing package baseline for fertilizer formulation. Earlier chemistry and planning development history remains in Git and the archived documentation; this changelog does not retroactively claim those developments were in the published 0.2.0 artifact.
