# Historical pH planning requirements

Archived from the measured-curve guide during documentation reorganization.
The following text is a historical design requirement, not the current API
status or evidence that every proposed boundary is implemented. The current
[water-to-delivery guide](../site/guide/water-to-delivery.md) describes the
implemented equilibrium workflow and its limits. Original wording follows.

## Required mathematical model

The final P3 model must solve aqueous equilibrium directly from the complete solution definition; it must not require a new titration experiment to discover the governing chemistry. Its unknowns include aqueous species activities and reagent amount. Its equations are:

```text
mass action:        K_r = product_i(a_i ^ nu_i)
activity:           a_i = gamma_i * m_i
electroneutrality:  sum_i(z_i * m_i) = 0
alkalinity:         Alk = sum_i(alpha_i * m_i)
target condition:   -log10(a_H+) = pH_target
phase constraint:   SI_p = log10(IAP_p / K_p) <= configured limit
```

The model needs the water and fertilizer totals, temperature, allowed reagent stoichiometry, activity model, thermodynamic database, and a gas boundary: either closed total inorganic carbon or a specified CO2 partial pressure. Without the gas boundary, pH/alkalinity data alone do not uniquely define carbonate speciation, so an exact mathematical solution would be falsely precise.

FlahaX will verify its solver against PHREEQC golden fixtures that contain all those inputs and expected activities, species distribution, saturation indices, and reagent amount. The USGS documentation describes PHREEQC's activity-based speciation and saturation-index calculations, including the distinction between total concentrations and aqueous species activities [PHREEQC Version 3](https://doi.org/10.3133/tm6A43). No new physical laboratory experiment is required to define or regression-test this model.

P3 does not establish a universal hydroponic pH target. Crop, root-zone system, substrate, and operating procedure own the selected setpoint.
