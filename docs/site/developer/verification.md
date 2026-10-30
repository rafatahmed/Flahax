# Package verification and equilibrium delivery

## Independent numerical oracles

Run `python -m unittest tests.test_numerical_oracles -v` from the checkout with
`PYTHONPATH=src`. The offline harness in `tools/numerical_verification.py` imports
only the Python standard library. Its reference calculations do not import the
runtime solver, chemistry model, or PHREEQC input generator.

- `box_least_squares(A, b, lower, upper)` enumerates every face of a finite box
  for up to six variables. Rational elimination gives an exact minimum of
  `sum((A*x-b)**2)` and its gradient. Singular faces can be skipped because a
  minimum on a compact box has a representative on a face with independent free
  columns. Tests check hand-solved optima, KKT signs, boundary optima and rank
  deficiency. Compare objective and feasibility when optima are nonunique.
  General linear inequalities, integer and nonlinear problems are outside this
  oracle's scope; do not use it to certify them.
- `acid_bracket(C, Ka, Kw, digits=80)` returns decimal-grid bounds for the ideal
  monoprotic-acid equation `H - Kw/H - Ka*C/(Ka+H) = 0`. Exact rational signs and
  strict monotonicity establish a unique enclosed root. The width is at most
  `10**(-digits)` in the supplied concentration basis. The 16–200 digit range is
  a resource limit. Tests independently check the denominator-cleared cubic,
  exact rational roots, water-only behavior and nested precision intervals.
  This is an ideal analytical model, not a full electrolyte or activity model.
- `error_account` reports absolute error, relative error (undefined at zero),
  and the separate absolute/relative contributions to the inclusive allowance
  `atol + rtol*abs(reference)`. Decimal input text is interpreted exactly; binary
  float inputs use their round-trip decimal spelling. Nonfinite values and
  negative allowances fail. Callers own and justify tolerances.

`compare_reference` requires matching declared temperature, concentration units,
final analytical totals, pH, carbon boundary, oxidation-state convention, phases
and charge-balancing boundary. Missing quantities or budgets fail. It retains
both methods, provenance hashes, per-quantity errors and any shared hashes.
It validates hash syntax; the capture/replay runner must verify actual bytes.
These declarations are not inferred from numerical outputs or authenticated by
the comparison function.

The integration control checks the existing Fe-EDTA PHREEQC capture and every
associated file hash, then compares runtime molalities at the **final sodium-balanced
inventory**. The original PHREEQC input balances sodium; comparing against its
unadjusted initial sodium would be a different problem. Existing capture
tolerances are reused unchanged. FlahaX's Davies/water-activity approximations
and the pinned reference method remain explicit. A deliberately doubled sodium
output must fail. Other controls reject wrong feasible optimization results,
wrong acid roots, mismatched conditions and malformed evidence.

Retain source revision/dirty-file hashes, exact inputs, command and interpreter,
reference executable/database/input hashes, comparison budgets and their origin,
per-quantity errors, and failed controls in the evidence record. Run the mandatory
live replay below to validate the installed reference; offline comparisons do
not substitute for it. Shared thermodynamic constants and generated reference
inputs can hide common errors. Even disjoint hashes do not prove independent
parameter provenance. Neither harness coverage nor reference agreement establishes
physical accuracy. Numerical tolerance selection and broader golden-reference
qualification remain separate work; physical validation is a later stage.

## Numerical stopping and diagnostic contracts

Run `python -m unittest tests.test_numerical_precision tests.test_root_finding
tests.test_solver_convergence -v`. These controls compare scaled systems with
exact rational solutions and ideal acid roots with 80-digit exact-sign brackets.
They exercise zero/trace right-hand sides, nearly dependent columns, overflow,
nonfinite values, exhausted iteration budgets and adjacent floating-point endpoints.

| Calculation | Acceptance or diagnostic rule | Scope of the evidence |
|---|---|---|
| Bracketed root | `hi-lo <= width + relative*abs(hi)`, exact evaluated zero, or an explicit caller acceptance predicate | No hidden tolerance; invalid signs fail, and exhausted budgets or unattainable widths raise `nonconvergent`. Continuity and endpoint evaluations are caller obligations. |
| Equilibrium linear step | Row-equilibrated pivoted elimination; reject zero pivots and nonfinite results | Uniformly scaled systems from `1e-150` to `1e150` are checked against rational solutions. Removing the dimensional `1e-25` pivot floor does not certify ill-conditioned forward error. The nonlinear solver must still close its residual. |
| Calculated pH | Charge residual at most `1e-12` and bracket width at most `1e-7`; exact-zero scan points can return immediately | Both limits are unchanged. Small charge alone cannot bound pH error in a weakly buffered system. Sign comparisons avoid multiplying tiny residuals into zero. |
| Aqueous Newton solve | Existing log mass-action residual below `2e-10` | A log balance error of this size corresponds to a relative balance error below `10**(2e-10)-1` before floating-point and phase-clipping effects. Returned diagnostics expose the actual balance error separately. |
| Ionic strength and water activity | Existing absolute update thresholds below `1e-12` | Diagnostics distinguish fixed ionic strength from iterated ionic strength. Small updates are iteration checks, not universal forward-error bounds. Warm/cold and pinned-reference controls remain mandatory. |
| NNLS optimality | Existing per-column allowance `10*max(rows,columns)*ROUNDOFF*term_magnitudes` | `ROUNDOFF` is binary64 spacing at one, `2**-52`, not unit roundoff. Direct residual and gradient checks are available through `nnls(..., diagnostics=record)`. The report identifies excluded columns and does not invent a condition-number estimate. |

The optional NNLS diagnostic applies to a nonempty supplied least-squares problem;
it does not certify later recipe simplification or hard-limit policy. A failed
diagnostic remains failed even if the active-set search has stopped. Rank and
active-set policy review continues with the dedicated solver work. No fitting,
chemistry, or reference tolerance was increased by these changes.
NNLS rejects nonzero columns whose squared norms underflow to zero or overflow,
and nonfinite right-hand-side product magnitudes. These are representability
failures, not infeasibility certificates. Rescale the mathematical problem;
do not widen nutrient acceptance limits to make it pass.

`AqueousResult.numerical_diagnostics` records mass-action and component-balance
residuals, ionic-strength/water updates and their existing limits. Residuals are
distinct from forward error: a nearly singular problem can have a small residual
and uncertain coordinates. The controlled linear tests bound backward error by
eight binary64 spacings times the evaluated term magnitudes; their `1e-9`
coordinate comparison covers the explicitly tested near-dependent systems only.
The ideal-acid test uses the attained bracket width plus eight endpoint ulps for
evaluation rounding. These are test-family allowances, not new runtime tolerances
or applicability claims. Physical validation remains separate.

## User manual and retained release artifacts

The canonical manual is `src/flahax/data/USER_GUIDE.md`. It is bundled as a package resource in both distributions; all nine Python examples are executed during source regression and isolated wheel/sdist verification. The verification report records the exact manual hash and example count. The bundled `API_REFERENCE.md` covers every top-level public export; source tests reject signature drift and clean installs check export coverage and record its hash. `docs/index.md` is the documentation navigation page; historical material is separate.

To retain only artifacts that passed clean-install checks, use `python tools/verify_distribution.py --artifacts-dir dist/<version>`. The destination must be new or empty; existing release files are never overwritten. This command builds and tests locally; it does not tag, upload or publish. Afterward, run `python -m twine check --strict dist/<version>/*` in a development environment with `twine` installed. The build and metadata tools are not runtime dependencies. Releases themselves are built and uploaded by the [hardened release workflow](https://github.com/rafatahmed/Flahax/blob/main/docs/publishing.md).

## Installed distributions

Run `python -m pip install build` in a development virtual environment, then `python tools/verify_distribution.py`. The tool builds wheel and sdist (wheel from sdist), installs each non-editably in a separate temporary virtual environment, runs from outside the checkout with `-I` and without `PYTHONPATH`, and asserts the imported package is inside that environment. It verifies zero runtime dependencies, the catalogue product count (29 in the packaged catalogue), the exact chemistry resource hash, catalogue solve, nitric target, equilibrium delivery adapter, and both `python -m flahax` and `flahax` CLI entry points. A JSON report containing distribution hashes and observed numerical values is written to `build/distribution-verification.json`. Nothing is published.

The source distribution now includes offline fixture inputs/outputs, extensions and reproduction tools as well as tests; the wheel includes runtime Python and JSON resources only. Neither contains PHREEQC binaries. Python 3.11–3.13 CI runs source regression and clean distribution smoke checks. Local Python 3.14 testing is additional evidence, not a substitute for that matrix.

## Mandatory live reference validation

The reviewed `tests/reference_inventory.json` pins all 197 pre-existing PHREEQC
fixture files, including expected results, comparison budgets, extensions,
historical successes, failure captures and probe inputs. The inventory verifier
rejects missing, changed or unregistered files. The manifest is reviewable source,
not a cryptographic signature; changing both a fixture and its inventory requires
an explicit evidence review, not automatic regeneration to make a test pass.

The current live families comprise 10 product cases, 11 phase cases and four acid
cases (27 retained input programs including the additional nitric-acid stages).
Every replay now checks the pinned executable, base database and temporary merged
database. The phase captures' original metadata is preserved; the common pin
qualifies the **current replay installation**, not an unrecorded historical binary.
Execution rejects errors, warnings, absent charge-error evidence, charge error
above the existing 0.1% limit, empty output, duplicate headings, mismatched row
widths and nonfinite numbers. Missing installations fail the required CI job.

Four older JSON fixtures, six intermediate successes, diagnostic failures and
standalone probes remain historical evidence. Some identify a different PHREEQC
version or lack complete executable/database provenance. They are checked for
integrity and retain their existing comparisons, but are not labelled as current
matched live qualification. Historical broad tolerances are not adopted as
current numerical accuracy bounds. Preserved failed captures stay failed.

Run `python -m unittest tests.test_reference_integrity
tests.test_preserved_chemistry_evidence tests.test_live_reference_policy -v` for
inventory, malformed-data, overwrite, warning and missing-installation controls.
The required live job also runs these controls alongside product/phase/acid replay.

Capture tools require `--output NEW_DIRECTORY` outside the historical fixture
tree. For example, `python tools/phreeqc_evidence.py --output ../new-product-captures`;
the phase and acid tools accept the same option. Existing destinations and
existing per-case artifacts are rejected before execution. New captures remain
candidates for review; they do not replace golden files or amend the inventory.
Original inputs and failed output are retained when a capture fails.

PHREEQC and FlahaX share thermodynamic data, and some fixed-valence input
transformations read runtime reactions. Their agreement tests implementation
consistency under declared assumptions, not independent parameter or physical
validation. Missing ligand interactions remain explicit model limitations rather
than being repaired in reference databases.

`tools/provision_phreeqc.ps1` uses the [official USGS Windows 3.8.6-17100 installer](https://water.usgs.gov/water-resources/software/PHREEQC/). It verifies installer SHA-256 before administrative extraction into TEMP, then verifies executable and database SHA-256. An existing installation is reused only after hash verification. No PATH, base database or global installation is changed. The Windows CI job sets `FLAHAX_PHREEQC_ROOT` and `FLAHAX_REQUIRE_PHREEQC=1`; missing tools are an error, not a skipped success.

```powershell
./tools/provision_phreeqc.ps1
$env:PYTHONPATH = 'src'
$env:FLAHAX_REQUIRE_PHREEQC = '1'
python -m unittest tests.test_product_phreeqc -v
```

Ordinary tests may still skip live replay when PHREEQC is unavailable, while all checked-in golden regressions remain mandatory. CI uploads live test logs and distribution reports. Remote CI cannot be claimed passed while GitHub's account billing lock prevents jobs from starting.

## Explicit equilibrium delivery API

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
doses = {'Potassium Carbonate': 0.01, 'Potassium Sulfate': 0.02}  # g/kg water
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
    maximum_reagent_volume=VolumeLitres(0.1), targets={'K': 13.9},
    maximum_nutrient_error_percent=1,
)
print(plan.reagent_volume_litres, plan.nutrient_contribution, plan.warnings)
```

This example is exercised in both installed distributions. `tests/test_equilibrium_delivery.py` also tests the real mixed-product PHREEQC target, complete reviewed-plan composition, mismatched identities/commands, missing records, out-of-domain water, wrong acid direction, zero dose, inconsistent assays, and supersaturation rejection.

## Check reaction provenance without rebuilding databases

Run `python tools/qualify_chemistry_model.py --database PATH/minteq.v4.dat --report audit.json`
against the pinned external database. This read-only check covers all selected
reactions and records source/model hashes. Run `python -m unittest tests.test_model_qualification`
for independent conservation, transform, domain and sensitivity checks. See the
[qualification scope](../models/reaction-qualification.md); a successful check
is not experimental calibration of inherited constants.
