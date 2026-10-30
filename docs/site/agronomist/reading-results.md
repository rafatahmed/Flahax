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

The packaged pH products (potassium hydroxide 45 %, potassium bicarbonate and
potassium carbonate to raise the pH; phosphoric acid 75 % and nitric acid 65 % to
lower it) are always evaluated, so a feed that mixes off the target pH gets a
reagent in the needed direction. The exit code is 0 for a ready or review plan, 3 for a blocked plan and 1
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
| `ready` | Calculation checks passed; physical validation remains separate. |
| `requires_review` | Review required: a target is missed with its reason, or explicit condition-qualified phase evidence still needs review (see [saturation indices](../developer/water-to-delivery.md#saturation-indices-and-acceptance)). |
| `blocked` | Not usable as planned: a declared maximum is exceeded on the laboratory analysis, a phase that forms at feed conditions is supersaturated, no reagent reaches the pH, or the chemistry could not be calculated. The reason is given. A review never downgrades a block. |

When a pH reagent is selected, the recipe to weigh is the refitted one that
counts the reagent's nutrients. The batch sheet lists what to weigh per tank,
the concentrate strength at the injection ratio, the reagent volume, the
warnings to read before mixing and blank lines for measured EC and pH.

## Concentrate tanks

The default grouping (`group_tanks`) follows Yara, *Fertilizantes para
fertirrigación*, page 65 mixing compatibility table, read with page 63. The
table's twelve "No" pairs are exactly three rules, applied to every product from
its elemental analysis. Calcium/phosphate, calcium/sulfate and
magnesium/phosphate separations remain hard constraints. Neither equipment count
nor a micronutrient's small dose waives them. These are conservative separation
screens, not predictions of precipitation at every concentration.

`group_tanks` computes a minimum-tank layout under those constraints. Supply
`max_tanks` to impose an equipment limit; if it cannot fit, the function reports
`too_many_tanks`. An exhausted search is reported separately. The default reports
required tanks without inventing equipment. `summarize_batch` assumes two available
tanks unless `available_tanks` is supplied and blocks preparation when more are
required. Every product remains in the report, including products assigned to
additional required tanks. Reagents retain their separate channel.

See [condition-qualified assignments](stock-assignments.md) for the mixture-model
interface, alternative search and approval boundary. Historical two-tank captures
are retained as historical evidence; they are not current preparation instructions.

The tank table states compatibility, not dissolution approval. The single-product
screen in `summary['solubility']` distinguishes qualified limits from conditional
screening floors. A floor exceedance is **inconclusive**, not proof that a product
will not dissolve. A comparison below a floor does not approve a mixed stock.
Unqualified comparisons keep the batch under review; other blocking findings
remain blocking.

The unchanged historical table contains 20 products, principally CRC-derived
values, plus CALCINIT and urea source values. Its density-one conversions are
conditional screening values, not measured limits. CALCINIT's source specifies
20 °C; the historical extension through 40 °C is no longer applied. Intermediate
temperatures require explicit interpolation review. Missing basis, grade, density
or temperature evidence is never silently supplied. See the
[qualification contract](solubility-qualification.md) for conversion equations,
source provenance and the caller-reviewed limit interface.

Your own `compatibilityRule` records (`--rules`, or
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
from pathlib import Path
Path('report.html').write_text(render_report(summary), encoding='utf-8')
Path('batch-sheet.html').write_text(render_batch_sheet(summary), encoding='utf-8')
```

`summary` is plain JSON-ready data with the same numbers as the two pages.


## Weighed chemistry and rejected reagents

When a reagent is selected, chemistry uses its mixed and target states. When none
is selected, chemistry and EC use the retained unadjusted recipe state: the same
recipe whose products are weighed. Rejected-candidate pH and saturation diagnostics
remain separate in `chemistry.rejected_candidate_diagnostics`, labeled
`rejected_candidate_not_weighed`. They do not supply final-feed chemistry or EC.
`chemistry.state_basis` identifies the state used. Existing phase and equipment
blocks still apply.

If a legacy manually constructed pH plan has no retained state for the weighed
recipe, chemistry is unavailable and EC is `not_supported` with reason
`weighed_recipe_state_unavailable`; a rejected state is never substituted.

The unchanged field-session regression previously combined weighed pH 5.32 with
rejected-candidate mixed pH 5.20. It now consistently presents 5.32 for the weighed
recipe and retains 5.20 only in the rejected-candidate diagnostic. This corrects
state identity, not equilibrium parameters or acceptance tolerances.


## Match outputs to the same calculation

Reports and sheets show a calculation reference. Compare it with
`calculation_identity.result_id` in the JSON summary when keeping or sharing
outputs. The reference binds the input records, product doses, selected chemistry
state and model sources. Editing a bound summary causes rendering to fail; rerun
with the corrected inputs rather than editing calculated fields.

The JSON `statuses` distinguish nutrient feasibility, chemistry and phase
qualification, pH, EC, stock mixing, delivery and physical validation. A feasible
nutrient recipe does not establish stock compatibility or validated delivery.
Missing numerical convergence evidence is labeled `not_reported`; physical
validation remains a separate later stage. The existing overall block always
wins over review or successful individual stages.


## Remedies are evaluated alternatives, not promises

The full report and JSON summary list next actions for unmet requirements and
show any explicitly supplied alternative scenarios. A catalogue product without
confirmed availability, a treatment without analysis provenance or missing
stock-equipment data is a **potential remedy**. It has not been validated by
merely appearing in the list.

An **evaluated candidate** resolves at least one requirement after re-running the
workflow with unchanged crop targets and hard limits. Read its remaining and newly
introduced requirements: nutrient feasibility alone cannot establish pH, stock,
equipment or physical suitability. The original recipe remains the recipe to
weigh until a new calculation explicitly adopts different inputs. A budget-limited
search says which options were not evaluated; it never calls them impossible.


## Saved results and consent

Acceptance records identify one exact calculated proposal. They never turn a
blocked limit into a pass, certify an unassessed EC, or establish physical
validation. Changed inputs, grams or evidence require a new result review.
Saved sessions contain answers; they are not consent. New sessions detect changed
referenced records or model sources before rerunning. Older sessions have no
historical provenance claim and must be reviewed against current inputs when
migrated. See the developer guide's saved-state schemas for explicit migration.


## Exact output evidence and zero targets

An explicit nutrient target of zero remains a hard zero in the report, sheet and terminal
nutrient table. Its absolute difference remains defined; its percentage difference is
**undefined (zero target)**. An omitted target is incidental and is not converted into zero.

Every HTML report and sheet includes an inert JSON summary in
`pre#flahax-result-data`. Parsing its text recovers the full-precision result, including
dose, status and provenance fields. The displayed tables are rounded for reading.
The export identity detects modification; a legacy unbound summary remains explicitly
unverified. This identity establishes record integrity, not scientific validation.

The scientific qualifications distinguish estimated, partial and unsupported EC.
Known-species subtotals cannot be used as total estimates or uncertainty bounds.
A range is displayed only if the result actually provides one; otherwise the interval
remains unquantified. Model, numerical and input uncertainty are reported separately.
Feasibility does not imply accepted chemistry, qualified stocks, delivery or physical validation.
