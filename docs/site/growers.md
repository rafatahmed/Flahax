# For growers and agronomists

This page takes you from a water analysis and a crop to a printed batch sheet,
in four steps, then works through a tomato example on a real brackish well.
FlahaX plans a batch; it does not run pumps or dose anything. Its evidence is
computational: it has not been validated in the laboratory or in the field, so
every sheet ends with measurements you take after mixing.

## The quick way: `flahax mix`

`flahax mix` asks for the same five things in order and remembers your answers,
so the next batch is one command:

1. **Specification**: tank A, tank B and acid container sizes, the injection
   ratio, the temperature, and whether you fill the tanks full (several
   irrigations) or make just enough for one irrigation.
2. **Water analysis**: RO water, a saved analysis, or a new one typed from the
   lab report in its own units (mg/L, meq/L or mmol/L; NO3 and SO4 as printed).
   Enter means *not measured*, `0` a measured zero, and `<0.02` below detection,
   as the lab prints it. The charge balance is shown at once.
3. **Crop formula**: a packaged formula, a saved one, or a packaged one changed
   value by value.
4. **Fertilizers available**: the catalogue, a saved store, or ticking what you
   have. A product you add is either a **chemical** (MKP, calcium nitrate) with
   the label on your bag, or a **compound** (an NPK 20-20-20 + TE) typed from its
   data sheet: the nitrogen forms, P2O5, K2O, the micronutrients and the
   chelating agent. FlahaX checks that the label's charges balance; a compound
   that does not balance is still used for nutrients, but no acid is planned for
   that batch.
5. **pH requirement**: the target pH of the irrigation solution.

```bash
flahax mix                          # first time: answers the five steps
flahax mix sessions/tomato-ro       # next time: no questions
```

In a terminal window (Windows Terminal, the Windows console, or a Linux or macOS
terminal of at least 80 x 24) `flahax mix` opens full screen. The arrow keys
move, Enter chooses, typing narrows a long list such as the crop formulas, Space
ticks the fertilizers you have, and Esc asks before quitting. The steps go
forward only. In a wide window your answers so far stay on the left. When the
batch is calculated the result opens on **Tanks** (tank A, tank B and the acid
container with what to weigh); Tab shows **Nutrients** (the agronomist table and
the pH path) and **Notes** (every review note once). A blocked batch opens on
Notes with the reason. The sheets are written before the result appears, the
same as in the line-by-line mode. `flahax mix --plain` keeps the line-by-line
questions, which are also used automatically when the output is not a terminal
(a script, a pipe or an editor's output panel).

At the end choose who the result is for. **Grower**: the batch sheet with tank
A and tank B (prepared litres and grams to weigh, with tick boxes), the acid
container and the checks after mixing. **Agronomist**: the same, plus the
nutrient table (target, from water, required, achieved, final, difference),
the limits and the pH path. **Developer or manager**: both, plus the full
report and `summary.json`. Tank A holds calcium and the micronutrients and never
takes acid; tank B holds the sulfates and phosphates, magnesium sulfate and any
phosphate compound included; acid has its own container and injector. A stock
that would not dissolve at your temperature blocks the sheet, and products
without sourced solubility data are listed as not checked.

The steps below do the same with `flahax batch`, one command with files, for
scripts and for checking a plan by hand.

## Why FlahaX needs your water's pH and balances the lab report

**Why calculate pH at all.** The acid you add depends on how strongly the
water and the fertilizers resist a pH change. Bicarbonate in well water is the
main buffer: the more of it, the more acid. FlahaX calculates the pH the mix
will have and the acid that brings it to your target, instead of a rule of
thumb, so it needs the water's composition and its measured pH.

**Why the lab report is balanced.** In any water the positive charges (calcium,
magnesium, sodium, potassium) equal the negative ones (bicarbonate, chloride,
sulfate, nitrate). A lab report never adds up exactly, because every value
carries a small measurement error. To calculate pH, FlahaX closes that small
gap: on chloride, or on the alkalinity when the report has no chloride. This
changes only the chemistry model; your targets and limits always use the
values on the report. A report more than 5 % out of balance is flagged when
you enter it, because that usually means a typing or unit error. RO water has
nothing to balance.

## What you need before you start

| You need | Where it comes from |
|---|---|
| A water analysis with its **measured pH** and **bicarbonate** (or alkalinity) | Your water laboratory. For RO or desalinated water alone, nothing: use `ro`. |
| A crop formula | One of the packaged formulas, or your own targets in mg/L |
| Your acid's strength and density, if the feed needs acid | The acid supplier's certificate of analysis |
| Any maximum concentrations you must respect (for example Na and Cl) | Your crop guidelines or advisor. FlahaX never assumes one. |
| FlahaX installed | `python -m pip install flahax`, or `python -m pip install --upgrade flahax` if you have an older version (see [install](guide/usage.md)) |

## Step 1. Enter your water analysis

Save the analysis as a small JSON file, for example `well.json`:

```json
{"id": "station-104", "measured_ph": 7.8,
 "mg_per_litre": {"Ca": 244, "Mg": 100.8, "K": 44.2, "Na": 680, "Cl": 1280.4,
                  "S": 241.43, "N_NO3": 3.474, "HCO3": 196.9}}
```

Every value is mg/L **of the element**. Laboratories often report the ion
instead; convert with these factors:

| The laboratory reports | Enter | Multiply by |
|---|---|---|
| Nitrate, NO3 | `N_NO3` | 0.2259 |
| Ammonium, NH4 | `N_NH4` | 0.7765 |
| Sulfate, SO4 | `S` | 0.3338 |
| Phosphate, PO4 | `P` | 0.3261 |
| Alkalinity as CaCO3 | `HCO3` (as bicarbonate) | 1.2193 |
| Bicarbonate, HCO3 | `HCO3` | 1 |

The other keys are `Ca`, `Mg`, `K`, `Na`, `Cl`, `Fe`, `Mn`, `Zn`, `Cu`, `B`
and `Mo`.

- **Write measured zeros as 0.** `"Cl": 0` means the laboratory found no
  chloride, and FlahaX keeps it at zero. An ion you leave out counts as
  not measured, which is not the same as zero.
- **Below detection.** List the limit instead, for example
  `"below_detection": {"Mn": 0.01}`. FlahaX treats the value as zero,
  records the limit, and never adjusts it.
- **Bicarbonate is required with a measured pH.** Write `"HCO3": 0` only if
  the laboratory found none.

FlahaX checks the analysis at its measured pH. If the charges already balance
it is used as it is. If they are slightly off (up to 5 %), FlahaX closes the gap
on chloride for its chemistry only. Your measured values are still what every
target and limit is checked against, and the report shows both side by side. A
gap above 5 % is refused: ask the laboratory to check the analysis.

**Blending with RO or desalinated water.** Add `--water-share 8` in step 3 to
use your analysed water as 8 % of the batch water and ion-free water for the
rest. For RO water alone, use `--water ro` instead of a file.

## Step 2. Choose the crop formula

List the packaged formulas, then pick one by its exact name:

```bash
flahax batch --list-formulas
```

`--crop tomato` accepts text that matches exactly one name; if it matches
several, FlahaX lists them and asks you to choose. To use your own targets,
write them in mg/L (N_NO3 and N_NH4 as N) and pass the file with `--targets`:

```json
{"N_NO3": 140, "P": 50, "K": 352, "Ca": 180, "Mg": 50, "S": 168,
 "Fe": 5, "Mn": 0.8, "Zn": 0.1, "B": 0.3, "Cu": 0.07, "Mo": 0.03}
```

## Step 3. Run the command

```bash
flahax batch --formula "Tomato (Howard Resh)" --water well.json --water-share 8 --acid "HNO3:0.60:1.37:Nitric acid 60%" --limit Na=68.97 --limit Cl=106.35 --output tomato-batch
```

- `--acid` takes the formula, mass fraction and density (kg/L) from your
  certificate, plus an optional name. Repeat it to offer more than one acid.
- If the feed needs raising instead, FlahaX also tries the packaged bases:
  potassium hydroxide 45 %, potassium bicarbonate and potassium carbonate.
- `--limit` sets each maximum in the final solution. A maximum also allows that
  ion in the recipe up to the limit. For example, `--limit Cl=...` lets FlahaX
  use a chloride fertilizer if it helps, while staying under the limit.
- `--volume` sets the batch size (default 1000 L), `--ph` the target pH
  (default 5.8) and `--ratio` the injection ratio (default 1:100).

All options are listed in [batch report, sheet and tanks](guide/grower-outputs.md).

FlahaX writes three files into the new folder:
- `batch-sheet.html`: one printable page for the person mixing;
- `report.html`: the full report with charts;
- `summary.json`: the same numbers, for your records or other software.

The command's exit code is 0 for a ready plan or one that needs review, and 3
for a blocked plan.

## Step 4. Read the batch sheet

Read it from top to bottom before you weigh anything.

1. **The status box.**

   | Status | Meaning |
   |---|---|
   | **Ready** | Every target is met and the pH plan is accepted. |
   | **Requires review** | Usable after you read the "Read before mixing" list and agree with it. |
   | **Blocked** | Do not mix. The sheet says why: usually a limit your water already breaks, a mineral that would precipitate, or no acid or base that reaches the pH. |

2. **Weigh and dissolve.** This gives the grams of each product per batch,
   grouped by concentrate tank, and the strength of each concentrate at your
   injection ratio.
   - Tank A holds the calcium products, micronutrients and chelates. Never put
     acid into tank A.
   - Keep the two tanks apart. Magnesium sulfate shares tank B with the
     phosphates by FlahaX's two-tank rule; the sheet lists each such pair.
   - FlahaX does not check that each concentrate dissolves at that strength.
     Check it with your supplier's solubility data.

3. **pH.** How much reagent to add per batch. Add it in steps and measure.

4. **Limits.** Each maximum you declared, with the final concentration from
   your laboratory values and the decision. If you declared none, the sheet
   says that nothing was checked.

5. **Read before mixing.** Every warning and review reason, in plain words.

6. **Measure after mixing.** The planned EC and pH, with space for what you
   measure.

## Worked example: tomato on a brackish well

The well is station 104 from Shomar et al. (2024), *Groundwater*,
doi:10.1111/gwat.13411, at measured pH 7.80: the `well.json` above. It is
very salty. The goal is a Howard Resh tomato feed that keeps sodium and
chloride under 3 mmol/L each, 68.97 mg/L Na and 106.35 mg/L Cl (De Kreij,
Voogt and Baas 2003, open systems).

**How much well water can you use?** Divide each limit by the well's
concentration. Chloride decides:
- chloride: 106.35 ÷ 1280.4 = 8.3 %;
- sodium: 68.97 ÷ 680 = 10.1 %.

Take a whole percent below the chloride figure, 8 %, and blend the rest with
RO water. The products add a little sodium (the molybdate), so check the final
value on the sheet rather than relying on this arithmetic alone.

**Run** the command from step 3. FlahaX 0.6.0 gives this sheet:

| Tank | Product | g per 1000 L | Concentrate g/L at 1:100 |
|---|---|---:|---:|
| A | Calcium Nitrate (ag grade) | 835.5 | 83.55 |
| A | Potassium Nitrate | 147.6 | 14.76 |
| A | Iron II Sulfate (Hepahydrate) | 24.9 | 2.49 |
| A | Mn EDTA | 6.2 | 0.62 |
| A | Boric Acid | 1.7 | 0.17 |
| A | Copper Sulfate (pentahydrate) | 0.3 | 0.03 |
| A | Zinc Sulfate (Monohydrate) | 0.3 | 0.03 |
| A | Sodium Molybdate (Dihydrate) | 0.1 | 0.01 |
| B | Potassium Sulfate | 501.7 | 50.17 |
| B | Magnesium Sulfate (Heptahydrate) | 423.3 | 42.33 |
| B | Potassium Monobasic Phosphate | 220.0 | 22.00 |

- **Tanks.** There are two tanks. By FlahaX's rule magnesium sulfate shares
  tank B with the phosphate, although Yara's compatibility table says not to
  mix them: keep tank B's strength within what your supplier says dissolves,
  and check it for cloudiness.
- **Targets.** Every target is met within 1 %.
- **pH.** The blend mixes at pH 5.84, so only **1.5 mL** of 60 % nitric acid
  per 1000 L brings it to 5.8.
- **Limits.** Cl is 102.4 mg/L and Na 55.1 mg/L, both within their limits.
- **EC.** The estimate is about 2.6 mS/cm. It is experimental, so measure it.

**Why "requires review".** The sheet lists four reasons:
- **Ammonium.** The recipe carries 9.2 mg/L NH4-N, a nutrient you did not
  target and gave no maximum for. Check it, or declare a maximum.
- **The well analysis is 3.5 % out of charge balance.** For the chemistry,
  FlahaX closed it on chloride (−9.5 %). That step is a modelling assumption,
  not a measurement, so the pH and precipitation results need your judgement.
  Your limits were still checked on the measured 1280.4 mg/L. State the
  laboratory's chloride uncertainty in the water file
  (`"balance_ion_uncertainty_percent"`) and FlahaX will accept the closure if
  it falls within it.
- **Hydroxylapatite and MnHPO4 are supersaturated.** These two calcium and
  manganese phosphates do not form in practice at feed conditions. The sheet
  gives the reasons and sources ([saturation
  indices](guide/water-to-delivery.md#saturation-indices-and-acceptance)).
- **Iron(II) sulfate.** The recipe uses it, and in an aerated feed iron(II)
  oxidizes and settles out with some phosphate. A chelated iron is the safer
  choice. To make FlahaX use one, pass a product list without iron sulfate
  (`--products`).

**What 9 % would do.** With `--water-share 9` the sheet is **Blocked**. The
water alone brings 115.2 mg/L chloride, over the limit, whatever the
fertilizers do.

**On RO water only** (`--water ro`), the same formula needs 47 mL of nitric
acid per 1000 L: RO water has no bicarbonate, and the mix sits at pH 6.9.
Without an `--acid` the sheet is blocked: no base can lower the pH. A full,
scripted version of the brackish-well example, with charts, is in the
repository (`python -m examples.tomato_report --output tomato-report`).

## After mixing: what to measure

1. **Measure pH and EC** of the final solution at the dripper or tank outlet,
   after it has mixed for a few minutes. Write both on the sheet.
2. **pH.** If it is off the target, adjust in small steps and measure again.
   Never add more acid than the sheet plans in one go.
3. **EC.** The planned EC is an estimate. A measured value close to it confirms
   the weighing. A large gap usually means a weighing error, a different
   product grade or a different water: check those before adjusting anything.
4. **Concentrates.** Check each concentrate tank for undissolved product or
   cloudiness. Tank A must not be cloudy.
5. **Keep records.** Keep the sheet with its measured values. When the water
   source, the season or the product grade changes, run FlahaX again with a new
   analysis.

## When to call an agronomist

- The sheet is **blocked** and the reason is not one you can fix yourself.
- The sheet **requires review** and you cannot judge a reason, especially a
  precipitation note or the chemistry assumption.
- Your water analysis is refused (more than 5 % out of balance), or your water
  breaks a limit even at a small share.
- Targets are missed with the reason `conflicting_targets`: the formula
  itself does not balance, and a different formula may be needed.
- The measured pH or EC after mixing differs a lot from the sheet and you
  cannot find a weighing or product error.
- Plants show deficiency or toxicity symptoms, or the drainage EC or pH drifts
  from one irrigation to the next.

## Reference

### Reading a plan's stages

A full plan is split into stages. The report lists every stage with its status
and reason.

| Status | What it means | What to do |
|---|---|---|
| `calculated` | The stage returned a result | Check its warnings and the stages that depend on it |
| `needs_input` | Required evidence is missing | Supply the inputs it names; FlahaX does not invent them |
| `requires_review` | Usable after review: an incidental nutrient without a maximum, a review-class mineral, a missed target or a chemistry assumption | Read the reason and decide |
| `blocked` | The stage was rejected | Read its message and correct the inputs |

A calculated stage is not a validated delivery plan.

Read more: [user manual](guide/manual.md),
[water, targets and acid](guide/water-to-delivery.md).

### Reading a calculated EC result

FlahaX estimates the EC of the planned solution for comparison with your meter
after mixing. It is experimental, and its results use these statuses:

| Status | What it means |
|---|---|
| `estimated` | FlahaX gives an EC estimate. |
| `estimated`, with a range | Some charged dissolved species have no conductivity value. Their share cannot be negative, so the range starts at the part FlahaX can count and extends only upward. The true value tends to lie in the lower half. The middle of the range and its half-width describe only this missing share; they are not an accuracy statement. |
| `partial` | You supplied the pH and the analysis is missing some counterions. Only the part from known species is reported, with no total. |
| `not_supported` | The mixture is outside the conditions the method covers, or FlahaX calculated the pH and the analysis does not balance closely enough. The result says why, and no EC is given. A blend with undisclosed ingredients also gives this status. |

Every result carries the sentence "Accuracy on this fertilizer mixture has
not yet been established." No measured accuracy is claimed. When you compare a
prediction with your meter, FlahaX reports the difference without a pass or
fail verdict. Always check EC with a suitable meter after the solution is
prepared.

Read more: [stock and irrigation EC](guide/conductivity.md),
[site planning](guide/site-planning.md).

### Catalogue terms

**Undisclosed blends (`composition_undisclosed`).** A factory blend has a
declared nutrient analysis, but its exact ingredients, counterions or
additives may not be disclosed. FlahaX can still use the declared analysis to
build a recipe. It will not calculate pH, precipitation or EC for a mixture
that contains such a blend: it reports `composition_undisclosed` instead of
quietly leaving the blend out. A blend whose components are disclosed goes
through the chemistry normally.

**Analysis basis.** For each nutrient, FlahaX records where the value it used
came from:

| Basis | Source of the value |
|---|---|
| `lot_measured` | The measured value on your lot certificate |
| `grade_typical` | The typical value on the supplier's data sheet |
| `grade_minimum` | Only a minimum on the data sheet (flagged as a lower bound) |
| `identity_theoretical` | The theoretical analysis of the pure compound |
| `declared_catalogue` | The value in the shipped catalogue |

A record without this information is reported as `unattributed`; the basis is
never guessed. You pass in your own grades and lots; FlahaX does not store
them. When a grade gives a range, FlahaX shows the resulting nutrient band and
does not pick a "safe" end. Confirm the actual grade of each product before
physical use.

Read more: [traceable materials](guide/materials.md),
[stock planning](guide/stock-planning.md), [pH planning](guide/ph-planning.md).
