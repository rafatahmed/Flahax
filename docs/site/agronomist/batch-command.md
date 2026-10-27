# A batch from files: `flahax batch`

This page takes you from a water analysis and a crop to a printed batch sheet in four steps with
`flahax batch`, then works through a tomato example on a real brackish well. FlahaX plans a batch;
it does not run pumps or dose anything. Its evidence is computational: it has not been validated in
the laboratory or in the field, so every sheet ends with measurements you take after mixing.
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

This worked example explicitly chooses an NH4-N maximum of 14 mg/L, including
the RO comparisons below. It is an illustrative caller constraint, not a crop
recommendation. Supply limits appropriate to your own requirements; FlahaX no
longer supplies an ammonium allowance automatically.

```bash
flahax batch --formula "Tomato (Howard Resh)" --water well.json --water-share 8 --acid "HNO3:0.60:1.37:Nitric acid 60%" --limit Na=68.97 --limit Cl=106.35 --limit N_NH4=14 --output tomato-batch
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

All options are listed in [batch report, sheet and tanks](reading-results.md).

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
   | **Requires review** | Review the stated evidence and conditions; this status alone does not approve mixing. |
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

The figures below preserve a historical run. They are not current predictions or
mixing approvals: the earlier phase-name exemptions have been retired, and EC
fit/coverage limits may also prevent a complete estimate. Re-run the command and
use its current blocked/review diagnostics; do not reuse the historical dose or
EC as an operating instruction.

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

**Historical review findings.** The old sheet listed these reasons; unresolved
phase applicability now blocks approval:
- **Ammonium.** The recipe carries 9.2 mg/L NH4-N, a nutrient you did not
  target and gave no maximum for. Check it, or declare a maximum.
- **The well analysis is 3.5 % out of charge balance.** For the chemistry,
  FlahaX closed it on chloride (−9.5 %). That step is a modelling assumption,
  not a measurement, so the pH and precipitation results need your judgement.
  Your limits were still checked on the measured 1280.4 mg/L. State the
  laboratory's chloride uncertainty in the water file
  (`"balance_ion_uncertainty_percent"`) and FlahaX will accept the closure if
  it falls within it.
- **Hydroxylapatite and MnHPO4 are supersaturated.** Their names do not prove that
  precipitation is absent at these conditions. Without applicable reviewed evidence,
  the phase assessment prevents approval. The sheet retains the findings ([saturation
  indices](../developer/water-to-delivery.md#saturation-indices-and-acceptance)).
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

## Concentration basis

Water JSON can declare final solvent mass/volume or final solution density and
complete nonwater mass. See [concentration and solvent mass](../models/concentration-basis.md)
for input examples, carrier/hydrate accounting and blend assumptions. Legacy
inputs retain a reported 1 kg solvent/L assumption with unquantified uncertainty.

## Titrated total alkalinity

Use `alkalinity_meq_per_litre` in water JSON for a signed total-alkalinity
measurement, separately from `mg_per_litre`. Do not combine it with `HCO3`,
including zero. Interactive entry now stores titrations in equivalents, not
as carbon. Legacy HCO3 carbon assumptions remain explicitly reported.

The supported proton reference includes carbonate, phosphate, borate, ammonia,
sulfate and major-ion complexes. Unqualified organic/trace-metal alkalinity is
rejected. Measured zeros and fixed carbon stay fixed; no chloride does not
authorize altering the titration. The original laboratory inventory continues
to determine nutrient limits.
