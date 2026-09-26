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

The target-pH/reagent reference-equivalence fixture is deliberately not claimed complete. It requires the G2/G3 choices below so that PHREEQC input and FlahaX equations share a stated database version, activity-model validity range, gas boundary, and reagent stoichiometry. Until then, pH planning is bounded by a measured titration curve and requires post-mix verification.

## Required external gates before operational use

- G2/G3: select and approve the thermodynamic database, activity model, gas boundary, and allowed reagent stoichiometry for the operating ionic-strength range.
- G6: independent reviewer signs off on numerical evidence and required bench/site validation.
- P7: define a separate, read-only FlahaFAST interface contract; it is not implemented in the package.

## Release decision

The package may be released as a dependency-free **planning and verification prototype**. It must not be advertised as an autonomous dosing, pump-control, or universally validated chemistry system. P4 and P5 are implemented; P6 remains active only for the explicitly stated target-pH reference-equivalence evidence.
