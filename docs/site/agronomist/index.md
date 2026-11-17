# Agronomist guide

This guide is for the person who designs the feed: who reads the lab report, chooses or builds the
crop formula, defines the products from their labels, sets the target pH and the limits, and
reviews the plan before anyone mixes.

```{mermaid}
---
caption: How a lab analysis is used
---
flowchart TB
    L[Lab report<br/>mg/L, meq/L or mmol/L,<br/>measured pH, detection limits] --> C[Convert units<br/>retain analytical nutrient totals]
    C --> T[Water nutrient credits<br/>finished-feed targets and limits]
    C --> M[Speciate at measured pH<br/>report charge imbalance]
    M --> R[Carry residual charge<br/>preserve the analysed ions]
    R --> P[Mixed-feed pH<br/>saturation assessment<br/>reagent dose]
```

The laboratory nutrient values supply the water credits in the finished-feed calculation.
FlahaX reports charge imbalance and carries it as residual charge when calculating chemistry.
It preserves the analysed ions, and the size of the imbalance alone does not reject the water.
Titrated alkalinity can supply the inorganic-carbon inventory through its supported proton
reference. The report retains the analytical inputs and the resulting chemistry evidence.
Review missing measurements and any model-domain qualifications before interpreting pH.

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
