# Fertilizer Equilibrium Model

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
