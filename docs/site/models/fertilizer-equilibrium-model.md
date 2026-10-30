# Fertilizer Equilibrium Model

## Current unified model contract

Results carry [model-domain and omitted-competition qualifications](reaction-qualification.md).
Numerical convergence alone does not qualify an incomplete reaction family.

The [shared material inventory](material-inventory.md) supplies pre-fit nutrients
and chemistry components, with explicit incomplete/composition-disagreement fields.

`catalogue_dose_totals(doses)` converts `library.json` products in **g/kg water**, not g/L, into analytical molal totals. `solve_catalogue_product_doses(doses, ph, water_totals=..., allow_precipitation=True)` sums them into `aqueous_model.solve`. Macro and trace wrappers use that same solver. `plan_catalogue_nitric_target(doses, initial_ph, target_ph, water_totals=..., phases=...)` adds nitrate and repeatedly calls the identical model. Volume-based recipe callers must supply water mass; density is not guessed.

The generated `data/chemistry_25c.json` stores the exact master-basis expansion of 197 aqueous entries and 28 phases from pinned MINTEQ plus two extensions. [Every reaction](chemistry-coverage-matrix.md) has its original equation, log K and source line. `LIGAND_PROFILES` is derived from that file, not an independently rounded table.

All 29 packaged catalogue products (Flaha Agri Tech Analysis Ver 0.0, supplied by Flaha Agri Tech, not independent laboratory verification) have explicit records. Fe-DTPA and Fe-o,o-EDDHA supply one ligand per Fe(III), with no other Dtp/Edd metal families. Fe/Mn/Zn/Cu-EDTA products and the declared Micro Combi Mix 1 and 2 supply their declared EDTA equivalents; both blends also supply sodium molybdate, and Mix 2 supplies boric acid. Nitric and phosphoric acid supply nitrate and phosphate with an implicit proton. A potassium citrate product you supply carries one ligand per three K. Urea remains neutral (two N per molecule); potassium carbonate supplies one inorganic carbon per two K. Assayed nitrate/sulfate/sodium are never added again as inferred counterions. Ferrous sulfate preserves Fe(II).

Rounded elemental assays do not specify every unlabelled counterion. Fixed-pH results report `charge_balance` and do not claim automatic electroneutrality. References declare NaCl background and charge-adjust Na while retaining all product totals. Site use requires complete water/assay data. The legacy field `inert_mass_fraction` means unassayed elemental remainder, including oxygen/hydration/carrier, **not** measured inert carrier.

All positive components are unknown log activities in one Newton system:

```text
log10(a_species) = log_beta + sum(basis_power * log10(a_basis))
T_component = sum(aqueous stoichiometry * molality) + sum(solid stoichiometry * amount)
SI_phase = sum(phase_power * log10(a_basis)) - log_K_phase
```

Pivoted elimination and damped line search solve all balances together. An active set enforces nonnegative solids, SI = 0 for present phases and SI <= 0 for eligible absent phases. Each phase change resolves the whole mixture, not disconnected macro/trace kernels. Zero-total species are omitted exactly; stalled solves raise `DeliveryError('nonconvergent', ...)`.

Ionic strength and dilute water activity iterate to 1e-12 (ionic strength by a safeguarded secant step on I(speciation at I) - I, water activity by substitution). Dose and pH searches warm-start each solve from the previous one; the start changes only the iteration path. Component Newton residual is below 2e-10 log10 units; tests require elemental residual below 1e-9 relative + 1e-15 mol/kgw. Davies uses A = 0.509; neutral log10(gamma) = 0.1 I; water activity is approximated by `1 - sum(m)/55.5084`. PHREEQC retains its native ion-specific gamma parameters. Fixture tolerances explicitly bound this difference; the activity models are not claimed identical at every composition.

Only 25 C and I <= 0.1 mol/kgw are supported. Negative/nonfinite/unknown totals, unsupported phases, pH outside [0,14], and out-of-range temperature/ionic strength fail explicitly. Numerical pH bounds are not experimental validation of every constant over that entire interval. No Pitzer extrapolation, gas exchange, urea hydrolysis, redox kinetics, sorption or precipitation kinetics is inferred.

### Unified nitric-acid target

`nitric_target` conserves every non-nitrate component and finds nitrate addition such that final electrical-charge residual equals initial residual: neutral HNO3 addition. Every ligand, borate, molybdate, ammonium, phosphate and carbonate reaction participates, without a truncated alkalinity formula. Initial measured pH fixes the proton inventory. Targets requiring base are rejected; a supplied phase set enables the same phase equations at both endpoints. Every result requires post-mix measurement.

For the 7.4 to 6.0 mixed-product reference, fixed-valence PHREEQC nitrate titration requires **0.0006712882238301735 mol/kgw** HNO3; corrected `Fix_H+` gives **0.0006712943408644**. Batch nitrogen valences are decoupled with the documented [USGS Amm.dat technique](https://water.usgs.gov/water-resources/software/PHREEQC/documentation/phreeqc3-html/phreeqc3-5.htm), preserving every reaction constant. Otherwise native batch redox oxidizes ammonium: a different scientific problem. The reduction ladder remains under `tests/fixtures/phreeqc/failures/`.

### Compatibility

Historical `phreeqc.dat` tests explicitly call `solve_legacy_phreeqc_macro` and `plan_legacy_phreeqc_nitric`. Public macro, mixed and catalogue APIs use MINTEQ consistently. Compatible result views retain old names; `result.aqueous` exposes full species, positive precipitated amounts, residuals and iterations. Numerical evidence is not operational/bench certification.

## Historical reference

Earlier reduced-model development notes are [archived separately](https://github.com/rafatahmed/Flahax/blob/main/docs/history/reduced-equilibrium-model.md). Legacy kernels and fixtures remain available for compatibility and regression evidence; they are not the current mixed-system planning contract.

### Retained compatibility kernels and numerical checks

The public macro and trace wrappers use the simultaneous model above. The
explicit `solve_legacy_phreeqc_macro` and `plan_legacy_phreeqc_nitric` functions,
calcite/gypsum reference solvers, isolated phosphate speciation and reduced
struvite mixture retain their original reaction subsets for compatibility and
historical fixture interpretation. They do not inherit the current model's
ligand coverage, phase competition or full charge accounting.

Both current and retained iterative kernels report `nonconvergent` when their
convergence budgets are exhausted. The retained macro calcium-sulfate iteration
now allows 100 sweeps instead of 20: the historical target-pH fixture did not
meet its existing 1e-14 update criterion in 20 sweeps. The criterion and fixture
tolerances are unchanged. Retained phase allocation also checks for remaining
supersaturation with available component inventory before returning.

The reduced struvite mixture's isolated calcium-sulfate pair uses a rationalized
positive quadratic root. Free calcium plus neutral pair equals total calcium;
free sulfate plus pair equals total sulfate. This replaces a fixed-point cycle
that could previously violate those balances. It does not add reactions or
qualify the reduced model for general mixtures.

Kernel tests distinguish independently accumulated component balances,
activity-based saturation indices and a 60-digit Decimal pairing oracle from
fault-injected iteration/fallback checks. Reaction-table balance checks share
the model's stoichiometry; they are independent bookkeeping, not independent
thermodynamic data. Passing branch coverage and numerical tests establishes
neither parameter accuracy nor physical validation.
