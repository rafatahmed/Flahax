# Agronomist guide

This guide is for the person who designs the feed: who reads the lab report, chooses or builds the
crop formula, defines the products from their labels, sets the target pH and the limits, and
reviews the plan before anyone mixes.

```{mermaid}
---
caption: How a lab analysis is used
---
flowchart TB
    L[Lab report<br/>as printed: mg/L, meq/L or mmol/L,<br/>measured pH, detection limits] --> C[Converted to elements<br/>and checked at the measured pH]
    C -->|more than 5 % out of balance| X[Refused:<br/>ask the laboratory]
    C -->|balanced, or a small gap| D{Two uses}
    D --> T[Laboratory values<br/>nutrient targets and limits]
    D --> M[Balanced water<br/>chemistry only: pH, saturation,<br/>acid dose]
```

The laboratory values are what every target and limit is checked against. The small gap every
lab report has is closed for the chemistry only, on chloride or, when no chloride is measured, on
the alkalinity. The report shows both side by side.

## In this guide

| Page | What it covers |
|---|---|
| [A batch from files](batch-command.md) | The water analysis file, the formula, `flahax batch`, reading the sheet, and a worked tomato example on a brackish well |
| [Formulas and products](formula-and-products.md) | Catalogue products, supplier labels and data sheets, and materials defined by formula, ions or analysis |
| [pH, acids and bases](ph-and-acids.md) | How the recipe and its pH reagent are planned together |
| [Tanks and solubility](tanks-and-solubility.md) | Which products share a concentrate tank, and the solubility check |
| [Reading the results](reading-results.md) | The batch sheet, the report and the nutrient table |

For the interactive way, see the [grower guide](../grower/index.md): `flahax mix` asks the same
questions and saves the answers. For why FlahaX calculates pH, see
[Why FlahaX needs your water's pH](../explanation/water-and-ph.md).
