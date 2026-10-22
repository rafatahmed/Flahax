# FlahaX 0.5.0 — User Manual

Fertilizer formulation • bounded chemistry • reviewed delivery planning

**Version:** 0.5.0, released 2026-10-20. The release workflow ran the Python 3.11–3.13 checks and the live PHREEQC replay on the tagged commit; see the repository's release evidence.

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

For exact public signatures and result-record fields, see the bundled
[Public API reference](API_REFERENCE.md). Both documents are installed under
`flahax/data/`; neither requires network access to read.

## 1. Purpose and boundaries

FlahaX selects fertilizer salts and their grams per litre for fixed nutrient targets after accounting for source water. Optional Python APIs evaluate one mixed aqueous system and prepare auditable delivery plans. The package is dependency-free at runtime and performs no pump I/O, deployment or database writes.

Source-water chemistry starts from a laboratory analysis. From 0.4.0, the water is speciated at its **measured pH**, and the analysis's small charge imbalance is closed on one named ion and reported, instead of being turned into a pH error (section 11). From 0.5.0, `recommend` explains every missed target, reports whether the formula itself is electrically balanced, holds incidental ions (by default ammonium) within stated limits, and records each product's source document (section 11). FlahaX is open source under the Apache License 2.0.

The mixed model covers 32 catalogue products, 197 aqueous entries and 28 phases. Its accepted boundary is **25 °C**, **ionic strength <= 0.1 mol/kg water**, fixed oxidation states and closed analytical inorganic carbon. Equilibrium does not predict precipitation speed, stock shelf life or a commercial lot's true assay. Positive saturation indices indicate risk, not a kinetic prediction.

Fe-DTPA and Fe-o,o-EDDHA are Fe(III)-only 1:1 catalogue products. Fe/Mn/Zn/Cu-EDTA retain their declared forms. CH-micro includes those EDTA forms, borax and sodium molybdate. Do not substitute arbitrary product chemistry based on a similar name.

## 2. Installation and first recipe

Python 3.11 or newer is required. The hosted verification matrix targets 3.11–3.13; local checks do not replace that matrix.

Install the published package in a virtual environment. From a source checkout, `python -m pip install .` installs the same version:

```text
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# POSIX shell: source .venv/bin/activate
python -m pip install flahax==0.5.0
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

Use separate `N_NO3`, `N_NH4` and supported `N_UREA` targets; generic total `N` is not accepted. Other supported symbols include P, K, Ca, Mg, S, Fe, Mn, Zn, B, Cu, Mo, Na and Cl. An omitted target is different from an explicit zero. Sodium, chloride and carbonate product selection is conservative by default; explicit allowances do not waive chemistry or safety checks.

`result['salts']` contains selected products and doses. `result['rows']` contains
`symbol`, `target`, `final` and `deltaPct`. Use identity-bearing `salts` records
for product-to-dose mapping. Only `solve_weights` preserves the input salt order
in its raw `grams` vector; `recommend` filters and may recover products before
fitting. Do not zip its `grams` with the original catalogue. `feasible` reports
positive-target fit; it is not stock or delivery approval. Avoid additional
rounding before constraint checks.

`recommend` also returns `unmetTargets` (each target missed by more than 1%,
with a reason), `targetIonBalance` (the formula's own cation and anion meq/L),
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

A nonzero process exit is an error; inspect stderr rather than treating it as an empty recommendation. A successful process may still return an infeasible recipe. The CLI is a formulation interface, not a stock or pump executor.

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
doses = {'Potassium Carbonate': 0.01, 'Potassium Nitrate': 0.02}
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
    maximum_reagent_volume=VolumeLitres(0.1), targets={'K': 12.72},
    maximum_nutrient_error_percent=1,
)
assert plan.post_mix_measurement_required
assert 0 < plan.reagent_volume_litres < 0.1
print(plan.reagent_volume_litres, plan.nutrient_contribution)
```

Final solvent mass includes reagent carrier water, and final volume is the make-up volume. This is a fixed-solvent projection, not a free-pouring dilution model. Acid molality times kg water gives acid moles; nitrate-N assay gives reagent grams, and density gives reagent litres. Added nitrate is included in the final nutrient score. Initial charge imbalance above the declared 0.1% limit is rejected. An equal target pH produces exactly zero acid; a target requiring base is outside this HNO3 path.

## 7. Stock, calibration and review workflow

1. Obtain a feasible nutrient recipe and adapt it to an explicit batch volume.
2. Supply versioned compatibility rules, per-product solubility limits and temperature coverage to `plan_stocks`. Missing evidence is a rejection, not implicit compatibility.
3. Choose a pH route: measured-curve `plan_ph` returns `PhPlan`; the mixed-equilibrium adapter returns `EquilibriumPhPlan`. Do not interchange their required inputs.
4. Use sourced pump calibration and `plan_pump_command` to calculate bounded planning values. The default calibration-age policy uses the actual current date; simulations may supply an explicit assessment date.
5. Call `compose_delivery_plan` with matching recipe/stocks, pH plan, commands and audit metadata. Equilibrium acid requires a separate channel and a command matching its volume; zero acid means no acid command.
6. Request explicit state transitions. Incomplete plans, target supersaturation or formed solids cannot become validated equilibrium delivery plans. Operator approval is never automatic.

A plan or state label does not execute hardware or prove physical mixing occurred. Post-mix pH measurement remains required before correction; computational acceptance does not certify commercial products or site safety.

## 8. Errors and troubleshooting

| Symptom | Action |
|---|---|
| CLI says salts are required | Supply a nonempty array of product records; do not send targets alone. |
| `feasible` is false | Inspect all nutrient rows and available assays; do not force approval by hiding residuals. |
| `unknown_product` or identity mismatch | Use exact catalogue names and IDs for catalogue-only chemistry. |
| `charge_imbalance` | Investigate missing/incorrect measured ions and units; do not auto-add unmeasured salts. |
| `charge_imbalance_exceeded` | The water analysis is more than 5% out of balance at its measured pH. Ask the laboratory to check it; raise `maximum_imbalance_percent` only as a recorded decision. |
| `missing_carbon` or `ambiguous_carbon` | Measured-pH balancing needs inorganic carbon (`CO3-2`) or titrated alkalinity, exactly one of them. |
| `alkalinity_out_of_range` | The alkalinity is not consistent with the measured pH and ions, or needs carbon beyond the dilute model. Check units (eq/kg, not mg/L as CaCO3). |
| `missing_balance_ion`, `balance_ion_exhausted` or `unsupported_balance_ion` | Balance on `Cl-` or `Na+`, which must be present in the analysis and large enough to absorb the imbalance. |
| `activity_model_out_of_range` | The solution exceeds the accepted dilute model; do not extrapolate to concentrated stock. |
| `wrong_reagent_direction` | Nitric acid cannot reach a target requiring base. |
| `nutrient_tolerance_exceeded` | Review nitrate feedback and selected targets; changing tolerance needs a justified decision. |
| `precipitation_risk` | Inspect named phase indices/amounts; convergence alone is not delivery approval. |
| `stale_calibration` | Obtain a current calibration, not a fabricated timestamp. |
| Missing live PHREEQC | Ordinary offline regressions still run; release-mode live verification must fail rather than skip. |

Python callers should handle `InputError` for formulation and `DeliveryError` (with its stable `code`) for planning. Retain input provenance and rejection reasons.

## 9. Verification and reproducibility

From an installed development checkout, run `python -m unittest discover -s tests -t .` and `python -m compileall -q src tools`. Use `PYTHONPATH=src` if the checkout is not installed. Reference acceptance also requires the pinned external PHREEQC run with `FLAHAX_REQUIRE_PHREEQC=1`; the executable is never a runtime package dependency.

The fixture suite retains inputs, outputs, hashes, tolerances and failure reproducers. Runtime and reference use the same selected chemistry; agreement is numerical evidence, not universal experimental truth. G6's computational assessor is **Rafat Al Khashan**. No independent human signature or laboratory result is inferred.

For offline access to this manual after installation:

```text
python -c "from importlib.resources import files; print(files('flahax').joinpath('data/USER_GUIDE.md').read_text(encoding='utf-8'))"
```

## 10. Upgrading, integration and citation

0.5.0 preserves every 0.4.0 public export and signature; `recommend` gains the keyword-only `maximum_concentrations` and `max_ammonium_fraction`, and `catalogue_dose_totals` gains `materials`. It adds the material traceability API (`load_identities`, `identity_for_product`, `make_grade`, `make_lot`, `resolve_material`, `nutrient_band`) and experimental speciation-based irrigation EC (`calculate_irrigation_ec` and related functions); see the API reference. **Recipes change:** the default ammonium limit, the corrected catalogue assays (Mg nitrate hexahydrate, 75% phosphoric acid) and the constraint treatment of ceilings give different doses for most shipped formulas, and chelate sodium now appears in chemistry and EC. Re-run and review saved recipes before reusing them. The equilibrium solver is faster with numerically equivalent results. The full list is in `CHANGELOG.md`.

0.4.0 preserves every 0.3.1 public export and the no-argument recipe/CLI contract. It adds `balance_water_analysis` and an optional `measured_ph` entry in the workflow's `equilibrium` record; without it, behaviour is unchanged. 0.3.1 added the explicit planning subcommands. Check the nitric-result types when upgrading from development snapshots: use `AcidResult` for numerical states and `EquilibriumPhPlan` for reagent-volume composition. Package, record-schema and thermodynamic-model versions are distinct identifiers.

FlahaFAST integration is owned by the separate FlahaFAST project. No host paths, external writes or automatic control are configured by this package.

Citation: Rafat Al Khashan (2026), *FlahaX*, version 0.5.0. Use the repository's `CITATION.cff` and cite the version actually used. FlahaX is licensed under Apache-2.0; redistributions must keep the copyright notice and the `NOTICE` file.

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
| `requires_review` | Incidental nutrient contribution needs assessment | Review absolute mg/L and hard caps |
| `blocked` | That stage was rejected | Read `error_code` and `message`; correct inputs |

A zero NH4 target has no meaningful percentage deviation. Real products may
add NH4: report the absolute addition separately; never relabel it as zero.
Use `maximum_concentrations` to enforce explicit hard caps. Do not silently
relax those caps or replace the product assay to obtain a feasible fit.
When targets omit NH4 entirely, `recommend` allows incidental NH4-N up to the
smaller of 10% of the total target N and 1.5 mmol/L (21.01 mg/L N) by default,
an owner decision based on Dutch soilless practice (5-15% of total N, at most
1-1.5 mmol/L; De Kreij, Voogt et al.). `ammoniumLimit` reports it;
`max_ammonium_fraction` raises it and `None` turns it off.

### Reading misses, limits and provenance

```python
import math
from flahax import load_library, recommend

library = load_library()
grow = next(f for f in library['formulas'] if f['name'] == 'Generic Grow (maximumyield)')
result = recommend(library['salts'], grow['targets'])
assert result['targetIonBalance']['exceedsWarning']        # anions exceed cations by 17%
assert math.isclose(result['ammoniumLimit']['mgPerL'], 16)  # 10% of the 160 mg/L target N
assert not result['limitViolations']
assert {miss['reason'] for miss in result['unmetTargets']} == {'limited_by_ceiling'}
for miss in result['unmetTargets']:
    print(miss['symbol'], round(miss['deltaPct'], 2), miss['bindingLimits'])
print(result['salts'][0]['name'], result['salts'][0]['provenance']['identityId'])
```

Generic Grow lists 17% more anion than cation charge, so no salt combination
meets every target; its warning says so. Its N_NO3, K, Ca and S misses are all
`limited_by_ceiling`: meeting them would need more ammonium than the default
limit allows, and `bindingLimits` names it. Other reasons are `no_source` (no
product supplies the element), `incidental_tradeoff` (reachable, but the
penalty on an unrequested ion chose otherwise) and `conflicting_targets` (with
`conflictsWith`, and `reachableWithChloride` when chloride products would
reach it). Misses within 1% are not listed.

A binding ceiling is held exactly on its limit, less one part per million.
Potassium chloride and calcium chloride dihydrate are in the catalogue but are
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
raw = calculate_equilibrium_ph(well, complete_analysis=True, carbon_boundary='closed', phases=[])
assert raw.ph < 4.5                      # charge balance alone: far from the measured 7.8

balanced = balance_water_analysis(well, measured_ph=7.8)
assert balanced.state.ph == 7.8
assert abs(balanced.imbalance_percent + 3.52) < .01
assert abs(balanced.balance_adjustment_molal / balanced.analysed_balance_ion_molal + .0953) < 1e-4
print(f'{balanced.imbalance_percent:.2f}% imbalance closed on {balanced.balance_ion}')
```

`balance_water_analysis` speciates the water at the measured pH, then closes
the remaining charge on one named ion (`'Cl-'` by default, or `'Na+'`), as
PHREEQC's `charge` option does. The analysis imbalance and the adjustment are
returned for review. An imbalance above `maximum_imbalance_percent` (default
5%) is rejected with `charge_imbalance_exceeded`: correct the analysis rather
than forcing it. Supply inorganic carbon as `CO3-2`, or titrated total
alkalinity as `alkalinity_eq_per_kg` (treated as carbonate alkalinity;
phosphate, borate and organic contributions are neglected), never both.

In `plan_fertilizer_workflow`, add `measured_ph` to the `equilibrium` record
(with optional `alkalinity_eq_per_kg`, `balance_ion` and
`maximum_imbalance_percent`). The chemistry stage then starts from the
balanced water and reports it as `water_balance`. The fertilizer doses add
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
