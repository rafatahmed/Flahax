# Batch report, batch sheet and concentrate tanks

The installed package turns one formula and one water into three files: an HTML
report, a printable A4 batch sheet and a JSON summary. Everything is pure Python
and offline: the HTML has inline styles and charts, and no script, font or network
access. These are planning documents, not dosing instructions: measure EC and pH
after mixing.

## Interactive: `flahax mix`

`flahax mix` asks for the specification, water analysis, crop formula,
fertilizers and target pH, saves each answer under `$FLAHAX_HOME` (default
`~/.flahax`) in the same formats `flahax batch` reads, and writes the batch
sheet at the chosen depth: grower (tank cards, acid container, checks),
agronomist (adds the nutrient table, limits and pH path) or developer and
manager (adds `report.html`). `summary.json` is always written. In Python,
`grower_sheet.render_mix_sheet(summary, depth)` and
`grower_sheet.agronomist_rows(summary)` give the same from any
`batch_cli.run_batch` summary. See the [growers page](../grower/index.md).

## From the command line

```bash
flahax batch --formula "Tomato (Howard Resh)" --water ro --acid HNO3:0.60:1.37 --output tomato-batch
```

`flahax batch --list-formulas` lists the packaged formulas. `--crop` accepts text
that matches exactly one formula name and lists the matches otherwise. Use
`--targets my-targets.json` for your own mg/L targets (N_NO3 and N_NH4 as N).

| Option | Meaning | Default |
|---|---|---|
| `--water` | `ro` (no ions) or a water-analysis JSON file (below) | required |
| `--water-share` | use the analysed water as this percentage of the batch water, the rest ion-free (RO or desalinated); targets and limits scale the laboratory values, the chemistry is recomputed for the blend | 100 |
| `--volume` | final batch litres | 1000 |
| `--ph` | target feed pH | 5.8 |
| `--ratio` | final litres per litre of concentrate | 100 |
| `--acid` | `FORMULA:MASS_FRACTION:DENSITY[:NAME]` from your certificate, for example `HNO3:0.60:1.37`; repeat for more | none: acids are never assumed |
| `--limit` | a maximum in the final solution, `SYMBOL=MG_PER_L`, for example `Cl=106.35`; repeat for more | none: limits are never assumed, and undeclared ones are not checked |
| `--max-reagent-litres` | largest pH reagent volume per batch | volume / 200 |
| `--products` | JSON array of your own product records | the packaged catalogue |
| `--rules` | JSON array of extra `compatibilityRule` records | none |
| `--output` | a new directory; existing paths are never overwritten | required |

The packaged bases (potassium hydroxide 45 %, potassium bicarbonate, potassium
carbonate) are always evaluated, so a feed that mixes below the target pH gets a
base. The exit code is 0 for a ready or review plan, 3 for a blocked plan and 1
for an input error.

### Water analysis file

```json
{"id": "station-104", "measured_ph": 7.8,
 "mg_per_litre": {"Ca": 244, "Mg": 100.8, "K": 44.2, "Na": 680, "Cl": 1280.4,
                  "S": 241.43, "N_NO3": 3.474, "HCO3": 196.9}}
```

Elements are mg/L of the element (S as S, P as P, N_NO3 and N_NH4 as N);
`HCO3` is bicarbonate in mg/L as HCO3. Iron is taken as Fe(III), the form in
aerated water. One litre of water is taken as one kilogram.

A value of 0 is a measured zero and stays zero (`"Cl": 0` for chloride-free
water, `"HCO3": 0` for carbon-free water); an omitted ion is not measured.
Optional keys: `"below_detection": {"Mn": 0.01}` (detection limits in mg/L;
taken as zero, never adjusted), `"balance_ion": "Cl"` or `"Na"`, and
`"balance_ion_uncertainty_percent": 10`, the stated uncertainty of that ion.

Targets and `--limit` maximums use these laboratory values. For the chemistry
only (pH, saturation, EC, reagent dose) the analysis is speciated at its
measured pH: used unchanged if it already balances; otherwise closed on the
balance ion within its stated uncertainty, or, without one, as an assumption
that puts the plan in review. An analysis more than 5 % out of charge balance
is refused. Missing chloride does not authorize changing a measured titration.
Positive, nonfixed directly supplied carbon may undergo the disclosed legacy model
reconciliation; measured zeros and fixed carbon remain unchanged. The report shows
laboratory and modelled water side by side (see
[measured-pH water balancing](../developer/water-to-delivery.md#measured-ph-water-balancing)).

## What the files say

The plan status is one of:

| Status | Meaning |
|---|---|
| `ready` | Every target is met and the pH plan is accepted. |
| `requires_review` | Usable after review: a target is missed with its reason, or explicit condition-qualified phase evidence still needs review (see [saturation indices](../developer/water-to-delivery.md#saturation-indices-and-acceptance)). |
| `blocked` | Not usable as planned: a declared maximum is exceeded on the laboratory analysis, a phase that forms at feed conditions is supersaturated, no reagent reaches the pH, or the chemistry could not be calculated. The reason is given. A review never downgrades a block. |

When a pH reagent is selected, the recipe to weigh is the refitted one that
counts the reagent's nutrients. The batch sheet lists what to weigh per tank,
the concentrate strength at the injection ratio, the reagent volume, the
warnings to read before mixing and blank lines for measured EC and pH.

## Concentrate tanks

The default grouping (`group_tanks`) follows Yara, *Fertilizantes para
fertirrigación*, page 65 mixing compatibility table, read with page 63. The
table's twelve "No" pairs are exactly three rules, applied to every product from
its elemental analysis. FlahaX waives the last one (see below):

| Keep apart | Why |
|---|---|
| calcium and phosphate | calcium phosphate precipitates in a concentrate (pp. 63, 65) |
| calcium and sulfate | gypsum precipitates in a concentrate (pp. 63, 65) |
| magnesium and phosphate | magnesium phosphate precipitates in a concentrate (p. 65); **waived** by the two-tank rule |

FlahaX rule (owner decision 2026-10-22): there are exactly **two** concentrate
tanks, A and B. Magnesium sulfate shares tank B with the phosphates, against
the magnesium-phosphate rule above. The report lists every pair this lets share
a tank (`TankGrouping.waived`), and check the strength of tank B against your
supplier's solubility data. Products that still need a third tank, for example
because of rules of your own, are refused with `too_many_tanks`.

FlahaX rule (owner decision, #79): micronutrients and chelates go to **tank A**
with the calcium products, because their doses are too small to precipitate
there; they are kept out of phosphate concentrates, where manganese and iron
phosphates can form (#78). **Tank A is never acidified** (Yara p. 63: do not
acidify tanks with microelement chelates): dose acid on its own channel or into
another tank. pH reagents always have their own channel.

The table states compatibility, not solubility. Check that every concentrate
dissolves at its strength and temperature; `plan_stocks` does this with your
sourced solubility limits, and `default_compatibility_rules(products)` gives it
the same rules as records. `summarize_batch(..., temperature_c=25)` also lists
each concentrate against sourced single-salt solubility at that temperature
(`summary['solubility']`); a stock that does not dissolve blocks the batch. The
packaged table (`data/solubility.json`) covers 20 products at 0-40 °C: 18 from
the CRC Handbook aqueous solubility table, calcium nitrate (ag grade) from
Yara's CALCINIT sheet (its 20 °C value used as a floor from 20 to 40 °C) and
urea from the U.S. Coast Guard CHRIS compilation. Mass percent is converted to
grams per litre at a density of 1 g/cm3, which understates solubility, so a
stock that would not dissolve is never passed. The chelates, CH - micro and
potassium citrate have no sourced data and show "not checked". Your own `compatibilityRule` records (`--rules`, or
`rules=` in Python) separate further products and override the micronutrient
rule.

## From Python

```python
from flahax import (VolumeLitres, catalogue_ph_reagents, load_library, plan_fertilizer_workflow,
                    render_batch_sheet, render_report, summarize_batch)

library = load_library()
products = library['salts']
targets = next(f['targets'] for f in library['formulas'] if f['name'] == 'Tomato (Howard Resh)')
nitric = dict(id='my-nitric', name='Nitric acid 60%', source='supplier certificate', revision='1',
              recordedAt='2026-10-22T00:00:00Z', chemicalFormula='HNO3', massFraction=.60, densityKgPerL=1.37)
workflow = plan_fertilizer_workflow(
    products, targets, {}, 5.8, final_volume=VolumeLitres(1000),
    equilibrium=dict(water_totals={}, water_mass_kg=1000, water_analysis_id='RO', complete_analysis=True,
                     carbon_boundary='closed', temperature_c=25, phases=[]),
    ph_adjustment=dict(products=[nitric] + catalogue_ph_reagents(), maximum_reagent_volume_litres=5))
summary = summarize_batch(workflow, products, title='Tomato', water_label='RO water')
open('report.html', 'w', encoding='utf-8').write(render_report(summary))
open('batch-sheet.html', 'w', encoding='utf-8').write(render_batch_sheet(summary))
```

`summary` is plain JSON-ready data with the same numbers as the two pages.
