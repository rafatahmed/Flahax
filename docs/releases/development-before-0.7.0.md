# Development history before the 0.7.0 candidate

This is a preserved pre-curation record from main d520bd7. Entries describe
successive development states and may be superseded. They are not the current
behavior or a release-readiness checklist. Use the [0.7.0 notes](0.7.0.md) and
[migration guide](../site/start/migration.md) for the final candidate contract.
Original failures and numerical qualifications remain in their evidence records.

## Former Unreleased changelog entries

- Correct the current release index while retaining historical publication evidence; add
  migration guidance and executable documentation checks for current calculation contracts.

- Preserve hard-zero targets and undefined relative differences in reports, sheets and terminal
  views; suppress blocked-sheet preparation actions and retain offline full-precision scientific
  qualifications, provenance and EC applicability evidence.

### Added

- Support rounded volumetric product stocks with real-water, assay and physical uncertainty;
  retain nutrient reserves and pH-range saturation checks without claiming lab verification (#257).

- Select and save available catalogue acids and bases in mix, add custom reagents, and
  restrict batch calculations with `--reagents`. Review old sessions with
  `--review-reagents` without overwriting their original answers (#231).

- Evaluate confirmed catalogue alternatives separately and report the direction, search result,
  charge check and nutrient misses for a grower batch (#231). Show solid pH reagent doses in
  grams in batch and mix (#229).

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

- Define the Python style policy and its compatibility/notation exceptions; wrap flowing
  comments and docstrings, separate import groups without reordering evaluation, normalize
  test/helper names and refresh generated API/CLI references without changing calculations (#273).

- Fit N_NO3, N_NH4 and N_UREA each as its own target; total N is their reported sum. Absent
  N_UREA is a declared zero; N_NH4 0 is no requirement, not a ban, and incidental NH4-N is held
  within min(10 % of total N, 1.5 mmol/L), basis Dutch soilless practice (De Kreij, Voogt et
  al.), shown in `ammoniumLimit`, the summary, report and sheets; `solve_weights` too (#209,
  #201).

- A target is met only within the numerical tolerance (1e-5 relative, 1e-6 mg/L for a declared
  zero, 1e-4 pH), which replaces the ±1 % band. Every deviation is reported ("targets missed:
  …", review); only a broken declared maximum blocks. pH reagent stages judge only their
  reagent's change; `maximum_nutrient_error_percent` is optional, no default (#210).

- The packaged catalogue is Flaha Agri Tech Analysis Ver 0.0: 24 fertilizers, 5 pH products and 13 crop formulas.

- A product label is reconciled with its compound, not refused: the charge its ions cannot
  balance is reported ("label analysis differs from KNO₃: 1.91 % K not assigned to an ion") and
  left out of the chemistry, while the nutrient fit keeps the label (G5, #214).

- The pH needs no completeness declaration. A water without `HCO3` or alkalinity shows "measure
  alkalinity (HCO3) of the water"; ionic strength above 0.1 mol/kg shows "not calculated"; the
  recipe is produced in both cases. Closed carbon, 25 °C and 1 L = 1 kg water are stated in the
  summary. `calculate_equilibrium_ph` drops `complete_analysis` and takes `residual_charge`
  (G1–G4, #215).

- A water analysis is taken as measured: its charge imbalance is reported and carried, and no
  ion is added, removed or adjusted. Removed: the 5 % rejection, closing on Cl, Na or carbonate
  (carbon from a titrated alkalinity stays), `balance_ion` water-file keys, the 0.1 % charge
  gates of the acid and delivery planners, and the formula-imbalance flag (G10, G11, #216).

- Precipitation is reported by evidence, never a refusal. Brushite (`CaHPO4:2H2O`), gypsum and
  calcite above saturation, or an allocated solid, label the recipe "precipitation risk";
  every other supersaturated phase is information with the basis of its constant. Removed:
  saturation blocking, the evidence and applicability inputs, `blocks` (G12–G14, #221).

- EC is a range, never refused. Its low end counts the species with a coefficient; its high end adds 80 per charge for those without, for phosphate beyond its fit domain and for unrecorded charge. `status` is `estimated` or `range`, with no midpoint. Removed: `partial`, the assay-residual and phosphate-fit refusals. `--ec` compares a requested EC (G6–G9, #224).

- Stock solubility compares each product with its own measured value, in the value's basis, with the source and tank temperatures shown and nothing interpolated (decisions G15-G19, #226). Order: the catalogue's waterSolubility, the historical table, none. Statuses are `ok`, `exceeds` (blocks) and `not_checked`; `screening_only`, `inconclusive` and `assumed_density_floor` are removed.
- Tanks follow the A/B layout (decisions G20-G22, #227): calcium and every micronutrient product in tank A, phosphates, magnesium sulfate and macro sulfates in tank B. The magnesium-phosphate rule is removed and the calcium-sulfate reason is reworded. A batch needing a third tank names the pair and the rule.

### Fixed

- Give all 13 catalogue formula checks independent test identities so the runner can
  schedule and report them separately. Preserve the real batch assertions and add
  an inventory/scheduling regression without raising timeout or chemistry limits (#274).

- Make equilibrium evidence independent of analytical-component insertion order so
  unchanged Sonneveld sessions replay across processes without a false candidate-identity
  mismatch. Preserve input/source and selected-candidate guards (#272).
- Align the current documentation and packaged manual with source-water handling,
  recipe-fit and ammonium rules, supported workflows and the hosted CI matrix (#271).

- Withhold manufacturer-screening EC totals containing positive Ultrasol Magsul doses;
  retain the disputed 1.2 mS/cm brochure value as evidence (#244).
- Record all chemistry input byte identities, the versioned PHREEQC extraction route and
  a deterministic source-manifest digest; preserve all scientific records (#245).
- Replace broad priority claims with supported capabilities and a dated comparison (#246).
- Validate custom batch records and reagent densities before configuration; reject duplicate
  product names before they can corrupt pH chemistry or reagent selection (#240, #241).

- Accept valid custom product names beginning with `test_`; reject actual placeholder formulas
  and invalid assays rather than inferring chemistry from a display-name prefix (#242).

- Reconcile sequential pH nutrient reports and limit checks with the actual returned reagent
  dose (#237). Respect fixed-zero sources in joint proposals and enable zero-cap refinement
  without changing tolerances or iteration limits (#238).

- Fill nutrient stocks independently of the reagent container capacity at the shared injection
  ratio; report reagent doses per fill, refill counts and final partial fills without changing
  solver methods or nutrient tolerances (#231).

- Refresh remedy messages from the final recipe, explain separate search and nutrient statuses,
  and label numerical dose residues without weighing checkboxes. Preserve exact quantities and
  clarify reagent-container capacity in fill mode (#231).

- Preserve accented Windows input such as à without consuming the next character in
  `flahax mix`; retain arrow navigation, editing keys and held-key repeats (#127).

- Capture the PHREEQC product fixtures from the packaged catalogue (Micro Combi Mix 2 replaces the retired CH - micro; the citrate case is dropped as no catalogue product holds citrate), so the golden test runs the engine's label reconciliation without a patch (#222).

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


## Former detailed development notes

# FlahaX unreleased changes: detailed notes

## Volumetric product stocks (#257)

Fixed-ratio recipes accept grams of supplied product per litre of stock, rounded mL doses,
and explicit stock concentration, dispenser and density bounds alongside real-water and
product elemental/ingredient uncertainty. Stock carrier replaces pure make-up water.
Rounded delivery retains nutrient accounting, the 5% example reserve and saturation checks
across pH 6.28–6.32. Impossible carrier and batch mass are rejected. Legacy pure-compound
stocks remain supported. Stock specifications are illustrative; laboratory testing and
measured verification remain deferred. See `docs/steiner-ratio-recipe.md` for the contract.

## Custom batch record validation (#240, #241)

Batch checks custom fertilizer and pH-reagent records before constructing a calculation.
Records need nonempty string IDs and names; each offered list must use distinct names.
The reagent-name check includes certificates added with `--acid`. Rename ambiguous entries
before retrying: two different products must not share a display name, because name-based
chemistry and reporting cannot distinguish them. Previously, that collision could change
the calculated starting pH and reverse the required correction direction.

Malformed records and nonnumeric, nonfinite or nonpositive liquid reagent densities now
produce plain input errors rather than uncaught exceptions. Valid custom assays and product
availability remain unchanged, as do numerical tolerances and solver controls.

Valid custom names beginning with `test_` no longer cause products to be discarded as
placeholders (#242). The declared formula and assay determine eligibility; the literal
unfinished formula `Input Formula Here` and invalid or missing assays remain rejected.

## Sequential accounting and explicit zero maxima (#237, #238)

Sequential pH candidates now reassess nutrient totals, total nitrogen, loss and declared
maximum checks using the actual returned reagent dose and unchanged fertilizer amounts.
The settling tolerance no longer leaves assessments tied to the preceding assumed dose.
Ordinary fits retain their search provenance; only actual blended recipes are labelled as blends.

Joint proposals keep sources at zero when an existing hard constraint proves that no dose is
allowed. The existing active-face refinement also applies to binding zero maxima. This avoids
discarding an entire proposed step because it includes a forbidden product, and permits local
stationarity refinement at a zero cap. Solver tolerances, iteration limits and final verification
are unchanged. A zero ammonium target still means no requirement; an explicit zero ammonium
maximum prohibits ammonium. Convergence does not imply that nutrient targets are met, and
does not prove a global optimum.

## Final recipe report consistency (#231)

Remedy stage messages now match the final recipe shown in the batch summary. Reports explain
local stationarity, nutrient matching and nutrient feasibility diagnostics separately, without
changing their underlying calculation statuses or implying a global optimum or impossibility.
Positive doses below the existing display-zero precision are labelled as numerical residue and
have no weighing checkbox; their exact values remain in the exported calculation data.
Sheets name reagent containers without assuming they contain acid.
No solver controls, nutrient tolerances, recipe quantities or acceptance decisions change.

## Nutrient stock fill and reagent refills (#231)

Fill mode now uses the smaller A/B nutrient tank to determine irrigation volume. A separate
reagent tank can be refilled at the same injection ratio instead of shrinking the nutrient batch.
With 100 L A/B tanks and a 10 L reagent tank at 1:100, the batch supplies 10,000 L irrigation:
100 L in each nutrient tank, and ten 10 L reagent fills. Reports distinguish the total reagent
amount from the amount per fill, including a scaled final partial fill. Once mode permits the
same reagent refills while still rejecting nutrient stock volumes that exceed A/B capacity.
Previously saved calculations retain their original volumes; a new calculation uses this rule.
Concentration targets, solver methods and acceptance tolerances are unchanged; batch quantities
scale with the corrected irrigation volume.

## Available pH reagents (#231)

Mix selects catalogue acids and bases together using the fertilizer-list interaction:
the whole catalogue, a saved list, or individual available products. Existing saved acid
certificates remain selectable. Custom supported liquid or solid reagents declare their
assay and physical form, liquid density and known water content; unknown composition is
not inferred. Only the selected list is passed into the unchanged direction and numerical
checks. Batch accepts the same product-record array through `--reagents`; an empty array
stays empty, while explicitly supplied `--acid` certificates are additional available products.

Old sessions lacking availability require `--review-reagents` and a new session name.
The original session is preserved. This reagent-only review cannot bypass existing
input/model-drift checks. Catalogue is reserved for the built-in selection, so saving an
empty or restricted list under that name cannot silently restore all products.

## Earlier changes

The full text of unreleased changes, as recorded when each was merged, newest first. The [changelog](../../CHANGELOG.md) groups them into a short summary. These notes do not designate a future release version. Package metadata remains `0.6.1.dev0`.

These entries are a chronological record. Older entries can describe behavior
superseded by later changes; historical decision labels are references to those
decisions, not evidence that the current solver is qualified. In particular, label
charge rejection described in the catalogue entry below was subsequently removed:
the current workflow reconciles a declared compound with its label and reports
unassigned amounts, as described in the label-reconciliation entry.

- Windows `flahax mix` reads Unicode console key events instead of ambiguous character prefixes (#127). Typing à no longer consumes the next character or turns H/P/K/M into arrow actions. Navigation, editing, held-key repeats and Alt+numpad characters remain supported. Native hidden-console tests exercise both the terminal reader and the mix text-entry and selection widgets; POSIX input is unchanged.

- A product label is reconciled with its compound instead of refused (decision G5, #214). `flahax.label_reconciliation` takes the charge the declared ions of the compound cannot balance from the excess side's declared nutrients in proportion to their charge contribution and reports it as `unassigned_percent`; chemistry uses the label minus that amount and the nutrient fit keeps the label. A label that leaves a charged ion unstated (a chelate's sodium, a carbonate) or states one side only (an acid, urea, KOH) is closed by that ion, so nothing is unassigned. A blend has no defined compound and keeps its label, with the note "has no defined compound: its label analysis is used as declared". Potassium nitrate at N 13.0 and K 38.2 leaves about 1.91 % K unassigned. The 1 % label charge gate (`materials._CHARGE_RESIDUAL_LIMIT_PERCENT`), the grade-range exclusion test and the `identity_inconsistent` refusals in `mix_cli` and `fertilizer_workflow` are removed; a label naming a nutrient the compound's ions do not carry is still refused.
- The pH needs no declaration (decisions G1–G4, #215). `calculate_equilibrium_ph(totals, *, phases, temperature_c=25.0, carbon_boundary='closed', residual_charge=0.0)` no longer takes `complete_analysis` and solves to the net charge `residual_charge` (eq/kg water) instead of zero. In the workflow, a water with neither an `HCO3` key nor a measured alkalinity gives the chemistry and pH stages `needs_input` with the message "measure alkalinity (HCO3) of the water"; an ionic strength above 0.1 mol/kg gives `not_calculated` with "ionic strength above 0.1 mol/kg: outside the activity model's range"; `HCO3: 0` is a measured zero and is calculated. The recipe is produced in all three cases. The summary lists the stated model conditions: closed carbon, 25 °C only, and 1 L of solution taken as 1 kg of water.
- A water analysis is taken as measured (decisions G10 and G11, #216). `balance_water_analysis` no longer rejects an imbalance (the 5 % limit and `charge_imbalance_exceeded`), no longer closes on Cl-, Na+ or an adjusted carbonate (`balance_ion`, `maximum_imbalance_percent`, `balance_ion_uncertainty_percent` and `fixed` are removed, as are `missing_balance_ion`, `fixed_balance_ion`, `reconciliation_out_of_bounds` and `closed_on_alkalinity`), and returns `imbalance_percent` and `residual_charge_eq`, which the pH solves, the pH-adjustment planner and the joint problem's reference charge carry. Carbon taken from a titrated alkalinity stays, because it comes from a measurement. `calculate_ec_from_totals` takes `residual_charge_eq_per_kgw` for its calculated-pH mode, and a reagent search that leaves the activity model's range gives the pH-adjustment stage `not_calculated`. A water file with `balance_ion` or `balance_ion_uncertainty_percent` is refused with `unknown_field`. The 0.1 % initial-charge gates of the acid-option and delivery planners (`charge_imbalance`) are removed because their doses are found from charge differences. The formula-imbalance flag `exceedsWarning` and `ION_BALANCE_WARNING_PCT` are removed; `recommend` states the imbalance as "The formula's declared ions are not balanced: cations {c} vs anions {a} meq/L ({p} %)." and never claims no salt combination meets the targets.
- Precipitation is reported by evidence and never refuses a candidate or a plan (decisions G12–G14, #221). `assess_saturation(state)` returns `risk` (the readily forming phases `CaHPO4:2H2O`, `Gypsum` and `Calcite` above saturation, and any allocated solid), `information` (every other supersaturated phase with the basis of its constant: MnHPO4 is an unmeasured constant, Plummer et al. 1976 program data; the rest are database constants, minteq.v4, not individually reviewed), `advisories` (Iron(II) is held at a fixed oxidation state; in an aerated tank it oxidizes.) and `solids`. Gypsum is detected only as the by-product of bad mixing and is never an input, a product, a reference value or a remedy. Removed: the `blocks`, `blocking`, `review`, `thermodynamic` and `applicability` keys, the `conditions`, `evidence` and `si_uncertainty` parameters, the `precipitation_risk` rejection in the acid, pH-reagent and delivery planners, and `mixing_approved`. The summary carries `chemistry.risk` and `chemistry.information`; `statuses.phase` is `requires_review` with a risk and `assessed` without. A risk reads "The recipe carries a precipitation risk: CaHPO4:2H2O SI 0.16."
- EC is a range, never refused and never blocking (decisions G6–G9, #224). `calculate_ec_from_totals` returns `ec25_range_ms_cm = (low, high)`: `low` is the sum over the species with a conductivity coefficient; `high` is `low` plus `|z| × 80 × m` (`LAMBDA_MAX_PER_CHARGE = 80.0`) for each species without one, for H2PO4- and HPO4-2 beyond the phosphate fit ionic strength, and for the charge a supplied pH leaves unbalanced. `ec25_ms_cm` is `low` only when `low == high`, otherwise `None`; there is no midpoint in any output. `status` is `estimated` or `range`; only a state the activity model cannot solve is `not_supported`. The assay charge residual is reported in the result and never changes the status. Removed: the `partial` status, the `assay_charge_residual_too_large`, `ionic_strength_outside_phosphate_fit`, `missing_species_contributions` and `unrecorded_counterions` reasons of `calculate_ec_from_totals`, and the 0.1 % assay gate. The qualifier of every result is now "Model: McCleskey et al. (2012); its reported accuracy (-0.7 ± 5 %) is for natural waters, not fertilizer solutions. Measure EC after mixing." `flahax batch --ec` and `summarize_batch(requested_ec_ms_cm=...)` compare a requested EC25 with the range: "compatible with the estimated range; target attainment unverified", or "requested {r:.2f} mS/cm is {d:.2f} mS/cm from the estimated range". The report card, the batch sheet and the mix sheet show the range as low to high.
- Stock solubility uses measured data (decisions G15-G19, #226). `check_stock_solubility(tanks, ratio, temperature_c, *, table=None, product_grades=None, products=None)` compares each stock g/L with the product's `physicalProperties.waterSolubility` (catalogue records passed as `products`), then with the historical table, then reports `not_checked` with reason "no solubility data". The comparison is in the source's own basis, with no conversion and no solution density assumed; a value in an unknown unit is `not_checked`. Each row states `basis`, `source_temperature_c` and `tank_temperature_c` and there is no interpolation (a table uses its nearest point, the lower on a tie). Statuses: `ok`, `exceeds` (blocks), `not_checked`. Removed: `screening_only`, `inconclusive`, `assumed_density_floor`, the `screening_g_per_l` field, the review, grade and interpolation-review qualification of limits. Every row and the sheet say "single-product check; the mixed tank is not assessed".
- Tanks use the A/B layout (decisions G20-G22, #227). `CLASS_RULES` keeps calcium-phosphate and calcium-sulfate for macro products only; the magnesium-phosphate rule is deleted, and the calcium-sulfate reason reads "calcium and sulfate precipitate in a concentrate". A micronutrient product (every nutrient in `MICRONUTRIENTS`) goes to tank A and is screened against phosphate only. A batch that needs more tanks than are available is blocked with "needs a third tank: P cannot share with Q (rule)".
- A target is met only within the numerical tolerance (decision G25, validated 2026-10-24): 1e-5 relative for a positive target, 1e-6 mg/L for a declared zero, 1e-4 pH units, in the new module `flahax.requirement_fit` (`met`, `RELATIVE_TOLERANCE`, `ZERO_TARGET_TOLERANCE_MG_PER_L`, `PH_TOLERANCE`) (#210). It replaces the ±1 % band (`engine.TOLERANCE_PCT`, removed) in `feasible`, in the short-target recovery, in the target-only diagnosis and in `unmetTargets`. `feasible` is every declared requirement met and no declared maximum exceeded. Every deviation is reported: in `plan_fertilizer_workflow` the formulation stage blocks (`infeasible_recipe`) only on a broken declared maximum; a missed target makes it `requires_review` with "targets missed: …" (each difference to three significant figures in fixed notation, for example +1400 %, before any incidental-nutrient review), and the batch, titration, nitric, acid and stock stages continue (`FinalSolutionRecipe.feasible` is true unless a declared maximum is broken). A deviation the formulation stage accepts never blocks a later stage, and `plan_equilibrium_delivery` plans an accepted empty recipe on the water alone (it formerly required a nonempty recipe): the titration, nitric (`plan_equilibrium_delivery`) and acid-selection (`plan_acid_options`) stages judge only the change their reagent makes. `maximum_nutrient_error_percent` is now optional with no default, and every stage rejects a declared value that is not finite and positive (`invalid_value`; the nitric adapter formerly accepted 0) (the titration stage formerly defaulted to 1 %, and each stage compared the whole deviation from the target); when given, it is a declared requirement on the reagent's own change to each positive target, measured from the recipe before the reagent, and a stage fails with `nutrient_tolerance_exceeded` only when that change exceeds it, or with `nutrient_limit_exceeded` when the reagent pushes a nutrient past a declared maximum. A declared zero is met within 1e-6 mg/L everywhere: in `limitViolations`, `requirementConflicts`, `unmetTargets` and on the sheets (5e-7 mg/L of urea from the water meets an absent or zero N_UREA; 2e-6 mg/L breaks it and blocks). The pH plan and the joint workflow use `PH_TOLERANCE` (1e-4) in place of the former 1e-3 in `ph_adjustment`; no tested pH result changed. A feed whose mixed pH is within 1e-4 of the target now reads "no pH reagent is needed" when no plan is selected, instead of asking for a base (#212). Because a target 0.0056 % short is now short, recovery admits a held-back product that is its only source: for Lettuce 2 (Howard Resh) on the packaged catalogue sodium molybdate replaces Micro Combi Mix 1 for Mo, which is then met exactly, sodium falls from 0.814 to 0.442 mg/L, and P finishes at 49.8384 mg/L for 50 (-0.323 %), a deviation the former band counted as met. The batch and mix sheets mark in red each target not met within the tolerance (formerly beyond 1 %), and the recovery warning reads "… stayed short of its target without it" (formerly "more than 1% short").
- N_NO3, N_NH4 and N_UREA are each their own fitted target (decision D1); total N is reported in `totalN` (target, final, difference, `fitted: false`) as the sum of the three forms and never fitted (#209, #201). An absent N_UREA is a declared zero, and urea-bearing products are not used unless the formula declares urea. N_NH4 absent or 0 is no ammonium requirement: no row and no ban (G24), so calcium nitrate stays usable. The ammonium the products bring is then held within min(10 % of total target N, 1.5 mmol/L NH4 = 21.01 mg/L N) (G23), with the basis "Dutch soilless practice (De Kreij, Voogt et al.)", reported in `ammoniumLimit` and shown on the batch summary, the report and the batch and mix sheets; a declared N_NH4 maximum replaces it and `max_ammonium_fraction=None` removes it. `solve_weights`, the coupled pH plan and the joint problem use the same nitrogen rows and allowance, and total N is recomputed after a pH reagent. For Cucumber (Howard Resh), N_NO3 140 and N_NH4 0, the allowance is 14 mg/L.
- The packaged catalogue is Flaha Agri Tech Analysis Ver 0.0 (Flaha Agri Tech, 2026-10-29; supplied by Flaha Agri Tech, not independent laboratory verification) (#206). `library.json` holds 29 products, 24 fertilizers and 5 pH products, 13 crop formulas and the 3 waters it held before. Every product carries the analysis review record (`analysisReview`), and the library records the analysis as a whole in `fertilizerAnalysis`. The pH products, all `role: ph_reagent` and never selected as nutrient salts, are Potassium Hydroxide (45% solution), Phosphoric Acid (75%), Nitric Acid (65% solution), Potassium Bicarbonate and Potassium Carbonate; `catalogue_ph_reagents()` returns all five, so `flahax batch` and `flahax mix` now evaluate the two packaged acids beside any acid given with `--acid`. New products: Nitric Acid (65% solution), Micro Combi Mix 1 and Micro Combi Mix 2. Removed products: Ammonium Dibasic Phosphate, Calcium Chloride (Dihydrate), CH - micro (kept as a retired reference in `retiredProductReferences`), Potassium Chloride, Potassium Citrate and Potassium Dibasic Phosphate; the packaged catalogue has no chloride product. Removed formulas: Chilli (maximumyield), Generic Bloom (maximumyield), Generic Dry Season (Howard Resh), Generic Grow (maximumyield), Generic Wet Season (Howard Resh), Generic for Berries (Growing Edge), Rice (Douglas Peckenpaugh) and Tropical Lettuce (Douglas Peckenpaugh). At the time of that catalogue change, Potassium Nitrate was reported as 2.57 % out of charge balance against KNO3 and the then-active 1 % label gate stopped its chemistry with `identity_inconsistent`. That gate was subsequently removed; the current label-reconciliation behavior is described above. NOTICE and the attribution test credit Flaha Agri Tech for the analysis.
- Micro Combi Mix 1 and 2 have a declared composition (2026-10-30). Fe is Fe(III)-EDTA, Mn, Zn and Cu are EDTA chelates, Mo is sodium molybdate and, in Mix 2, B is boric acid. The sodium counter-ions follow the catalogue's own chelate identities (NaFeEDTA; Na2 Mn, Zn and Cu EDTA; Na2MoO4), and the ion forms are mol/kg from the catalogue's element percentages. The new identity status `declared_blend` resolves as a disclosed blend without the `assumed_composition` flag (`assumptionStatus`: `declared_composition_not_independently_verified`), and its chemistry source reads "declared composition of" the product. Mix 2's chemistry profile names boric acid among its components (family `edta_boric_acid_molybdate_blend`), as CH-micro's profile names borax.
- Nitric acid is a strong acid in the engine's ion tables: `HNO3` dissociates fully into H+ and nitrate, the proton implicit, as for phosphoric acid. Nitric Acid (65% solution) converts to nitrate from its assay, with no counter-ions; parsing of the existing nitrate salts is unchanged.
- A `flahax batch` or `flahax mix` run whose formulation stage cannot meet a target, with no other stage blocking it, now ends "requires review" (exit 0) and reports the shortfall, for example K at -100 % when a K maximum of 0 forbids every potassium product (decision 2026-10-30). Before the packaged catalogue (Flaha Agri Tech Analysis Ver 0.0) such runs ended blocked (exit 3), because no packaged reagent could lower the pH; the packaged acids now give the pH stage a reagent.
- The engine-mechanics tests run on a frozen copy of the 33c5df2 catalogue (`tests/fixtures/catalogue-33c5df2.json`, the library at commit 33c5df2), entered through `tests.catalogue_history.historical_catalogue()`, so they keep testing the mechanics they were written for. Tests of the packaged catalogue itself run on Flaha Agri Tech Analysis Ver 0.0.
