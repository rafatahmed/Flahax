# Package verification and equilibrium delivery

## P6.6: installed distributions

Run `python -m pip install build` in a development virtual environment, then `python tools/verify_distribution.py`. The tool builds wheel and sdist (wheel from sdist), installs each non-editably in a separate temporary virtual environment, runs from outside the checkout with `-I` and without `PYTHONPATH`, and asserts the imported package is inside that environment. It verifies zero runtime dependencies, 28 catalogue products, the exact chemistry resource hash, catalogue solve, nitric target, equilibrium delivery adapter, and both `python -m flahax` and `flahax` CLI entry points. A JSON report containing distribution hashes and observed numerical values is written to `build/distribution-verification.json`. Nothing is published.

The source distribution now includes offline fixture inputs/outputs, extensions and reproduction tools as well as tests; the wheel includes runtime Python and JSON resources only. Neither contains PHREEQC binaries. Python 3.11–3.13 CI runs source regression and clean distribution smoke checks. Local Python 3.14 testing is additional evidence, not a substitute for that matrix.

## P6.7: mandatory live reference validation

`tools/provision_phreeqc.ps1` uses the [official USGS Windows 3.8.6-17100 installer](https://water.usgs.gov/water-resources/software/PHREEQC/). It verifies installer SHA-256 before administrative extraction into TEMP, then verifies executable and database SHA-256. An existing installation is reused only after hash verification. No PATH, base database or global installation is changed. The Windows CI job sets `FLAHAX_PHREEQC_ROOT` and `FLAHAX_REQUIRE_PHREEQC=1`; missing tools are an error, not a skipped success.

```powershell
./tools/provision_phreeqc.ps1
$env:PYTHONPATH = 'src'
$env:FLAHAX_REQUIRE_PHREEQC = '1'
python -m unittest tests.test_product_phreeqc -v
```

Ordinary tests may still skip live replay when PHREEQC is unavailable, while all checked-in golden regressions remain mandatory. CI uploads live test logs and distribution reports. Remote CI cannot be claimed passed while GitHub's account billing lock prevents jobs from starting.

## P5.5: explicit equilibrium delivery API

`plan_equilibrium_delivery` returns **EquilibriumPhPlan**, distinct from the measured-curve **PhPlan**. Both are accepted by `compose_delivery_plan`; no existing measured-curve signature or CLI recommendation contract changes. `plan_nitric_acid_target` and `plan_catalogue_nitric_target` return the numerical **AcidResult**; callers requiring reagent volume and delivery composition use the new adapter. Equal initial and target pH now returns exactly zero acid.

Required inputs include a feasible `FinalSolutionRecipe` with matching catalogue IDs/names, final solvent mass in kg, complete analytical water totals in mol/kg water, water record ID, measured initial pH, target pH, a sourced HNO3 assay and density, dedicated acid channel, maximum reagent volume, nutrient targets and error tolerance. Recipe grams/L are converted using actual batch salt mass divided by supplied kg water; no g/L-to-g/kg equality is assumed.

For acid molality d, water mass W, nitrate-N mass fraction f and reagent density rho:

```text
n_HNO3 = d * W
reagent_g = n_HNO3 * 14.0067 / f
reagent_L = reagent_g / (1000 * rho)
added_nitrate_N_mg_L = n_HNO3 * 14.0067 * 1000 / final_volume_L
```

The reagent is explicitly HNO3 in water, not any nitrate-bearing mixture. Its nitrate-N fraction cannot exceed pure nitric acid; optional normality must agree with assay/density within 1%. Non-nitrate nutrient additions or another acid are rejected. The existing recipe scorer receives analytical water nutrients, product assays and added nitrate. Specified nutrient tolerances, dose limits, initial charge error <= 0.1%, 25 C and I <= 0.1 mol/kg water are enforced.

**Solvent convention:** final solvent inventory includes any reagent carrier water; final recipe volume is the make-up volume. Both endpoints are a fixed-solvent projection. The API does not predict additive solution volumes, contraction or a free-pouring dilution path. A caller unable to supply this boundary must not substitute arbitrary density assumptions.

The result records full input inventories, reagent provenance, selected phases, model/base/catalogue hashes and a required measurement warning. Composition verifies recipe identity, keeps acid separate from fertilizer stock channels, and checks the calibrated acid command matches the planned volume. Positive target SI or formed solids prevents transition to `validated`, even when the numerical solver converged. A zero-acid plan must not include an acid command. Normal stock compatibility, calibration and explicit operator transitions remain required; this package performs no execution.

### Runnable synthetic example

```python
from flahax import (load_library, final_solution_recipe, VolumeLitres,
                    plan_equilibrium_delivery)

products = {p['name']: p for p in load_library()['salts']}
doses = {'Potassium Carbonate': 0.01, 'Potassium Nitrate': 0.02}  # g/kg water
recipe = final_solution_recipe({'feasible': True, 'salts': [
    {'id': products[name]['id'], 'name': name, 'gramsPerLitre': dose * 95 / 100}
    for name, dose in doses.items()
]}, VolumeLitres(100))

plan = plan_equilibrium_delivery(
    recipe, water_mass_kg=95,
    # Fully specified synthetic electrolyte; not a real-site water prescription.
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
print(plan.reagent_volume_litres, plan.nutrient_contribution, plan.warnings)
```

This example is exercised in both installed distributions. `tests/test_equilibrium_delivery.py` also tests the real mixed-product PHREEQC target, complete reviewed-plan composition, mismatched identities/commands, missing records, out-of-domain water, wrong acid direction, zero dose, inconsistent assays, and supersaturation rejection.
