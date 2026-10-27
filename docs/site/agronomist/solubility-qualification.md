# Single-product solubility qualification

`flahax.stock_solubility.check_stock_solubility` compares product mass per final
stock volume with a source-qualified reference. It does not model mixed-stock
solubility. Temperature, chemical form, commercial grade and concentration basis
must match the source. Common-ion and other mixture effects require separate
evidence; a single-product comparison cannot approve a tank.

## Read a result

| Status | Meaning |
| --- | --- |
| `ok` | Within a caller-reviewed single-product limit |
| `exceeds` | Above that qualified limit; batch blocked |
| `screening_only` | At or below a conditional floor; review remains required |
| `inconclusive` | Above a floor; dissolution failure is not established |
| `not_checked` | Source, basis, grade, temperature or interpolation is unresolved |

`limit_g_per_l` is populated only for qualified limits. Floors instead populate
`screening_g_per_l`. Every row retains `reason`, `source`, `qualification` and
`mixture_approved=False`. Public JSON, HTML and terminal reports preserve this
distinction. No empty set of comparisons establishes solubility.

## Convert a source basis

`source_concentration_g_per_l` performs arithmetic with explicit supplied densities.
With solution density rho in g/mL and product/solute mass ratio R:

- mass percent w: `10 * rho * w * R`;
- g solute per 100 g water, x: `1000 * rho * x / (100 + x) * R`;
- g solute per L water, x: `1000 * rho * x / (1000 * rho_water + x) * R`;
- g solute per L final solution, x: `x * R`.

For hydrates, R must explicitly represent the product-to-source-solute molar mass
ratio. Converting the basis does not establish the applicability of a density or
grade. Missing density is rejected for water/mass bases, rather than replaced by 1.
Negative, nonfinite and malformed inputs are rejected. Conversion tests use exact
rational mass/volume witnesses with synthetic densities; they are arithmetic
verification, not new physical measurements.

## Historical source boundary

The shipped JSON values remain byte-identical. Only the pinned historical table
is annotated in memory as `assumed_density_floor`; custom tables receive no such
qualification automatically. The historical density-one premise is not a measured
lower bound for every grade or mixture.

The [Yara CALCINIT product sheet](https://www.yara.com/siteassets/crop-nutrition/our-fertilizer-product-range/field-fertigation/yaratera-calcinit-product-sheet.pdf)
states 1200 g/L **water** at 20 °C. The historical 545.9 g/L **solution** conversion
assumes solution density 1 g/mL and water density 0.9982 g/mL. These assumptions
remain historical, not newly adopted measurements. The original JSON extension to
40 °C remains in the file for provenance but is not accepted by the screen.
For example, 600 g/L against the 545.9 floor is now inconclusive, not a proven
failure. No source value or numerical tolerance was changed.

The original CRC and urea tabulations have not been independently requalified in
this change. Their retained values are conditional references, never certified
limits. Commercial-grade equivalence also remains unverified. This explicit
qualification boundary completes the mathematical screen without requiring
physical validation or claiming it has happened.

## Supply reviewed records

A custom record has `product`, `source`, `points` (temperature °C, concentration
in g product/L final solution) and `qualification`. To use a limit or established
lower bound, qualification must include `kind` (`limit` or `lower_bound`),
`basis='g_product_per_l_solution'`, `reviewed=True`, a nonempty `review_id` and
`grade_id`. Pass matching `product_grades={product_name: grade_id}`. Review metadata
is a caller assertion, not authentication or an automatic literature review.

Exact source points need no interpolation. Intermediate points require
`interpolation='linear'` and a nonempty `interpolation_review_id`; extrapolation
is refused. An optional `source_temperatures_c` further restricts applicability.
The low-level `limit_at` utility is algebraic interpolation only and does not
establish physical applicability. Batch reporting currently uses the historical
packaged table, so it cannot obtain qualified-limit approval through that table.
