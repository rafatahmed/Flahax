# Sonneveld Appendix I: design and verify 1,000 L

This example turns a standard recirculating-tomato feed into a reviewed,
pH-adjusted, rounded batch. It combines Sonneveld A–D target design, illustrative
root-zone feedback, alternative-product search and separate micronutrient-stock
delivery. Sodium nitrate is excluded. The grower follows
[Review a Sonneveld batch](../grower/sonneveld-walkthrough.md); this page explains
what you need to check before handing over the profile.

## On this page

- [Inputs and evidence](#inputs-and-evidence)
- [Design the targets](#design-the-targets)
- [Credit water and solve the acid/fertilizer recipe](#credit-water-and-solve-the-acidfertilizer-recipe)
- [Declared uncertainty](#declared-uncertainty)
- [Rounded recipe and verification](#rounded-recipe-and-verification)
- [Interpret the checks](#interpret-the-checks)
- [Prepare a farm-specific profile](#prepare-a-farm-specific-profile)

## Inputs and evidence

Download the complete {download}`sonneveld-appendix-i.json <../../../examples/sonneveld-appendix-i.json>`.
It is the same input exercised by `tests/test_mix_sonneveld.py`, not an abbreviated
JSON sketch. From a source checkout with FlahaX installed, run:

```bash
flahax mix --plain --sonneveld-batch examples/sonneveld-appendix-i.json --output appendix-i-output
```

The [grower walkthrough](../grower/sonneveld-walkthrough.md#review-and-approve-the-feed)
gives the review answers and adoption step. A downloaded copy can be used from
any folder with the corresponding filename, without importing a test module.

This reconstruction follows [Sonneveld, Voogt and Spaans (1999), Appendix I](https://doi.org/10.17660/ActaHortic.1999.481.38).
Some transcription cells are reconstructed using the paper's equations; the
target-design regressions preserve that provenance. The pH 5.5 case, explicit
fertilizer grades, additional sodium sulfate, stocks and uncertainty settings
are FlahaX worked extensions, not reported measurements from the paper.

| Input | Declared value and basis |
|---|---|
| Batch | 1,000 L final feed; dilute approximation of 1,000 kg solvent |
| Source water | Ca 1.00, Mg 0.40, sulfate 0.30 and bicarbonate 2.20 mmol/L |
| Chemistry | 25 °C, closed retained inorganic carbon, aqueous-only equilibrium, Davies activity model |
| Feed design EC | 1.80 dS/m in the paper's empirical charge-budget rule |
| Formulation pH | 5.50, with acid quantity solved rather than fixed |
| Nitric acid | 65% w/w HNO3, density 1.39 kg/L; only offered pH reagent |
| Iron | Disodium Fe-DTPA, 11% Fe; its sodium is counted |
| Additional fertilizer | Defined anhydrous sodium sulfate grade; no sodium nitrate offered |
| Sodium ceiling | Illustrative 9.00 mg/L; rounded-preparation ceiling 8.55 mg/L after 5% reserve |

No source-water pH measurement is supplied by this reconstruction. The carbon
inventory uses the stated bicarbonate, not an assumed measured pH. Its source
water and final-volume precision are fixed in this example; uncertainty in
those measurements is not included in the bounds below.

```{rst-class} accounting-flow
```

```{mermaid}
---
caption: Accounting, part 1 — design and formulate the selected recipe
---
flowchart TB
    accTitle: Appendix I target design and formulation
    accDescr: Build full-precision D targets from the crop baseline, corrections and design EC. Fit with source-water credits and reagent nutrient contributions. The original inventory misses at pH 5.5, so bounded search admits the declared sodium sulfate and selects a verified alternative.
    A[Crop baseline A<br/>explicit corrections B and design EC] --> D[Balanced C<br/>full-precision finished targets D]
    D --> F[Fit fertilizers and solve pH reagent<br/>count nutrients and counterions]
    W[Source-water nutrient credits<br/>and retained carbon inventory] --> F
    G[Declared fertilizer grades<br/>and nitric acid grade] --> F
    F --> M[Original inventory misses at pH 5.5]
    M --> S[Bounded search admits sodium sulfate<br/>select the verified alternative]
```

Continue with that selected recipe in part 2. Its rounded quantities and source
water are reconstructed together before the grower adopts the preparation.

```{rst-class} accounting-flow
```

```{mermaid}
---
caption: Accounting, part 2 — reconstruct and verify rounded preparation
---
flowchart TB
    accTitle: Appendix I rounded preparation and verification
    accDescr: Round dry weights, separate product-stock doses and nitric acid. Reconstruct the finished feed with stock-carrier displacement inside the final 1000 litres. Check all 13 nutrient bounds, sodium reserve, sampled pH and nominal saturation. Adopt the preparation while retaining physical qualification requirements.
    DR[Round dry fertilizer weights] --> V[Reconstruct finished feed<br/>water plus products plus reagent]
    ST[Round separate stock doses<br/>carrier displaces source water] --> V
    AC[Round nitric acid dose<br/>count its nitrate contribution] --> V
    V --> B[Inside final 1000 L, check 13 nutrient bounds<br/>sodium reserve, sampled pH and nominal saturation]
    B --> O[Review and adopt the verified preparation<br/>save sheet, report and calculation evidence]
    O --> P[Physical preparation qualification<br/>and measured batch validation remain]
```

Read the flow as five accounting steps: design D; fit with source-water and
acid nutrient contributions; retry the declared additional fertilizer; round
and reconstruct including carrier displacement; then review bounds and
qualifications. The sections below retain these steps when the diagram cannot
render. See the [grower's current screen captures](../grower/sonneveld-walkthrough.md#screen-capture-provenance)
for review, selection, rounded amounts and notes.

## Design the targets

1. Start with Column A: a crop/system baseline with balanced macronutrient
   charge. These are **feed concentrations**, not root-zone guide values.
2. Review the illustrative dated root-zone sample. K is 6.5 against guide 8,
   Ca is 10 against 10, and B is 0.035 against 0.050 mmol/L. The agronomist
   explicitly chooses corrections K +2, ammonium +0.5 and B +0.010 mmol/L.
   Sample-to-guide differences do not automatically become feed corrections.
3. Apply those increments as Column B, then redistribute the adjustable
   cations and anions to the original charge budget to obtain Column C.
   Ammonium and phosphate retain their separately chosen concentrations.
4. Raise the charge budget from 15 to 18 mmol charge/L using
   `10 × 1.8`, producing Column D. K, Ca and Mg scale as a group; nitrate and
   sulfate scale as another. Ammonium, phosphate and micronutrients are held.
5. Review and approve the exact preview in `flahax mix`. The approval binds
   this sample and design; changing either requires a new review.

All values in this table are mmol/L, **including micronutrients**. B lists
increments; an em dash means no explicit correction.

| Nutrient | A baseline | B increment | C balanced | D target |
|---|---:|---:|---:|---:|
| NH4 | 1 | +0.5 | 1.5 | 1.5 |
| K | 6.5 | +2 | 7.171875 | 8.765625 |
| Ca | 2.75 | — | 2.3203125 | 2.8359375 |
| Mg | 1 | — | 0.84375 | 1.03125 |
| NO3 | 10.75 | — | 10.75 | 13.09545455 |
| Phosphate, as P | 1.25 | — | 1.25 | 1.25 |
| Sulfate, as S | 1.5 | — | 1.5 | 1.82727273 |
| Fe | 0.015 | — | 0.015 | 0.015 |
| Mn | 0.010 | — | 0.010 | 0.010 |
| Zn | 0.004 | — | 0.004 | 0.004 |
| B | 0.020 | +0.010 | 0.030 | 0.030 |
| Cu | 0.00075 | — | 0.00075 | 0.00075 |
| Mo | 0.00050 | — | 0.00050 | 0.00050 |

For example, the provisional K/Ca/Mg charge is
`8.5 + 2 × 2.75 + 2 × 1 = 16`. With ammonium raised to 1.5, the original
15 charge budget leaves 13.5 for those cations. Column C therefore uses factor
`13.5 / 16 = 0.84375`. Column D uses factor `(18 − 1.5) / 13.5`, so
calcium becomes 2.8359375 mmol/L. The nitrate/sulfate factor in D is
`(18 − 1.25) / (15 − 1.25) = 1.2181818…`.

FlahaX passes full-precision D to formulation, rather than rounding it to the
printed table first. This explains small differences from earlier runs fitted
to printed Ca 2.84, K 8.76, nitrate 13.10 and sulfate 1.83. Conversion to
mg/L uses elemental molar mass: nitrate and ammonium are **as N**, phosphate
as P and sulfate as S. The formula's positive and negative analytical charges
both equal 18; this does not make the more detailed EC estimate equal 1.80.

## Credit water and solve the acid/fertilizer recipe

The water already supplies part of calcium, magnesium and sulfur. The pH
solver jointly counts the fertilizer contributions and nitrate from HNO3.
At pH 5.5 the original product pool misses nutrient targets; the bounded
available-product search admits anhydrous sodium sulfate and refits the recipe.
It is an available fertilizer declared in the profile, not an invented product.

At this volume, the nitric acid's approximate nitrate contribution is
`127.76 × 1.39 × 0.65 / 63.01 = 1.832 mmol/L`. It therefore replaces part of
the nitrate otherwise supplied by fertilizer. Holding the paper's fixed
2.20 mmol/L bicarbonate-neutralization dose would use about 153.43 mL of this
acid grade; that is a different calculation and does not impose pH 5.5.

The rounded check reconstructs the final feed after all dry weights, stock
volumes and acid are rounded. The two demineralized product-stock doses total
308.24 mL. Their volume replaces the same volume of source water, retaining
source-water fraction `1 − 308.24 / 1,000,000 = 0.99969176`. Its water credits
and carbon are scaled accordingly; stock carrier is not counted as additional
source-water nutrients. Final volume includes every addition. Fixed solvent
mass and source-water displacement are declared approximations of this adapter.

## Declared uncertainty

These bounds are illustrative input specifications, not instrument certificates:

- First six macro fertilizers and sodium sulfate: ±0.010 g weighing error.
- Dry Fe-DTPA, Mn sulfate, Zn sulfate and boric acid: ±0.0001 g weighing error.
- Every dry product: ±0.0002 relative assay error (±0.02%), scaling its
  disclosed components together.
- Copper and molybdate product stocks: each 1.00 g/L, concentration error
  ±0.0003 relative (±0.03%), density interval 0.998–1.002 kg/L, dose error
  ±0.05 mL, nominal doses rounded to 0.01 mL.
- Liquid nitric acid: dose error ±0.025 mL, active mass fraction
  0.6499–0.6501 and product density 1.3899–1.3901 kg/L.
- Dry nominal weights rounded to 0.001 g; acid nominal volume to 0.01 mL.

The acceptance settings are ±0.1% of each of the 13 positive nutrient targets,
pH 5.50 ±0.002 and 5% reserve below each declared nutrient ceiling. The assay,
weighing and dispensing errors are additional to rounding. Water-analysis and
final-volume errors are not represented in this batch adapter. Numerical fit
tolerances are separate; see [How a recipe is calculated](../explanation/how-a-recipe-is-calculated.md).

## Rounded recipe and verification

<!-- Rounded example tables are checked against the downloadable profile's public workflow. -->

| Product | Rounded amount for 1,000 L |
|---|---:|
| calcium nitrate tetrahydrate | 433.557 g dry product |
| ammonium nitrate | 120.062 g dry product |
| magnesium sulfate heptahydrate | 155.584 g dry product |
| monopotassium phosphate | 170.106 g dry product |
| potassium nitrate | 615.877 g dry product |
| potassium sulfate | 124.078 g dry product |
| iron DTPA | 7.615 g dry product |
| manganese sulfate monohydrate | 1.690 g dry product |
| zinc sulfate heptahydrate | 1.150 g dry product |
| boric acid | 1.855 g dry product |
| sodium sulfate anhydrous | 24.039 g dry product |
| copper sulfate pentahydrate | 187.26 mL of 1.00 g/L separate stock |
| sodium molybdate dihydrate | 120.98 mL of 1.00 g/L separate stock |
| Nitric acid, 65% w/w | 127.76 mL product (177.5864 g solution) |

The following values are elemental **mg/L**, with both nitrogen forms as N.
Displayed digits are rounded for readability; calculations use unrounded targets.
All 13 rows pass their full-precision ±0.1% bounds.

| Nutrient | Designed D target | Rounded nominal | Declared-error interval |
|---|---:|---:|---:|
| Ca | 113.65870313 | 113.64641047 | 113.62999351–113.66282812 |
| Mg | 25.06453125 | 25.06151605 | 25.05746065–25.06557185 |
| K | 342.72103594 | 342.72134997 | 342.64158033–342.80112410 |
| N_NO3 | 183.42410318 | 183.42230400 | 183.37561773–183.46899484 |
| N_NH4 | 21.01005000 | 21.01006252 | 21.00411092–21.01601481 |
| P | 38.71720250 | 38.71686109 | 38.70684213–38.72688096 |
| S | 58.58236364 | 58.57933208 | 58.56410274–58.59456360 |
| Fe | 0.83767500 | 0.83765000 | 0.83747147–0.83782853 |
| Mn | 0.54938044 | 0.54931499 | 0.54917263–0.54945737 |
| Zn | 0.26152000 | 0.26148362 | 0.26140859–0.26155866 |
| B | 0.32430000 | 0.32431748 | 0.32423514–0.32439983 |
| Cu | 0.04765950 | 0.04765950 | 0.04763248–0.04768653 |
| Mo | 0.04797500 | 0.04797698 | 0.04794277–0.04801121 |

## Interpret the checks

The documented run finds a verified alternative and the nearest rounded doses
pass without adjacent-dose refitting. The overall summary remains
`requires_review`, even though the declared nutrient/preparation checks pass.
That status retains chemistry and physical-preparation qualifications.

| Check | Result and meaning |
|---|---|
| Root-zone feedback | Approved illustrative sample/design; corrections explicitly chosen |
| Product search | Original fit misses; declared sodium sulfate alternative passes; sodium nitrate absent |
| Rounded analytical bounds | All 13 nutrients pass ±0.1%, including dry, stock and acid errors |
| Sodium reserve | Upper bound 8.499246 mg/L < 8.55 mg/L reserved ceiling; about 0.050754 mg/L remaining margin |
| Nominal modeled pH | 5.499143 |
| Sampled pH interval | 5.498093–5.500191, inside 5.498–5.502; minimum margin only about 0.000093 pH units |
| Estimated EC at 25 °C | 2.090793–2.200912 mS/cm, numerically the same units as dS/m; a composition-based estimate, not measured EC or an uncertainty interval |
| Nominal saturation | No readily forming phase risk flags; information retained for goethite, hydroxylapatite and MnHPO4 |
| Physical qualification | Still open: product assays, stock preparation/stability, dispensing accuracy, final volume and measured finished-batch pH, EC and nutrients |

The analytical bounds enclose the declared linear mass/assay errors. The pH
range samples common low/high fertilizer masses with independent carrier-volume
and reagent-potency endpoints; it is not a proof of all nonlinear interior
combinations or independent per-product pH extrema. Saturation is checked at the
nominal rounded composition, not across every uncertainty combination or every
pH between the sampled points. No allocated solids in this aqueous-only run
does not establish that a physical stock remains dissolved.

The small pH margin makes this a reproducible tight-bound example, not a robust
field guarantee. This page uses the baseline 1 g/L stocks. Earlier exploratory
stock-strength variants trade copper tolerance margin for sampled pH margin;
they are separate profiles and must be reviewed and verified separately.

## Prepare a farm-specific profile

Replace the illustrative observations, crop/system baseline, water inventory,
product grades, limits and equipment uncertainties with supported records.
Keep the elemental nutrient-credit and equilibrium inventories consistent.
Choose feed corrections from agronomic judgment, review the full-precision D
targets, and import the new profile for grower approval. A changed target design
or sample invalidates its old approval fingerprint.

Retain the adopted session plus the batch sheet, full report and JSON result.
The [format reference](../reference/file-formats.md#sonneveld-import-profile)
documents all nested inputs, units, defaults and replay/drift checks. Review
model qualifications and [physical validation requirements](../evidence/physical-validation-protocol.md)
before treating a calculated recipe as a qualified preparation procedure.
