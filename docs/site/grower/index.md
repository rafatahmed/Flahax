# Grower guide

This guide is for the person who prepares the batch. The standard `flahax mix`
interview asks five questions about tanks, water, crop targets and available
products. When your agronomist supplies a Sonneveld profile, use the
[profile review walkthrough](sonneveld-walkthrough.md) instead: review the feed
design, adopt the verified rounded preparation and save its evidence.

```{mermaid}
---
caption: The five steps of flahax mix
---
flowchart LR
    S1[1. Tanks<br/>sizes, ratio,<br/>temperature] --> S2[2. Water<br/>RO or your<br/>lab report]
    S2 --> S3[3. Crop<br/>formula]
    S3 --> S4[4. Fertilizers<br/>and acids<br/>you have]
    S4 --> S5[5. Target pH]
    S5 --> R[Results:<br/>tanks, nutrients,<br/>notes]
    R --> B[Batch sheet<br/>to print]
```

FlahaX saves your answers, so the next batch is one command: `flahax mix sessions/NAME`.

## In this guide

| Page | What it covers |
|---|---|
| [What you need](inputs.md) | The water report, formula, acid certificate and limits to have ready |
| [Review a Sonneveld batch](sonneveld-walkthrough.md) | Import a prepared profile, approve the preview, review rounded quantities and repeat the saved batch |
| [Run a batch](run-a-batch.md) | The five steps, the full screen and `--plain`, repeating a saved batch |
| [Read the batch sheet](batch-sheet.md) | Tank A, tank B and the acid container: what to weigh and in what order |
| [Mix safely](mix-safely.md) | What to measure after mixing, and when to call your agronomist |

New to FlahaX? Start with [Install](../start/install.md) and [Your first batch](../start/first-batch.md).
