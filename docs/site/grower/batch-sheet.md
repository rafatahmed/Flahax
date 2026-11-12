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
    C[Reagent container<br/>refill as needed] -->|same ratio, separate injector| I
    I --> D[Drippers]
```

## What each card tells you

- **Tank A and tank B.** How many litres to prepare in your tank, then each product with the grams
  to weigh and a box to tick. In fill mode the smaller nutrient tank sets the batch; a larger
  nutrient tank is partly filled. The separate reagent container does not limit A or B.
- **Tank A never takes acid.** Calcium stays apart from sulfates and phosphates, and the
  micronutrients stay with calcium, so tank A must never be acidified.
- **Reagent container.** The total liquid reagent amount, the amount per fill, and the number
  of fills at the same injection ratio as A and B. A final partial fill has its own scaled dose.
  For 100 L A/B tanks and a 10 L reagent tank at 1:100, prepare 100 L in A and B for 10,000 L
  irrigation. Prepare ten 10 L reagent fills (one initial fill and nine refills), each containing
  one-tenth of the total reagent amount. Do not put the total batch amount into the first fill.
  For acid products, **add acid to water, never water to acid.**
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
uncovered species, uncertainty status and model/source identifiers. When some species have no
conductivity value the EC is a range: the low end counts the known species and the high end adds
an upper limit for the rest. No uncertainty interval is invented.

The expandable **Full calculation evidence** contains the exact summary as inert, escaped JSON,
including calculation and export identities. It works offline without scripts or network access.
Human-readable amounts may be rounded; retained digits are computational precision, not a claim
of measurement accuracy. A positive small dose is never displayed as zero in a dosing quantity.

**Next:** [Mix safely](mix-safely.md). For the full nutrient table, see
[Reading the results](../agronomist/reading-results.md).
