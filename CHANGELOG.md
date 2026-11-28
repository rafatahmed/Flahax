# Changelog

Notable changes for growers, agronomists and developers. Versions follow
[PEP 440](https://peps.python.org/pep-0440/); before 1.0 a minor release can
change interfaces and behavior. Each release describes the final difference
from its predecessor. Detailed notes retain sources, limitations and migration.

## [Unreleased]

Development checkout: 0.7.2.dev0. No user-facing changes recorded since 0.7.1.

## [0.7.1] - 2026-11-28

A hardening and speed update for growers, agronomists and developers: ammonium and total
nitrogen handled explicitly, acceptable ranges and pH intervals, equipment-fit checks,
qualified solubility, clearer failures, stricter inputs, and faster import and solves.
Python 3.11 or newer; no runtime dependencies. Default recipes can differ from 0.7.0 because
the ammonium allowance is now opt-in: recalculate saved recipes.
[Full notes](https://github.com/rafatahmed/Flahax/blob/main/docs/releases/0.7.1.md).

### Added

- `python -m tools.performance_budgets check` compares import, first-call and solver work with the budgets in `benchmarks/budgets.json`: module, solve and Newton-iteration counts fail when they exceed their ceiling (also in the test suite), and timings relative to a calibration loop are reported (#347).
- Every result and report states that no real-mixture predictive accuracy is claimed, and `docs/physical-validation-protocol.md` drafts the staged physical validation that issue #41 asks to have reviewed; it authorizes no laboratory work (#314).
- The summary and report list the dissolved species and any predicted precipitate apart from the nutrient totals, and state that meeting a target does not establish that nutrients stay dissolved or available (`chemistry.species_mol_per_kg`, `chemistry.precipitated_mol_per_kg`) (#312).
- Total nitrogen (`N`, mg/L as N) is a target in `recommend`, the workflow and `flahax batch`, alone or with nitrogen forms. Alone it imposes no form split; with a nitrate and a positive ammonium target it must agree with their sum (an absent urea counts as zero); with other forms both are scored and `totalN.overlapForms` lists the overlap (#291, #311).
- `flahax batch` takes `--available-tanks` and `--tank-capacity`; the report lists the tanks the recipe needs against yours, and a tank too small for its stock blocks without changing the recipe (#293).
- Acceptable deviation ranges, none by default: `deviation_ranges` on `recommend` and the workflow, and `--range-percent`, `--range` and `--require-ranges` on `flahax batch`. Assess classifies the result; Require constrains the fit and keeps an unmet candidate. A zero target or declared maximum is never relaxed (#305).
- `target_ph` accepts an acceptable interval `(low, high)` (`--ph-min` and `--ph-max` on `flahax batch`): a mix inside needs no reagent, otherwise the plan aims at the nearest bound, never a midpoint; single-purpose pH stages refuse an interval (#304).
- `--fit-equipment` and `available_product_search(on_equipment_miss=True)` search other products for a recipe that fits the declared tanks; tanks and separation rules never change, and the mode and equipment are saved in `remedies` (#294).
- A saved result keeps `supplied_inputs`, bound to its input fingerprint, and `saved_input_differences` names what a recalculation changed (#297).

### Changed

- The release workflow installs `build`, `twine` and setuptools from `tools/release/requirements-release.txt` with `--require-hashes` and builds without isolation, so artifacts are made by reviewed tool versions; other jobs pin `build==1.6.1` and Dependabot proposes monthly updates (#348).
- `compose_delivery_plan`, `delivery_report` and `transition_plan` refuse a stage value whose own fields contradict each other (`cross_stage_constraint`): a changed pH plan (blank ids, target outside pH 0-14, reagent volume with zero mass or demand), a pump command with no calibration id or runtime, a stock plan whose approval disagrees with its status (#348).
- A solver that gives up names where: the message keeps its wording and adds the stage, iteration count and residual (Newton, line search, phase active set, ionic strength, root search, pH bracketing, dose bracketing), and `DeliveryError.details` carries the same facts; `solve` also lists the earlier warm-start and cold-start failures. Successful results are unchanged (#348).
- `import flahax` loads no submodule: public names resolve on first use, so import time no longer grows with the package (#335).
- The first `recommend` call takes about 67 ms instead of 90 ms: packaged data is read directly through `importlib.resources` and `pathlib` is imported only when needed (#342).
- The aqueous solve is faster and returns bit-identical results (#337), and each pH point of the uncertainty grid starts from its nearest solved pH (#339).
- Sixteen helpers that other modules import lose their leading underscore and gain a docstring where they had none, for example `canonical_result.digest`, `engine.recipe_report` and `stock_evidence.required_text`. Code that imported the old private names uses the new ones; nothing is exported from `flahax` and no result differs.
- The nitrogen rules live in `flahax.nitrogen`: the three forms, `nitrogen_rows`, `fitted_targets`, `total_nitrogen`, the ammonium allowance and `total_n_report`, moved from `composition` and `engine`. `evaluate_remedies` takes the planner as an argument, so `fertilizer_workflow` and `evaluated_remedies` no longer import each other. No recipe, total-N report or ammonium cap differs.
- `run_batch` and `BatchOptions` move from `flahax.batch_cli` to `flahax.batch_request`, the water reader to `flahax.water_input`, and `read_json` to `flahax.inputs`; `flahax batch`, `flahax mix` and `flahax.batch_cli.main` behave as before and no output differs. Code that imported those names from `batch_cli` imports them from the new modules.
- `flahax.grower_report` is split into `batch_summary`, `report_html`, `result_wording` and `report_format`. `summarize_batch`, `render_report` and `render_batch_sheet` import from `flahax` as before and no report, sheet or summary differs. Other names move to the new modules; the reason and row helpers lose their underscore.
- One number check, `flahax.inputs.number`, replaces nine private copies in the engine modules and three guards in `flahax batch`. Error codes are unchanged. A numeric string is no longer coerced to a number in delivery contracts, and the stock, pH and stability evidence checks raise `DeliveryError` (still a `ValueError`) for a malformed number.
- Targets are validated by one function, `validate_targets`; `validate_profile` is only for water, maxima and assays and no longer takes the `total_n` flag that let an entry point keep the old rule (#316).
- `tools/check_numeric_review.py` reports `fully_classified` and `scientifically_qualified` as separate outcomes and no longer prints one `valid` flag, so a complete audit cannot be read as scientific qualification (#309).
- The batch report and `plan_stocks` qualify a solubility value through one function (`qualify_single_product`): `verified` only where the recorded temperature range and the concentration basis support it, otherwise the gap is named. `StockPlan.qualification` is new and a solubility-limit record may state an optional `basis` (#307).
- The glossary no longer implies a fixed A/B: the stock assignment may use more than two tanks and the result lists every one (`tanks.tanks`) (#308).
- An absent or zero `N_NH4` target is no requirement and no maximum. The ammonium allowance is now an opt-in preset (`max_ammonium_fraction`), so default recipes may use ammonium nitrate and report NH4-N for review (#290).
- Products sharing an exact name are rejected as `ambiguous_product_name` before dose resolution (#288).
- `plan_stocks` no longer raises `missing_solubility_limit`: with no limit at the temperature it keeps the quantities, lists the product in `StockPlan.unverified` and approves nothing (#295).

### Fixed

- A measured concentration (water, target or assay) above 2,000,000 mg/L, or a `True`/`False`, is an `InputError` instead of an `OverflowError` or non-finite masses; a maximum stays an upper bound, so 1e9 still means no limit. A water file whose `measured_ph` is NaN or infinite is refused (#348).
- The aqueous solver and `nitric_target` raise `DeliveryError` (`out_of_range`, `invalid_totals`, `activity_model_out_of_range`) for a pH, total or ionic strength that is not a number, instead of a `TypeError`; a pH of `True` is no longer read as 1 (#348).
- Sums of floats give the same digits on Python 3.11 and 3.12 or newer: 3.12 changed the built-in `sum`, so results differed in the last digits. The emitted total is compared with `float_sum` in tests (#334).
- Total nitrogen counts an absent urea as a zero requirement: a declared nitrate and a positive ammonium now determine the total, a total that disagrees with them is rejected before fitting (for example `N` 150 with `N_NO3` 100 and `N_NH4` 30), and a consistent total is scored once (#303).
- Coupled recipes are assessed at the emitted reagent dose, and search provenance survives dose reassessment (#288).
- Each solubility row states that it is a single-product value and whether its temperature is verified; a value recorded at another temperature is flagged, not silently accepted (#295).
- The glossary defines stock assignment, required and available tanks, equipment fit and single-product solubility (#296).
- Workflow stage statuses are one documented set (`calculated`, `requires_review`, `needs_input`, `blocked`, `not_calculated`) and a stage with any other status is refused; the developer guide no longer omits `not_calculated` (#300).
- The report and summary now state the numeric criterion for a met target (1e-05 relative, 1e-06 mg/L for a declared zero) instead of "configured tolerances"; the constants are unchanged (#299).
- The README troubleshooting row cites the error codes the CLI emits (#287).
- Catalogue lookups, the sensitivity matrix and cold-solve memory no longer make the full test suite take about an hour (#289).

## [0.7.0] - 2026-11-19

A recipe-design and verification update for growers and agronomists: Sonneveld
feed targets, broader fertilizer search, practical rounded product stocks and
reviewed root-zone feedback. Python 3.11 or newer; no runtime dependencies.
All 135 package-level export names from 0.6.0 remain and 16 are added, but input,
status, solver and saved-session contracts change. Recalculate and review old
workflows. Physical validation remains separate in #41.
[Full notes](https://github.com/rafatahmed/Flahax/blob/main/docs/releases/0.7.0.md).

### Added

- Sonneveld A-D feed-target design from a crop/system baseline, explicit nutrient
  corrections and irrigation EC, integrated with batch and mix. Root-zone samples
  and guide comparisons support grower-approved feed changes, not automatic crop
  control (#264, #266).
- Bounded search over eligible alternative fertilizer combinations, retaining
  verified candidates if later attempts fail. Rank tolerance attainment before
  declared preferences and report the best result found within the budget (#261, #266).
- Rounded volumetric product stocks in batch and TUI preparation, including
  practical copper dosing, carrier-water accounting, dry/product/reagent
  uncertainty, nutrient reserves and pH-range saturation screening (#257, #263, #266, #270).
- Joint fertilizer/reagent problem and search APIs, actual-weighed-recipe
  rescoring, shared material inventories and immutable result archives. Acceptance
  binds exact input/source/result content; a local search result is not a global
  optimality proof (#161, #177, #179, #181, #232).
- Executable Appendix I cases, profile import, saved-session review and repeat,
  grower/agronomist walkthroughs, strict file-format reference and offline
  documentation assets. The 1,000 L examples remain illustrative (#259, #275).

### Changed

- Fit nitrate-N, ammonium-N and urea-N separately; report their sum as total N.
  Absent urea is zero. Absent/zero ammonium is no requirement, with a default
  allowance min(10% of target N, 1.5 mmol/L); an explicit cap replaces it and
  max_ammonium_fraction=None disables the allowance (#209, #213).
- Minimize positive-target relative error without hidden dose or incidental-ion
  penalties. Nonzero ridge is rejected. Preserve positive dose precision and
  hard maxima; report target misses separately from invalid/blocked results (#161, #196, #210).
- Use numerical tolerances of 1e-5 relative for positive targets, 1e-6 mg/L for
  declared zeros and 1e-4 pH. Preparation tolerances are explicit inputs;
  reagent-change tolerance has no default. These are not agronomic safety bands (#210).
- Retain measured-water inventories and residual charge without inventing or
  changing ions. Infer carbon from applicable alkalinity accounting and state
  solvent/carbon assumptions. Reconcile supported product labels and disclose
  unassigned assay amounts (#214, #215, #216).
- Report calculated EC as estimated or range, without a midpoint. The upper
  estimate uses the disclosed 80-per-charge convention for uncovered contributions;
  it is not a proven physical bound. Withhold the disputed Magsul screening total (#224, #244).
- Report feed saturation as risk or information, not precipitation kinetics.
  Solubility rows retain product basis and temperature; a single-product check
  does not qualify a mixed tank. Preserve applicable separation and delivery
  qualifications (#221, #226, #227).
- Use the current catalogue of 24 fertilizers, five pH products and 13 formulas,
  with declared composition/provenance and retained source/model limitations.
  Explicit custom records remain supported (#201, #206, #245).
- Make reagent availability explicit, including acids, bases, empty/custom lists
  and separate reagent refills. Show solid reagents in grams; recompute reports
  from final returned quantities (#229, #231).
- Organize documentation by audience and task; define the Python style policy
  and reviewed exceptions. Compatible prose/import-layout changes preserve
  calculations and scientific data (#271, #273, #275).

### Removed

- The five University of Florida tomato presets and extension-based feed-pH and
  residual-bicarbonate advice. Choose reviewed targets explicitly; user-saved
  targets are not silently rewritten
  ([094b4e0](https://github.com/rafatahmed/Flahax/commit/094b4e0)).
- Obsolete water balance-ion/completeness inputs, label-charge refusals, EC
  partial/refusal statuses and phase blocks fields. Migrate using the documented
  replacement inputs/statuses; do not transfer old acceptance (#214, #215, #216, #221, #224).

### Fixed

- Separate pre-upload release finalization from verified publication receipts,
  enforce matching valid manual/changelog dates, and make packaged README
  documentation links portable to PyPI (#278).

- Reconstruct sequential nutrient rows and limits from the actual returned
  reagent dose; preserve zero-cap sources during joint proposals/refinement
  without loosening numerical limits (#237, #238).
- Validate custom record IDs/names, duplicate names, assays and reagent densities;
  accept valid product names beginning with test_ (#240, #241, #242).
- Preserve native terminal input, Unicode editing and cleanup; integrate verified
  preparation into the TUI and retain source-bound session review (#127, #182, #183, #268, #269).
- Make unchanged Sonneveld sessions replay deterministically across processes.
  Independently schedule all 13 real catalogue formula checks without raising
  timeout or chemistry limits (#272, #274).
- Reconcile current readiness/support references with completed software
  acceptance and separate physical validation. Curate this changelog, restore
  proven encoding damage and check duplicate categories, orphan bullets and
  complete wrapped-entry length (#276, #277).

## [0.6.0] - 2026-10-24

The grower release: FlahaX becomes a tool a grower or agronomist can run without code
(`flahax mix`, `flahax batch`), plans the recipe and its pH reagent together, checks stock
solubility, and moves to Beta. No breaking API change (14 names added, none removed); Python 3.11
or newer, still with no runtime dependencies. Known limits: the full-screen `flahax mix` is alpha
(`--plain` always works; typing "à" on Windows swallows the next key, #127), solubility checks are
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

- The documentation site is organised for its readers (Diátaxis): Get started, a grower, an agronomist and a developer and researcher guide, Reference (command line, Python API, input files, error codes), Explanation, Evidence and Project, with diagrams; moved pages redirect from their old addresses.
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
- The maintainer's trial of the full-screen mode: Windows arrow keys (#135), readable key help (#137), confirm before leaving (#138), filter and tick keys (#139), number display (#140), wrapping (#141), grower words (#142), and #125-#132, #143-#147.
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
- Catalogue: Mg Nitrate is Mg(NO3)2·6H2O; Phosphoric Acid (75%) is a 75 % solution; Calcium Nitrate cites the Haifa sheet; ammonium sulfate and urea cite ChemicalBook sheets.
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
third-party runtime dependencies; the chemistry boundary is 25 °C, Davies I ≤ 0.1 mol/kg water,
fixed product oxidation states and closed analytical inorganic carbon. Hosted checks were blocked
by account billing; the maintainer approved publication on verified local evidence.
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

[unreleased]: https://github.com/rafatahmed/Flahax/compare/v0.7.1...HEAD
[0.7.1]: https://github.com/rafatahmed/Flahax/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/rafatahmed/Flahax/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/rafatahmed/Flahax/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/rafatahmed/Flahax/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/rafatahmed/Flahax/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/rafatahmed/Flahax/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/rafatahmed/Flahax/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/rafatahmed/Flahax/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/rafatahmed/Flahax/releases/tag/v0.1.0
