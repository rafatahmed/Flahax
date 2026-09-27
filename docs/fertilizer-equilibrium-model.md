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

## Historical reduced model (superseded; retained for fixture provenance)

## Defined scope

`solve_fertilizer_equilibrium` is the dependency-free, 25 °C macronutrient
model used to extend P2/P3. It accepts analytical molal totals for Ca, Mg,
orthophosphate, inorganic carbon, sulfate, ammonium, nitrate, potassium,
sodium, and chloride. Its source baseline is the official USGS PHREEQC 3.8.6
release and `phreeqc.dat`; checked-in fixtures retain exact input and output.

The runtime reduced model uses Davies coefficients only through
`I <= 0.1 mol/kgw`:

```text
log10(gamma_i) = -0.509 z_i^2 (sqrt(I) / (1 + sqrt(I)) - 0.3 I)
a_i = gamma_i m_i
```

Inputs outside that range fail with `activity_model_out_of_range`; they are
not extrapolated.

## Equations

The solver iterates ionic strength with mass-balanced carbonate, ammonium, and
Ca/Mg/Na phosphate complexes. For a generic complex,

```text
beta = a_complex / product(a_reactants)
analytical_total = sum(species containing the element)
```

Carbonate uses the `phreeqc.dat` 25 °C reactions:

```text
CO3^2- + H+     <-> HCO3-       log beta = 10.329
CO3^2- + 2 H+   <-> CO2(aq)    log beta = 16.681
```

The phase constraints are reported as

```text
SI = log10(IAP) - log10(K)
```

for calcite, gypsum, hydroxyapatite, and struvite. If precipitation allocation
is enabled, a bounded bisection removes only the corresponding stoichiometric
analytical totals until the active phase reaches `SI = 0` within numerical
tolerance. That is an equilibrium allocation, not a kinetic precipitation or
stock-hold-time prediction.

## Direct target-pH acid plan

`plan_nitric_acid_target` evaluates a completely specified closed-carbon
solution at initial and target pH. The initial nitric-acid requirement is the
decrease in calculated alkalinity:

```text
n_HNO3 = Alk(initial) - Alk(target)
Alk = [HCO3-] + 2[CO3^2-] + [HPO4^2-] + 2[PO4^3-] + [OH-] - [H+]
```

The checked-in `target_ph_nitric_dose.json` fixture uses PHREEQC `Fix_H+` with
HNO3 to reach pH 6.0. FlahaX matches its acid amount within `0.0005 mol/kgw`;
the broader `0.05` fixture tolerance applies to the intentionally reduced
Davies-versus-ion-association activity comparison.

## CH-micro trace blend

The checked-in `CH - micro` product is now a defined chemical record, based on
the project-owner's declared composition rather than an inferred trade name:

```text
Fe 7.00%  as Fe(III)-EDTA     Mn 2.00%  as Mn-EDTA
Zn 0.40%  as Zn-EDTA          Cu 0.11%  as Cu-EDTA
B  1.30%  as borax            Mo 0.05%  as sodium molybdate
```

`ChMicroProductDose(g_per_kg_water).totals()` converts those elemental assays
to analytical molal totals. One mole of EDTA per mole of Fe, Mn, Zn, or Cu is
therefore included directly; the model never substitutes free metals for those
chelates. `solve_ch_micro_equilibrium` solves EDTA mass balance with Fe(III),
Mn, Zn, Cu, Ca, and Mg competition. It also solves boric-acid/borate and
molybdate/HMoO4-/H2MoO4 acid-base distributions. As with the macro model, it
requires a stated pH, 25 C, and Davies-domain ionic strength (`I <= 0.1`).

The EDTA and molybdate constants are from PHREEQC 3.8.6 `minteq.v4.dat`; the
product component identities are a project-owned product declaration recorded
on 2026-09-26. Fe is explicitly fixed as Fe(III); this is a redox boundary,
not an inferred oxidation calculation.

## Remaining product data exclusions

The formula library also includes Fe-DTPA, Fe-EDDHA, citrate, and free-metal
salts. Their product-specific ligand records and complete mixed-system PHREEQC
fixtures remain separate requirements. They must not be silently converted to
free ions or certified for precipitation behavior before that evidence exists.

## Sources

- Parkhurst, D. L. and Appelo, C. A. J. (2013), *Description of Input and
  Examples for PHREEQC Version 3*, USGS Techniques and Methods 6-A43,
  [doi:10.3133/tm6A43](https://doi.org/10.3133/tm6A43).
- [USGS PHREEQC Version 3 release](https://www.usgs.gov/software/phreeqc-version-3),
  used to generate the checked-in fixture with PHREEQC 3.8.6-17100.
