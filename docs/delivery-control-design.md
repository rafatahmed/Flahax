# Stock Tanks, pH, and Dosing Control: Technical Design Frame

## Purpose and boundary

FlahaX currently solves a **final working-solution** problem: it chooses non-negative salt masses that make the delivered nutrient concentrations as close as possible to the crop targets. Its output is grams of each salt per litre of water reaching the plant.

This note defines a future, separate delivery layer that can transform an accepted FlahaX recipe into:

1. compatible concentrated stock-tank recipes;
2. an acid or base dose based on water buffering; and
3. calibrated pump volumes and run times.

It is a design specification, not an implementation. The existing nutrient solver remains the source of truth for the final ion balance. The delivery layer must not silently alter a feasible recipe.

## System model

```text
water analysis + crop targets + available products
                     |
                     v
          FlahaX nutrient-balance solver
                     |
                     v
stock compatibility -> pH/alkalinity dose -> pump commands
                     |                         |
                     +------ measured EC, pH, flow, level ------+
```

Each stage has a distinct physical meaning. Nutrient balance is an elemental mass-balance calculation. Tank assignment is a solubility and compatibility problem. pH is an aqueous acid-base equilibrium problem. Hardware control is a measurement-and-actuation problem. Treating any one of these as a proxy for another is unsafe: for example, EC cannot prove that individual nutrient concentrations are correct.

## Scientific model hierarchy

The delivery layer should advance in validated stages. It must not claim a more detailed physical prediction than its inputs support.

| Stage | Model | Permitted decision | Must not claim |
|---|---|---|---|
| 1 | Elemental mass balance plus conservative compatibility rules | A/B/acid channel assignment and calculated dose | Exact pH, solubility, or individual-ion confirmation from EC |
| 2 | Product-specific solubility limits, titration curves, and field pump calibrations | Approved operating envelope | General validity outside the measured temperature, product, and water range |
| 3 | Activity/speciation and saturation-index calculation | Additional precipitation-risk screening | Guaranteed absence of precipitate without bench validation |
| 4 | Dynamic reservoir mass balance plus ion measurements | Supervised correction of recirculating systems | Autonomous nutrient-specific control from pH and EC alone |

This hierarchy follows the central finding in closed-hydroponic modelling: pH and EC are commonly controlled, but they do not themselves control or identify the elementary ion composition. Le Bot *et al.* therefore modelled nutrient composition dynamically from crop and climate variables rather than treating EC/pH as a complete chemical measurement [Dynamic Simulation of Nutrient Solution Composition in a Closed Hydroponics System](https://doi.org/10.1016/S1474-6670(17)36068-8).

### Traceability standard

Every computed plan should be reproducible from an immutable input record: FlahaX version; salt and reagent assays; water-analysis result and date; units; target recipe; temperature; compatibility/solubility dataset version; calibration record; and the exact model settings. A changed assay, water profile, calibration, or temperature range invalidates the previous approval. This is as important as the equations: it makes a delivered dose auditable.

## 1. Working-solution basis

For nutrient ion `i`, final concentration is

```text
C_final,i = C_water,i + sum_j(m_j * p_j,i * 10)
```

where:

- `C_final,i` and `C_water,i` are ppm (mg/L);
- `m_j` is the FlahaX result for salt `j`, in g/L of final solution;
- `p_j,i` is the stored elemental assay as a percentage; and
- `10` converts 1 g/L at 1% into 10 mg/L.

For a batch of `V_f` litres, the salt mass required is:

```text
M_j = m_j * V_f
```

This equation is valid only after the product assay and water analysis have been accepted. The actual product label, lot, and units must be recorded; an elemental assay and an oxide-labelled fertilizer grade are not interchangeable.

## 2. Stock-tank model

### 2.1 Dilution calculation

Define the injector ratio as `R = V_final / V_stock`: one litre of stock makes `R` litres of final solution. For a single stock channel with a stable volumetric ratio:

```text
C_stock,j = R * m_j                         [g/L stock]
V_stock,required = V_f / R                  [L]
M_j = C_stock,j * V_stock,required           [g]
```

For example, a final dose of `0.500 g/L` at `R = 100` requires a stock concentration of `50.0 g/L`. For multiple channels, calculate each channel from its own calibrated `R_k`; do not assume all injectors have equal ratios.

The calculation must use an actual delivered ratio, not a nominal label ratio. If a pump dispenses volume `V_s` during a measured water volume `V_w`, its field ratio is `R = V_w / V_s`.

### 2.2 Compatibility is a hard constraint

At stock concentration, ions can precipitate even though they would remain soluble after dilution. A first-pass compatibility graph must prohibit a tank assignment when two products create a known incompatible pair. At minimum, calcium-bearing products must be segregated from concentrated phosphate and sulfate products.

The reason is chemical equilibrium. A precipitation risk exists when an ion activity product exceeds a solid's solubility product:

```text
IAP = a_Ca2+ * a_SO4^2-       > K_sp(CaSO4)
IAP = a_Ca2+ * a_HPO4^2-      > K_sp(CaHPO4)
```

Activity is not merely concentration:

```text
a_i = gamma_i * c_i
I = 1/2 * sum_i(c_i * z_i^2)
```

`gamma_i` is the activity coefficient, `c_i` is concentration, `z_i` is ion charge, and `I` is ionic strength. Because concentrated fertilizer stocks have high ionic strength, a simple concentration-only calculation is not reliable enough to certify a stock as soluble. Product-specific solubility data, water temperature, hydration state, mixing order, and an engineering safety margin are required.

For a chemistry-engine stage, express the result as a saturation index:

```text
SI_phase = log10(IAP / K_sp)
```

`SI_phase > 0` means the specified equilibrium model is supersaturated with respect to that phase; it is a risk signal, not a promise that precipitation will occur on the controller's time scale. A proper calculation needs aqueous speciation, activities, temperature-dependent equilibrium constants, gas assumptions, and a stated thermodynamic database. The USGS PHREEQC model is an appropriate independent validation tool because it calculates species activities, saturation indices, mixing, mineral equilibria, and reaction paths; it should be used for offline validation, not silently embedded as an unverified production dependency [PHREEQC Version 3 documentation](https://doi.org/10.3133/tm6A43).

Therefore the first release should use conservative rule-based separation plus maximum sourced concentration tables. The mathematical completion path is activity/speciation calculation with a named thermodynamic database and regression against reference outputs. A physical jar/hold test may later validate a particular product lot or installation; it is not required to define or verify the mathematical model. Calcium-phosphate precipitation has been specifically investigated in hydroponic nutrient solutions, reinforcing the need for an explicit phase model [Formation of Calcium Phosphate Precipitation in Nutrient Solution for Hydroponic Cultivation](https://doi.org/10.1080/00380768.1993.10419799).

### 2.3 Proposed tank-assignment function

Conceptually:

```text
plan_stocks(recipe, injection_channels, compatibility_rules,
            solubility_limits, temperature_c) -> StockPlan
```

It should return each salt's assigned channel, stock concentration, required stock volume, and warnings. It must reject—not automatically work around—an incompatible or over-solubility assignment.

Suggested initial arrangement:

- **A tank:** calcium nitrate and compatible nitrate salts.
- **B tank:** phosphates, sulfates, magnesium salts, potassium salts, and micronutrients when product compatibility permits.
- **Acid/base channel:** separate from A/B stock unless the specific product and system design have been validated for combined use.

## 3. pH and alkalinity model

### 3.1 Measure alkalinity, not only pH

pH is `-log10(a_H+)`: it describes the instantaneous hydrogen-ion activity. It does not tell the controller how much acid is needed. Alkalinity measures acid-neutralizing capacity, usually from bicarbonate/carbonate species, and is the required control input.

When reported as mg/L as calcium carbonate:

```text
Alk_meq/L = Alk_mg/L_as_CaCO3 / 50.043
```

The factor is the equivalent weight of CaCO3, approximately 50.043 mg per milliequivalent. A target residual alkalinity must be selected for the crop, substrate, and irrigation strategy; it is not universally zero.

### 3.2 Acid-dose equation

The robust approach is a titration curve of the actual source water at its operating temperature. Let `D_H+(pH_target)` be the measured acid demand in meq/L to reach the selected endpoint. For final volume `V_f`:

```text
n_H+ = V_f * D_H+(pH_target)                 [meq]
V_acid = n_H+ / N_acid                       [L]
```

where `N_acid` is the delivered normality (meq/L) of the acid product after any dilution. Use product density and assay to establish `N_acid`; do not infer it from a trade name. A measured titration curve is an optional site-calibration path. The mathematical path instead solves carbonate speciation, dissolved CO2/gas boundary, alkalinity, activities, and electroneutrality from the complete solution definition.

The same form applies to a base channel using `n_OH-` and base normality.

### 3.3 Acid/base nutrients must return to the nutrient balance

Acid or base products can add nutrients. The delivery layer must convert that addition back to ppm and re-run, or at least re-score, the nutrient balance:

```text
Delta_C_i = M_reagent * p_reagent,i * 1000 / V_f     [mg/L = ppm]
C_final,i,new = C_final,i + Delta_C_i
```

For a product mass `M_reagent` in grams and elemental mass fraction `p_reagent,i` (for example, `0.138` rather than `13.8`), this equation adds nitrate from nitric acid, phosphorus from phosphoric acid, sulfur from sulfuric acid, potassium from potassium hydroxide, and so on. These products must never be treated as pH-only reagents.

### 3.4 Proposed pH-planning function

```text
plan_ph(water_analysis, reagent, target_ph, target_residual_alkalinity,
        titration_curve, final_volume_l) -> PhPlan
```

The plan should provide the initial calculated dose, the elemental additions, valid operating range, and a mandatory post-mix measurement request. Automatic closed-loop correction should be bounded by maximum dose per event, minimum mix time, sensor freshness, and an operator alarm threshold.

For many hydroponic systems, nutrient-solution pH is commonly managed around 5.0–6.0, but this is a starting range, not a universal setpoint; the crop and root-zone system own the target. Oklahoma State notes both the importance of pH/EC monitoring and the common 5.0–6.0 range for hydroponics [Hydroponics](https://extension.okstate.edu/fact-sheets/hydroponics) and [EC and pH guide](https://extension.okstate.edu/fact-sheets/electrical-conductivity-and-ph-guide-for-hydroponics).

## 4. Dosing-hardware model

### 4.1 Command calculation

For channel `k`, a calibrated volumetric pump rate is `q_k` in L/min. Given a required stock volume `V_k`:

```text
t_k = V_k / q_k                              [min]
```

When dosing proportional to measured irrigation flow `Q_w`, with an actual injection ratio `R_k`:

```text
Q_stock,k = Q_w / R_k
t_k = V_stock,k / q_k
```

The controller should use a pulse total from a water-flow meter or a verified batch volume, rather than only a scheduled runtime. Flow and pump capacity drift with pressure, viscosity, wear, tubing age, supply voltage, and check-valve condition.

### 4.2 Calibration and uncertainty

Calibrate each channel by collecting a timed dose, weighing it when practical, converting mass to volume using measured solution density, and repeating enough times to estimate variation. For `V = q * t`, a first-order independent uncertainty estimate is:

```text
u(V)^2 = t^2 * u(q)^2 + q^2 * u(t)^2
```

If `q` and `t` are correlated, include `2*t*q*cov(q,t)`. The system should persist the calibration date, test temperature, stock density, mean rate, standard deviation, and permitted deviation. Commands exceeding calibrated operating bounds must fail closed.

### 4.3 Sensor roles and safety interlocks

- **Water flow / totalizer:** establishes dilution volume and detects no-flow conditions.
- **Pump pulse or flow confirmation:** verifies commanded delivery; a runtime command alone is not confirmation.
- **Tank level:** prevents dry-run and detects implausible consumption.
- **pH sensor:** verifies acid/base outcome after adequate mixing; requires calibration, temperature compensation, drift checks, and cleaning.
- **EC sensor:** detects broad salinity changes only. It cannot validate individual ions or replace laboratory analysis.

Every automatic command needs maximum dose limits, minimum mix time, stale-sensor rejection, manual stop, audit logging, and an alarm state. A failed sensor, absent irrigation flow, implausible level change, or out-of-bound pH/EC must prevent further automatic dosing until acknowledged and investigated.

Conceptually:

```text
issue_dose(plan, calibration, telemetry) -> DoseCommand | SafetyInterlock
verify_delivery(command, telemetry_after_mix) -> VerificationResult
```

## 5. Reservoir mass balance (recirculating systems)

For a recirculating reservoir, a static recipe is insufficient. Nutrient inventory changes with uptake, top-up water, dosing, bleed, and sampling. For ion `i` over a control interval:

```text
M_i,k+1 = M_i,k + M_i,dosed + C_i,makeup*V_makeup
          - M_i,uptake - C_i,bleed*V_bleed - M_i,other_loss
C_i,k = M_i,k / V_k
```

Plant uptake and unmeasured losses are not directly observable from EC and pH. They must be estimated from laboratory ion analysis, validated crop models, or conservative operating rules. Consequently, the initial version should support batch or proportional injection before attempting autonomous nutrient-specific control in recirculating systems.

## 6. Data contracts and acceptance criteria

Required inputs:

- current water-analysis record: ions, pH, alkalinity, EC, temperature, sampling date, source, and revision;
- fertilizer and acid/base product assay, density where relevant, lot, and units;
- target final volume or measured irrigation water volume;
- injector/pump calibration and stock-tank capacity;
- compatibility and solubility limits with their temperature range and source;
- crop, growth stage, root-zone system, and approved pH/residual-alkalinity bounds.

Before a plan can be accepted, it must meet all of the following:

1. The underlying FlahaX recipe is feasible, or an explicit operator accepts the listed nutrient misses.
2. No proposed tank contains a forbidden compatibility pair.
3. Each stock concentration is below its validated temperature-dependent limit with a documented safety margin.
4. Acid/base nutrient additions are included in the final balance and the result remains within configured tolerance.
5. Requested volumes and runtimes lie within current pump calibrations and tank capacities.
6. Mathematical acceptance requires regression against named reference-solver fixtures, including activities and saturation indices. Deployment measurements are optional installation evidence and do not replace the mathematical regression.

## 6.1 Package-quality requirements

A scientifically sound model still needs reliable software boundaries. Before any delivery feature is released, require:

- **Dimensional inputs:** accept and store explicit units; normalize internally to L, g, mg/L, meq/L, °C, and minutes. Reject ambiguous `ppm`, oxide-grade, density, or ratio values.
- **Pure planning functions:** `plan_stocks`, `plan_ph`, and hardware command calculation must be deterministic and side-effect free. Hardware I/O belongs behind a separate adapter.
- **No invented chemistry:** absent alkalinity, reagent normality, density, solubility data, temperature limits, or calibration must produce an explicit incomplete-plan error, never a plausible-looking dose.
- **Constraint-first solver:** stock compatibility, solubility ceilings, tank capacities, calibrated pump bounds, and safety limits are hard constraints; cost or recipe simplicity can be optimization objectives only after those constraints pass.
- **Independent verification:** unit tests cover units, mass conservation, known dilution cases, constraint rejection, and uncertainty propagation. Chemical-model tests compare golden fixtures against a cited, named equilibrium solver and thermodynamic database. Physical measurements, if later collected, are deployment evidence rather than the model-definition gate.
- **Versioned reference data:** product assays, thermodynamic data, compatibility rules, titration curves, and calibration records each carry source, date, temperature range, and revision identifier.

These rules keep the current lightweight package intact: FlahaX can remain dependency-free and deterministic while an optional, separately validated delivery integration performs field-specific chemistry and control.

## 7. Validation sequence

1. Define the complete solution inputs: total ions, temperature, pH/alkalinity, gas boundary, product stoichiometry, and named solid phases.
2. Run the cited reference equilibrium solver with a named activity model and thermodynamic database; retain activities, species, ionic strength, and saturation indices as golden output.
3. Compare FlahaX numerical outputs to those fixtures within declared numerical tolerances.
4. Verify injector ratio and pump-volume arithmetic separately with deterministic calibration fixtures.
5. Run package regression, conservation, constraint, and reference-equivalence tests before release.
6. If deployed later, supervised irrigation or physical tests may validate the installation; they do not establish the governing mathematical model.

## References

### Core scientific and modelling references

- Sonneveld, C. and Voogt, W. (2009). *Plant Nutrition of Greenhouse Crops*. Springer. DOI: [10.1007/978-90-481-2532-6](https://doi.org/10.1007/978-90-481-2532-6). This is the principal greenhouse-crop nutrient-management reference for recipe design, water quality, substrate systems, and analytical interpretation. Bibliographic record: [Wageningen University & Research](https://research.wur.nl/en/publications/plant-nutrition-of-greenhouse-crops/).
- Le Bot, J., Adamowicz, S. and Robin, P. (1998). “Dynamic Simulation of Nutrient Solution Composition in a Closed Hydroponics System.” *IFAC Proceedings Volumes*, 31(12), 219–224. DOI: [10.1016/S1474-6670(17)36068-8](https://doi.org/10.1016/S1474-6670(17)36068-8). Foundation for treating recirculating nutrient composition as a dynamic mass-balance problem rather than an EC/pH-only problem.
- Parkhurst, D. L. and Appelo, C. A. J. (2013). *Description of Input and Examples for PHREEQC Version 3*. U.S. Geological Survey Techniques and Methods 6-A43. DOI: [10.3133/tm6A43](https://doi.org/10.3133/tm6A43). Reference for activity-based aqueous speciation, saturation indices, mixing, and equilibrium validation.
- “The Formation of Calcium Phosphate Precipitation in Nutrient Solution for Hydroponic Cultivation” (1993). DOI: [10.1080/00380768.1993.10419799](https://doi.org/10.1080/00380768.1993.10419799). Direct evidence for treating calcium/phosphate compatibility as a hard design concern.

- Oklahoma State University Extension, [Electrical Conductivity and pH Guide for Hydroponics](https://extension.okstate.edu/fact-sheets/electrical-conductivity-and-ph-guide-for-hydroponics). Describes water analysis, EC, pH, and nutrient-solution management.
- Oklahoma State University Extension, [Hydroponics](https://extension.okstate.edu/fact-sheets/hydroponics). Discusses hydroponic pH/EC management and the need to check adjustments.
- Penn State Extension, [Interpreting Irrigation Water Tests](https://extension.psu.edu/interpreting-irrigation-water-tests). Explains alkalinity, its reporting as CaCO3, and why pH must be interpreted with alkalinity.
- University of Minnesota Extension, [Should you acidify your high tunnel irrigation water?](https://blog-fruit-vegetable-ipm.extension.umn.edu/2022/04/should-you-acidify-your-high-tunnel.html). Covers acid injection, injector ratios, and nutrient additions from nitric, phosphoric, and sulfuric acids.
- Penn State Extension, [Irrigation Water Quality Guidelines for Turfgrass Sites](https://extension.psu.edu/irrigation-water-quality-guidelines-for-turfgrass-sites). Gives the equivalent-based residual sodium carbonate equation and illustrates use of meq/L in irrigation-water chemistry.

These references establish operational principles. Product-specific compatibility, solubility, and dosing limits must be sourced from the actual manufacturer documentation and verified under the intended operating conditions before automation is enabled.
