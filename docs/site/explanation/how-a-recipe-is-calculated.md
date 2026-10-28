# How a recipe is calculated

FlahaX goes from a crop formula and a water analysis to a recipe, a pH plan and condition-qualified concentrate
assignments in four stages. Each stage records what it decided and why, and a plan that needs a person's
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
than 1 % is reported with its reason, for example no product supplies it, or a relaxed search still misses targets. A target-only charge imbalance cannot
prove a conflict: untargeted counterions may supply the missing charge. Ions you did not target are kept within
the maximum constraints supplied to the solver. When `N_NH4` is omitted,
incidental NH4-N uses the disclosed Dutch default
(`min(10% of total target N, 1.5 mmol/L)`); pass `max_ammonium_fraction=None`
to opt out.

Supported formula counterions enter the fit before dose selection. The
[material inventory](../models/material-inventory.md) records the same analytical
components used by chemistry, including ligands that are not nutrient targets.

## 2. Plan the pH reagent with the recipe

Explicit joint mode solves fertilizer and reagent quantities together under declared nutrient,
charge, mass and solvent constraints. Its controls, residuals and numerical status remain
visible; failed search does not prove impossibility. Legacy calls retain sequential fitting
when an offered reagent matches the initial direction. Bounded zero-reagent recovery can
search alternative fertilizer allocations in its documented domain. See the
[joint problem contract](../developer/joint-problem.md) for exact mode inputs and limits.

## 3. Assess phase risk

Saturation indices describe thermodynamic driving force, not precipitation speed. Decisions
use condition-qualified phase evidence: missing or unsupported evidence stays explicit.
A phase name alone is not a universal exemption or a prediction of field behavior.
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
