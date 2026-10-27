# Read the batch sheet

The batch sheet (`batch-sheet.html`) is a printable record of the calculated plan. The full screen
shows the same on its **Tanks** view.

```{mermaid}
---
caption: Illustrative tank layout; actual assignments depend on qualified conditions
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

## Calculation status

- **Calculation complete.** The calculation checks passed. This does not establish physical
  validation, supplier compatibility or measured performance.
- **Review required.** Unresolved qualifications remain; read the notes with your agronomist.
- **Do not mix.** The plan is blocked. Quantities are diagnostic only: the sheet suppresses
  preparation instructions, reagent preparation and completion boxes. Resolve the recorded
  reason and calculate a new result.

Every depth retains **Scientific qualifications**: separate result statuses, EC applicability,
uncovered species, uncertainty status and model/source identifiers. A known-species EC subtotal
is not a total estimate, bound or midpoint. No uncertainty interval is invented.

The expandable **Full calculation evidence** contains the exact summary as inert, escaped JSON,
including calculation and export identities. It works offline without scripts or network access.
Human-readable amounts may be rounded; retained digits are computational precision, not a claim
of measurement accuracy. A positive small dose is never displayed as zero in a dosing quantity.

**Next:** [Mix safely](mix-safely.md). For the full nutrient table, see
[Reading the results](../agronomist/reading-results.md).
