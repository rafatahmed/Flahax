# Reaction qualification and model domains

Qualification recorded **2026-10-26** for the pinned 25 C model: 197 aqueous
entries and 28 phases. Every entry is checked for original atom/charge balance,
transformed component balance and log-K transformation. This qualifies the
implementation of the selected equations, not all physical mixtures that a
caller can describe.

## Sources and transformation evidence

The source database SHA-256 is
`ab0a8f7c7375e1bd997990f4bc3a9af497516f10e57f4aaa3cefb55dccac5ae7`.
The [coverage matrix](chemistry-coverage-matrix.md) retains each equation,
constant, source filename and line. `tools/qualify_chemistry_model.py` checks these
against an external pinned MINTEQ file and the unchanged project extension files:

```text
python tools/qualify_chemistry_model.py --database PATH/minteq.v4.dat --report audit.json
```

This command reads the model and databases and writes only the requested report.
It records model/source hashes, per-reaction checks, source correspondence and
parameter status. A changed base hash fails. No solver or model-builder function
is imported by the checker. Atom, charge and basis sums use rational arithmetic;
log-K comparison allows only a bound calculated from binary floating-point ULPs
and the number of terms. That bound is not thermodynamic uncertainty.

| Parameter origin | What is established | What is not established |
|---|---|---|
| Pinned MINTEQ compilation | Equation/log-K correspondence and basis conversion | Independent revalidation of every underlying measurement |
| DTPA/EDDHA extension | Exact implementation of the selected project profile | New infinite-dilution calibration, electrolyte transfer or commercial isomer composition |
| Phase extension | Declared reaction and constant, preserved source identity | Kinetics, mixing compatibility or general high-salinity validity |
| Fixed-valence master/urea identity | Conserved input and zero identity constant | Redox equilibration or urea hydrolysis |

PHREEQC defines aqueous association reactions and 25 C log K in
[SOLUTION_SPECIES](https://water.usgs.gov/water-resources/software/PHREEQC/documentation/phreeqc3-html/phreeqc3-50.htm),
and mineral dissolution reactions in
[PHASES](https://water.usgs.gov/water-resources/software/PHREEQC/documentation/phreeqc3-html/phreeqc3-36.htm).
Its [input description](https://water.usgs.gov/water-resources/software/PHREEQC/documentation/phreeqc3-html/phreeqc3-5.htm)
describes internal conversion to molality and rewriting reactions to master species.
FlahaX retains its own documented activity/water approximations; matching source
constants does not make those approximations identical to PHREEQC.

## Returned qualification

Every solver-produced `AqueousResult` carries `model_domain` and
`model_limitations`. Direct fixed-pH and calculated-pH entry points retain them,
as do result objects nested in reagent/mixture calculations. Inspect these fields
before treating numerical convergence as evidence of model coverage.

For each positive EDTA, citrate, DTPA or EDDHA input, the selected reaction set is
checked for complexes with positive Ca, Mg, Fe(II), Fe(III), Mn, Zn and Cu inputs.
A missing pair yields `omitted_competition` with the exact component names. Zero
inputs do not activate a pair. This inventory is explicitly limited to those
ligands/metals; an empty list is not proof that all possible reactions are present.
DTPA/EDDHA inputs also carry `selected_chelate_profile`. No missing complex or
constant is invented, and no numerical result is altered to suppress a warning.
Downstream report/acceptance propagation remains a separate contract from these
raw solver result fields.

## Admitted numerical and chemical conventions

| Boundary | Current behavior and limitation |
|---|---|
| Temperature | Only 25 C; no temperature extrapolation |
| Ionic strength | Computed and supplied values must stay at or below 0.1 mol/kg water |
| pH | Numerical interval [0,14]; another boundary may reject a point inside it |
| Activity | Charged Davies expression; neutral log10(gamma) = 0.1 I |
| Standard state | Dimensionless molal activities; pure solid activity is unity |
| Water | `max(0.9, 1 - sum(aqueous molalities)/55.5084)`; inherited dilute approximation |
| Carbon | Closed analytical inventory, no imposed gas reservoir |
| Valence | Separate conserved oxidation states, no electron equilibration |
| Urea | Neutral conserved inventory, no hydrolysis |
| Precipitation | Equilibrium allocation for selected phases, no kinetic prediction |

Numerical bounds do not certify every parameter across that entire domain.
All 225 reactions are evaluated in a complete synthetic inventory; independent
mass-action and saturation equations check the returned activities. Tests also
check domain edges, fixed-valence and urea conservation, water activity, all 28
selected ligand/metal pairs, and in-memory parameter sensitivity. Perturbations
are test copies only; reference/database bytes are preserved.

A database citation does not establish that a phase constant has no measurement
behind it. In particular, the full MnHPO4 source chain remains unverified here;
phase-decision wording and kinetics require their separate review. Agreement
between solvers sharing a constant is implementation evidence, not independent
constant validation. Physical validation remains a later stage.
