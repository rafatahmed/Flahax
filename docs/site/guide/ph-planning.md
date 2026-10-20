# Titration-Bounded pH Planning (P3)

`plan_ph` currently calculates an initial acid or base dose from a known titration curve. It is a planning function, not a controller: it neither changes pH nor operates pumps. This is an optional calibration path, not the final mathematical pH model.

## Required records

The plan fails unless all of these match by record ID:

1. A water analysis with measured pH, alkalinity as mg/L CaCO3, temperature, and ions.
2. A measured titration curve for that exact water-analysis ID and reagent ID.
3. An acid or base product assay with elemental fractions, density in kg/L, and normality in meq/L.
4. The final batch volume, achieved ion profile, and target ion profile.

Alkalinity establishes that the water buffer has been measured. The titration curve is the dose source because it represents the actual water/reagent system; the function does not substitute a generic pH equation for that experiment.

Alkalinity is normalized for reporting and future residual-alkalinity modelling:

```text
alkalinity [meq/L] = alkalinity [mg/L as CaCO3] / 50.043
```

## Current calibration model

For requested pH inside two measured curve points, linear interpolation gives the acid/base demand:

```text
d(target) = d0 + (pH_target - pH0) / (pH1 - pH0) * (d1 - d0)     [meq/L]
n_reagent = d(target) * V_final                                  [meq]
V_reagent = n_reagent / N_reagent                                [L]
M_reagent = V_reagent * density * 1000                           [g]
```

The target pH must fall inside the measured curve range. Extrapolation is rejected. Curve pH values must be strictly monotonic as reagent demand rises, and their direction must agree with the product type: decreasing pH for acid, increasing pH for base.

The reagent's elemental additions are included in the final nutrient score:

```text
Delta_C_i = M_reagent * f_i * 1000 / V_final                     [mg/L]
```

For example, nitric acid can contribute nitrate nitrogen; phosphoric acid can contribute phosphorus; sulfuric acid can contribute sulfur; and potassium hydroxide can contribute potassium. The plan never labels these as pH-only additions.

## API

```python
from flahax import VolumeLitres, plan_ph

plan = plan_ph(
    water_analysis,
    titration_curve,
    reagent,
    target_ph=6.0,
    final_volume=VolumeLitres(100),
    maximum_reagent_volume=VolumeLitres(1),
    achieved=achieved_ions,
    targets=target_ions,
)
```

The returned `PhPlan` includes dose demand, reagent volume/mass, elemental nutrient contribution, rescored rows, and `post_mix_measurement_required=True`.

`maximum_reagent_volume` is a required hard safety bound. A dose above it is rejected; the caller must investigate the water, curve, reagent record, or intended target rather than silently applying a larger correction.

## Operational boundary

Before an operator uses a plan:

1. Confirm the reagent's product ID, lot, density, and normality against its current certificate or validated record.
2. Confirm that the water analysis and titration record still represent the actual water source and temperature range.
3. Add the calculated initial dose with appropriate chemical handling controls, mix for the defined procedure, and measure pH.
4. Compare the measurement with the target and investigate a material deviation; do not use P3 as an unattended correction loop.
5. Retain the measurement, operator, timestamp, and product/water record IDs with the batch record.

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
