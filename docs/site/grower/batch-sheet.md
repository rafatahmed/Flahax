# Read the batch sheet

The batch sheet (`batch-sheet.html`) is what you print and take to the tanks. The full screen
shows the same on its **Tanks** view.

```{mermaid}
---
caption: Two concentrate tanks and the acid container, each on its own injector
---
flowchart LR
    A[Tank A<br/>calcium nitrate,<br/>micronutrients<br/>never acid] -->|1 : ratio| I[Irrigation water]
    B[Tank B<br/>sulfates and phosphates,<br/>magnesium sulfate] -->|1 : ratio| I
    C[Acid container<br/>acid added to water] -->|own injector| I
    I --> D[Drippers]
```

## What each card tells you

- **Tank A and tank B.** How many litres to prepare in your tank, then each product with the grams
  to weigh and a box to tick. If one container limits the batch, the card says which ("your 100 L
  acid container sets the batch").
- **Tank A never takes acid.** Calcium stays apart from sulfates and phosphates, and the
  micronutrients stay with calcium, so tank A must never be acidified.
- **Acid container.** How many millilitres of your acid to add to water, and the volume to make it
  up to. **Add acid to water, never water to acid.**
- **Check after mixing.** The pH to expect and, when it can be estimated, the EC. Write your
  measured values on the sheet.

## If the sheet says "review notes" or "do not mix"

- **Review notes before mixing.** Read each note on the sheet (or the **Notes** view). Most are
  for your agronomist to judge; mix only when every note is understood.
- **Do not mix.** The plan is blocked, and the first note says why: for example a limit is broken,
  a stock would not dissolve, or no acid was offered for a feed that needs one. Fix the reason, or
  call your agronomist.

**Next:** [Mix safely](mix-safely.md). For the full nutrient table, see
[Reading the results](../agronomist/reading-results.md).
