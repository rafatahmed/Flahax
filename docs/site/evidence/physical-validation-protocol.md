# Physical validation protocol (draft)

:::{note}
**Status: draft for independent review. No samples have been prepared and no
results exist.** This page fixes what will be measured, how, and what counts as
agreement *before* any measurement, so the results cannot shape the criteria.
Choosing a reviewer, a laboratory and a budget is the maintainer's decision
and has not been made. This page authorizes no spending, outreach or
experiment.
:::

## Why this is separate

Everything FlahaX publishes so far is computational evidence: conservation,
convergence and agreement with PHREEQC 3.8.6 on the same thermodynamic data
([benchmark results](benchmark-results.md),
[computational assessment](computational-review.md)). Agreement with PHREEQC
shows the equations are solved correctly. It cannot show that the equations,
the constants, the product assays or the water analysis describe a real tank.
This protocol tests that, and keeps three things apart in every result:

| Kind of evidence | Question it answers | Where it comes from |
|---|---|---|
| Implementation agreement | Does FlahaX solve its model correctly? | PHREEQC comparison (already published) |
| Model and data uncertainty | How far can the prediction move within the uncertainty of its inputs? | Propagating the laboratory's stated input uncertainties through FlahaX (this protocol, before measuring) |
| Measured physical agreement | Does the real solution behave as predicted? | Measurements under this protocol |

A disagreement inside the input-uncertainty band is reported as such, not as
a model failure. A disagreement outside it is a finding, whichever way it
points.

## What is tested

The predictions a grower acts on, in order of how much harm a wrong one does:

| | Prediction | Measured as | Role |
|---|---|---|---|
| Q1 | Acid (or base) needed to bring the feed to its target pH | Titration of the prepared feed with the assayed reagent | Primary |
| Q2 | pH of the feed after the planned reagent dose | pH after adding exactly the planned dose | Primary |
| Q3 | Stock tanks FlahaX accepts stay clear; a combination it blocks does not | Visual check, turbidity, filtered vs unfiltered Ca, P and Fe | Primary |
| Q4 | Nutrient concentrations in the final feed | ICP-OES (cations, P, S, micronutrients); ion chromatography or colorimetry (NO3-N, NH4-N, Cl) | Primary |
| Q5 | pH of the feed before any reagent | pH of the unadjusted feed | Secondary, reported |
| Q6 | EC of the feed | EC at 25 °C | Report only: the EC estimate is a manufacturer-anchor screen with no uncertainty claim |

Speciation, saturation indices and activities are not measured directly. They
are tested only through their consequences above (pH, reagent dose,
precipitation).

## Test matrix

| | Water | Why |
|---|---|---|
| W1 | Laboratory deionized water (ASTM Type II or better) | No bicarbonate: pH and acid demand come from the products alone |
| W2 | A real alkaline source water as growers use it, at the blend share a grower would use, fully analysed for this study | Bicarbonate buffering, sodium and chloride: the case the measured-water and limit logic (#84) was built for |

| | Formula | Why |
|---|---|---|
| F1 | Tomato (Howard Resh) | The growers' worked example |
| F2 | Lettuce General (Howard Resh) | A second crop, and the only one of the three with an ammonium target (15 mg/L NH4-N) |
| F3 | Hoagland solution | The most widely published reference formula |

Six conditions (2 waters × 3 formulas). Target pH 5.8 for all. In W1 with
60 % nitric acid, all three formulas currently get a usable plan that needs
review (`flahax batch`, 2026-10-22); the W2 plans are made in step 2. Each condition
is prepared as tank A and tank B stocks at 100:1 and diluted to the final
feed (10 mL of each stock made up to 1 L), exactly as the batch sheet
instructs. One extra **positive control** stock combines calcium nitrate and
potassium sulfate in one 100× concentrate, a pair the tank grouping always
separates (calcium with sulfate); it must
precipitate, or the stock-stability measurement cannot detect anything.

### Replicates

- Three independent preparations per condition, each from its own weighing.
- Each pH and EC reading in duplicate; each laboratory analysis as the
  laboratory's standard duplicate.
- The positive control once per day of preparation.

### Sample count

| Item | Count |
|---|---|
| Final feeds (6 conditions × 3 preparations) | 18 |
| Stocks, tanks A and B (6 × 2 × 3) | 36, plus 1 positive control per day |
| Titrations (one per feed) | 18 |
| Feed analyses, ICP-OES and anions | 18 |
| Stock filtered/unfiltered Ca, P and Fe at 24 h | 36 pairs |
| Product lot assays (each product actually used) | about 10 |
| W2 full analysis, including alkalinity by titration | 3 |

## Order of work

The predictions are made from **measured inputs**, then frozen, then the
solutions are prepared. Nothing about the solutions is measured until the
predictions are frozen.

1. **Inputs.** Record each product's lot, supplier certificate and, where the
   reviewer requires it, an independent assay. Analyse W2 in triplicate
   (major ions, alkalinity by titration, pH, EC, detection limits). Assay the
   acid (titration against a standardized base) and measure its density.
2. **Predictions.** Run `flahax batch` for each condition with the measured
   water file, the assayed products and the assayed acid, at 1 L final volume
   and a 100:1 ratio. Separately, perturb each input within its stated
   laboratory uncertainty and rerun, to give the model-and-data band for
   Q1, Q2, Q4 and Q5. The analysis script that does this is written and
   committed before step 3.
3. **Freeze.** Commit the inputs, the command lines, every `summary.json`,
   the uncertainty bands, the FlahaX version and commit, and the SHA-256 of
   each file. Publish the commit hash (for example in the issue) before any
   solution is prepared.
4. **Prepare and measure.** Prepare stocks and feeds per the batch sheets.
   The analyst measuring pH and titrating does not see the predicted values.
5. **Compare.** Run the committed analysis script on the raw observations.
   Apply the exclusions below; nothing else is excluded.
6. **Publish** every result, passing or not, with this protocol's version.

## Measurement procedures

**Temperature.** Every measurement at 25.0 ± 0.5 °C in a water bath, with the
temperature recorded. FlahaX predicts at 25 °C.

**pH.** Combination glass electrode suitable for low ionic strength (W1
feeds are dilute). Three-point calibration (pH 4.01, 7.00, 10.01, traceable
buffers) at the start of each session; a pH 4.01 check buffer every ten
samples; recalibrate if it reads more than 0.02 off. Read after 60 s stirring
and when drift is below 0.01 pH per 30 s.

**Titration (Q1).** Titrate 500 mL of unadjusted feed with the assayed
reagent, diluted to a stated strength, in small increments past the target
pH, recording pH after each. The measured dose is the interpolated volume at
pH 5.8, converted to grams of product per 1000 L of feed.

**Planned dose (Q2).** To a fresh 500 mL of the same feed, add exactly the
planned dose (scaled from the batch sheet), stir and read the pH.

**Stocks (Q3).** Inspect against a black and a white background at 0, 1, 24
and 72 h; measure turbidity (NTU) at the same times. At 24 h, analyse Ca, P
and Fe on an unfiltered sample and on a 0.45 µm filtrate.

**Nutrients (Q4).** Feeds sampled after mixing and acid, acidified for
cations as the laboratory specifies; the laboratory's detection limits and
expanded uncertainties recorded with each result.

## Acceptance criteria (proposed; final after review)

The criteria below are the author's proposal. The reviewer may change them;
whatever version is signed off is frozen in step 3 and not changed after.

| | Criterion for agreement | Basis for the proposed number |
|---|---|---|
| Q1 | Measured dose within ±10 % of the predicted dose, or within 0.05 mmol H⁺ per litre when the dose is below 0.5 mmol/L | A grower doses acid by volume; 10 % is within injector repeatability. Small doses are judged absolutely, because a percentage of a near-zero dose is meaningless |
| Q2 | Mean pH after the planned dose within ±0.2 of 5.8 | Feeds are managed in windows of about 0.5 pH; 0.2 leaves room for meter uncertainty (about ±0.05) |
| Q3 | Every stock FlahaX accepts: no visible precipitate at 24 h, turbidity rise below 1 NTU, and filtered within 5 % of unfiltered for Ca, P and Fe. Positive control: visible precipitate | A precipitate that a grower would not see still removes nutrient; the filtration check catches it |
| Q4 | Macronutrients within ±10 % and micronutrients within ±15 % of the predicted concentration, computed with the measured product assays | Typical ICP-OES and IC expanded uncertainties are 3-5 %; weighing and dilution add little |
| Q5 | Reported with its error and the uncertainty band; no pass or fail | The unadjusted pH is not what the grower delivers |
| Q6 | Reported with its error; no pass or fail | No accuracy is claimed for the EC estimate |

A condition **agrees** when the mean of its three preparations meets the
criterion. Each result is also labelled *inside* or *outside* the
model-and-data band. A result can therefore be: agrees; disagrees but inside
the input band (inputs too uncertain to judge); or disagrees outside the band
(a finding about the model, constants or products).

## Exclusions (fixed in advance)

A measurement is excluded only for:

- a failed calibration check that was not repeated within the session;
- a preparation error written in the log *before* the result was seen
  (wrong product, spilled stock, wrong volume);
- a laboratory result the laboratory itself flags as invalid.

Every exclusion is published with its reason. Outliers are not removed for
being outliers.

## What is recorded

For each condition and preparation: the product lots and certificates;
product and acid assays; the water analysis with detection limits and
uncertainties; weighings (balance and resolution); volumes and glassware
class; every raw pH, titration, turbidity, EC and temperature reading with
time; instrument models, serial numbers and calibration records; the
laboratory reports as received; FlahaX version, commit and the SHA-256 of
every input and prediction file. Results are published as a versioned
snapshot beside the benchmark snapshots, with the same rule that files keep
their exact bytes.

## What a pass would and would not show

A pass shows that, for these two waters, three formulas, these product lots
and 25 °C, FlahaX's acid plan, pH, stock grouping and nutrient arithmetic
match what was measured within the stated limits. It does not extend to
other temperatures, concentrate strengths above 100:1, recirculated
solutions, other product grades or waters outside the tested range, and it
does not certify FlahaX for dosing. A failure is published with the same
prominence as a pass.

## Decisions for the maintainer

Nothing here starts until each of these is decided:

1. **Reviewer.** An independent water chemist or horticultural laboratory
   scientist, with no stake in FlahaX, to review this protocol before it is
   frozen. Contacting one is outreach and needs approval.
2. **Laboratory and budget.** The sample count above sets the scope; the
   cost depends on the laboratory.
3. **Water W2.** Which real water, and at what blend share.
4. **Who prepares the solutions.** The same person may prepare them; the pH
   and titration readings should be taken without seeing the predictions.

Tracking: rafatahmed/Flahax#41 (protocol and evidence), under the
limitations tracker rafatahmed/Flahax#42.
