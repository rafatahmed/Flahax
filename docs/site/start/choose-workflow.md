# Choose a workflow

Start with the inputs and task you have. Growers usually review and prepare;
agronomists choose the crop targets, water and product records; developers
integrate or reproduce the calculation. Any of these readers can use more than
one route.

```{mermaid}
---
caption: Choose the entry point that matches your inputs
---
flowchart TB
    accTitle: Choose a FlahaX entry point
    accDescr: Interactive inputs lead to the standard mix wizard, a prepared Sonneveld profile leads to review and approval, separate target and water files lead to the batch command, and Python inputs lead to the fertilizer workflow. Linked instructions follow in the table.
    START[What do you have?] --> W[Water, crop targets and products<br/>to enter interactively]
    START --> S[A prepared Sonneveld profile<br/>to review and approve]
    START --> B[Target and water files<br/>for a repeatable command]
    START --> P[Python inputs<br/>for integration or research]
    W --> MIX[Standard wizard<br/>flahax mix]
    S --> REVIEW[Profile review<br/>flahax mix --sonneveld-batch]
    B --> BATCH[Batch command<br/>flahax batch]
    P --> PY[Python workflow<br/>plan_fertilizer_workflow]
```

The diagram's four routes are linked below. This table also supplies the
instructions when diagrams are unavailable or the page is printed.

| Starting point | Linked instructions | What you review next |
|---|---|---|
| Standard wizard: enter answers yourself | [First RO-water batch](first-batch.md), then [run a batch](../grower/run-a-batch.md) with your own inputs | Tank quantities, nutrients and notes; [read the batch sheet](../grower/batch-sheet.md) |
| Prepared Sonneveld profile | [Grower review walkthrough](../grower/sonneveld-walkthrough.md); agronomists start with [Appendix I](../agronomist/sonneveld-appendix-i.md) | Sample/feed approval, selected alternative, rounded quantities and [uncertainty notes](../agronomist/sonneveld-appendix-i.md#interpret-the-checks) |
| Separate target/water/product files | [A batch from files](../agronomist/batch-command.md) and [input formats](../reference/file-formats.md) | Targets, water credits, reagent, achieved nutrients and preparation qualifications |
| Python integration | [First recipe in Python](first-recipe.md), then [water-to-delivery workflow](../developer/water-to-delivery.md) and [API reference](../reference/api.md) | Returned stage statuses, residuals, chemistry and delivery evidence |

## Follow your audience path

- **Grower:** [what you need](../grower/inputs.md) → choose the standard wizard
  or profile review above → review the [standard tank sheet](../grower/batch-sheet.md)
  or [rounded profile quantities](../grower/sonneveld-walkthrough.md#review-the-rounded-preparation) →
  [mixing checks and measurements](../grower/mix-safely.md).
- **Agronomist:** [water and product records](../agronomist/batch-command.md)
  → [Sonneveld target design and verification](../agronomist/sonneveld-appendix-i.md)
  or supplied targets → [interpret the report](../agronomist/reading-results.md)
  → provide a reviewed profile to the grower.
- **Developer:** [Python entry points](../developer/python-api.md) →
  [file and session contracts](../reference/file-formats.md#sonneveld-import-profile)
  → [calculation stages](../explanation/how-a-recipe-is-calculated.md) →
  [verification](../developer/verification.md).

## Reuse or change an existing result

For an unchanged saved session, follow the [replay instructions](../grower/sonneveld-walkthrough.md#save-export-and-repeat)
for its workflow. For a changed Sonneveld sample, design, product or equipment
bound, [update and reimport the profile](../grower/sonneveld-walkthrough.md#when-an-input-changes).
For other saved workflows, use [migration guidance](migration.md). Preserve
the original record and review a newly calculated result.

All routes produce calculation evidence. See [scope and limits](../explanation/scope-and-limits.md)
for where that evidence ends and physical qualification and measurements begin.
