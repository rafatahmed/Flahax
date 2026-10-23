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
| `balance_ion`, `balance_ion_uncertainty_percent` | Optional: the ion that closes the charge balance (`Cl` or `Na`) and its stated uncertainty |

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
[{"id": "cmbpfudkh00n5q8z9rvo5siqe", "name": "Ammonium Dibasic Phosphate",
  "formula": "(NH4)2HPO4", "elements": {"N_NH4": 21.217, "P": 23.451}}]
```

`elements` is % w/w of each nutrient in the product as sold. A product can also be defined by its
ions or by a supplier analysis; see [Formulas and products](../agronomist/formula-and-products.md).

## Request on standard input

`flahax` (or `flahax recommend`) reads one JSON object with `salts` (product records as above),
`targets` (as above) and an optional `water` (mg/L of each element), and writes the recipe as
JSON.

## Saved items of `flahax mix`

`flahax mix` saves under `$FLAHAX_HOME` (default `~/.flahax`), one JSON file per item, in the
folders `waters/`, `formulas/`, `stores/`, `acids/` and `sessions/`. A session records the answers
of one batch:

| Key | Meaning |
|---|---|
| `spec` | `tank_litres` (`A`, `B`, `acid`), `ratio`, `temperature_c`, `mode` (`fill` or `once`), `irrigation_litres` |
| `water`, `water_share` | The saved water name (or `ro`) and its share of the batch water, % |
| `limits` | Declared maximum concentrations, mg/L |
| `formula`, `formula_title` | The formula name and the title shown on the sheet |
| `store`, `acids` | The saved product list (or `catalogue`) and the saved acid names |
| `ph`, `depth` | Target pH, and the sheet depth: 1 grower, 2 agronomist, 3 full report |

A damaged or hand-edited session is refused with the error `invalid_session`, naming the field.
