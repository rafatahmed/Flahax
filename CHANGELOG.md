# Changelog

All notable changes to FlahaX are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow
[PEP 440](https://peps.python.org/pep-0440/); while FlahaX is below 1.0, a minor release may change
behaviour, and every such change is listed under **Changed** or **Removed**. The full notes of
each release, with numbers, sources and decisions, are in
[docs/releases](https://github.com/rafatahmed/Flahax/tree/main/docs/releases).

## [Unreleased]

- Correct the current release index while retaining historical publication evidence; add
  migration guidance and executable documentation checks for current calculation contracts.

- Preserve hard-zero targets and undefined relative differences in reports, sheets and terminal
  views; suppress blocked-sheet preparation actions and retain offline full-precision scientific
  qualifications, provenance and EC applicability evidence.

### Added

- Add native console/PTY and controlled terminal lifecycle checks, including
  canonical-result and stale-session rejection in the full-screen workflow (#182).

- Export canonical-result acceptance and archive APIs at package level. Validate
  public CLI/file contracts and preserve hard nutrient maxima and explicit
  permissions in recommendation JSON; reject unsupported fields (#181).
- Update mix CLI regression assertions for qualified blocked workflows while
  preserving historical numerical transcripts (#180).

- Bind explicit proposal acceptance to exact result content, validate saved-result
  archives, and detect saved-session input/source drift with explicit legacy
  migration. Consent never waives calculation guards (#179).

- Evaluate explicitly supplied catalogue bundles, treated-water analyses and stock
  equipment alternatives under unchanged targets and limits. Retain candidate
  evidence, remaining requirements and honest conditional/budget outcomes (#178).

### Changed

- Fit N_NO3, N_NH4 and N_UREA each as its own target and report total N as their sum; an
  absent N_UREA is a declared zero; N_NH4 0 is no requirement, not a ban, and incidental NH4-N
  is held within min(10 % of total N, 1.5 mmol/L), Dutch soilless practice, shown in
  `ammoniumLimit` and the batch summary (#209, #201).

- The packaged catalogue is the owner's Flaha Agri Tech Analysis Ver 0.0: 24 fertilizers, 5 pH products and 13 crop formulas.

### Fixed

- Normalize POSIX mode-inspection/setup/restoration failures and attempt rollback
  after partial input-mode setup; validate the distinct native `termios.error`
  path as well as ordinary I/O failures (#183).

- Stop terminal input on POSIX EOF and attempt screen/cursor cleanup after partial
  screen-entry failures while restoring console mode and retaining the original
  error (#182).

- Bind workflow reports to immutable calculation snapshots, product records and
  model-source fingerprints. Reject changed calculated fields, retain shared
  export identities, and separate computational and delivery qualifications (#177).

- Reconcile stock masses, final-volume ratios and distinct reagent/pump channels
  before delivery validation. Reject stock-volume overflow/underflow and future
  calibration dates; retain titration final-volume identity and qualify additive
  carrier accounting separately from hydraulic and contact models (#175).

- Keep weighed-recipe chemistry, pH and EC on the same equilibrium state when no
  reagent is selected. Retain rejected-candidate diagnostics separately and report
  unavailable legacy state identity explicitly (#174).

- Retain stock separations regardless of tank count or micronutrient dose. Search
  equipment-constrained alternatives, require matched mixture-model applicability,
  and prevent unqualified stock layouts from validating delivery plans (#161).

- Distinguish historical solubility screening floors from qualified limits. Require
  explicit source basis, grade and temperature evidence; report floor exceedances
  as inconclusive and retain qualification in public reports (#172).
- Separate synthetic terminal rendering states from actual phase-blocked workflow
  tests, preserving blocked status and absent reagent selection (#173).

- Remove phase-name exemptions from saturation decisions. Keep thermodynamic
  signs, applicability evidence and allocated solids distinct; unresolved or
  out-of-condition evidence prevents approval without inventing kinetics (#161).

- Keep unknown conductivity contributions partial instead of inventing a universal
  bound or midpoint. Preserve EC qualifications in grower output, distinguish
  uncertainty sources, and evaluate explicit joint assay scenarios (#161).

- Reject irrigation EC predictions beyond the recorded phosphate fit ceiling,
  retain fit-domain audit evidence, and reproduce coefficients with independent
  Decimal QR verification and withheld KCl comparisons (#161).

- Integrate explicit joint fertilizer/reagent fitting into the public workflow;
  rebuild final quantities and diagnoses and independently verify final pH.
  Add bounded zero-reagent recovery when the legacy call offers no reagent in
  the initial required direction; retain unresolved search and hard limits.

- Recheck final joint charge corrections on cold equilibrium states and rebuild
  stationarity at the corrected quantities. Restore charge through bounded
  fertilizer adjustments when the reagent cannot move in the required direction.

- Add opt-in joint objective-gap and first-order stationarity checks for nonzero
  best-fit results, with rational certificates and fresh constraint verification.
  Add linearized charge-equality steps and separately checked charge sensitivities;
  preserve existing target thresholds and production acceptance policy.
  Use direct nutrient gradients and precision-preserving feasible-step comparisons
  to prevent roundoff from hiding near-optimum progress. Opt-in implicit equilibrium
  derivatives, curvature polishing and verified zero-boundary recovery address stiff
  chelate sensitivities; independent derivative and cold-state checks retain failures.

- Add joint-fit qualification checks with independent rational nutrient accounting,
  water-only objective lower bounds and retention of every multistart failure.
  Add matched acid-reference regressions; production acceptance is unchanged.

- Add a joint fertilizer/reagent numerical search with feasible steps, checked
  sensitivities, rank-aware fallback and fresh final residual verification.
  Explicit caller controls and incomplete-search diagnostics keep numerical
  candidates separate from production acceptance.

- Add immutable joint fertilizer/reagent problem records and fixed-candidate
  evaluation with explicit nutrient/component units, charge residuals, zero-dose
  boundaries and hard constraints. Add a supplied-inventory compiler; optimizer
  integration and joint acceptance remain separate.

- Recover permitted available nutrient sources from an empty initial pool and
  repeat substitution when a new deficit appears. Record searched inventory and
  incomplete-search outcomes without changing targets or expanding available stock.

- Distinguish target-subset charge from emitted nutrient inventory without claiming
  impossibility from partial charge sums. Label unmet-target structural proofs and
  relaxed search observations explicitly, including source-water and zero misses.

- Preserve every positive product dose at full floating-point precision so emitted
  quantities reproduce nutrient results, including trace molybdenum.
- Render mass-only pH reagents in grams across terminal, report and batch sheets
  without inventing a liquid volume or crashing (#169).
- Add `rescore_weighed_recipe` to reassess actual weighed masses against original
  nutrient targets, source water and hard limits without refitting.

- Prevent recipe simplification from degrading the original nutrient fit or
  accumulating drift across product removals. Recheck zeros and maxima on each
  trial and retain all positive internal doses; product count cannot increase
  primary loss or use the feasibility band as an accuracy allowance.

- Fix coupled pH trial direction crossings and discontinuous product switches by
  bracketing and verifying a blend of the endpoint recipes. Rebuild final nutrient
  assessments without changing targets, ceilings or chemistry constants. Initial
  opposite-direction products remain inapplicable; global joint fitting remains open.

- Fix primary fitting to minimize positive-target squared relative error without
  hidden dose or incidental-ion penalties. Keep incidental reporting and hard limits.
  `ridge` now defaults to zero and rejects nonzero values; remove old explicit
  regularization arguments. Report unexplained fit degradation without blaming a
  removed penalty, and recognize binding ceilings within the solver convergence criterion.


- Enforce explicit zero nutrient requirements and targeted hard maxima; report
  contradictory targets and source-water excess without relaxing the inputs.


- Conserve calcium/sulfate in retained pairing calculations and reject exhausted
  legacy equilibrium iterations; add kernel conservation, domain, phase and
  failure-path controls with explicit current/legacy model distinctions.


### Added

- Independent rational bounded-fit and high-precision acid-equilibrium oracles,
  matched-reference error accounting, and adversarial verification controls.
  Reports identify shared provenance and the limits of reference agreement;
  runtime tolerances and reference data remain unchanged
  ([#161](https://github.com/rafatahmed/Flahax/issues/161)).

### Changed

- Aqueous results now identify omitted ligand/metal competition and selected
  chelate-profile limitations, with explicit model-domain metadata. Added read-only
  qualification of every pinned reaction's source, balances and basis transform;
  reference constants and database bytes are unchanged.

- Nutrient fitting now includes supported material counterions before selecting doses,
  including sodium carried by chelates. A shared inventory traces nutrient percentages
  and conserved chemistry components, with explicit incomplete and blend-disagreement
  fields. Water and acid/base nutrient supply use the same component projection.

- Ammonium limits are now explicit caller inputs: no default fraction or hidden
  absolute cap. Material provenance identifies source/assumption status and the
  versioned atomic-mass convention; retained atomic values are unchanged
  ([#161](https://github.com/rafatahmed/Flahax/issues/161)).

### Fixed

- Protect retained PHREEQC reference bytes with a complete inventory and require
  fresh capture destinations. Reject malformed/nonfinite reference results, verify
  executable/database pins for every current live family, and distinguish historical
  evidence from shared-data implementation agreement
  ([#166](https://github.com/rafatahmed/Flahax/issues/166)).

- Reject invalid or unfinished root searches, remove the scale-dependent absolute
  equilibrium pivot floor, and require pH-width evidence alongside charge closure.
  Added numerical residual and NNLS optimality diagnostics with independent scaled
  and high-precision controls; existing acceptance tolerances are unchanged
  ([#165](https://github.com/rafatahmed/Flahax/issues/165)).

- Account for supported noncarbonate alkalinity before inferring missing carbon.
  Preserve measured zero/fixed carbon and titrated alkalinity; keep interactive
  titration input separate from the legacy HCO3 carbon approximation. Reject
  unqualified proton references rather than inventing carbonate
  ([#161](https://github.com/rafatahmed/Flahax/issues/161)).

- Respect explicit final solvent mass or density/nonwater mass when converting
  water mg/L to molality; scale detection limits and blends on the same basis.
  Report concentration assumptions and provide a water/carrier/hydrate ledger
  ([#161](https://github.com/rafatahmed/Flahax/issues/161)).

- Reject non-finite/non-positive identity masses and boolean ion stoichiometry,
  while retaining explicitly unavailable masses as null
  ([#163](https://github.com/rafatahmed/Flahax/issues/163)).

### Added

- Offline requirement/ledger validators, numeric-decision inventory and review gates, and source-bound
  statement/branch coverage collection and gates, with preserved failing audit controls
  ([#159](https://github.com/rafatahmed/Flahax/issues/159),
  [#160](https://github.com/rafatahmed/Flahax/issues/160),
  [#161](https://github.com/rafatahmed/Flahax/issues/161),
  [#162](https://github.com/rafatahmed/Flahax/issues/162)). No runtime correction is claimed.

- The Zenodo DOI in `CITATION.cff` and the README: concept DOI 10.5281/zenodo.23605678, version 0.6.0 10.5281/zenodo.23605679.

## [0.6.0] - 2026-10-24

The grower release: FlahaX becomes a tool a grower or agronomist can run without code
(`flahax mix`, `flahax batch`), plans the recipe and its pH reagent together, checks stock
solubility, and moves to Beta. No breaking API change (14 names added, none removed); Python 3.11
or newer, still with no runtime dependencies. Known limits: the full-screen `flahax mix` is alpha
(`--plain` always works; typing "Ã " on Windows swallows the next key, #127), solubility checks are
single-salt lower bounds, and there is no physical validation yet (#41).
[Full notes](https://github.com/rafatahmed/Flahax/blob/main/docs/releases/0.6.0.md).

### Added

- Troubleshooting for installing, upgrading and the full-screen `flahax mix` in the user guide and the README.
- `flahax mix`: five steps (specification, water analysis, crop formula, fertilizers available, target pH) that save waters, formulas, product stores, acids and sessions under `$FLAHAX_HOME` (default `~/.flahax`) and write a batch sheet for the grower, the agronomist or the full report; `flahax mix sessions/NAME` repeats a batch.
- Full-screen `flahax mix` in a terminal, standard library only (#124): arrow keys, type-to-filter lists, tick lists, and Tanks, Nutrients and Notes views. `--plain`, scripts and pipes keep the line-by-line questions.
- `flahax batch`: one formula and one water to `batch-sheet.html`, `report.html` and `summary.json`, with the pH plan (#79); `--water-share` blends a measured water with RO water (#84).
- Recipe and pH reagent planned together (`plan_coupled_ph`), with pH-up reagents (#74-#77).
- Sourced stock solubility for 20 products (CRC Handbook, Yara, U.S. Coast Guard CHRIS), checked at the stock temperature.
- Materials defined by what they put in the water (`material_chemistry`): a chemical formula, its ions, or a supplier analysis.
- Public API: `plan_coupled_ph`, `reagent_dose`, `catalogue_ph_reagents`, `PhAdjustmentPlan`, `PhCandidate`, `material_chemistry`, `group_tanks`, `default_compatibility_rules`, `TankGrouping`, `ConcentrateTank`, `TankProduct`, `summarize_batch`, `render_report`, `render_batch_sheet`.
- An error-code reference in the user guide covering all 91 codes, checked by a test.
- `SECURITY.md`, a code of conduct (Contributor Covenant 2.1), Codecov coverage, README status badges, and CI on Windows and macOS (#150).
- A draft physical-validation protocol (#41) and the Irriblend-DSW optimiser in the competitor benchmark (#40).

### Changed

- The documentation site is organised for its readers (DiÃ¡taxis): Get started, a grower, an agronomist and a developer and researcher guide, Reference (command line, Python API, input files, error codes), Explanation, Evidence and Project, with diagrams; moved pages redirect from their old addresses.
- `flahax --help` describes every command, with examples and links to the documentation and the issue tracker; the README follows the order a reader needs (installation, quick start, commands, troubleshooting); the changelog follows Keep a Changelog 1.1.0 for every release.
- Supplier labels may differ from their chemical's charge balance by up to 1 % (was 0.1 %) (#93).
- A water report without chloride closes its charge balance on alkalinity instead of being blocked (#100).
- Concentration limits and targets use the laboratory water analysis; the charge-balanced water is for chemistry only (#84).
- Untargeted nutrients are assessed once, with the products that supply them; ammonium keeps the 10 % allowance, shown with its source (#92).
- Phases that do not form at feed conditions (hydroxylapatite, goethite, MnHPO4, vivianite) make a plan `requires_review` with the reason, instead of rejecting it (#78).
- The growers page is a task path with a worked example that a test re-runs (#80).
- Development status Beta; Python 3.14 supported; maintainers, affiliation, a full NOTICE of data sources and verified references in `CITATION.cff`.
- Code style: PEP 8 at 99 columns enforced in CI, file headers, and docstrings on every public definition (#120-#122).

### Fixed

- `recommend()` raised "NNLS did not reach optimality" when the water alone exceeded one declared maximum while another was binding (#86).
- Bad input at any entry point, or a damaged session file, gives a plain message instead of a traceback (#117, #149).
- First field tests of `flahax mix`: the formula list (#98), the start screen and `--version` (#102), saved sessions and small weights (#105), unknown acid formulas (#112), repeated notes (#113) and titles (#114).
- Every output of one batch agrees: pH path, weights, acid volume and notes on the terminal, sheet and report (#107-#110).
- The owner's trial of the full-screen mode: Windows arrow keys (#135), readable key help (#137), confirm before leaving (#138), filter and tick keys (#139), number display (#140), wrapping (#141), grower words (#142), and #125-#132, #143-#147.
- The 0.5.0 manual and changelog kept the release-candidate wording; publishing now has a finalize step before tagging (#71).

## [0.5.0] - 2026-10-20

Faster and more reliable formulation and equilibrium, chloride products, material traceability
and irrigation EC, with the first fully passing Benchmark v1. Recommended doses change for 20 of
the 26 shipped formulas (catalogue corrections below).
[Full notes](https://github.com/rafatahmed/Flahax/blob/main/docs/releases/0.5.0.md).

### Added

- `recommend()` reports `targetIonBalance` (warning beyond 10 %) and `unmetTargets`, each missed target with its reason (#39).
- Incidental-ion ceilings in the fit (`maximum_concentrations`); any excess is reported in `limitViolations`.
- Potassium chloride and calcium chloride (dihydrate) in the catalogue (30 products), used only when chloride is targeted or allowed.
- Material traceability: identities, grades and lots, `resolve_material` and `nutrient_band`; every catalogue product names its identity, analysis basis and source.
- Experimental irrigation EC25 from speciation (McCleskey 2012), with bounded estimates for uncovered species, phosphate coefficients fitted to Pethybridge et al. (2006), and `calculate_irrigation_ec_band`.
- Per-salt provenance and `identitiesSha256` in `recommend()` results.
- Feed-pH notes against Dutch soilless practice and a residual-bicarbonate warning in the acid plan.
- Documentation site at https://flahax.readthedocs.io/.
- Benchmark v1 snapshot 2026-10-20-linux-df0d30b, the first with every correctness gate passing (#66).

### Changed

- `recommend()` is 2.8-4.0x faster (#59); equilibrium solves are 3-5x and their searches 10-25x faster (#37, #61), with numerically equivalent results.
- Incidental NH4-N is allowed up to the smaller of 10 % of total N and 1.5 mmol/L when the formula has no N_NH4 (#54).
- Incidental-ion ceilings reach their limit in one refit (#56).
- Catalogue: Mg Nitrate is Mg(NO3)2Â·6H2O; Phosphoric Acid (75%) is a 75 % solution; Calcium Nitrate cites the Haifa sheet; ammonium sulfate and urea cite ChemicalBook sheets.
- Chelates carry their sodium counterions in chemistry, and formulation reports that sodium as incidental Na.
- Chlorine uses 35.45 g/mol everywhere.
- NNLS raises `InputError` at its iteration cap instead of returning a non-optimal fit (#55).

### Fixed

- NNLS stopped early on near-dependent or small-scale problems (#36) and gave start-dependent recipes under ceilings (#68).
- The equilibrium solver failed between pH 4.2 and 5.05 for chelate-rich solutions (#52) and stalled at some near-singular states.
- Catalogue chemistry dropped chloride and assumed a calcium salt carried nitrate.
- Benchmark v1 measured no timings (#64).

### Removed

- Internal specifications and plans from the repository.

## [0.4.0] - 2026-10-17

The first release under the Apache License 2.0, with water analyses speciated at their measured
pH. [Full notes](https://github.com/rafatahmed/Flahax/blob/main/docs/releases/0.4.0.md).

### Added

- `balance_water_analysis`: a laboratory water analysis speciated at its measured pH, carbon from the analysis or titrated alkalinity, and the remaining charge closed on Cl- or Na+ (imbalances above 5 % rejected). The workflow accepts `measured_ph` and reports `water_balance`.
- Publication drafts under `docs/publication/`, excluded from the source distribution.
- The author's ORCID in `CITATION.cff`.

### Changed

- Licence: Apache License 2.0 with a `NOTICE` file. Releases up to and including 0.3.1 remain under the Flaha Free Use License 1.0.
- The release workflow uploads only a tag that matches a new package version, after the full tests, clean installs, the live PHREEQC replay and reviewer approval, via PyPI Trusted Publishing.
- The documentation covers 0.3.1 and 0.4.0.

### Removed

- Two unreferenced 0.2.0 images from `docs/` and the source distribution.

## [0.3.1] - 2026-10-17

Replaces the yanked 0.3.0, whose source distribution contained a third-party PDF, and adds the
planning commands and reports. [Full notes](https://github.com/rafatahmed/Flahax/blob/main/docs/releases/0.3.1.md).

### Added

- Command-line workflow, EC screening and injector sizing (interactive or JSON); the original stdin contract is unchanged.
- Pre-acid EC screening for the exact SQM brands (unknown accuracy) and channel volume and flow sizing for pump, venturi and Dosatron injectors.
- Recipe-calibrated EC25 for stock tanks and the irrigation solution, meter TDS conversion, and recipe-preserving injection and pump planning.
- Source-water-to-formulation orchestration, calculated pH, and single-acid planning for nitric, phosphoric, sulfuric and citric acids, with four PHREEQC acid references.
- An offline HTML capability report with accessible charts, runnable `examples/`, a complete public API inventory and seven manual examples.

### Changed

- FlahaX is described as a plant-nutrient chemistry engine (planned for FlahaFAST, not yet integrated).
- The standard workflow offers nitric and phosphoric acids; zero-target incidental nutrients are separated from the positive-target fit.

### Removed

- The supplied YaraVita guide and other manufacturer PDFs from Git tracking and the source distribution; their SHA-256 hashes are recorded.

## [0.3.0] - 2026-09-27 [YANKED]

Yanked on PyPI on 2026-10-17, after 0.3.1 was published: its source distribution contained a
third-party PDF. Use 0.3.1. Core `recommend` and CLI input contracts are unchanged, with no
third-party runtime dependencies; the chemistry boundary is 25 Â°C, Davies I â‰¤ 0.1 mol/kg water,
fixed product oxidation states and closed analytical inorganic carbon. Hosted checks were blocked
by account billing; the owner approved publication on verified local evidence.
[Release record](https://github.com/rafatahmed/Flahax/blob/main/docs/releases/0.3.0.md).

### Added

- One bounded mixed aqueous model for all 28 catalogue product conversions, with preserved PHREEQC product, phase and nitric-acid reference evidence.
- Assay-qualified equilibrium-to-delivery planning: explicit water mass, reagent density, nitrate contribution, nutrient rescoring and source hashes.
- Dedicated acid-channel checks and rejection of target supersaturation or formed solids during delivery validation.
- Isolated wheel and sdist verification, hash-pinned external PHREEQC provisioning and a required live-reference CI job.
- A self-contained user manual shipped in the wheel and source distribution, with tested Python examples.

### Changed

- Public nitric-target functions return `AcidResult`; use `EquilibriumPhPlan` for reagent-volume planning. Earlier reduced-model fixtures keep explicitly named legacy solvers.
- Delivery record schema `0.1` and chemistry model identifiers are versioned independently of the package.

### Fixed

- Identical initial and target pH return exactly zero nitric acid.
- CLI examples supply the required salts array; historical chemistry notes are archived separately.
- Test calibration dates are deterministic; runtime calibration expiry remains enforced.

## [0.2.0] - 2026-09-25

The package baseline for fertilizer formulation, published with a PyPI trusted publisher. Earlier
development history remains in Git; this changelog does not claim it for the 0.2.0 artifact.

### Changed

- Releases are published to PyPI with a trusted publisher.

## [0.1.0] - 2026-09-25

### Added

- The first FlahaX package on PyPI, with its release workflow.

[unreleased]: https://github.com/rafatahmed/Flahax/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/rafatahmed/Flahax/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/rafatahmed/Flahax/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/rafatahmed/Flahax/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/rafatahmed/Flahax/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/rafatahmed/Flahax/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/rafatahmed/Flahax/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/rafatahmed/Flahax/releases/tag/v0.1.0
