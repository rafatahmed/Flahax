# Conservative Stock Planning (P2)

`plan_stocks` converts a feasible final-solution recipe into a compatible concentrated-stock plan. It is conservative by design: it uses only supplied, versioned compatibility and solubility records. It does not infer product compatibility from names, formulas, or nutrient assays.

## API

```python
from flahax import (
    InjectionRatio, StockTank, TemperatureCelsius, VolumeLitres, plan_stocks,
)

plan = plan_stocks(
    recipe,
    InjectionRatio(100),
    [StockTank("A", VolumeLitres(20)), StockTank("B", VolumeLitres(20))],
    compatibility_rules,
    solubility_limits,
    TemperatureCelsius(20),
)
```

`recipe` must be a feasible `FinalSolutionRecipe`. A plan is not a hardware command and does not mix or dose any material.

## Equations

For final salt dose `d` in g/L, injection ratio `R` in final L per stock L, and final batch volume `V_f`:

```text
C_stock = d * R                 [g/L stock]
V_stock = V_f / R               [L stock]
```

Each used tank must have capacity at least `V_stock`. The planner performs all comparisons before display rounding.

## Required evidence

Every salt in the recipe needs a sourced solubility-limit record that covers the requested temperature:

```text
productId
maxGramsPerLitre
temperatureMinC
temperatureMaxC
source, revision, recordedAt
```

Every incompatibility must be an explicit `separate` compatibility-rule record. For a multi-product rule, no two listed products may share a concentrated tank. This is deliberately stricter than assuming a rule applies only to one named pair.

The planner rejects:

- an infeasible nutrient recipe;
- a missing or temperature-out-of-range solubility limit;
- a required concentration above its limit;
- a tank smaller than required stock volume; and
- an assignment that violates all available separation constraints.

## Deterministic assignment

The planner evaluates valid tank assignments in tank-ID order and chooses one that uses the fewest tanks. It returns the first deterministic assignment at that minimum. This is an explainable constraint solution, not a chemical equilibrium calculation.

## Mathematical verification is the completion criterion

The current planner is a conservative constraint solver. It is not yet a full aqueous-equilibrium model. P2's scientific completion criterion is regression against an authoritative speciation/saturation calculation, using a named thermodynamic database, activity model, temperature, complete ionic composition, and named solid phases.

For each phase `p`, the reference calculation is:

```text
SI_p = log10(IAP_p / K_p)
IAP_p = product_i(a_i ^ nu_i)
a_i = gamma_i * c_i
```

`SI_p > 0` means supersaturation under the selected model. The reference output must retain `SI`, `log IAP`, `log K`, ionic strength, activities, and database identity. PHREEQC reports these quantities and supports activity models including ion-association, Pitzer, and SIT; FlahaX will use it as the independent numerical reference, not as an unexamined black box. [PHREEQC Version 3](https://doi.org/10.3133/tm6A43) documents this model and its inputs.

The existing separation rules remain useful as a conservative fallback when a complete equilibrium input is unavailable. They must not be represented as the proof of chemical compatibility.

## Optional deployment validation record

Physical evidence can later validate a particular product lot, water source, storage vessel, and mixing process. It is not required to establish the mathematical model or verify FlahaX against the cited reference solver. If such evidence is wanted for deployment, record:

| Field | Required evidence |
|---|---|
| Product | Product ID, lot, assay/certificate, hydration state |
| Water | Water-analysis ID, temperature, source |
| Stock | Planned concentration, prepared mass, final stock volume, mixing order |
| Conditions | Minimum/maximum storage temperature and hold duration |
| Observation | Clarity, sediment, crystallization, heat, colour change, photograph if available |
| Result | Pass/fail, reviewer, timestamp, and source record revision |

A passing reference regression proves agreement with the selected mathematical model. A physical test, if performed, is evidence about a particular real-world deployment—not a substitute for the mathematical model.
