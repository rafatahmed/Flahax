# PHREEQC Reference Fixtures

FlahaX uses checked-in PHREEQC golden fixtures as its dependency-free scientific verification baseline. PHREEQC is **not** a runtime dependency of the package.

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
