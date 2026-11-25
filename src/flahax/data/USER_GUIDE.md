# FlahaX 0.7.1.dev0 — User Manual

Fertilizer formulation • bounded chemistry • reviewed delivery planning

**Version:** 0.7.1.dev0, unpublished development checkout. Published 0.7.0 (2026-11-19) is archived at https://doi.org/10.5281/zenodo.24356739; its release evidence does not certify subsequent development changes.

## Contents

1. Purpose and boundaries
2. Installation and first recipe
3. Inputs, units and results
4. Command-line use
5. Catalogue equilibrium
6. Nitric-acid delivery planning
7. Stock, calibration and review workflow
8. Errors and troubleshooting
9. Verification and reproducibility
10. Upgrading, integration and citation
11. Site workflow, EC and injection examples
12. Sonneveld profile review and rounded preparation

For exact public signatures and result-record fields, see the bundled
[Public API reference](API_REFERENCE.md). Both documents are installed under
`flahax/data/`; neither requires network access to read.

## 1. Purpose and boundaries

Growers and agronomists use FlahaX to turn crop-feed targets, source water and available products into candidate batch recipes. Targets may be supplied directly or calculated with Sonneveld A–D design and grower-approved feed corrections. Fertilizer and pH-reagent contributions, rounded dry/stock doses and declared uncertainty enter the relevant workflow checks. Python APIs also evaluate mixed aqueous systems and prepare auditable delivery plans. The package is dependency-free at runtime and performs no pump I/O, deployment or database writes.

Source-water chemistry can start from a laboratory analysis at its **measured pH**. The analytical ions remain unchanged; the reported imbalance is carried as residual charge, and imbalance size alone does not reject the water (section 11). The interactive interview offers review and continuation when imbalance exceeds 5%. From 0.5.0, `recommend` explains every missed target, reports whether the formula itself is electrically balanced, holds incidental ions within explicitly supplied limits, and records each product's source document (section 11). FlahaX is open source under the Apache License 2.0.

The packaged catalogue is Flaha Agri Tech Analysis Ver 0.0 (supplied by Flaha Agri Tech, not independent laboratory verification): 13 crop formulas and 29 products, 24 fertilizers and 5 pH products. The mixed model has 197 aqueous entries and 28 phases. Its accepted boundary is **25 °C**, **ionic strength <= 0.1 mol/kg water**, fixed oxidation states and closed analytical inorganic carbon. Equilibrium does not predict precipitation speed, stock shelf life or a commercial lot's true assay. Positive saturation indices describe thermodynamic supersaturation; phase risk labels and information do not predict kinetics.

Fe-DTPA and Fe-o,o-EDDHA are Fe(III)-only 1:1 catalogue products. Fe/Mn/Zn/Cu-EDTA retain their declared forms. Micro Combi Mix 1 and 2 are declared blends of those EDTA forms and sodium molybdate; Mix 2 also declares its boron as boric acid. Do not substitute arbitrary product chemistry based on a similar name.

## 2. Installation and first recipe

Python 3.11 or newer is required. The hosted verification matrix targets 3.11–3.14; local checks do not replace that matrix.

Install from a reviewed source checkout using the commands below. Published 0.7.0 is available on PyPI; `python -m pip install flahax==0.7.0` installs that exact
version. Verify availability and the installed version; do not silently select
a different release.

```text
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# POSIX shell: source .venv/bin/activate
python -m pip install .
python -c "import flahax; print(flahax.__version__)"
```

Pin the version for reproducible work. Never treat an unavailable version as permission to install an unreviewed substitute.

This complete example also converts the result into a 100 L batch:

```python
from flahax import load_library, recommend, final_solution_recipe, VolumeLitres

result = recommend(
    load_library()['salts'],
    targets={'N_NO3': 128, 'P': 58, 'K': 211, 'Ca': 104, 'Mg': 40, 'S': 54},
    water={'Ca': 20},
)
assert result['feasible'], result['rows']
recipe = final_solution_recipe(result, VolumeLitres(100))
for salt in recipe.salts:
    print(salt.name, salt.dose.value, 'g/L;', salt.mass.value, 'g in batch')
```

This is a numerical demonstration, not a universal crop prescription. Review every nutrient row and warning before using a recipe.

## 3. Inputs, units and results

| Input or output | Unit / interpretation |
|---|---|
| Nutrient `targets` and source `water` | Elemental mg/L (ppm); not oxide percentages |
| Product `elements` | Elemental mass percent, 0–100 |
| `gramsPerLitre` | Grams of product per litre of final working solution |
| `VolumeLitres` | Final batch or explicitly named stock/reagent volume |
| Catalogue chemistry dose | Grams of product per kg water, not per litre solution |
| Analytical water totals | Moles per kg water, keyed by the model's basis species |
| Acid density | kg/L; nitrate-N assay is elemental N percent, not HNO3 percent |
| `InjectionRatio` | Final litres per litre of stock |

Use separate `N_NO3`, `N_NH4` and supported `N_UREA` targets, total `N` (mg/L as N), or both. Each form is its own fitted target; `totalN` reports their sum. Total `N` alone is one requirement with no form split; with all three forms the forms are scored once and the total must agree with their sum; with some forms both are scored and `totalN.overlapForms` lists the overlap. Total `N` is a target only, never water, a maximum or an assay. An absent `N_UREA` is a declared zero. An absent or zero `N_NH4` is no ammonium requirement and no ammonium maximum: incidental NH4-N is reported, and the optional ammonium allowance described in section 11 is applied only when you select it. Other supported symbols include P, K, Ca, Mg, S, Fe, Mn, Zn, B, Cu, Mo, Na and Cl. An omitted target is different from an explicit zero. Sodium, chloride and carbonate product selection is conservative by default; explicit allowances do not waive chemistry or safety checks.

`result['salts']` contains selected products and doses. `result['rows']` contains
`symbol`, `target`, `final` and `deltaPct`. Use identity-bearing `salts` records
for product-to-dose mapping. Only `solve_weights` preserves the input salt order
in its raw `grams` vector; `recommend` filters and may recover products before
fitting. Do not zip its `grams` with the original catalogue. `feasible` reports
positive-target fit; it is not stock or delivery approval. Avoid additional
rounding before constraint checks.

`recommend` also returns `unmetTargets` (each target not met within the
numerical tolerance, 1e-5 relative or 1e-6 mg/L for a declared zero, with a reason), `targetIonBalance` (the formula's own cation and anion meq/L),
`ammoniumLimit`, `limitViolations` (incidental ions above a stated maximum) and,
for every selected product, `provenance` (record, chemical identity, analysis
basis and source documents). Section 11 shows how to read them.

## 4. Command-line use

`flahax` and `python -m flahax` read one JSON object from stdin. A **nonempty explicit `salts` array is required**; the CLI does not load a default catalogue silently. `targets` is required and `water` may be omitted. The following portable Python caller uses the packaged catalogue deliberately:

```python
import json
import subprocess
import sys
from flahax import load_library

payload = {'salts': load_library()['salts'], 'targets': {'K': 100}, 'water': {}}
run = subprocess.run(
    [sys.executable, '-m', 'flahax'], input=json.dumps(payload),
    text=True, capture_output=True, check=True,
)
answer = json.loads(run.stdout)
assert 'feasible' in answer
print(answer['feasible'])
```

For `recommend`, exit 0 means a recommendation was calculated, including an
infeasible one: always inspect `feasible`, `limitViolations` and `unmetTargets`.
Planning JSON commands (`workflow`, `ec`, `size`) also use exit 0 for a returned
qualified result; inspect stage statuses and missing-input/model qualifications.
For `batch` and `mix`, exit 3 means a blocked result was written, exit 0 means the
result was written (possibly requiring review), and exit 1 means invalid input or
an operation failure. Invalid command-line syntax uses exit 2. An interrupted top-level
command uses exit 130; the mix interview catches interruption and returns 1.
No successful exit certifies chemistry, field readiness or physical validation.

The recommendation JSON accepts `salts`, `targets`, `water`, `allow_ions`,
`allow_carbonates`, `ridge`, `maximum_concentrations` and
`max_ammonium_fraction`. Units match Python: elemental mg/L for targets, water
and maxima; fertilizer doses are g/L. An explicit zero maximum stays a hard zero.
`allowIons` and `allowCarbonates` remain compatibility aliases; supplying both an
alias and its snake-case name is an error. Permission flags must be JSON booleans,
not strings. Unsupported or misspelled fields fail explicitly instead of being
silently ignored. Products must be supplied explicitly; permissions do not expand
the inventory. This interface is a formulation calculator, not a stock or pump executor.

The top-level Python exports `CanonicalResult`, `accept_result`,
`verify_acceptance`, `save_result` and `load_result` expose immutable result identity
and exact-proposal consent. Consent never modifies a result's scientific status.
For versioned archives and explicit saved-session migration, see
[the developer workflow guide](https://flahax.readthedocs.io/en/latest/developer/water-to-delivery.html).

### Additional planning commands in 0.3.1

The original no-argument CLI above remains unchanged. New commands accept
JSON on stdin or request inputs interactively; they never operate hardware:

```text
python -m flahax workflow --interactive
python -m flahax ec --interactive
python -m flahax size --interactive
```

`workflow` requires actual fertilizer records, crop targets, explicit water
nutrients, target pH and final volume. Missing chemistry remains `needs_input`;
Ca = 20 mg/L alone does not identify alkalinity or calculate pH. The standard
acid choices are nitric and phosphoric, with user-supplied assay/density and
nutrient/dose limits. Zero nutrient targets are reviewed separately from
positive-target fit; hard maximum concentrations remain enforceable.

`ec` supplies an explicitly approximate, pre-acid manufacturer-anchor estimate
for supported exact SQM products at 25 C. No new measurements are required
for this screening calculation. It rejects concentrated stock channels,
unsupported products and out-of-scope loadings rather than fabricate total
EC. Numerical accuracy is unknown. The separate measured-profile API is
optional, not a prerequisite for the screening command.

`size` calculates channel stock volumes and flow rates from final batch
volume or active area, gross irrigation depth and duration. It supports pump,
venturi and Dosatron design categories but cannot select a model without
manufacturer operating data. Stock-to-final and stock-to-carrier ratios differ.

The source-checkout examples generate HTML/Markdown/JSON reports with tank
contents, acid accounting and unresolved product assignments. Candidate A/B
groupings are not approved concentrated-stock recipes. Recipe phosphoric
acid must not be counted again as an additional pH-correction dose.

Detailed schemas and examples are in the repository's `docs/site-planning.md`
and `examples/README.md`; both are included in the source distribution.

## 5. Catalogue equilibrium

```python
from flahax import catalogue_dose_totals, solve_catalogue_product_doses

doses = {'Iron DTPA': 0.01}  # grams per kg water
totals = catalogue_dose_totals(doses)
state = solve_catalogue_product_doses(doses, 6.0, allow_precipitation=False)
assert totals['Fe+3'] > 0
assert state.aqueous.species['FeDtp-2'] > 0
print(state.aqueous.ionic_strength)
```

This is fixed-pH product speciation, not a complete source-water prescription. Supply measured, complete analytical water totals for real mixtures, and anchor them at the measured pH with `balance_water_analysis` (section 11). The solver does not invent missing counterions to make a deficient analysis acceptable. Inspect component residuals, activities, saturation indices and precipitated amounts; never infer safety from pH alone.

## 6. Nitric-acid delivery planning

The low-level `plan_catalogue_nitric_target` and `plan_nitric_acid_target` return `AcidResult` with initial/target states and acid molality. `plan_equilibrium_delivery` additionally requires product identity, water mass, assay, density, dose limits and nutrient tolerances, and returns `EquilibriumPhPlan`.

The example below is an explicitly synthetic electrolyte, not site-measured water or a mixing instruction:

```python
from flahax import load_library, final_solution_recipe, VolumeLitres, plan_equilibrium_delivery

products = {p['name']: p for p in load_library()['salts']}
doses = {'Potassium Carbonate': 0.01, 'Potassium Sulfate': 0.02}
recipe = final_solution_recipe({'feasible': True, 'salts': [
    {'id': products[name]['id'], 'name': name, 'gramsPerLitre': dose * 95 / 100}
    for name, dose in doses.items()
]}, VolumeLitres(100))
plan = plan_equilibrium_delivery(
    recipe, water_mass_kg=95,
    water_totals={'Na+': 0.002, 'Cl-': 0.0020776451648549022},
    water_analysis_id='synthetic-example-v1', initial_ph=7.4, target_ph=6,
    reagent_channel_id='acid',
    reagent={'schemaVersion': '0.1', 'id': 'nitric', 'source': 'synthetic-example',
             'revision': '1', 'recordedAt': '2026-09-27T00:00:00Z',
             'name': 'Nitric acid', 'kind': 'acid', 'chemicalFormula': 'HNO3',
             'elements': {'N_NO3': 13.8}, 'densityKgPerL': 1.4},
    maximum_reagent_volume=VolumeLitres(0.1), targets={'K': 13.9},
    maximum_nutrient_error_percent=1,
)
assert plan.post_mix_measurement_required
assert 0 < plan.reagent_volume_litres < 0.1
print(plan.reagent_volume_litres, plan.nutrient_contribution)
```

Final solvent mass includes reagent carrier water, and final volume is the make-up volume. This is a fixed-solvent projection, not a free-pouring dilution model. Acid molality times kg water gives acid moles; nitrate-N assay gives reagent grams, and density gives reagent litres. Added nitrate is included in the final nutrient score. The HNO3 calculation uses the declared initial pH and inventories; the removed water-imbalance rejection is not an acceptance test. An equal target pH produces exactly zero acid; a target requiring base is outside this HNO3 path.

## 7. Stock, calibration and review workflow

1. Obtain a feasible nutrient recipe and adapt it to an explicit batch volume.
2. Supply versioned compatibility rules, per-product solubility limits and temperature coverage to `plan_stocks`. A structural assignment is not mixture approval: a reviewed mixture model must cover the exact stock and its conditions before delivery validation. Missing model evidence remains `requires_review`.
3. Choose a pH route: measured-curve `plan_ph` returns `PhPlan`; the mixed-equilibrium adapter returns `EquilibriumPhPlan`. Do not interchange their required inputs.
4. Use sourced pump calibration and `plan_pump_command` to calculate bounded planning values. The default calibration-age policy uses the actual current date; simulations may supply an explicit assessment date.
5. Match every stock and reagent channel to exactly one calibrated command before validation; conserve product masses and retain positive carrier remainder on an additive-volume basis. Titration plans must retain the matching final volume. Contact time and hydraulic mixing are not modeled. Call `compose_delivery_plan` with matching recipe/stocks, pH plan, commands and audit metadata. Equilibrium acid requires a separate channel and a command matching its volume; zero acid means no acid command.
6. Request explicit state transitions. Incomplete plans, target supersaturation or formed solids cannot become validated equilibrium delivery plans. Operator approval is never automatic.

A plan or state label does not execute hardware or prove physical mixing occurred. Post-mix pH measurement remains required before correction; computational acceptance does not certify commercial products or site safety.

## 8. Errors and troubleshooting

| Symptom | Action |
|---|---|
| CLI says salts are required | Supply a nonempty array of product records; do not send targets alone. |
| `feasible` is false | Inspect all nutrient rows and available assays; do not force approval by hiding residuals. |
| `unknown_product` or identity mismatch | Use exact catalogue names and IDs for catalogue-only chemistry. |
| `missing_file` or `invalid_json` | A file named on the command line (water, targets, products, rules, a saved item or session) is missing, unreadable or not valid JSON; the message names the file and the line and column. |
| `material_undefined` | A product has only a name. Give its formula, its ions, or its analysis by nutrient form. |
| `identity_inconsistent` | A material's analysis states a nutrient its ions do not carry (for example phosphorus on potassium nitrate). Check the formula or the label. A label that only differs from its compound's proportions is not refused: chemistry uses the compound in the amount the limiting declared nutrient supplies, and the surplus is reported, as in "label analysis differs from KNO₃: 1.91 % K not assigned to an ion". |
| `ph_not_planned_for_product` | A compound's data sheet is incomplete or does not balance: it is used for nutrients, but no pH reagent is planned. Complete the nitrogen forms, chelating agent and counter-ions. |
| `too_many_tanks` | The products need more tanks than the supplied equipment limit; no separation is waived. |
| `tank_too_small` | One irrigation needs more stock than a tank holds; the message names the tank. |
| `missing_carbon` or `ambiguous_carbon` | Measured-pH balancing needs inorganic carbon (`CO3-2`, 0 for water measured carbon-free) or titrated alkalinity, exactly one of them. |
| `alkalinity_out_of_range` | The alkalinity is not consistent with the measured pH and ions, or needs carbon beyond the dilute model. Check units (eq/kg, not mg/L as CaCO3). |
| `contradictory_water_inputs` | The water was given two ways that disagree (a `water_balance` record with `measured_ph`, or with other `water_totals`, or analytical totals that differ from the record's). Supply one. |
| `activity_model_out_of_range` | The solution exceeds the accepted dilute model; do not extrapolate to concentrated stock. |
| `wrong_reagent_direction` | Nitric acid cannot reach a target requiring base. |
| `nutrient_tolerance_exceeded` | Review nitrate feedback and selected targets; changing tolerance needs a justified decision. |
| `precipitation_risk` | Inspect named phase indices/amounts; convergence alone is not delivery approval. |
| `stale_calibration` | Obtain a current calibration, not a fabricated timestamp. |
| Missing live PHREEQC | Ordinary offline regressions still run; release-mode live verification must fail rather than skip. |

Python callers should handle `InputError` for formulation and `DeliveryError` (with its stable `code`) for planning. Retain input provenance and rejection reasons.

### Installing and upgrading

| Symptom | Cause | What to do |
|---|---|---|
| After installing from GitHub, a new feature is missing (for example `flahax mix --plain` is unknown) | Between releases every commit on `main` has the same development version, so `pip install --upgrade` keeps the files already installed (#134) | Reinstall: `python -m pip install --force-reinstall --no-deps "git+https://github.com/rafatahmed/Flahax.git@main"`. Released versions from PyPI upgrade normally with `python -m pip install --upgrade flahax`. |
| `flahax` is not recognised as a command after installing | pip said "Defaulting to user installation" and put the `flahax` program in a folder that is not on your PATH; pip's warning names that folder | Run `python -m flahax` (it works everywhere), or add the folder pip names to your PATH. |
| `flahax --version` shows an older version than you installed | The command and pip belong to different Python installations | Use the same Python for both: `python -m pip install ...` and `python -m flahax`. `python -c "import flahax, sys; print(flahax.__version__, flahax.__file__, sys.executable)"` shows which copy runs. |

### The full-screen `flahax mix`

| Symptom | Cause | What to do |
|---|---|---|
| The questions come line by line instead of full screen | The output is not a terminal (an editor's output panel, a pipe, a script), or the console cannot be put in full-screen mode (for example Git Bash) | Run `flahax mix` in Windows Terminal, PowerShell, `cmd`, or a Linux or macOS terminal. `flahax mix --plain` always asks line by line. |
| The screen says "Enlarge the window to at least 80 x 24" | The window is too small | Make the window larger; the answer you were typing is kept. Q quits. |
| Arrow keys type letters (`àH`, `àP`) or the help line is invisible | A copy older than 0.6.0 | Upgrade (see above) and check `flahax --version`. |
| Some symbols show as `?` or as plain `+ - |` lines | The console's character set cannot show them | Use Windows Terminal; the results are unchanged. |
| Esc or Q asks "Y/N" | Leaving asks first, so a stray key does not close the screen | Press Y to leave, any other key to stay. The sheets are already written once the results show. |

### Error code reference

Every `DeliveryError` carries one of these codes; its message names the value or file at fault. Codes above are not repeated. A test keeps this list complete.

**Input values and files**

| Code | Meaning | What to do |
|---|---|---|
| `invalid_value` | A number or text is out of its allowed range or form (for example a negative volume, a pH outside 0-14, a duplicate ID). | Correct the named value. |
| `invalid_session` | A saved `flahax mix` session file is damaged or was edited by hand: it is not a JSON object, or a field is missing or of the wrong type. | Fix the named field, or run `flahax mix` again to make a new session. |
| `reagent_selection_required` | An older mix session did not record which pH reagents are available. | Run `flahax mix sessions/NAME --review-reagents` to select available acids and bases and save new answers. Changed inputs or model sources still require their separate review. |
| `ambiguous_product_name` | Two supplied products share a display name used to resolve chemistry doses. The message identifies both product IDs. | Give the products distinct names before running the workflow or chemistry conversion. Pure nutrient fitting retains distinct IDs. |
| `invalid_type` | A value has the wrong kind (a list where a mapping is needed, text where a number is needed). | Supply the kind the message names. |
| `missing_field` | A required input is absent (targets, reagent records, a document field). | Add the named field. |
| `unknown_field` | A key is not recognised, for example an unsupported water key. | Use the keys the message lists. |
| `out_of_range` | A physical input is outside what the model accepts (pH, ionic strength, concentrations). | Check units and values; FlahaX does not extrapolate. |
| `unknown_ion` | A nutrient or ion symbol is not one FlahaX knows. | Use N_NO3, N_NH4, P, K, Ca, Mg, S, Fe, Mn, Zn, Cu, B, Mo, Na, Cl. |
| `invalid_ions` | A water or nutrient profile for a quantity conversion is not a valid map of ion symbols to mg/L. | Correct the profile the message names. |
| `ambiguous_unit` | A quantity could be read two ways, such as total N. | Split it as the message says (N_NO3 and N_NH4). |
| `unknown_formula` / `ambiguous_formula` | `--formula` names no packaged formula, or `--crop` matches several. | Use `--list-formulas` and give the exact name. |
| `unknown_item` | `flahax mix` cannot find a saved session or item. | Run `flahax mix sessions` to list them. |
| `unknown_command` | Not one of `workflow`, `ec`, `size`. | Use one of those. |

**Water analysis**

| Code | Meaning | What to do |
|---|---|---|
| `incomplete_water_analysis` | The chemistry needs a complete analysis declared as complete. | Supply every measured ion and mark the analysis complete. |
| `inconsistent_water_analysis` | Two water inputs disagree (formulation mg/L against chemistry totals, or titration water against formulation water). | Use one analysis for every stage. |
| `invalid_totals` | Analytical totals are not a mapping of known components to non-negative numbers. | Correct the named component. |
| `alkalinity_exhausted` | The report has no chloride and is so far out of balance that closing on the alkalinity would need negative carbonate. | Check the analysis with the laboratory; ask for chloride and alkalinity. |
| `unsupported_carbon_boundary` | Calculated pH needs inorganic carbon treated as closed. | Use `carbon_boundary='closed'`. |
| `ph_not_bracketed` | No charge-balanced pH exists between 0 and 14 for these totals. | The inputs are inconsistent; check the analysis and doses. |

**Products and materials**

| Code | Meaning | What to do |
|---|---|---|
| `invalid_composition` | A material's ions, chelating agent or blend components are not consistent. | Correct the ions, agent or components named. |
| `unknown_identity` | A grade names a chemical identity FlahaX does not ship. | Use an identity from the catalogue, or define the material by formula or ions. |
| `material_mismatch` | A grade, lot or material record does not match the product it is attached to. | Attach it to the product it describes. |
| `product_chemistry_mismatch` | A product record differs from its catalogue identity without a grade that explains it, or a compound's id is not its grade id. | Give the label as a grade, or use the catalogue record unchanged. |
| `unsupported_product_chemistry` | No chemistry can be built for the product (unknown name, or phosphate without its form). | Define it by formula, ions or a complete data-sheet analysis. |
| `composition_undisclosed` | A blend of undisclosed composition is used for chemistry. | Enter it from its data sheet, or use it for nutrients only. |
| `catalogue_chemistry_mismatch` | The packaged catalogue and its chemistry records disagree (a packaging fault). | Report it as a bug. |
| `missing_document_reference` | A supplier grade lacks its document (supplier, title, date). | Add the data-sheet reference. |
| `inconsistent_assay` | An assay is impossible (mass fraction above one, more nitrate than pure nitric acid). | Check the certificate values. |
| `invalid_identity_record` | A packaged identity record is malformed (a packaging fault). | Report it as a bug. |

**Recipe, limits and pH**

| Code | Meaning | What to do |
|---|---|---|
| `infeasible_recipe` | The recipe breaks a declared maximum, so no later stage can use it. A missed target is not this error: it is a reported deviation and the stage asks for review. | Read the formulation reason; adjust products, water or limits. |
| `nutrient_limit_exceeded` | A plan exceeds a maximum you declared. | Lower the source of that nutrient or the water share; the limit is never relaxed for you. |
| `incidental_review_required` | Nutrients the formula did not ask for have no declared maximum, so the plan cannot be validated. | Declare maxima for them, or accept the review. |
| `unsupported_reagent` | The pH reagent is not one FlahaX models. | Use HNO3, H3PO4, H2SO4 or C6H8O7 (acids) or the packaged bases. |
| `dose_limit_exceeded` | The reagent dose exceeds the volume or the limit you set. | Raise the limit only if the equipment allows, or change the target pH. |
| `missing_measurement` | A measured value is needed (reagent density, water pH and alkalinity). | Measure it and supply it. |
| `outside_titration_range` | The target pH lies outside the measured titration curve. | Extend the titration, or choose a target inside it. |
| `mismatched_record` | A titration curve or pump channel belongs to another water or stock. | Use the records that belong together. |

**Chemistry model**

| Code | Meaning | What to do |
|---|---|---|
| `nonconvergent` | The equilibrium solver did not converge. | Report the inputs as a bug; FlahaX never returns an unconverged answer. |
| `temperature_out_of_range` / `unsupported_temperature` / `temperature_outside_reference` / `temperature_reference_mismatch` | The chemistry and conductivity data are for 25 °C. | Use 25 °C for chemistry; stock solubility uses your temperature separately. |
| `unknown_phase` / `missing_species` | A mineral or species is not in the pinned reaction set. | Use phases from the shipped set. |
| `unsupported_ionic_strength` | Outside the dilute model (ionic strength above 0.1). | Do not apply the dilute model to concentrated stock. |
| `unsupported_legacy_input` | An old input form that a newer function replaces. | Use the function the message names. |

**Stocks, tanks and injection**

| Code | Meaning | What to do |
|---|---|---|
| `capacity_exceeded` | Every tank is smaller than the stock volume needed. | Use larger tanks or a higher injection ratio. |
| `solubility_exceeded` | A stock exceeds its recorded solubility (stock planner). A product with no limit at the requested temperature is kept and listed as unverified, not rejected. | Dilute (lower ratio), warm the stock room, or supply the limit. |
| `no_stock_assignment` | No tank arrangement satisfies the compatibility rules. | Add a tank or change products. |
| `invalid_ratio` / `ambiguous_volume` / `unknown_equipment_type` | Injection sizing inputs are inconsistent. | Correct the ratio, give one volume form, choose dosing_pump, venturi or dosatron. |
| `dry_tank_risk` / `out_of_calibration_range` | The stock cannot supply the planned injection, or the pump is asked outside its calibration. | Prepare more stock or recalibrate. |
| `inconsistent_recipe` | Recipe, stocks and products refer to different items (duplicates, missing products). | Rebuild the plan from one recipe. |

**Delivery plans, EC and reference data**

| Code | Meaning | What to do |
|---|---|---|
| `cross_stage_constraint` / `incomplete_plan` / `invalid_plan_transition` | A delivery plan's stages do not belong together, a stage is missing, or a state change is not allowed. | Build every stage from the same recipe and follow the plan states. |
| `invalid_ec_profile` / `mismatched_ec_profile` / `outside_ec_calibration` / `ambiguous_ec_input` / `unknown_channel` | A measured EC calibration is malformed, belongs elsewhere, or is asked outside its range; or EC and TDS were both given. | Supply one complete calibration for this recipe, channel and water, and one reading. |
| `invalid_ph_input` / `invalid_phase_policy` / `incomplete_prediction` / `invalid_audit_inputs` | Calculated-EC options conflict. | Follow the option rules in the message. |
| `invalid_fixture` | A PHREEQC reference fixture is unreadable or of an unsupported schema (verification tooling). | Recapture the fixture with the pinned PHREEQC. |

**Current calculation and saved-result errors**

| Code | Meaning and action |
|---|---|
| `canonical_result_mismatch` | Output content no longer matches its canonical calculation. Recalculate; do not mix fields from different runs. |
| `invalid_acceptance`, `stale_acceptance` | Acceptance evidence is malformed or belongs to different result content. Review the current result and record new acceptance. |
| `invalid_saved_result`, `stale_session` | Saved data is malformed or its source inputs/results changed. Load valid data or recalculate before reuse. |
| `invalid_remedy` | The requested remedy is not a valid scoped change. Inspect the permitted remedy and its inputs. |
| `ionic_strength_outside_phosphate_fit` | Raised by `ionic_molal_conductivity` above the phosphate fit ionic strength. `calculate_ec_from_totals` does not refuse: it bounds that phosphate and reports an EC range. |
| `invalid_ec_scenarios` | EC sensitivity scenarios are malformed. Supply the required explicit scenario inputs. |
| `unknown_component`, `duplicate_product` | A component is not supported or a product ID is repeated. Correct the analytical inventory or unique product IDs. |
| `missing_density` | A volume-based reagent calculation lacks density. Supply sourced density or use a supported mass-based input. |
| `numerical_failure`, `unresolved_sensitivity`, `unusable_trial` | A numerical trial or derivative could not be qualified. Inspect diagnostics; do not accept an unverified solution. |
| `missing_chemistry`, `inconsistent_basis` | Joint fitting lacks chemical inventory or uses inconsistent solvent bases. Supply complete, consistent inputs. |
| `joint_search_incomplete`, `joint_verification_failed` | The joint search or independent verification did not qualify a solution. Retain the diagnostics and resolve the reported constraints or numerical failure. |
| `invalid_role` | A reagent role is inconsistent with the supported request. Correct the role; do not infer it from a display name. |
| `duplicate_field` | A request repeats a field. Supply each field once so the intended value is unambiguous. |
| `future_calibration` | A calibration is dated after the evaluation time. Correct the timestamps before evaluating equipment. |
| `invalid_phase_evidence`, `invalid_si_uncertainty` | Phase applicability evidence or saturation-index uncertainty is invalid. Supply qualified evidence; do not suppress the phase finding. |
| `invalid_mixture_result`, `unqualified_stock_mixture` | The stock-mixture assessment is invalid or lacks applicable qualification. The proposed stock cannot be approved on that evidence. |
| `stock_search_limit` | Stock assignment search exhausted its budget. This is not proof that no arrangement exists. Review constraints and search diagnostics. |
| `invalid_solubility_input`, `invalid_solubility_basis`, `invalid_solubility_table` | Solubility data has invalid values, units/basis or table structure. Correct the sourced record before screening. |
| `unqualified_solubility_limit` | A solubility message was requested for a row that is not an exceedance of a single-product value. |

**Fixed-ratio recipes, uncertainty and stock dosing**

The ratio workflow adapts Steiner's design method. Water/product accounting,
uncertainty bounds, mineral saturation checks and the search policy are FlahaX
extensions. A numerical pass is not measured preparation or stability evidence.
Preserve failed or incomplete checks; do not remove bounds to obtain a pass.

| Code | Meaning and action |
|---|---|
| `duplicate_strength` | Supply either a fixed `counted_mmol_l` or a search `strength_range`, not both. |
| `invalid_ratio_input` | A ratio, concentration, pH, volume or other numeric field is invalid. Supply finite values, three shares per ion group with a positive sum, and physically valid amounts; the message names the field. |
| `invalid_ratio_limits` | Use supported elemental mg/L ceilings: K, Ca, Mg, nitrate-N (`N_NO3`), P, S, Na, Cl or ammonium-N (`N_NH4`). Check names, units and finite nonnegative values. |
| `invalid_nutrient_reserve` | Reserve must be a fraction from zero up to, but not including, one. A positive reserve needs explicit nutrient ceilings. |
| `invalid_ratio_water` | Supply `demineralized` or a complete identified water analysis with measured pH, supported temperature, source-water mass and explicit required ion totals, including justified zeros. Check the named fields and concentration basis. |
| `missing_water_ammonium` | An ammonium ceiling needs an explicit source-water `NH4+` total, including a justified zero. Do not infer absence from a missing result. |
| `invalid_ratio_products` | Each product needs a unique name, supported composition, elemental assay, role and solvent fraction. Correct missing fields or a mass inventory that exceeds 100%. |
| `ambiguous_ratio_reagents` | Declare pH reagents through product roles or `ph_reagents`, not both. |
| `invalid_ph_reagents` | The pure-salt allocation accepts a nonempty, unique selection of KOH and/or HNO3. Declare the intended permitted reagents explicitly. |
| `ratio_water_exceeds_target` | Source water already supplies more than a target nutrient. Review source-water quantity/composition or targets; adding salts cannot remove that excess. |
| `ratio_limit_exceeded` | Source water or the calculated recipe exceeds a declared ceiling. Inspect the complete nutrient inventory, including pH reagents; revise the preparation inputs rather than ignoring the limit. |
| `ratio_infeasible` | The requested ratios and strength cannot close charge at the specified pH in this model. Review those inputs and the supported chemistry. |
| `ratio_allocation_infeasible` | The pure-salt allocation needs an unpermitted pH reagent or an unsupported source. Check permitted reagents and whether the requested composition is supported. |
| `ratio_product_fit_failed` | The local product allocator did not produce an acceptable fit, exhausted its budget, or could not satisfy limits/solvent inventory. Inspect products and constraints. This does not prove global infeasibility or identify a mineral as the cause. |
| `ratio_verification_failed` | Independent recipe reconstruction or charge verification failed. Preserve the request and diagnostics for investigation; do not use the unverified allocation. |
| `missing_ph_range`, `invalid_ph_range` | Rounding, uncertainty and strength-search checks need two finite pH endpoints containing the target, within 0-14. Supply the intended operating interval. |
| `invalid_rounding` | Set `mass_decimals` to an integer from zero to eight; verify the rounded recipe at the chosen precision. |
| `invalid_phases` | Select at least one supported mineral: brushite, monetite or hydroxyapatite. Check names instead of silently dropping a phase. |
| `phase_unavailable` | A selected mineral has no finite saturation index. Preserve the incomplete calculation and investigate model support/data; absence of an SI is not a saturation pass. |
| `ph_refinement_incomplete` | Adaptive pH refinement exhausted its budget. Treat coverage as incomplete, not passing; inspect the reported unresolved intervals. |
| `invalid_strength_range`, `invalid_scan_points` | Use an increasing pair of positive strengths and an integer scan count from three to 1001. A finite search still cannot prove a global maximum. |
| `missing_uncertainty`, `invalid_uncertainty` | Supply the exact preparation fields for the selected pure-salt/stock mode. Errors must be finite and nonnegative, purity bounds positive and at most one, and volume must remain positive. Only an inert inactive fraction is supported. |
| `invalid_analysis_uncertainty` | Water/product uncertainty fields do not match the selected mode or their bounds are invalid/incomplete. Bound every relevant product and element, including pH reagents; retain the required water, volume and scenario-budget fields. |
| `unsupported_ratio_water_uncertainty` | The selected pure-salt uncertainty/stock mode cannot handle real-water inputs. Use the supported explicit water/product uncertainty workflow when applicable; do not substitute demineralized water to hide contributions. |
| `unsupported_ratio_product_uncertainty` | The requested combination of products, uncertainty and stock evidence is not supported. Explicit products use the water/product uncertainty modes; native volumetric stock verification cannot be combined with those modes. |
| `unsupported_ratio_reagent_uncertainty` | Nitric-acid uncertainty or stock verification is unsupported in the selected pure-salt mode. Retain that limitation rather than assuming an exact acid dose. |
| `invalid_assay_document_source`, `missing_assay_document` | Select a supported grade or lot source and supply the linked grade/lot records. Missing documents cannot establish bounds. |
| `unsupported_assay_impurity_bounds` | Document impurity limits need explicit composition and bounded inventories. They cannot be replaced by zero or inferred from active-content factors. |
| `unsupported_elemental_grade` | The selected grade/composition does not support this elemental uncertainty model or does not preserve nominal inventory. Use a supported single identity or an explicitly supported ingredient model. |
| `assay_document_element_mismatch` | A lot introduces elements absent from the nominal product. Add their explicit nominal composition and bounds before verification. |
| `incomplete_assay_bounds` | Every declared element needs positive nominal content and explicit positive lower/upper bounds. A typical value alone is not an uncertainty interval. |
| `unsupported_blend_bounds` | Blend verification requires disclosed, supported ingredients without unmodeled impurity limits. Supply supported composition evidence; do not invent ingredient chemistry. |
| `invalid_blend_bounds` | Bound every disclosed ingredient, at most eight, with finite mass fractions from zero to one containing each nominal fraction. |
| `invalid_blend_mass_bounds`, `invalid_elemental_mass_bounds` | Upper ingredient or elemental bounds plus solvent exceed product mass. Reconcile the stated composition and physical bounds. |
| `blend_assay_mismatch` | The nominal blend does not match its declared ingredient inventory. Reconcile composition/assay records before applying correlated bounds. |
| `unsupported_elemental_counterion_bounds` | Derived counterions need defensible explicit bounds. Do not treat unbounded counterions as fixed or absent. |
| `unsupported_physical_uncertainty` | Closed-batch physical uncertainty requires elemental mode and an explicit source-water analysis. Use the supported combination. |
| `invalid_physical_uncertainty` | Supply complete, ordered density, source-water quantity and solvent intervals containing nominal values. Density/source quantity must stay positive and solvent fractions cannot exceed one. |
| `invalid_source_solvent_bounds` | The source-water non-solvent fraction is smaller than its known elemental inventory. Reconcile analysis and solvent bounds on the same mass basis. |
| `missing_stock_dosing` | Stock verification or batch-stability records require a stock-dosing specification. Records alone do not define the preparation. |
| `invalid_stock_dosing` | Supply concentrations in g/L for every declared stock, concentration-relative error, dose error in mL and dose decimals. Legacy pure-compound dosing requires all six compound/hydrate stocks; product dosing uses every product name. Check finite positive concentrations, relative error below one, and integer dose decimals from zero to six. |
| `rounded_chemistry_incomplete` | FlahaX could not solve the chemistry of the rounded batch. Review the source-water analysis, stock concentrations and rounded product and reagent doses, then recalculate. The rounded batch has no verified pH or EC result. |
| `rounded_dose_infeasible` | The declared dispensing error exceeds the rounded dose. Use a preparation method with sufficient precision for that dose and recalculate. |
| `invalid_product_stock_dosing` | Declare product-mass g/L, demineralized-water carrier and positive ordered density bounds for every stock. Use elemental assay uncertainty with closed-batch physical accounting. Product concentration must fit inside total stock mass at the lowest density; do not substitute active-ion assay values for supplied-product concentrations. |
| `ratio_stock_carrier_infeasible` | At the bounded stock density and dose, product mass plus its weighing allowance exceeds total stock mass. Review concentration, dispensing, density and weighing specifications; a negative carrier-water mass cannot be prepared. |
| `unsupported_product_stock_evidence` | Volumetric product stocks currently support numerical assessment only. Stock-assay and batch-stability record integration is deferred for this mode; no measured verification or physical-stability claim is available. |
| `ratio_stock_dose_infeasible` | A positive rounded stock dose is smaller than its dosing uncertainty. Review stock concentration and the justified dispensing specification. |
| `ratio_stock_volume_infeasible` | Stock doses, including their error bounds, leave no dilution-water allowance at the minimum final volume. Review concentrations and volumes; stock volumes count toward the final batch. |

## 9. Verification and reproducibility

From an installed development checkout, run `python -m unittest discover -s tests -t .` and `python -m compileall -q src tools`. Use `PYTHONPATH=src` if the checkout is not installed. Reference acceptance also requires the pinned external PHREEQC run with `FLAHAX_REQUIRE_PHREEQC=1`; the executable is never a runtime package dependency.

The fixture suite retains inputs, outputs, hashes, tolerances and failure reproducers. Runtime and reference use the same selected chemistry; agreement is numerical evidence, not universal experimental truth. G6's computational assessor is **Rafat Al Khashan**. No independent human signature or laboratory result is inferred.

For offline access to this manual after installation:

```text
python -c "from importlib.resources import files; print(files('flahax').joinpath('data/USER_GUIDE.md').read_text(encoding='utf-8'))"
```

## 10. Upgrading, integration and citation

### Migration to 0.7.0 from 0.6.0

Recalculate saved recipes from their original inputs; do not reuse an old acceptance
or relabel a historical result as a new calculation. Package, schema, model/source
hashes and result identity are distinct identifiers.

- Target zero is a hard zero, met within 1e-6 mg/L, except `N_NH4` (no ammonium
  requirement); omitted targets are incidental. A missed target is a reported
  deviation, not a block; only a broken declared maximum blocks. Reagent stages judge
  only their reagent's own change; `maximum_nutrient_error_percent` is optional, with
  no default. Declare nutrient maximums explicitly. The optional ammonium
  allowance min(10% of total N, 1.5 mmol/L) applies only when selected (`ammoniumLimit`).
- Remove nonzero ridge; dose size and incidental nutrients are not fitting penalties.
  Keep product IDs with doses rather than zipping a filtered result to the catalogue.
- Supply an explicit nonempty product array to the JSON recipe CLI. Unknown input
  fields and ambiguous total N are rejected.
- Declare final solution volume separately from final solvent mass. Retain water,
  fertilizer and reagent inventories and count reagent nutrients exactly once.
- Explicit joint fitting requires declared solvent fractions, mass caps and controls.
  Legacy sequential fitting and bounded zero-reagent recovery remain separate modes.
- EC is `estimated` (one value) or a `range` (low and high, no midpoint); it is refused
  only when the mixture cannot be solved. Unquantified uncertainty remains unknown.
- Phase and stock decisions require condition-qualified evidence. Do not restore
  retired phase exemptions or force two tanks by waiving separations.
- Delivery remains a draft when stock-mixture or command evidence is missing.
  Acceptance binds to the exact result; changing inputs, sources or quantities requires
  recalculation. Legacy unbound summaries remain unverified.
- Reports retain full-precision evidence offline. Blocked sheets are diagnostic.
  Numerical completion is not physical validation.

Sonneveld imports use `mix --sonneveld-batch FILE` with explicit preview and
approval. Review source water, products, stock carriers, rounding, uncertainty
and ceilings/reserves before saving a new session. The embedded profile can
repeat after the original import file is removed; changed samples or designs
require new approval and source/input drift guards remain active. Broader
search is bounded and does not guarantee a global optimum.

The online [migration guide](https://flahax.readthedocs.io/en/latest/start/migration.html)
maps these changes to current references and executable checks.

### Historical release changes


0.5.0 preserves every 0.4.0 public export and signature; `recommend` gains the keyword-only `maximum_concentrations` and `max_ammonium_fraction`, and `catalogue_dose_totals` gains `materials`. It adds the material traceability API (`load_identities`, `identity_for_product`, `make_grade`, `make_lot`, `resolve_material`, `nutrient_band`) and experimental speciation-based irrigation EC (`calculate_irrigation_ec` and related functions); see the API reference. **Recipes change:** the default ammonium limit, the corrected catalogue assays (Mg nitrate hexahydrate, 75% phosphoric acid) and the constraint treatment of ceilings give different doses for most shipped formulas, and chelate sodium now appears in chemistry and EC. Re-run and review saved recipes before reusing them. The equilibrium solver is faster with numerically equivalent results. The full list is in `CHANGELOG.md`.

0.4.0 preserves every 0.3.1 public export and the no-argument recipe/CLI contract. It adds `balance_water_analysis` and an optional `measured_ph` entry in the workflow's `equilibrium` record; without it, behaviour is unchanged. 0.3.1 added the explicit planning subcommands. Check the nitric-result types when upgrading from development snapshots: use `AcidResult` for numerical states and `EquilibriumPhPlan` for reagent-volume composition. Package, record-schema and thermodynamic-model versions are distinct identifiers.

FlahaFAST integration is owned by the separate FlahaFAST project. No host paths, external writes or automatic control are configured by this package.

Citation: Rafat Al Khashan (2026), *FlahaX*, version 0.7.0 (2026-11-19; include the reviewed source revision). Published version DOI: https://doi.org/10.5281/zenodo.24356739. Development 0.7.1.dev0 must also identify its exact source revision; that DOI identifies published 0.7.0. Use the repository's `CITATION.cff` and cite the version actually used. FlahaX is licensed under Apache-2.0; redistributions must keep the copyright notice and the `NOTICE` file.

Further reference: [repository documentation](https://github.com/rafatahmed/Flahax/tree/main/docs), [source and issues](https://github.com/rafatahmed/Flahax), [PyPI project](https://pypi.org/project/flahax/).

## 11. Site workflow, EC and injection examples

Each Python block in this manual is a complete, independently executed example.
The following examples cover the 0.3.1, 0.4.0 and 0.5.0 additions without inventing
site chemistry, EC calibration or manufacturer operating curves. The
measured-pH example uses a published well analysis, cited in the code.

### Nutrient water is not an acid/base analysis

```python
from flahax import load_library, plan_fertilizer_workflow, VolumeLitres

workflow = plan_fertilizer_workflow(
    load_library()['salts'],
    {'N_NO3': 128, 'P': 58, 'K': 211, 'Ca': 104, 'Mg': 40, 'S': 54},
    {'Ca': 20}, 6.5, final_volume=VolumeLitres(100),
)
assert workflow.nutrient_gap['Ca'] == 84
assert workflow.stages['chemistry'].status == 'needs_input'
print(workflow.stages['chemistry'].required_inputs)
```

This subtracts water Ca from the crop target; it does not calculate pH from Ca.
Supply the complete `equilibrium` record to proceed. Read all stages, not only
`recommendation['feasible']`:

| Stage status | Meaning | Next action |
|---|---|---|
| `calculated` | That stage returned a numerical result | Inspect warnings and dependent stages |
| `needs_input` | Required evidence is absent | Provide the named `required_inputs` |
| `requires_review` | Calculated result needs assessment, such as target misses or preparation qualifications | Review residuals, absolute mg/L, limits and qualifications |
| `blocked` | That stage was rejected | Read `error_code` and `message`; correct inputs |

A zero NH4 target is no ammonium requirement: it sets no row, and products that
carry NH4 (calcium nitrate) stay eligible. The NH4 they add is reported as an
incidental contribution in absolute mg/L, never relabelled as zero.
Use `maximum_concentrations` to enforce explicit hard caps. Do not silently
relax those caps or replace the product assay to obtain a feasible fit.
When targets declare no NH4-N requirement (N_NH4 absent or 0), `recommend` adds no
ammonium maximum and reports the NH4-N the products bring. Passing
`max_ammonium_fraction=0.10` selects the optional allowance, which holds incidental
NH4-N within min(`max_ammonium_fraction` × total target N, 1.5 mmol/L NH4 = 21.01 mg/L N),
following Dutch soilless practice (De Kreij, Voogt et al.); `ammoniumLimit` records the
limit, the fraction, the cap and that basis. A positive NH4 target or an explicit N_NH4
maximum takes precedence over the allowance.

### Reading misses, limits and provenance

```python
import math
from flahax import load_library, recommend

library = load_library()
pepper = next(f for f in library['formulas'] if f['name'] == 'Pepper (Howard Resh)')
result = recommend(library['salts'], pepper['targets'], max_ammonium_fraction=0.10)
assert result['targetIonBalance']['imbalancePercent'] < -39   # anions exceed cations by 39%
assert result['ammoniumLimit'] is None  # the explicit 18 mg/L NH4 target takes precedence
assert not result['limitViolations']
assert {miss['reason'] for miss in result['unmetTargets']} == {'conflicting_targets'}
for miss in result['unmetTargets']:
    print(miss['symbol'], round(miss['deltaPct'], 2), miss['conflictsWith'])
print(result['salts'][0]['name'], result['salts'][0]['provenance']['identityId'])
```

Pepper (Howard Resh) has an imbalanced nutrient charge subtotal, and this
particular fit reports target misses. That subtotal is an informational convention;
it does not prove that a complete chemical inventory cannot meet the targets. Its misses are all
`conflicting_targets`, and `conflictsWith` names the targets each one competes
with. Because the formula states an NH4 target, `max_ammonium_fraction` sets no
allowance and `ammoniumLimit` is `None`. Current miss reasons include `no_source`, `water_exceeds_target`,
`target_above_maximum`, `prohibited_by_zero_requirement`, `limited_by_ceiling`,
`fit_degradation` and `conflicting_targets`. The first four carry a proof scoped
to the declared nonnegative nutrient inventory and constraints. The remaining
reasons disclose incomplete relaxed searches, not impossibility proofs.
There is no dose-size or incidental-nutrient penalty. Read `searchScope`,
`proofScope`, `bindingLimits` and `reachableWithChloride` with the returned
residuals; a relaxed search does not certify the original constrained recipe.
Numerical acceptance is 1e-5 relative for positive targets and 1e-6 mg/L for
explicit zeros; preparation tolerances are separate requirements.

A binding ceiling is held exactly on its limit, less one part per million.
The packaged catalogue has no chloride product. A chloride product you add is
never used unless the formula targets Cl or a Cl ceiling is given, for example
`maximum_concentrations={'Cl': 106.35}` (3 mmol/L, a common raw-water limit for
open systems). Each product's `provenance` names its catalogue record, chemical
identity, analysis basis and source documents; keep it with the recipe.

### Real water analyses: start from the measured pH

A laboratory analysis is never exactly charge-balanced. Calculating pH from
charge balance alone turns that small analytical error into a large pH error:
for a brackish well, 0.5% more chloride moves the calculated pH by about half
a unit. When the laboratory measured the water's pH, start from it:

```python
from flahax import balance_water_analysis, calculate_equilibrium_ph

# Published Qatar well (Shomar et al. 2024, Table S1, station 104), mol/kg water.
# CO3-2 is total inorganic carbon (38.75 mg/L as C).
well = {'Na+': 680 / 22.98977e3, 'K+': 44.2 / 39.0983e3, 'Ca+2': 244 / 40.078e3,
        'Mg+2': 100.8 / 24.305e3, 'Cl-': 1280.4 / 35.45e3, 'SO4-2': 723.3 / 96.06e3,
        'NO3-': 15.38 / 62.004e3, 'CO3-2': 38.75 / 12.011e3}
raw = calculate_equilibrium_ph(well, carbon_boundary='closed', phases=[])
assert raw.ph < 4.5                      # charge balance alone: far from the measured 7.8

balanced = balance_water_analysis(well, measured_ph=7.8)
assert balanced.state.ph == 7.8
assert abs(balanced.imbalance_percent + 3.52) < .01
assert balanced.balance_ion is None and balanced.totals == well   # no ion is adjusted
print(f'{balanced.imbalance_percent:.2f}% imbalance, used as measured')
```

`balance_water_analysis` speciates the water at the measured pH and takes it
as measured. Its charge imbalance is returned as `imbalance_percent` and
carried as `residual_charge_eq`: no ion is added, removed or adjusted to close
it, and no imbalance size rejects the analysis. The analysis itself stays in
`analytical_totals`: targets and maximum concentrations always use it, and
`totals` (the same analysis plus any carbon taken from a titrated alkalinity)
only feeds the chemistry (#84). Supply inorganic carbon as `CO3-2`, or titrated total
alkalinity as `alkalinity_eq_per_kg` on the supported inorganic proton reference.
Phosphate, borate, ammonia and sulfate protonation are included. Unqualified
organic/trace-metal systems are rejected. Never supply both, even for zero carbon.

In `plan_fertilizer_workflow`, add `measured_ph` to the `equilibrium` record
(with optional `alkalinity_eq_per_kg`). The chemistry stage then starts from the
measured water and reports it as `water_balance`. The fertilizer doses add
exact charge, so the mixed pH stays anchored to the measured water.

### Restricted calculated irrigation EC

```python
import math
from flahax import estimate_manufacturer_ec

doses = {'Ultrasol K Plus': 0.5, 'Ultrasol Calcium': 0.25, 'Ultrasol MKP': 0.1}
estimate = estimate_manufacturer_ec(doses, water_ec_ms_cm=0.5)
assert estimate['status'] == 'screening_estimate'
assert math.isclose(estimate['ec_ms_cm'], 1.52)
stock = estimate_manufacturer_ec(doses, water_ec_ms_cm=0.5, channel='tank:A')
assert stock['status'] == 'not_supported'
assert stock['ec_ms_cm'] is None
print(estimate['ec_ms_cm'], estimate['uncertainty_ms_cm'])
```

Expected: 1.52 mS/cm, with unknown uncertainty (`None`), not a validated
accuracy interval. This synthetic recipe uses exact supported commercial
identities. It is not the pepper recipe. Supply either water EC at 25 C or
meter TDS plus its explicit conversion factor, never both. Unknown products,
acid addition, other temperatures, stock channels and loadings above 1 g/L
return `not_supported`; a null EC is unavailable, not zero conductivity.

### A/B stock volumes and injection flow

```python
from flahax import size_injection_requirements

sizing = size_injection_requirements(
    equipment_type='dosatron', active_area_m2=2000, gross_depth_mm=5,
    duration_hours=2,
    channels={name: {'final_litres_per_stock_litre': 100,
                     'available_stock_litres': 100} for name in ('A', 'B')},
)
assert sizing['final_volume_litres'] == 10000
assert sizing['carrier_water_litres'] == 9800
assert sizing['channels']['A']['required_flow_litres_per_hour'] == 50
assert sizing['selected_model'] is None
print(sizing['channels'])
```

Each channel needs 100 L prepared stock at 50 L/h. The final 10,000 L already
includes both stocks; do not add their volumes twice. This sizes flows only:
it does not assign fertilizer to tanks or establish compatibility. Use
`plan_stocks` with actual product records and sourced rules for allocation.
Put additional equilibrium acid on its separate approved channel; phosphoric
acid already present in the nutrient recipe must not be dosed a second time.
Include every injected channel in volume accounting. Equipment model selection
still needs pressures, layout, liquid properties and manufacturer curves.

### CLI files and reports

For JSON-file input in PowerShell use
`Get-Content -Raw request.json | python -m flahax workflow`; on POSIX shells use
`python -m flahax workflow < request.json`. Use `ec` or `size` for the other
commands. Interactive prompts go to stderr; results go to stdout. Exit success
means the request was processed, not that every stage passed. Retain the full
JSON, including blocked stages, provenance and assumptions.

The graphical report generator is a **source-checkout example**, not a wheel
CLI command: `python -m examples.run_all --output build/my-examples`. Install
the checkout first or set `PYTHONPATH=src`. Reports must distinguish final
irrigation from A/B stock concentrations, recipe acid from additional acid,
candidate tank assignments from approved stock plans, and unavailable values
from zero. Never use synthetic example records as site measurements.

## Explicit solvent basis

`SolventBasis(final_volume_litres, water_mass_kg)` converts mg/L and mol/kg water
without equating litres with kilograms. Its `from_solution_mass` constructor
requires density and complete nonwater mass. Its `from_water_ledger` constructor
sums disjoint source, reagent-carrier and dissolved-hydrate water. Final solvent
includes these contributions already; do not count them twice.

Water JSON accepts `final_volume_litres` with `water_mass_kg`, or with both
`density_kg_per_litre` and `nonwater_mass_kg`. The fixed final ratio scales to the
batch volume. Legacy inputs report the 1 kg solvent/L assumption and unquantified
uncertainty. Explicit inputs do not establish measurement uncertainty.

## Titrated total alkalinity

| Error | Meaning | Action |
|---|---|---|
| `unsupported_alkalinity` | An active species has no qualified proton reference, or alkalinity is only a detection interval. | Supply a supported complete analysis; do not infer carbonate from unsupported contributors. |
| `invalid_alkalinity` | A species amount is non-finite, negative or not numeric. | Correct the molal species inventory before calculating alkalinity. |

Use `alkalinity_meq_per_litre` in water JSON for a signed total-alkalinity
measurement, separately from `mg_per_litre`. Do not combine it with `HCO3`,
including zero. Interactive entry now stores titrations in equivalents, not
as carbon. Legacy HCO3 carbon assumptions remain explicitly reported.

The supported proton reference includes carbonate, phosphate, borate, ammonia,
sulfate and major-ion complexes. Unqualified organic/trace-metal alkalinity is
rejected. Measured zeros and fixed carbon stay fixed; no chloride does not
authorize altering the titration. The original laboratory inventory continues
to determine nutrient limits.

## 12. Sonneveld profile review and rounded preparation

This route is available in the current development source. A profile is a
complete reviewed-input document, not the standard five-step interview session.
Use the current [grower walkthrough](https://flahax.readthedocs.io/en/latest/grower/sonneveld-walkthrough.html)
and [agronomist Appendix I example](https://flahax.readthedocs.io/en/latest/agronomist/sonneveld-appendix-i.html)
for the complete example, figures and target/nominal/bounds table. Those guides
and the example JSON are separate from the two Markdown resources installed in
the wheel. Obtain them before going offline; installing the wheel alone does
not install the full website or `examples/sonneveld-appendix-i.json`.

From a source checkout the full profile is `examples/sonneveld-appendix-i.json`.
From the built site, download that file to your working folder and run:

```text
flahax mix --sonneveld-batch sonneveld-appendix-i.json --output appendix-i-output
# Add --plain for line-by-line review instead of the full-screen TUI.
```

1. Review the dated root-zone sample, guide values, explicit feed corrections
   and full-precision finished-feed targets. The grower/agronomist selects
   corrections; the sample-to-guide differences do not automatically become doses.
2. Continue all preview pages or stop. Enter the grower name and review reason
   to approve the exact sample/design fingerprint. Save under a distinct name.
3. Let the workflow fit fertilizer and pH-reagent nutrients together and try
   declared additional products if needed. It never invents available products.
4. Review the selected rounded preparation and choose the adoption option or
   Stop. The Appendix I example selects the sodium sulfate alternative; sodium
   nitrate is absent from both fertilizer lists.
5. Review Tanks, Nutrients and Notes, then retain `batch-sheet.html`,
   `report.html` and `summary.json`. Exit 0 may still mean `requires_review`.

The example's final volume is 1,000 L, modeled pH target 5.5, closed carbon,
25 °C and 1,000 kg final solvent. Source water supplies Ca 1.00, Mg 0.40 and
sulfate 0.30 mmol/L, with 2.20 mmol/L retained inorganic carbon from bicarbonate.
The pH solver finds the dose of 65% w/w HNO3 at 1.39 kg/L; it is not fixed to
complete bicarbonate-neutralization equivalents. Acid nitrate and all declared
product counterions count in the finished feed.

The full-precision A–D design gives small differences from the paper's printed
rounded D cells. For the documented grades, the rounded recipe uses 24.039 g
anhydrous sodium sulfate, 187.26 mL copper sulfate pentahydrate stock and
120.98 mL sodium molybdate dihydrate stock (each 1.00 g/L of supplied product
per litre of final stock), and 127.76 mL nitric-acid product. Other dry weights
are on the generated sheet and the agronomist walkthrough. Stocks stay separate;
all additions are included in the final 1,000 L, with stock carrier displacing
source water in this adapter.

The profile includes dry weighing/assay errors, stock concentration/dispensing
errors and nitric-acid assay/density/volume bounds. Its ±0.1% nutrient intervals,
sampled pH 5.5 ±0.002 and 5% reserve below the illustrative 9 mg/L sodium ceiling
are preparation requirements. The reserved ceiling is 8.55 mg/L. They do not
certify source-water or final-volume uncertainty, a nonlinear pH interval, every
saturation state, product assays, stock stability or measured batch pH/EC.
Numerical acceptance and physical validation remain separate.

Unchanged saved inputs replay with:

```text
flahax mix sessions/appendix-i --output appendix-i-repeat
```

Unchanged sessions created with this build replay in separate processes with
identical full-precision summaries, including when the import file is removed.
The public CLI regression varies process hash seeds while retaining all nutrient,
pH and reserve checks ([#272](https://github.com/rafatahmed/Flahax/issues/272)).
Preserve original sessions and exports across software updates. A calculation
change can require reimport and review of an older record; never edit fingerprints
to force replay.

The saved session embeds the profile, preview approval, selected result identity
and versioned input/source fingerprints. It does not need the original import
file. A new sample, correction, product, reagent or equipment bound needs an
updated profile and a new interactive review; retain the old record. Source/model
drift may require reimport rather than replay. `--review-reagents` is not the
Sonneveld reapproval path. The JSON result export is not a session or import
profile. See [input and saved-session formats](https://flahax.readthedocs.io/en/latest/reference/file-formats.html#sonneveld-import-profile).

For fully offline use, retain the **complete built HTML directory**, including
`_static` and `_downloads`, plus the profile and results. With Mermaid unavailable,
use the linked route table and numbered accounting steps. The installed manual
and API reference can be located without network access using the resource command
in section 9. Physical preparation qualification and finished-batch measurements
remain open even when all declared software checks pass.
