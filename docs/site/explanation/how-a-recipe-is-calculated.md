# How a recipe is calculated

FlahaX uses crop-feed targets, a water analysis and available products to calculate candidate
recipes and their pH-reagent requirements. A grower or agronomist reviews the selected recipe
and its preparation checks. The targets can be supplied directly or derived through
[Sonneveld target design and approved root-zone feedback](../agronomist/batch-command.md).

```{mermaid}
---
caption: The recipe and its pH reagent are planned together
---
flowchart TB
    T[Finished-feed targets, mg/L] --> G[Subtract what the water<br/>already supplies]
    W[Water analysis] --> G
    G --> F[Fit: grams per litre of each<br/>available product, never negative]
    F --> P[Equilibrium model:<br/>pH of the mixed recipe]
    P --> D[Acid or base dose<br/>to the target pH]
    D --> N[Count the reagent's own nutrients,<br/>for example nitrate from nitric acid]
    N --> F
    D --> S[Saturation indices<br/>assess phase risk]
    S --> K[Concentrate tanks:<br/>compatibility and solubility]
    K --> R[Batch sheet, report<br/>and summary]
    D --> V[Optional rounded preparation<br/>dry, stock and reagent doses<br/>declared uncertainty and limits]
    V --> R
```

## 1. Fit the recipe

The water's own nutrients are subtracted from the targets, and FlahaX chooses the grams per litre
of each available product so that the final solution comes as close to every target as the
products allow, with nonnegative amounts. Numerical target acceptance uses a relative tolerance
of 1e-5 for a positive nutrient target and 1e-6 mg/L for a declared zero. A larger deviation
is reported with its reason and achieved concentration. A target-only charge imbalance cannot
prove a conflict because untargeted counterions may supply the remaining charge. The fit
applies the declared maximum concentrations.

For absent or zero ammonium targets, the default incidental NH4-N allowance is the smaller
of 10% of total target nitrogen and 1.5 mmol/L ammonium. It is reported as `ammoniumLimit`.
An explicit NH4-N maximum takes precedence. The Python interface can change the fraction
or disable this allowance. A positive NH4-N target is fitted as its own nitrogen-form target.

Supported formula counterions enter the fit before dose selection. The
[material inventory](../models/material-inventory.md) records the same analytical
components used by chemistry, including ligands that are not nutrient targets.

When requested, bounded searches evaluate additional declared products and alternative starts.
The report retains attempted candidates, failures, budgets and residuals so the grower can
review an alternative. Exhausting the search budget leaves the search incomplete.

### Numerical acceptance and preparation tolerance

The numerical pH acceptance tolerance is 1e-4 pH units. These solver acceptance values describe
numerical agreement with the requested targets. The rounded preparation workflow separately
uses the nutrient and pH tolerances supplied in its configuration.

For example, the worked Appendix I preparation uses ±0.1% for nutrient bounds and ±0.002 pH
units. It checks the actual rounded dry weights, separate stock volumes and reagent dose
under the declared uncertainty. The 5% reserve reduces each declared nutrient ceiling in
that preparation check. Crop suitability remains a grower or agronomist decision.

## 2. Plan the pH reagent with the recipe

Explicit joint mode solves fertilizer and reagent quantities together under declared nutrient,
charge, mass and solvent constraints. Its controls, residuals and numerical status remain
visible; failed search does not prove impossibility. Legacy calls retain sequential fitting
when an offered reagent matches the initial direction. Bounded zero-reagent recovery can
search alternative fertilizer allocations in its documented domain. See the
[joint problem contract](../developer/joint-problem.md) for exact mode inputs and limits.

## 3. Assess phase risk

Saturation indices describe thermodynamic driving force, not precipitation speed. A phase
that forms readily (brushite, gypsum, calcite) above saturation marks the recipe with a
precipitation risk; every other supersaturated phase is information with the basis of its
constant. Nothing is refused for it, and none of it predicts field behavior.
See [water-to-delivery](../developer/water-to-delivery.md#saturation-indices-and-acceptance).

## 4. Assign concentrate tanks

Assignments follow explicit separation constraints, qualified solubility records and the
supplied equipment. A layout can require more than two tanks. Missing stock-mixture evidence
leaves review or a draft; the planner does not waive separation to fit the equipment.
See [stock assignments](../agronomist/stock-assignments.md) for conditions and downstream gates.

## Where to read more

- [Method](../models/method.md): the ppm equation, the solver and a worked example.
- [Fertilizer equilibrium model](../models/fertilizer-equilibrium-model.md) and its
  [coverage](../models/chemistry-coverage-matrix.md).
- [pH, acids and bases](../agronomist/ph-and-acids.md) and
  [Tanks and solubility](../agronomist/tanks-and-solubility.md).
- [Why FlahaX needs your water's pH](water-and-ph.md).
