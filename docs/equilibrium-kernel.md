# First Internal Equilibrium Kernel

FlahaX now contains a deliberately narrow, dependency-free aqueous-equilibrium kernel: open-CO₂ calcite equilibrium at 25 °C using Davies activity coefficients. It is the first mathematical P2.6/P3.6 component, verified against the checked-in PHREEQC Example 3 fixture.

## Supported system

```text
CO2(g) <-> CO2(aq)
CO2(aq) <-> H+ + HCO3-
HCO3- <-> H+ + CO3^2-
H2O <-> H+ + OH-
CaCO3(s) <-> Ca^2+ + CO3^2-
```

The kernel assumes:

- 25 °C only;
- a specified open CO₂ partial pressure;
- calcite at equilibrium;
- the Davies activity-coefficient equation; and
- no ion pairing, other solids, redox chemistry, or transport.

This is an explicit scope boundary. It must not be used to claim arbitrary fertilizer-solution compatibility or generic pH control.

## Equations

For every aqueous reaction:

```text
K_r = product_i(a_i ^ nu_i)
a_i = gamma_i * m_i
```

The Davies coefficient at 25 °C is:

```text
log10(gamma_i) = -0.509 * z_i^2 * (sqrt(I) / (1 + sqrt(I)) - 0.3I)
I = 1/2 * sum_i(m_i * z_i^2)
```

The solver iterates ionic strength and solves electroneutrality:

```text
2[Ca^2+] + [H+] - [HCO3-] - 2[CO3^2-] - [OH-] = 0
```

Calcite saturation is:

```text
SI_calcite = log10(a_Ca2+ * a_CO3^2-) - log10(K_calcite)
```

## Reference result

For PHREEQC Example 3, part A—25 °C, log PCO₂ = -2, calcite equilibrium—PHREEQC reports pH 7.306, ionic strength `4.954e-3 mol/kgw`, and calcite/CO₂ saturation indices 0.00/-2.00. FlahaX compares its internal kernel to the checked-in fixture within `1e-4` absolute tolerance. The official PHREEQC input and output are published in the [PHREEQC example repository](https://github.com/phreeqc-dev/phreeqc3/blob/master/examples/ex3), and the solver's activity/speciation framework is documented by the [USGS](https://doi.org/10.3133/tm6A43).

## API

```python
from flahax import solve_calcite_co2_equilibrium

result = solve_calcite_co2_equilibrium(log_pco2=-2.0)
print(result.ph, result.si_calcite)
```

The next kernels must add sulfate, phosphate, magnesium, potassium, nitrate/ammonium, dissolved-product complexes, target-pH reagent mole balance, and named solid phases. Each extension needs a matching checked-in PHREEQC fixture before it becomes part of a production planning decision.
