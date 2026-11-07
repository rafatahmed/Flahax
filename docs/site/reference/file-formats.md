# Input files

FlahaX reads plain JSON. Every number carries a stated unit, and a value you leave out is never
guessed.

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
