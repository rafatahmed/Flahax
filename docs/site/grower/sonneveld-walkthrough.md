# Review a Sonneveld batch

Use this route when your agronomist has prepared a Sonneveld batch profile.
The profile contains the feed design, water, available products and dispensing
limits. FlahaX shows the sample and proposed feed before you approve it, then
finds and checks a rounded recipe. This route produces a direct batch with
separate small product stocks; it does not ask for the usual A/B tank sizes.

This walkthrough uses the 1,000 L Appendix I example at pH 5.5 without sodium
nitrate. Its root-zone sample and equipment uncertainties are illustrative,
not measurements from a farm. The [agronomist walkthrough](../agronomist/sonneveld-appendix-i.md)
explains the chemistry and complete verification.

## On this page

- [Get the profile](#get-the-profile)
- [Review and approve the feed](#review-and-approve-the-feed)
- [Review the rounded preparation](#review-the-rounded-preparation)
- [Save, export and repeat](#save-export-and-repeat)
- [When an input changes](#when-an-input-changes)

## Get the profile

Install the FlahaX revision containing this workflow; see [Install](../start/install.md).
Download {download}`sonneveld-appendix-i.json <../../../examples/sonneveld-appendix-i.json>`
to your working folder. From a source checkout, the same file is at
`examples/sonneveld-appendix-i.json`. The commands below assume you downloaded
it to your current folder. This example is also included in the source archive;
the installed wheel is not claimed to contain the example file.

Run this in a terminal at least 80 columns wide and 24 rows high:

```bash
flahax mix --sonneveld-batch sonneveld-appendix-i.json --output appendix-i-output
```

For line-by-line questions, use the same inputs with `--plain`:

```bash
flahax mix --plain --sonneveld-batch sonneveld-appendix-i.json --output appendix-i-output
```

Use a new output folder for each comparison so the evidence stays separate.
An agronomist should supply a reviewed profile with your actual water, products
and equipment bounds before using this route for a crop.

## Review and approve the feed

1. Review sample `illustrative-appendix-i`, dated `2026-11-17`. The measured
   potassium is 6.5 mmol/L against a guide of 8; calcium is 10 against 10;
   boron is 0.035 against 0.050. These are example root-zone observations.
2. Review the proposed feed adjustments: K +2, ammonium +0.5 and B +0.010
   mmol/L. They are agronomist-selected corrections, not amounts automatically
   derived from the sample differences.
3. Review the resulting finished-feed targets. Continue through all four
   review screens using Enter, or choose **Stop** if anything is wrong.
4. Enter your name and reason for approving this exact sample/feed preview.
   For a practice run, use `Example grower` and `Illustrative Appendix I review`.
5. Save the answers as `Appendix I`. The session name becomes `appendix-i`.

Approval records your review of the target design. It does not establish that
the batch or stocks have been physically prepared and tested.

## Review the rounded preparation

The calculation includes nitrate from nitric acid. If the original fertilizers
miss the targets, it also tries the available anhydrous sodium sulfate grade.
Sodium nitrate is absent from both product lists.

Choose **Use verified alternative** only after reviewing the result. In plain
mode, choose option `2`; option `1` stops without saving the batch.
The results screen shows **Rounded batch doses**, **Rounded finished nutrients**
and preparation notes. Tab changes views; arrows scroll. The worked amounts and
all 13 nutrient bounds are in the [verification table](../agronomist/sonneveld-appendix-i.md#rounded-recipe-and-verification).

Two small quantities are delivered from separately prepared stocks, each
containing 1.00 g of the named product per litre of final stock solution:

- Copper sulfate pentahydrate: **187.26 mL**.
- Sodium molybdate dihydrate: **120.98 mL**.

The nitric-acid product dose is **127.76 mL**, using the declared 65% w/w
product and 1.39 kg/L density. Review the dry weights on the same sheet.
All stocks and reagent are included in the **final 1,000 L**, rather than
being added to an already full 1,000 L tank. Keep the two product stocks
separate; this example does not qualify a combined micronutrient concentrate.

The supplied example checks ±0.1% nutrient bounds, sampled pH 5.5 ±0.002 and
a sodium ceiling of 8.55 mg/L after reserving 5% of the declared 9 mg/L.
These tight equipment bounds are illustrative requirements to verify with
your agronomist and equipment records. A passing calculation is not a
measurement of the finished batch.

## Save, export and repeat

The output folder contains `batch-sheet.html`, `report.html` and `summary.json`.
Open the sheet in a browser for the rounded quantities and the report for the
conditions and remaining qualifications. Save all three together.

The approved session is saved under `$FLAHAX_HOME/sessions/appendix-i.json`,
or `~/.flahax/sessions/appendix-i.json` when `FLAHAX_HOME` is unset.
The original import file is not needed to repeat unchanged approved inputs:

```bash
flahax mix sessions/appendix-i --output appendix-i-repeat
```

Measure and record finished-batch pH and EC after mixing under the reviewed
physical procedure. Individual nutrient confirmation requires analysis.
Follow the product safety instructions and [mixing guidance](mix-safely.md).

## When an input changes

Ask the agronomist to update the profile when the water analysis, sample, feed
correction, product assay, stock strength or dispensing bounds change. Import
the updated profile with `--sonneveld-batch`, review it again and use a new
session/output name. Do the same after a model/source change makes a saved
session stale. A Sonneveld session cannot use `--review-reagents` to bypass
the full profile review.

If no rounded recipe passes, review the reported misses and available products
with the agronomist. Record any changed target or equipment assumption before
recalculating. The search reports the best verified result it found within
its declared limits; it does not establish a global optimum.
