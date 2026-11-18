# Input files

Need a runnable example first? Follow the [grower profile review](../grower/sonneveld-walkthrough.md)
or the [agronomist calculation](../agronomist/sonneveld-appendix-i.md).
[Choose a workflow](../start/choose-workflow.md) distinguishes these inputs from
standard batch files and direct Python calls.

FlahaX reads plain JSON. Units belong to the field definitions below. Some fields have
documented defaults; omitted analytical measurements are not measured zeros.

## On this page

- [Water analysis](#water-analysis)
- [Nutrient targets](#nutrient-targets)
- [Products](#products)
- [Request on standard input](#request-on-standard-input)
- [Saved items of flahax mix](#saved-items-of-flahax-mix)
- [Sonneveld import profile](#sonneveld-import-profile)
- [Sonneveld saved session](#sonneveld-saved-session)

## Water analysis

Used by `flahax batch --water FILE`, saved by `flahax mix` under `waters/`.

```json
{"id": "station-104", "measured_ph": 7.8,
 "mg_per_litre": {"Ca": 244, "Mg": 100.8, "K": 44.2, "Na": 680, "Cl": 1280.4,
                  "S": 241.43, "N_NO3": 3.474, "HCO3": 196.9}}
```

| Key | Meaning |
|---|---|
| `id` | A name for the analysis |
| `measured_ph` | The pH the laboratory measured |
| `mg_per_litre` | mg/L of each element: `S` as S, `N_NO3` and `N_NH4` as N, `HCO3` as bicarbonate |
| `below_detection` | Optional: detection limits in mg/L, for example `{"Mn": 0.01}` |

A value of 0 is a measured zero; an ion left out is not measured. `HCO3` is required with a
measured pH (0 if none). The conversion factors from ions as printed (NO3, SO4, PO4, alkalinity as
CaCO3) are in [A batch from files](../agronomist/batch-command.md).

## Nutrient targets

Used by `flahax batch --targets FILE`: an object of nutrient to mg/L in the final solution.

```json
{"N_NO3": 128, "P": 58, "K": 211, "Ca": 104, "Mg": 40, "S": 54}
```

Keys: `N_NO3`, `N_NH4`, `P`, `K`, `Ca`, `Mg`, `S`, `Fe`, `Mn`, `Zn`, `Cu`, `B`, `Mo` (nitrogen as N,
sulfur as S).

## Products

Used by `flahax batch --products FILE` and saved by `flahax mix` under `stores/`: a JSON array of
product records, in the same form as the packaged catalogue.

```json
[{"id": "cmbpfudkn00naq8z9kd4qsr60", "name": "Ammonium Monobasic Phosphate",
  "formula": "(NH4)H2PO4", "elements": {"N_NH4": 12, "P": 27}}]
```

`elements` is % w/w of each nutrient in the product as sold. A product can also be defined by its
ions or by a supplier analysis; see [Formulas and products](../agronomist/formula-and-products.md).

## Request on standard input

`flahax` (or `flahax recommend`) reads one JSON object with `salts` (product records as above),
`targets` (as above) and an optional `water` (mg/L of each element), and writes the recipe as
JSON.

## Saved items of `flahax mix`

`flahax mix` saves under `$FLAHAX_HOME` (default `~/.flahax`), one JSON file per item, in the
folders `waters/`, `formulas/`, `stores/`, `acids/`, `reagents/` and `sessions/`. A session records the answers
of one batch:

| Key | Meaning |
|---|---|
| `spec` | `tank_litres` (`A`, `B`, `acid`), `ratio`, `temperature_c`, `mode` (`fill` or `once`), `irrigation_litres` |
| `water`, `water_share` | The saved water name (or `ro`) and its share of the batch water, % |
| `limits` | Declared maximum concentrations, mg/L |
| `formula`, `formula_title` | The formula name and the title shown on the sheet |
| `store`, `acids` | The saved product list (or `catalogue`) and the saved acid names |
| `reagent_store` | The saved available pH reagent list (or explicitly selected `catalogue`). New mix sessions store selected acid and base records together here; `acids` remains an empty list. Legacy explicitly reviewed records may retain additional certificate names. |
| `ph`, `depth` | Target pH, and the sheet depth: 1 grower, 2 agronomist, 3 full report |

A damaged or hand-edited session is refused with the error `invalid_session`, naming the field.

In a new calculation, fill mode derives irrigation volume from the smaller A/B nutrient tank.
All three channels use `spec.ratio`; the reagent container is refilled as needed. In exported
`summary.json`, `volumes.prepared_litres.acid` is the first reagent fill, not the total stock
consumed. `reagent_preparation` records total stock and reagent quantities, fill/refill counts,
and doses for full and final partial fills. Blocked calculations, on-target mixes and solid
reagents have no liquid preparation schedule. A liquid reagent quantity that cannot fit the
planned stock volume produces a blocked delivery diagnostic, without per-fill instructions.

A session without `reagent_store` requires explicit availability review using
`flahax mix sessions/NAME --review-reagents`. This saves a new session and preserves
the old one. Existing source/input drift checks still apply. Reagent lists are arrays
of the product records described under [batch inputs](../agronomist/batch-command.md);
an empty array means no available reagents. The name `catalogue` is reserved for
the built-in list.

## Sonneveld import profile

Used by `flahax mix --sonneveld-batch FILE`. This is a different input from the
five-step interview's saved session and from `flahax batch --sonneveld-targets`,
which takes only the target-design object. Download the complete executable
{download}`Appendix I profile <../../../examples/sonneveld-appendix-i.json>`;
see the [grower procedure](../grower/sonneveld-walkthrough.md) and
[agronomic interpretation](../agronomist/sonneveld-appendix-i.md).

The import profile must contain exactly these top-level keys. Empty lists/maps
must be explicit where appropriate; additional top-level keys are refused.

| Key | Shape and units |
|---|---|
| `title` | Nonempty display title and suggested session name |
| `sonneveld` | Target-design object described below, including `root_zone_feedback` for this import route |
| `final_volume_litres` | Positive final solution volume, including stock and reagent additions |
| `target_ph` | Required finished-feed pH setpoint |
| `water` | Nutrient credits in elemental mg/L, with `N_NO3` and `N_NH4` as N; this is not the laboratory-file wrapper `{id, measured_ph, mg_per_litre}` |
| `equilibrium` | Chemistry water inventory and declared model conditions, described below |
| `salts` | Array of original fertilizer product records; `elements` is % w/w, not mg/L |
| `alternative_products` | Array of additional available fertilizer records; `[]` offers none |
| `maximum_concentrations` | Map of nutrient ceilings in finished-feed mg/L; example `{"Na": 9.0}` |
| `ph_adjustment` | Available reagent records and their dose limits; example below |
| `volumetric_stocks` | Rounded product-stock, dry-dose and reagent settings; example below |

### Target design and root-zone review

`sonneveld` requires `baseline_mmol_l`, `adjustments_mmol_l` and
`irrigation_ec_ds_m`. Optional `minimum_mmol_l` constrains the designed Column D.
All nutrient profiles here use **mmol/L, including micronutrients**:
`"Cu": 0.00075` means 0.75 µmol/L. Valid nutrient keys are `N_NH4`, `N_NO3`,
`K`, `Ca`, `Mg`, `P`, `S`, `Fe`, `Mn`, `Zn`, `B`, `Cu`, `Mo`.

The baseline must include all seven macronutrients and balance their positive
and negative charge on the paper's analytical basis. Corrections are signed
increments for nutrients present in the baseline; other profiles are
nonnegative. The EC is a positive design input in dS/m, not a measured EC.

For `--sonneveld-batch`, include this structure:

```json
"root_zone_feedback": {
  "sample_id": "illustrative-appendix-i",
  "sampled_on": "2026-11-17",
  "measured_mmol_l": {"K": 6.5, "Ca": 10, "B": 0.035},
  "guide_mmol_l": {"K": 8, "Ca": 10, "B": 0.050}
}
```

`sampled_on` is an ISO calendar date. At least one measured nutrient must have
a matching guide; unmatched entries are reported, not silently filled in.
These observations provide review context; the explicit `adjustments_mmol_l`
still determine the corrections. The import always removes any supplied
`approval`, shows the preview and asks the grower to approve it again.
The lower-level target-design function also supports designs without feedback;
that does not remove the feedback requirement of this TUI import route.

### Water inventory and model conditions

The example's `water` credits are Ca 40.078, Mg 9.722 and S 9.618 mg/L.
Its separate `equilibrium` object is:

```json
{
  "water_totals": {"Ca+2": 0.001, "Mg+2": 0.0004,
                   "SO4-2": 0.0003, "CO3-2": 0.0022},
  "water_mass_kg": 1000,
  "water_analysis_id": "Sonneveld Appendix I",
  "temperature_c": 25,
  "carbon_boundary": "closed",
  "phases": []
}
```

`water_totals` uses the equilibrium basis in mol/kg water. `CO3-2` is the
inorganic-carbon basis inventory, not a claim that 2.2 mmol/L free carbonate is
present. This reconstruction treats the paper's bicarbonate as retained carbon;
it does not invent a measured water pH. `water_mass_kg` is solvent mass, not
final solution volume. This example uses the dilute approximation of 1,000 kg
water for 1,000 L finished feed. `phases: []` selects aqueous-only equilibrium;
the rounded output still reports a nominal saturation assessment. Keep nutrient
credits and the chemistry inventory consistent when changing water inputs.
See [concentration basis](../models/concentration-basis.md) for other bases.

### Reagents and rounded preparation

The profile offers only its declared nitric-acid grade:

```json
"ph_adjustment": {
  "products": [{"id": "appendix-nitric-acid", "chemicalFormula": "HNO3",
    "massFraction": 0.65, "densityKgPerL": 1.39,
    "source": "Example grade", "revision": "1",
    "recordedAt": "2026-11-17T00:00:00Z"}],
  "maximum_reagent_volume_litres": 1
}
```

The mass fraction is g active acid per g product. The density is kg/L of that
product; the maximum is litres of product for the whole batch. Product identity
and provenance do not replace a current assay certificate.

`volumetric_stocks` requires `stock`, `dry_mass_decimals`,
`reagent_volume_decimals`, `nutrient_tolerance_percent` and `ph_tolerance`.
Its optional fields are `alternative_stock_concentrations_g_l`,
`nutrient_ceiling_reserve` and `uncertainty`.

| Nested field | Meaning and example |
|---|---|
| `stock.basis`, `stock.carrier` | Required `"product_mass"` and `"demineralized_water"` |
| `stock.concentrations_g_l` | Exact product-name → grams of supplied product per litre of **final stock**; Cu and Mo products each 1.0 in this example |
| `stock.density_kg_l` | Same names → `[low, high]` kg/L of final stock; each `[0.998, 1.002]` |
| `stock.concentration_relative_error` | Dimensionless relative stock concentration error; `0.0003` means ±0.03% |
| `stock.dose_error_ml`, `stock.dose_decimals` | Absolute stock dispensing error ±0.05 mL and two decimal places for the nominal dose |
| `dry_mass_decimals` | Three decimal places in grams, independently of actual weighing error |
| `reagent_volume_decimals` | Two decimal places in mL for the liquid reagent |
| `nutrient_tolerance_percent`, `ph_tolerance` | ±0.1% of positive targets and ±0.002 pH units, not solver tolerances |
| `nutrient_ceiling_reserve` | Fraction from 0 to below 1, default 0; `0.05` makes a 9 mg/L declared ceiling 8.55 mg/L |
| `alternative_stock_concentrations_g_l` | Optional exact stock-name → nonempty array of alternative positive strengths to try |

Stock names must identify dosed fertilizers. Use one separate stock per named
product. Error and density bounds describe physical preparation; decimal
places only describe rounding. The batch retains fixed solvent mass and
subtracts stock volume from source-water volume when reconstructing water
credits and carbon. This adapter does not model uncertainty in final batch
volume or source-water analysis; do not interpret absent errors as measured
precision.

The optional `uncertainty` object accepts:

| Field | Units and behavior |
|---|---|
| `dry_product_error_g` | Exact dry product-name → nonnegative absolute weighing error, g |
| `dry_product_assay_relative_error` | Dry product-name → relative error from 0 to 1, scaling that product's disclosed components together |
| `reagent_volume_error_ml` | Nonnegative absolute dispensing error for liquid reagent |
| `reagent_density_kg_l_bounds` | `[low, high]` density interval containing the nominal liquid density; lower endpoint must be positive |
| `reagent_mass_fraction_bounds` | `[low, high]` from 0 to 1 containing the nominal active fraction |
| `reagent_mass_error_g` | Solid-reagent alternative to the liquid volume/density fields; not used with the nitric-acid example |

Omitted dry errors and reagent dispensing errors default to zero; omitted assay
and reagent density intervals collapse to the nominal values. The full example
explicitly supplies all applicable errors. Dry maps may contain only dry-dosed
product names; a stock-dosed product uses the stock settings instead.
See [the worked uncertainty values](../agronomist/sonneveld-appendix-i.md#declared-uncertainty)
and [rounded-dose interpretation](../agronomist/batch-command.md#rounded-volumetric-doses).

## Sonneveld saved session

Unchanged sessions created with this build are checked through public CLI
import, adoption and replay in separate processes with different hash seeds.
The original import file is not required, and the complete summary remains
byte-identical. Component order no longer changes equilibrium evidence
([#272](https://github.com/rafatahmed/Flahax/issues/272)). Input/source drift and
changed selected-candidate identities still require review. Older records can
require reimport after a calculation change; preserve their original evidence.

After interactive approval and adoption, FlahaX writes a session with exactly
these top-level fields:

```text
sonneveld_batch: the complete profile, with the approved sample/feed preview
selected_candidate: the selected calculation's result-ID string
saved_state:
  schema_version: 1
  inputs_sha256: digest of all session answers except saved_state
  references: {}
  sources: relative model/data filename -> SHA-256 digest
```

Inside `sonneveld_batch.sonneveld.root_zone_feedback`, FlahaX records:

```text
approval:
  approved_by: nonempty grower name
  reason: nonempty review reason
  design_sha256: digest of this sample and the full calculated feed design
```

The design fingerprint binds sample identity/date, measurements, guides and the
calculated feed design. `selected_candidate` binds the formulated result; it is
not the human-readable alternative ID from the report. `saved_state` binds all
answers and model/data sources. `references` is empty for this self-contained
route because products and water are embedded; ordinary interview sessions can
also fingerprint named external saved items. Hashes identify content; they are
not signatures or evidence of chemical or physical suitability.

Replay accepts `flahax mix sessions/appendix-i` or the actual saved-session
path. It verifies input and source fingerprints, recalculates and requires the
same selected result identity. The original import file can be moved or deleted
without losing the embedded inputs. Editing a saved answer without updating
its bound state produces `invalid_session`; source drift or a changed selected
calculation produces `stale_session`. The output `summary.json` is a result
export, not an import profile or a saved-session file.

To change a sample, correction, product, reagent, equipment setting or model
revision, update the **import profile**, reimport with `--sonneveld-batch`, review
the preview and adopt a newly calculated preparation. Use a new session name to
retain the old record. Neither `--review-reagents` nor hand-editing hashes is
the Sonneveld review path. An unbound object containing only `sonneveld_batch`
is refused as a replay session: it must go through profile import and review.
