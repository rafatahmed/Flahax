# How a recipe is calculated

FlahaX goes from a crop formula and a water analysis to a recipe, a pH plan and two concentrate
tanks in four stages. Each stage records what it decided and why, and a plan that needs a person's
judgement says so instead of guessing.

```{mermaid}
---
caption: The recipe and its pH reagent are planned together
---
flowchart TB
    T[Crop formula targets, mg/L] --> G[Subtract what the water<br/>already supplies]
    W[Water analysis] --> G
    G --> F[Fit: grams per litre of each<br/>available product, never negative]
    F --> P[Equilibrium model:<br/>pH of the mixed recipe]
    P --> D[Acid or base dose<br/>to the target pH]
    D --> N[Count the reagent's own nutrients,<br/>for example nitrate from nitric acid]
    N --> F
    D --> S[Saturation indices:<br/>does anything precipitate?]
    S --> K[Concentrate tanks:<br/>compatibility and solubility]
    K --> R[Batch sheet, report<br/>and summary]
```

## 1. Fit the recipe

The water's own nutrients are subtracted from the targets, and FlahaX chooses the grams per litre
of each available product so that the final solution comes as close to every target as the
products allow, with no negative amounts (non-negative least squares). A target missed by more
than 1 % is reported with its reason, for example no product supplies it, or the targets conflict
because the formula itself is not electrically balanced. Ions you did not target are kept within
the maximum constraints supplied to the solver. An ammonium allowance is added only
when explicitly requested; omitting a maximum does not select a crop-practice limit.

## 2. Plan the pH reagent with the recipe

The recipe is first fitted without acids as nutrient sources. The equilibrium model then
calculates the pH of the mixed recipe at 25 °C, and FlahaX solves the dose of each offered acid (or
of a packaged base) that reaches the target pH. A reagent brings nutrients too, such as the
nitrate in nitric acid, so the recipe is refitted counting that supply, and the dose is solved
again. Every candidate reagent is evaluated and the plan names the one selected.

## 3. Check what precipitates

At the target state FlahaX computes saturation indices for the solid phases its model knows. A
phase that forms at feed conditions blocks the plan; a phase whose positive index does not mean it
forms in a feed (for example hydroxylapatite or goethite) asks for review, with the reason and
sources.

## 4. Split into concentrate tanks

Products are grouped into tank A and tank B by compatibility rules: calcium apart from sulfates
and phosphates, micronutrients with calcium in tank A, magnesium sulfate with the phosphates in
tank B, and acid in its own container, never in tank A. The strength of each stock is checked
against sourced solubility at the stock temperature, and the volumes come from your tank sizes and
injection ratio.

## Where to read more

- [Method](../models/method.md): the ppm equation, the solver and a worked example.
- [Fertilizer equilibrium model](../models/fertilizer-equilibrium-model.md) and its
  [coverage](../models/chemistry-coverage-matrix.md).
- [pH, acids and bases](../agronomist/ph-and-acids.md) and
  [Tanks and solubility](../agronomist/tanks-and-solubility.md).
- [Why FlahaX needs your water's pH](water-and-ph.md).
