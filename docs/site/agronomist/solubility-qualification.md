# Single-product solubility check

`flahax.stock_solubility.check_stock_solubility` compares the mass of each product per
litre of stock with that product's own solubility value, in the value's own basis. It does
not model mixed-stock solubility. Common-ion and other mixture effects need separate
evidence; a single-product comparison cannot approve a tank. Every row says so:
"single-product check; the mixed tank is not assessed".

## Where the value comes from

1. The product's catalogue `physicalProperties.waterSolubility` (supplied reference data:
   the EDTA chelates, Micro Combi Mix 1 and 2, potassium nitrate, and the ammonium and
   potassium monobasic phosphates).
2. Otherwise the historical table of 20 products (principally CRC values, plus CALCINIT
   and urea).
3. Otherwise none, and the product is `not_checked`.

## Read a result

| Status | Meaning |
| --- | --- |
| `ok` | The stock is at or below the value |
| `exceeds` | The stock is above the value; the batch is blocked |
| `not_checked` | No solubility data ("no solubility data"); the batch stays under review |

Each row carries `limit_g_per_l`, `basis`, `source`, `source_temperature_c` and
`tank_temperature_c`. A 20 °C value is compared with a 25 °C tank and both temperatures
are shown; nothing is interpolated. A "g/L water" value is compared as stated and
labelled so (it is slightly higher than a "g/L solution" value). Where a source states
no volume basis the row says "volume basis unspecified by source". `mixture_approved` is
always `False`.

When a table gives several temperatures, the point nearest the tank temperature is used
(the lower one on a tie). The table values are grams of product per litre of solution at
an assumed density of 1 g/mL, and the row says so.

## Convert a source basis

`source_concentration_g_per_l` performs arithmetic with explicit supplied densities.
With solution density rho in g/mL and product/solute mass ratio R:

- mass percent w: `10 * rho * w * R`;
- g solute per 100 g water, x: `1000 * rho * x / (100 + x) * R`;
- g solute per L water, x: `1000 * rho * x / (1000 * rho_water + x) * R`;
- g solute per L final solution, x: `x * R`.

For hydrates, R must represent the product-to-source-solute molar mass ratio. Missing
density is rejected for water and mass bases, never replaced by 1. The stock check does
not convert: a catalogue value in a unit it does not know is `not_checked`.

## Historical table

The shipped values are unchanged. The
[Yara CALCINIT product sheet](https://www.yara.com/siteassets/crop-nutrition/our-fertilizer-product-range/field-fertigation/yaratera-calcinit-product-sheet.pdf)
states 1200 g/L **water** at 20 °C; the table's 545.9 g/L **solution** value assumes a
solution density of 1 g/mL and a water density of 0.9982 g/mL, converted by its author, not
by this check. Commercial-grade
equivalence is not verified.

## Supply your own table

A custom record has `product`, `source` and `points` (temperature °C, g product per L of
solution). Pass it as `table=`, and catalogue records as `products=`. A supplied
`product_grades={name: grade}` is accepted and never selects a value.
