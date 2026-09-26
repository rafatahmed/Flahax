# Delivery Planner Release Evidence

## Automated evidence

- Existing nutrient-solver regression suite passes unchanged.
- Delivery contract, stock, pH, pump, aggregate-plan, and chemistry fixture tests run dependency-free.
- A complete 100 L fixture composes a feasible recipe, compatible stock, measured-curve pH plan, calibrated command, and audit record; it must transition through `validated`, `operator-approved`, `executed`, and `verified` explicitly.
- A high-alkalinity (`500 mg/L as CaCO3`) measured-curve fixture confirms a bounded 20 mL initial nitric-acid dose for 100 L and retains the required post-mix measurement.
- The calcium/phosphate incompatibility fixture fails closed when only one tank is supplied.
- Sensitivity evidence demonstrates visible effects from measured dose demand, reagent assay, injector ratio, and pump flow; temperature outside the source-qualified solubility range fails closed.
- Pump commands are planning values only; package code contains no hardware I/O.
- The checked-in PHREEQC inputs provide provenance for reduced activities, species, and saturation-index regressions. They are a dependency-free verification baseline, not a runtime dependency.

## Mathematical evidence still required

The macro-ion target-pH/reagent fixture is now checked in: PHREEQC 3.8.6
`phreeqc.dat`, closed analytical inorganic carbon, 25 °C, and nitric acid.
The dependency-free Davies solver matches its acid amount within `0.0005
mol/kgw`; the broader activity/speciation comparison uses the declared `0.05`
tolerance. Chelated micronutrients and unspecified micro blends remain outside
this evidence because their ligand data are not present.

## Required external gates before operational use

- G2/G3: macro-ion reference/model choices are documented; select product-specific ligand data and a compatible thermodynamic dataset before approving chelated/micro products.
- G6: independent reviewer signs off on numerical evidence and required bench/site validation.
- P7: define a separate, read-only FlahaFAST interface contract; it is not implemented in the package.

## Release decision

The package may be released as a dependency-free **planning and verification prototype**. It must not be advertised as an autonomous dosing, pump-control, or universally validated chemistry system. P4 and P5 are implemented; P6 remains active only for the explicitly stated target-pH reference-equivalence evidence.
