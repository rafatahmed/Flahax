# Material masses and evidence status

FlahaX identifies its retained elemental values as `flahax-atomic-legacy-1`.
The values in `composition.ATOMIC` have not changed. They are a reproducible
calculation convention used for theoretical assays and oxide conversion, not
measurements of a supplier grade or a particular lot. Numerically, they are used
as elemental molar masses in g/mol.

The comparison reference is the [CIAAW Standard Atomic Weights 2024 table](https://ciaaw.org/atomic-weights.htm),
consulted on 2026-10-25. CIAAW distinguishes normal-material intervals and
values with stated uncertainty. Neither kind is a fertilizer assay uncertainty.
The compatibility table is not a verbatim transcription of that reference:
hydrogen retains 1.00784; oxygen retains the rounded 15.999; sodium retains
22.989769; manganese retains 54.938044. Their different precision and conventions
are explicit. Updating them requires a new convention and a review of all
derived assays, conversion factors and retained reference results.

Independent tests calculate magnesium-nitrate hexahydrate, ammonium-nitrate
nitrogen forms and phosphorus-oxide conversion using exact rational arithmetic
and manually specified atom counts. Their decimal-place assertions check binary
arithmetic against the retained convention; they do not specify physical accuracy.
Other product molar-mass literals and reference-model constants retain their
own historical conventions and are not silently relabelled as this table.

## Identity, grade and lot

A chemical identity supplies formula, hydration and ion-form assumptions.
A grade supplies a documented supplier analysis. A lot supplies a separately
documented measured analysis. The resolver retains the existing per-nutrient
precedence: lot, grade typical, grade minimum, then identity theory. A theoretical
fallback remains labelled as such. An identity comparator is not a certificate
for the product currently being weighed.

Material provenance now records `atomicMassConvention`, `sourceStatus` and
`assumptionStatus`. `sourceStatus` distinguishes `lot_documented`,
`grade_documented`, `catalogue_documented`, `catalogue_unattributed` and
`declared_unattributed`. Documented means a reference was supplied, not that its
contents were independently verified. `assumptionStatus` retains assumed blend
composition or explicitly says declared composition is not independently verified.
Missing impurity, hydration, ligand or counterion information is not evidence of
absence. Existing composition flags, identity status and nutrient basis remain
available; downstream model qualification is a separate decision.

## Explicit ammonium policy

`recommend` defaults to `max_ammonium_fraction=None`. Omitting an ammonium
maximum no longer invents a crop-practice limit. A caller may explicitly request
a fraction of total target nitrogen, or supply `maximum_concentrations` in mg/L.
The fraction has no additional 1.5 mmol/L cap. An explicit ammonium target or
absolute maximum retains precedence over the fraction.

This changes recipes that previously relied on the implicit allowance. It does
not change targets or prove the remaining incidental-ion objective is optimal.
Exact-zero targets now exclude contributing products, and absolute maxima also
constrain targeted nutrients. These constraints do not qualify the remaining
objective, secondary-selection or trace-reporting behavior.
