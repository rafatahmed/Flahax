# FlahaX examples

Start with **`run_all`** for a full capability report, then read or run the
individual modules. These examples use the current **unreleased checkout**,
including the water-to-delivery APIs; a PyPI 0.3.0 installation alone is not
sufficient. No PHREEQC installation or third-party Python dependency is needed.

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = 'src'
python -m examples.run_all --output build/my-first-examples
```

This creates `report.html` (offline visual report with nutrient, fertilizer and
EC charts plus chemistry, acid and injection tables), `report.md` (complete
text details) and `report.json` (all input assumptions and calculated output).
Open `report.html` in a browser; no server, JavaScript or internet is required.
Charts keep readable text and scroll horizontally on narrow screens. The
browser print dialog can produce a paper/PDF copy. Choose a **new**
output directory on each run: existing reports are never overwritten.
Omit `--output` to print JSON only. On POSIX use
`PYTHONPATH=src python -m examples.run_all --output build/my-first-examples`.
Always run from the checkout root, using `-m`, not by executing module files directly.

## Capability map

| Module / run command | Demonstrates | Important boundary |
|---|---|---|
| `python -m examples.pepper_formulation` | User's twelve fertilizers, crop targets, water nutrient subtraction, recommendation versus raw least squares, incidental NH4/Na review, 1000 L batch masses and missing-input diagnostics | Water Ca 20 is subtracted from crop Ca 104. Actual water acid/base data are not invented; pH remains uncalculated. Commercial phosphoric-acid grade needs confirmation. |
| `python -m examples.mixed_chemistry` | All 28 catalogue dose conversions; one macro/trace equilibrium solve including Fe-DTPA, Fe-o,o-EDDHA, CH-micro and urea; species, complexes, activities, SI, conservation residuals, iterations; separate precipitation allocation and Davies rejection | Fixed pH is imposed, not predicted. g/kg-water is not g/L. Fe-DTPA/EDDHA remain Fe-only catalogue forms. |
| `python -m examples.equilibrium_delivery` | Complete synthetic water-to-recipe workflow, calculated initial pH, nitric/phosphoric comparison, HNO3 demand, commercial mass/volume and nutrient rescoring, stock concentration, pump runtime/uncertainty, composed validated plan, audit and human report | Fictional water/assays/limits/calibration. No operator approval, dosing execution or real equipment contact. |
| `python -m examples.titration_and_stocks` | Matched water/reagent/curve interpolation, alkalinity conversion and added nitrate; two-tank assignment, concentration/capacity checks and rejection when evidence cannot support the request | Curve points and stock records are **synthetic**, not laboratory/manufacturer evidence. A water-only curve does not prove final fertilizer pH. |
| `python -m examples.cli_usage` | JSON request/response through `python -m flahax` | CLI covers formulation, not automatic delivery. |
| `python -m examples.ec_and_injection` | Independently calibrated A/B and irrigation EC, EC/TDS input, stock injection volumes and pump runtimes | Fictional calibration demonstration only; no universal EC law or linear concentrate scaling. |
| `python -m examples.calculated_site_planning` | Manufacturer-anchor EC screening without new measurements; explicit unavailable A/B predictions; farm-area/batch-based channel flow and volume requirements | Exact SQM identities, pre-acid at 25 C, unknown accuracy. Not the pepper recipe; no fabricated equipment model. |

Interactive site inputs are available through `python -m flahax workflow --interactive`,
`python -m flahax ec --interactive` and `python -m flahax size --interactive`.
See [site planning](../docs/site-planning.md) for JSON schemas and boundaries.

The examples cover the user-facing capability families. Older reduced
speciation kernels and compatibility wrappers remain available and tested in
the package; this folder intentionally uses the current coupled model rather
than presenting those kernels as additional independent fertilizer solvers.
For the entire export inventory inspect `flahax.__all__` and the
[API documentation index](../docs/index.md).

## Read the reports correctly

The **Tank A / B / acid** section is a source-based review of every pepper
product (Yara `04_Fertilizer.pdf`, pp.63,65,66), not an approved stock plan.
It separates macro/chelate candidates, a proposed dedicated acid channel and
unassigned trace products. Recipe acid mass is not counted twice as pH demand.
The separate synthetic EC example now lists its actual tank contents, stock
g/L and prepared volume and explicitly states that it contains no acid dose.

Report-only update validation: `python -m unittest tests.test_examples
tests.test_release_hygiene` passed 12 tests; `python -m compileall -q src examples`
and `git diff --check` passed. HTML was visually inspected in the browser.
No chemistry database, runtime stock-allocation algorithm or fixture was changed.

- Nutrient concentrations: mg/L; N_NO3 and N_NH4 are expressed as nitrogen.
- Formula recipes: grams per final litre. Batch masses use an explicitly supplied final volume.
- Analytical chemistry and product doses: mol/kg-water and g/kg-water respectively.
- Commercial acids: an explicit product assay/density; candidate records use mass fraction while the legacy HNO3 adapter uses nitrate-N percentage. The demonstrations intentionally keep these records distinct.
- SI is dimensionless; positive SI diagnoses supersaturation, not a rate prediction. Allocated solids appear separately.
- A zero nutrient target is not an automatic hard prohibition. Incidental additions require assessment; absolute maxima are separate inputs.
- `validated` is a software planning state, **not** independent scientific sign-off or operational approval. The pump example uses a fixed historical `as_of` date solely for reproducibility.

Never copy fictional limits, densities, curve points or calibration values into
an operating fertigation system. Substitute verified, matching records and
measure after mixing. The model remains bounded to 25 C/dilute conditions;
stock compatibility is rule-based, not a high-concentration equilibrium model.
EC estimates require recipe/source-matched measured profiles; see the
[EC guide](../docs/conductivity.md). There is no universal EC predictor, cost optimizer, disease/yield model, unrestricted
gas/redox chemistry, autonomous hardware control or FlahaFAST integration in
these examples.

## Verify and extend

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_examples -v
python -m compileall -q examples
```

`common.py` only supplies explicitly synthetic provenance, readable JSON
serialization and expected-error handling. Examples never import test helpers,
change catalogue data, modify credentials or contact external services.
Report serialization is a demonstration format, not a versioned persistence
contract. Source distributions include this folder; it is not an installed
runtime subpackage in the wheel.
