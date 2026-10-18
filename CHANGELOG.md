# Changelog

## Unreleased

- Add experimental irrigation EC25 from speciation (McCleskey 2012 Eq. 8) with explicit partial results, envelope checks and provenance; no accuracy claim.
- Add the material traceability API (`docs/materials.md`): shipped identity records (`load_identities`, `identity_for_product`), user grades and lots (`make_grade`, `make_lot`), `resolve_material` (per-nutrient basis, band ends, flags, provenance) and `nutrient_band`; `catalogue_dose_totals` and `calculate_irrigation_ec` take `materials=`, undisclosed blends raise or report `composition_undisclosed` in chemistry, and EC and equilibrium-delivery audits carry material provenance.
- Link every catalogue product in `library.json` to its chemical identity (`identityId`) and record its `analysisBasis` (`declared_catalogue`, `identity_theoretical` or `grade_typical`) and `source` document reference. Product `id` and `name` values are unchanged.
- Correct Mg Nitrate to Mg(NO3)2·6H2O theory (owner decision D1): formula `Mg(NO3)2` → `Mg(NO3)2.6H2O`; N_NO3 11 → 10.92564 %, Mg 9.65 → 9.47931 %; basis `identity_theoretical`. Its declared-form charge residual at 1 g/kg water goes from +0.5532 % to ~0 %, so it no longer trips the EC O5 gate on its own.
- Correct Phosphoric Acid (75%) to the 75 % w/w solution: P 31.61 → 23.706035 % (0.75 × 31.608046, product-mass dosing); PO4 delivered per gram falls to 0.74995 × the old value. Its stored assay is now reported as drifting from the H3PO4 formula, as intended for a solution.
- Calcium Nitrate (ag grade) keeps N_NO3 14.4 / N_NH4 1.1 / Ca 19 % and now cites the Haifa Cal NG technical data sheet (October 2018) with basis `grade_typical`. Metadata: Urea formula `Urea` → `CO(NH2)2` (the formula check now reads urea's amide N as N_UREA, so Urea stays eligible); display names "Iron(II) Sulfate (Heptahydrate)" and "Potassium Citrate (anhydrous)".
- Recommended doses (g/L, `recommend` with all eligible products and the formula's water) change for 20 of the 26 shipped formulas: Chilli, DEFAULT, Generic Bloom, Generic Dry Season, Generic Grow, Generic Wet Season, Generic for Berries, Hoagland, Lettuce 2, Lettuce General, Melons, Pepper (Howard Resh), Rice, Strawberry Drip Irrigation, Strawberry Fruiting, Tomato (Howard Resh), Tomatoes Fourth/Third Cluster and to termination, Tropical Lettuce. Pepper regression recipe (Test01, Ca 20 ppm water): Mg Nitrate 0.414486 → 0.421953, Phosphoric Acid (75%) 0.117392 → 0.151738; pepper water workflow: Mg Nitrate 0.414483 → 0.421949, Phosphoric Acid (75%) 0.098687 → 0.126809, incidental N_NH4 4.845114 → 4.845193 ppm.
- Chelates now carry their sodium counterions in chemistry totals (D2); recipes with chelates show incidental Na in equilibrium and EC results. Per formula unit: Fe-EDTA 1, Mn/Zn/Cu-EDTA 2, Fe-DTPA 2, Fe-o,o-EDDHA 1 Na, also added to CH - micro's borax and molybdate sodium; product `elements` are unchanged, so formulation is unaffected. Na+ at 1 g/kg water: Iron EDTA 0 → 53.52 mg, Zn EDTA 0 → 98.46 mg, Mn EDTA 0 → 108.80 mg, Copper EDTA 0 → 101.30 mg, Iron DTPA 0 → 90.57 mg, Iron EDDHA 0 → 24.70 mg, CH - micro 14.06 → 63.23 mg. Declared-form charge residuals fall to ~0 % (Iron EDTA −14.29 %, Zn/Mn/Cu EDTA −33.33 %, Iron DTPA −25.00 %, Iron EDDHA −14.29 %, CH - micro −12.76 %), so chelate recipes no longer trip the EC O5 gate. Borax declares its ion forms (`Na+`, `B(OH)4-`, `B(OH)3`; −0.5 charge per B in the residual): residual +100 % → +0.006 %; its equilibrium totals are unchanged (boron stays the H3BO3 basis).

## 0.4.0 — 2026-10-17

- Relicense FlahaX under the Apache License 2.0 and add a `NOTICE` file. Releases up to and including 0.3.1 remain under the Flaha Free Use License 1.0.
- Add `balance_water_analysis`: speciate a laboratory water analysis at its measured pH, take inorganic carbon from the analysis or from titrated alkalinity, and close the remaining charge on Cl- or Na+ with the imbalance and adjustment recorded. Imbalances above 5% (configurable) are rejected. The workflow's `equilibrium` record accepts `measured_ph` and reports `water_balance`. Charge balance alone turned a 3.5% analytical imbalance on a published Qatar well into a 4-unit pH error.
- Add publication drafts under `docs/publication/` (JOSS paper, field-trial article, story piece in English and Arabic, worked example); they are excluded from the source distribution.
- Add the author's ORCID to `CITATION.cff`.
- Harden the release workflow: a GitHub Release uploads only when its tag matches the package version and that version is new on PyPI, after the full test matrix, clean installs and the live PHREEQC replay pass, and after reviewer approval, via PyPI Trusted Publishing.
- Bring the documentation up to date with 0.3.1 and 0.4.0, and remove two unreferenced 0.2.0 images from `docs/` (and so from the sdist).

## 0.3.1 — 2026-10-17

- Reframe the README, package summary and citation around FlahaX as a plant-nutrient chemistry engine (planned for FlahaFAST, not yet integrated); harden `.gitignore`, `.gitattributes` and the distribution PDF leak check.
- Exclude the user-supplied YaraVita micronutrient guide from Git tracking and the source distribution, matching the other manufacturer PDFs; its SHA-256 is recorded in the source review. The published 0.3.0 sdist still contains it.
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

## 0.3.0 — 2026-09-27 (yanked 2026-10-17)

Yanked on PyPI after 0.3.1 was published: its source distribution contained a third-party PDF. Use 0.3.1.

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
