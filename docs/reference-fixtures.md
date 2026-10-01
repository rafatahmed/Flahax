# PHREEQC Reference Fixtures

FlahaX uses checked-in PHREEQC golden fixtures as its dependency-free scientific verification baseline. PHREEQC is **not** a runtime dependency of the package.

## Current P2/P3 golden suite

The authoritative mixed-model evidence uses installed **PHREEQC 3.8.6-17100**, unmodified `minteq.v4.dat`, and the temporary FlahaX merge. The earlier reduced `phreeqc.dat` references below remain historical regressions, not the full mixed-model acceptance suite.

| Directory below `tests/fixtures/phreeqc/` | Cases |
|---|---|
| `products/` | fe_edta, mn_edta, zn_edta, cu_edta, fe_dtpa, fe_eddha, ch_micro, citrate, mixed_products, mixed_target_ph_nitric |
| `phases/` | calcite, calcium_phosphate, gypsum, trace_hydroxides, trace_phosphates, trace_carbonates, magnesium_salts, zero_stock, struvite, ferrous_phases, mixed_product_phases |
| `failures/` | Full target-pH reduction ladder, failed initial-charge phase input, and zero-inventory-phase warning input |

Every golden case contains `.pqi`, complete `.out`, `.screen`, high-precision `.sel`, and `expected.json`. The JSON retains numeric selected output, exact analytical totals, numerical tolerances and SHA-256 of all artifacts and the reference database. Product JSON also records actual catalogue g/kg-water doses, executable hash and extension hashes. The target case includes initial, nitrate-titration and corrected Fix_H+ inputs/outputs. The original six individually converged root chelate captures remain intact, protected by `preserved-evidence.json` and regression tests.

Base SHA-256: `ab0a8f7c7375e1bd997990f4bc3a9af497516f10e57f4aaa3cefb55dccac5ae7`.
Executable SHA-256: `d1cc2ad3ae66af8a95c3fbb605affc4d22149c8d5aab4239919792c524635006`.
No executable or merged database is checked in.

### Additional unreleased acid-selection references

`acid_selection/` adds four synthetic NaCl-background cases (HNO3, H3PO4,
H2SO4 and C6H8O7) with `Fix_H+` at pH 6.5, initially charge-balanced pH,
full captures and hashes. These extend, rather than replace, the product and
phase evidence. They verify the new candidate-acid calculation in a bounded
reference solution, not arbitrary commercial water or acid blends. See
[the workflow guide](water-to-delivery.md) for tolerances and limitations.
Regenerate with `python tools/acid_selection_evidence.py` and verify with
`PYTHONPATH=src python -m unittest tests.test_acid_reference -v` (set
`FLAHAX_REQUIRE_PHREEQC=1` to require live replay).

### Reproduction (PowerShell)

```powershell
$root = Join-Path $env:TEMP 'flahax-phreeqc\installed\phreeqc-3.8.6-17100-x64'
$exe = Join-Path $root 'bin\Release\phreeqc.exe'
$database = Join-Path $root 'database\minteq.v4.dat'
$env:PYTHONPATH = 'src'
python tools/build_chemistry_model.py $database
python tools/phreeqc_evidence.py --exe $exe --database $database
python tools/phreeqc_phase_evidence.py
python tools/debug_nitric_phreeqc.py
python tools/archive_evidence_manifest.py
python -m unittest discover -s tests -t .
python -m compileall -q src
git diff --check
git status
```

The merger removes only the terminal END from a temporary copy, appends `database/flahax-chelates-25c.dat` and `database/flahax-phases-25c.dat`, then writes END. It verifies the base hash is unchanged. `Dtp` and `Edd` are independent custom components; neither carbon valence nor native database entries are repurposed. Failures are retained with full text, not deleted because a later case fails. Successful output paths are excluded from text normalization so recorded hashes survive checkout.

### Tolerances and validation

- PHREEQC generation rejects errors, warnings and **absolute charge error > 0.1% on every selected row**.
- Live replay: every selected numeric field, 1e-8 relative + 1e-12 absolute. The live test skips only when the stated executable/database is genuinely unavailable; no skipped live test counts as release acceptance.
- Runtime product molality: 15% relative + 1e-10 mol/kgw; log activity: 0.12 for species above 1e-10 mol/kgw; SI: 0.25; ionic strength: 3% + 1e-9. These bound Davies versus native ion-specific coefficients, not measurement error or universal stock safety.
- Runtime phase fixtures: 15% + 2e-8 mol/kgw aqueous; precipitated amount 8% + 2e-8 mol/kgw; SI 0.25. Total/solid inventories are normalized to the selected final kg water, including crystal hydration water.
- Nitric dose: 3% + 2e-6 mol/kgw against both independent target methods. Expected titration is 0.0006712882238301735 and Fix_H+ is 0.0006712943408644 mol/kgw.
- Internal component conservation: 1e-9 relative + 1e-15 mol/kgw; phase complementarity SI <= 1e-7; present-phase SI = 0 within 1e-7; finite iteration bounds and explicit domain/nonconvergence errors.

`tests/test_product_phreeqc.py` verifies hashes, every product conversion path, full species/activity/SI comparisons, acid equivalence, phase allocation, conservation and live replay. `tests/test_chemistry_acceptance.py` independently checks all 28 products, ligand mass action/order independence, frozen product boundaries, zero/dilute cases, Davies/temperature limits and nitrate conservation. `tests/test_preserved_chemistry_evidence.py` protects successes and diagnostic reproducers.

## Historical reduced fixture contract

## Fixture contract

Each fixture is a JSON document under `tests/fixtures/phreeqc/` and contains:

- the exact PHREEQC input text;
- SHA-256 of that input text;
- PHREEQC version, thermodynamic database, and aqueous activity model;
- source URL and concise source description;
- selected expected numeric output; and
- a declared absolute numerical tolerance.

`flahax.reference_fixtures` verifies fixture integrity and compares a FlahaX solver result to the expected values. A future equilibrium solver must pass these tests without downloading, installing, or invoking PHREEQC.

## Official fixture families

`calcite_co2_equilibrium.json` is based on PHREEQC Version 3 Example 3, part A: pure water at 25 °C equilibrated with calcite at log CO₂ partial pressure -2. The checked selected outputs are the imposed calcite and CO₂ saturation indices. The original input is published in the [PHREEQC Version 3 example repository](https://github.com/phreeqc-dev/phreeqc3/blob/master/examples/ex3), and the underlying model is documented by the [U.S. Geological Survey](https://doi.org/10.3133/tm6A43).

This fixture is a provenance and harness canary. It is not a hydroponic stock or pH case.

`gypsum_anhydrite_equilibrium.json` retains PHREEQC Version 3 Example 2. Its first 25 °C step equilibrates pure water with gypsum and anhydrite. The expected result is `SI(Gypsum) = 0`; anhydrite is undersaturated because gypsum is the stable calcium-sulfate phase below approximately 58 °C. The [official example input](https://github.com/phreeqc-dev/phreeqc3/blob/master/examples/ex2) and [USGS example explanation](https://water.usgs.gov/water-resources/software/PHREEQC/documentation/phreeqc3-html/phreeqc3-64.htm) provide the source and interpretation.

This is a deliberately small calcium–sulfate fixture—not an approval of a fertilizer stock. A future stock fixture must add stated fertilizer totals, background ions, temperature, and every phase that can limit that mixture.

## Calcium–magnesium–phosphate mixture fixture

`ca_mg_phosphate_complexation.json` was generated locally from official PHREEQC 3.8.9 source and `phreeqc.dat`. It records a fully stated chloride/phosphate counter-ion system, selected free-ion molalities, phosphate acid forms, ionic strength, and hydroxyapatite saturation index. It verifies a reduced dependency-free Ca/Mg/phosphate complexation kernel with an explicit `0.05` absolute tolerance. The tolerance documents the difference between that narrow Davies kernel and PHREEQC's full ion-association model; it is not a safety margin or a stock-approval threshold.

## Nitrogen / struvite probe

`struvite_probe.pqi` is the exact PHREEQC 3.8.9 input for the first nitrogen fixture. It defines struvite in the input (the base `phreeqc.dat` does not include that phase), uses literature/PHREEQC-forum `log K = -13.26` at 25 °C, and specifies 1 mmol/kgw Mg, NH₄, and phosphate with Na/Cl counter-ions at pH 8.5. Its selected output is `SI(Struvite) = -0.30`; the dependency-free boundary test verifies the same free-ion activity product. This remains a fixed-activity criterion, not a precipitation or dosing decision.

`ca_sulfate_struvite_probe.pqi` adds calcium and sulfate to that explicitly stated family. It is retained as a separate PHREEQC 3.8.9 reference because phase competition must not be inferred from salt names or combined total concentrations.

`carbonate_competition_probe.pqi` adds bicarbonate and records calcite, gypsum, struvite, and hydroxyapatite saturation indices. It is the first reference for carbonate competition; it does not establish precipitation quantities or kinetic order.

`calcite_allocation_probe.pqi` is the first phase-mass fixture. PHREEQC 3.8.9 adjusts calcite from `0.100000` to `0.100033792 mol/kgw`, reaches `SI(Calcite)=0`, and shifts pH to `8.07859`. FlahaX records this allocation with a typed sign convention: a decrease is dissolution; an increase is precipitation.

## Required fixture families before P2/P3 completion

| Family | Required model inputs | Expected outputs |
|---|---|---|
| Stock compatibility | Complete ion totals, temperature, activity model, database, named calcium/phosphate/sulfate phases | Ionic strength, activities, `log IAP`, `log K`, saturation indices |
| Target pH | Complete water/fertilizer totals, alkalinity, gas boundary, reagent stoichiometry, temperature, activity model, database | Reagent amount, pH, species activities, saturation indices |
| Boundary cases | Near-zero, zero, and positive saturation index; target pH endpoints | Defined numeric tolerances and explicit infeasibility outcomes |

The fixture generator is an offline research step: run PHREEQC with the selected version/database, retain its input and selected output, then check in the compact fixture. FlahaX tests remain dependency-free thereafter.
