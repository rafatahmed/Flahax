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

## P2/P3 end-to-end numerical acceptance

Validated on branch `p2p3-chemistry-completion`, Python 3.14, installed PHREEQC 3.8.6-17100. One coupled runtime model replaces disconnected chelate allocation. Base MINTEQ remains byte-for-byte unchanged; neither executable nor merged database is distributed.

| Requirement | Passing evidence |
|---|---|
| P2.5 reference verification | `tests/test_product_phreeqc.py`: 10 product/target families and 11 phase families, exact live replay, charge errors <= 0.1%, hashes, full species/activities/SI and phase amounts within declared tolerances |
| P2.7 full fertilizer model | `tests/test_chemistry_acceptance.py`: all 28 catalogue conversions, 197 aqueous entries/28 phases, simultaneous balances, Davies/temperature rejection, phase complementarity and convergence; `docs/chemistry-coverage-matrix.md` resolves aliases before extensions |
| P3.7 acid/base coverage | Actual mixed doses -> initial solve -> nitrate addition -> same target solve. Corrected Fix_H+ and independent nitrate titration agree; tests verify component/charge conservation and post-mix measurement requirement |
| Evidence preservation | `tests/test_preserved_chemistry_evidence.py` hashes six original successes and all diagnostic artifacts; `tests/fixtures/phreeqc/failures/README.md` explains the reduced failure ladder |

Exact validation commands (PowerShell sets `$env:PYTHONPATH='src'`, equivalent to the first command below):

```text
PYTHONPATH=src python -m unittest discover -s tests -t .
python -m compileall -q src
git diff --check
git status
```

The complete unittest run passes **100 tests with zero failures/errors/skips**, including installed-PHREEQC live execution. Compilation and whitespace validation pass. Numerical tolerances and regeneration commands are in `reference-fixtures.md`; executable/base/extension and output hashes are in each fixture's JSON. The closure commit is the commit containing this acceptance record (not an invented self-referential hash).

This accepts the explicitly selected project parameterization, not universal chemical accuracy. In particular the inherited literature-derived Dtp/Edd profile and its activity/concentration and stereoisomer assumptions are disclosed in `sources/flahax-chelate-thermodynamic-profile.md`. Independent review and lot-specific experimental validation remain G6, not silently inferred from two solvers agreeing.

## Historical reduced-model evidence (superseded)

The macro-ion target-pH/reagent fixture is now checked in: PHREEQC 3.8.6
`phreeqc.dat`, closed analytical inorganic carbon, 25 °C, and nitric acid.
The dependency-free Davies solver matches its acid amount within `0.0005
mol/kgw`; the broader activity/speciation comparison uses the declared `0.05`
tolerance. Chelated micronutrients and unspecified micro blends remain outside
this evidence because their ligand data are not present.

## Required external gates before operational use

- G2/G3: bounded mixed-product reference/model choices are implemented and numerically verified above; preserve their declared conditions and source-profile limitations.
- G6: independent reviewer signs off on numerical evidence and required bench/site validation.
- P7: define a separate, read-only FlahaFAST interface contract; it is not implemented in the package.

## Release decision

The package may be released as a dependency-free **planning and verification prototype**. P2/P3 numerical acceptance does not authorize autonomous dosing, pump control, deployment or universal chemical certification. P6's independent G6 review and bench/site evidence remain external release gates; P7 integration remains unimplemented.
