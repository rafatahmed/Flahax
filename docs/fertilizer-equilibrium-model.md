# Fertilizer Equilibrium Model

## Current unified model contract

`catalogue_dose_totals(doses)` converts `library.json` products in **g/kg water**, not g/L, into analytical molal totals. `solve_catalogue_product_doses(doses, ph, water_totals=..., allow_precipitation=True)` sums them into `aqueous_model.solve`. Macro and trace wrappers use that same solver. `plan_catalogue_nitric_target(doses, initial_ph, target_ph, water_totals=..., phases=...)` adds nitrate and repeatedly calls the identical model. Volume-based recipe callers must supply water mass; density is not guessed.

The generated `data/chemistry_25c.json` stores the exact master-basis expansion of 197 aqueous entries and 28 phases from pinned MINTEQ plus two extensions. [Every reaction](chemistry-coverage-matrix.md) has its original equation, log K and source line. `LIGAND_PROFILES` is derived from that file, not an independently rounded table.

All 28 catalogue products have explicit records. Fe-DTPA and Fe-o,o-EDDHA supply one ligand per Fe(III), with no other Dtp/Edd metal families. Fe/Mn/Zn/Cu-EDTA products and CH-micro supply their declared EDTA equivalents; CH-micro also supplies borax and sodium molybdate. Citrate supplies one ligand per three K. Urea remains neutral (two N per molecule); potassium carbonate supplies one inorganic carbon per two K. Assayed nitrate/sulfate/sodium are never added again as inferred counterions. Ferrous sulfate preserves Fe(II).

Rounded elemental assays do not specify every unlabelled counterion. Fixed-pH results report `charge_balance` and do not claim automatic electroneutrality. References declare NaCl background and charge-adjust Na while retaining all product totals. Site use requires complete water/assay data. The legacy field `inert_mass_fraction` means unassayed elemental remainder, including oxygen/hydration/carrier, **not** measured inert carrier.

All positive components are unknown log activities in one Newton system:

```text
log10(a_species) = log_beta + sum(basis_power * log10(a_basis))
T_component = sum(aqueous stoichiometry * molality) + sum(solid stoichiometry * amount)
SI_phase = sum(phase_power * log10(a_basis)) - log_K_phase
```

Pivoted elimination and damped line search solve all balances together. An active set enforces nonnegative solids, SI = 0 for present phases and SI <= 0 for eligible absent phases. Each phase change resolves the whole mixture, not disconnected macro/trace kernels. Zero-total species are omitted exactly; stalled solves raise `DeliveryError('nonconvergent', ...)`.

Ionic strength and dilute water activity iterate to 1e-12. Component Newton residual is below 2e-10 log10 units; tests require elemental residual below 1e-9 relative + 1e-15 mol/kgw. Davies uses A = 0.509; neutral log10(gamma) = 0.1 I; water activity is approximated by `1 - sum(m)/55.5084`. PHREEQC retains its native ion-specific gamma parameters. Fixture tolerances explicitly bound this difference; the activity models are not claimed identical at every composition.

Only 25 C and I <= 0.1 mol/kgw are supported. Negative/nonfinite/unknown totals, unsupported phases, pH outside [0,14], and out-of-range temperature/ionic strength fail explicitly. Numerical pH bounds are not experimental validation of every constant over that entire interval. No Pitzer extrapolation, gas exchange, urea hydrolysis, redox kinetics, sorption or precipitation kinetics is inferred.

### Unified nitric-acid target

`nitric_target` conserves every non-nitrate component and finds nitrate addition such that final electrical-charge residual equals initial residual: neutral HNO3 addition. Every ligand, borate, molybdate, ammonium, phosphate and carbonate reaction participates, without a truncated alkalinity formula. Initial measured pH fixes the proton inventory. Targets requiring base are rejected; a supplied phase set enables the same phase equations at both endpoints. Every result requires post-mix measurement.

For the 7.4 to 6.0 mixed-product reference, fixed-valence PHREEQC nitrate titration requires **0.0006712882238301735 mol/kgw** HNO3; corrected `Fix_H+` gives **0.0006712943408644**. Batch nitrogen valences are decoupled with the documented [USGS Amm.dat technique](https://water.usgs.gov/water-resources/software/PHREEQC/documentation/phreeqc3-html/phreeqc3-5.htm), preserving every reaction constant. Otherwise native batch redox oxidizes ammonium: a different scientific problem. The reduction ladder remains under `tests/fixtures/phreeqc/failures/`.

### Compatibility

Historical `phreeqc.dat` tests explicitly call `solve_legacy_phreeqc_macro` and `plan_legacy_phreeqc_nitric`. Public macro, mixed and catalogue APIs use MINTEQ consistently. Compatible result views retain old names; `result.aqueous` exposes full species, positive precipitated amounts, residuals and iterations. Numerical evidence is not operational/bench certification.

## Historical reference

Earlier reduced-model development notes are [archived separately](history/reduced-equilibrium-model.md). Legacy kernels and fixtures remain available for compatibility and regression evidence; they are not the current mixed-system planning contract.
