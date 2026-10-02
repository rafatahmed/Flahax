# FlahaX 0.3.1 — User Manual

Fertilizer formulation • bounded chemistry • reviewed delivery planning

**Version:** 0.3.1, release preparation; not yet published. The earlier 0.3.0 publication exception does not authorize this release or establish hosted verification for it.

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

## 1. Purpose and boundaries

FlahaX selects fertilizer salts and their grams per litre for fixed nutrient targets after accounting for source water. Optional Python APIs evaluate one mixed aqueous system and prepare auditable delivery plans. The package is dependency-free at runtime and performs no pump I/O, deployment or database writes.

The mixed model covers 28 catalogue products, 197 aqueous entries and 28 phases. Its accepted boundary is **25 °C**, **ionic strength <= 0.1 mol/kg water**, fixed oxidation states and closed analytical inorganic carbon. Equilibrium does not predict precipitation speed, stock shelf life or a commercial lot's true assay. Positive saturation indices indicate risk, not a kinetic prediction.

Fe-DTPA and Fe-o,o-EDDHA are Fe(III)-only 1:1 catalogue products. Fe/Mn/Zn/Cu-EDTA retain their declared forms. CH-micro includes those EDTA forms, borax and sodium molybdate. Do not substitute arbitrary product chemistry based on a similar name.

## 2. Installation and first recipe

Python 3.11 or newer is required. The hosted verification matrix targets 3.11–3.13; local checks do not replace that matrix.

Before publication, install the reviewed checkout in a virtual environment:

```text
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# POSIX shell: source .venv/bin/activate
python -m pip install .
python -c "import flahax; print(flahax.__version__)"
```

After 0.3.1 is actually published, the corresponding command is `python -m pip install flahax==0.3.1`. Until then use the reviewed checkout or verified local artifacts. Never interpret an unavailable version as permission to install an unreviewed substitute.

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

`result['salts']` contains selected products and doses. `result['rows']` contains `symbol`, `target`, `final` and `deltaPct`. The full `grams` vector follows the original input salt order, including zeros. `feasible` reports the formulation acceptance; it is not stock or delivery approval. Avoid rounding before any constraint checks.

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

This is fixed-pH product speciation, not a complete source-water prescription. Supply measured, complete analytical water totals for real mixtures. The solver does not invent missing counterions to make a deficient analysis acceptable. Inspect component residuals, activities, saturation indices and precipitated amounts; never infer safety from pH alone.

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

0.3.1 preserves the no-argument recipe/CLI contract and public compatibility kernels, and adds explicit planning subcommands. Check the nitric-result types when upgrading from development snapshots: use `AcidResult` for numerical states and `EquilibriumPhPlan` for reagent-volume composition. Package, record-schema and thermodynamic-model versions are distinct identifiers.

FlahaFAST integration is owned by the separate FlahaFAST project. No host paths, external writes or automatic control are configured by this package.

Citation: Rafat Al Khashan (2026), *FlahaX*, version 0.3.1 (release preparation). Use the repository's `CITATION.cff` when citing the prepared version and distinguish it from previously published artifacts. FlahaX uses the proprietary Flaha Free Use License; free use does not imply unrestricted modification or redistribution.

Further reference: [repository documentation](https://github.com/rafatahmed/Flahax/tree/main/docs), [source and issues](https://github.com/rafatahmed/Flahax), [PyPI project](https://pypi.org/project/flahax/).
