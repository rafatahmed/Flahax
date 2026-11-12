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

Custom analyses do not require a manufacturer match. Declared nutrient percentages
can support nutrient fitting without proving a full chemical composition. The
chemical model separately uses supported declared constituents; unidentified
ligands or counterions are not inferred from a similar commercial product.

## Explicit ammonium policy

`recommend` defaults to an ammonium fraction of 0.10. When `N_NH4` is
absent or zero in the original targets and no explicit ammonium maximum exists, the allowance is the smaller of
that fraction of positive total target nitrogen and 1.5 mmol/L expressed as nitrogen
(21.01005 mg/L). `max_ammonium_fraction=None` disables this generated maximum.
A positive ammonium target prevents this allowance. The public recommendation
workflow removes a zero ammonium target before fitting; it does not treat it as
an ammonium prohibition. An explicit ammonium maximum retains its own meaning. No allowance is generated
when total target nitrogen is zero.

The reported practice attribution is a policy reference, not evidence that this
allowance is agronomically appropriate for every crop, stage, water or system.
The [2016 handbook, printed p.16](https://www.nmi-agro.nl/wp-content/uploads/2020/04/160905_manual_nutrient_solutions_digital_en-8mb.pdf#page=16)
provides conditional 5–15% and 1–1.5 mmol/L pH-management guidance. The exact
10% default and combined minimum are software policy, not a universal crop
requirement. [De Kreij et al. (1999), Tables 8–9](https://edepot.wur.nl/273945)
includes 1.8 mmol/L for tomato under high-pH conditions.
The allowance must not be presented as measured safety or a nutrient requirement.
