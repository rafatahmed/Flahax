# Traceable materials: identity, grade and lot

FlahaX separates **chemical identity**, supplier grade and measured lot. Some
catalogue analyses have no source document; provenance records that absence rather
than implying verification. See [mass conventions and evidence status](../models/material-mass-convention.md).
Historical evidence:
[materials identity audit](../evidence/audit/2026-10-18-materials-identity/review.md).

Catalogue size does not measure chemical
coverage or model accuracy. FlahaX's chemistry approach uses explicit
chemical identities and composition assumptions. Its raw-material catalogue
should distinguish chemical identity from supplier grade and batch assay,
with traceable specifications and impurity information. Multiple commercial
products may represent the same underlying chemical source.

A factory blend has a declared nutrient analysis, but its exact ingredients,
proportions, counterions or additives may be incomplete or undisclosed. Some
manufacturers do disclose ingredients, so this varies by product.

FlahaX stays stateless: grades and lots are passed in, never stored.

## The three layers

| Layer | Holds | Source document | Shipped? |
|---|---|---|---|
| Identity | Name, formula, hydration, ion forms (including counterions), theoretical analysis | Reference material | Yes (`load_identities()`, `identity_for_product(name)`) |
| Grade | Owning identity (or a blend declaration), supplier, product, typical/minimum/maximum analysis, impurity limits | Technical data sheet | Reference grades only; users supply their own (`make_grade`) |
| Lot | Owning grade or identity, lot number, measured assay, optional uncertainty | Certificate of analysis | No; user supplied (`make_lot`) |

A grade belongs to one identity unless it is a blend. A lot points at a grade
or directly at an identity. `resolve_material(product_name, grade=, lot=)`
returns a `ResolvedMaterial` (assay per nutrient, basis, band ends, flags,
provenance). A grade or lot that names a different identity than the product is
rejected with `material_mismatch`.

## Document-reference rule

Every grade and lot needs a document reference: `supplier`, `title`, `issued`
(ISO date), `entered` (ISO date), optional `url`, optional `sha256`
(`DocumentReference`). A record without one is rejected with
`DeliveryError('missing_document_reference')`. Reference grades may name
commercial products with attribution (decision D3); they are examples, not
endorsements.

## Analysis basis

Analyses are elemental mass % keyed by form (`N_NO3`, `N_NH4`, `N_UREA`, `P`,
`K`, `Ca`, `Mg`, `S`, `Fe`, `Mn`, `Zn`, `Cu`, `B`, `Mo`, `Na`). Oxide input
(`P2O5`, `K2O`, `CaO`, `MgO`, `SO3`) is converted at load, with factors computed
from the atomic masses in `composition.ATOMIC`; each factor is recorded in the
provenance. Total `N` is accepted on a grade and split by the identity's
theoretical form ratio. A maximum-only analysis key is rejected, because a
maximum is not an assay.

| Available | Value used | Basis recorded | Flag |
|---|---|---|---|
| Lot certificate | Measured value | `lot_measured` | |
| Grade typical | Typical | `grade_typical` | |
| Grade minimum only | Minimum | `grade_minimum` | `lower_bound_grade_assay` |
| Identity only | Theoretical analysis | `identity_theoretical` | |
| Shipped catalogue analysis | Catalogue value | `declared_catalogue` | |

Selection follows the table, per nutrient. Other flags:

- `identity_inconsistent`: the grade's charge residual exceeds 0.1 %, or its
  range excludes the identity's theory. The range test is skipped for
  `aqueous_solution` and `chelate_salt_defined` identities, whose theory is
  the pure compound rather than the product as sold (a 75 % phosphoric acid
  at P2O5 54.0–54.6 % or an Fe-EDTA at Fe 12.8–13.2 % is not flagged); the
  charge-residual test still applies to them. Chemistry stages then apply the
  existing assay-residual rule; nothing is rejected silently.
- `lot_outside_grade_range`: a lot measured outside the grade's minimum or
  maximum, with no uncertainty stated. The certificate value is used and the
  band end is widened to include it (grade N-NO3 13.5–13.9 % with a lot at
  14.3 % gives the band 13.5–14.3 %).
- `blend_analysis_unreconciled`: see disclosed blends below.
- `assumed_composition`: a project-assumed blend, such as the pre-owner catalogue's
  CH - micro. The packaged Micro Combi Mix 1 and 2 are owner-declared blends and do
  not carry it.

## Nitrogen forms in a formula

A formula declares nitrogen by form: `N_NO3` (nitrate-N), `N_NH4` (ammonium-N) and
`N_UREA` (urea-N), each in mg/L as N. Each declared form is its own target and is fitted
on its own (decision D1). Total N is the sum of the three forms; it is reported as
`totalN` (target, final and difference), never fitted.

- `N_NO3` is fitted to its declared value.
- `N_UREA` absent means 0: a declared zero, met within 1e-6 mg/L. A urea-bearing
  product is then not used.
- `N_NH4` above 0 is fitted to its declared value. `N_NH4` absent or 0 is no
  ammonium requirement: there is no ammonium row and no ban, so products such as
  calcium nitrate, which carries a little ammonium, stay usable.

**Ammonium allowance.** When the formula declares no ammonium (`N_NH4` absent or 0)
and no ammonium maximum is given, the ammonium the products bring with them may reach
min(10 % of the total target N, 1.5 mmol/L NH4 = 21.01 mg/L N). The basis is Dutch
soilless practice (De Kreij, Voogt et al.): ammonium at 5–15 % of total N, at most
1–1.5 mmol/L. The allowance is shown with that basis in `ammoniumLimit`, on the batch
summary, the report and the sheets. For Cucumber (Howard Resh), N_NO3 140 and N_NH4 0,
the allowance is min(14, 21.01) = 14 mg/L. A declared `N_NH4` maximum replaces it.

## When a target is met

A target is met only within the precision of the calculation (decision G25): the final
value must be within 1e-5 of the target, relative (0.001 %), for a positive target, and
within 1e-6 mg/L for a declared zero; a pH is met within 1e-4 pH units. These are
numerical tolerances, validated on 2026-10-24, not agronomic ranges. They replace the
former ±1 % band.

Anything beyond them is a deviation, and every deviation is reported: the row's
difference, `unmetTargets` with its reason, and the formulation stage, which then
reads "targets missed: …" and asks for review. A missed target does not block the
recipe; only a broken declared maximum does. For Lettuce 2 (Howard Resh) with water
free of nutrients, P finishes at 49.84 mg/L for 50 (-0.323 %): under the former band
that counted as met, now it is listed.

## Using materials in calculations

`catalogue_dose_totals(..., materials=)` and `calculate_irrigation_ec(...,
materials=)` accept a mapping of product name to `ResolvedMaterial`. The
provenance (identity, grade and lot ids, documents, basis, flags, identities
hash) appears in the irrigation EC audit and in `plan_equilibrium_delivery`
audits; `calculate_irrigation_ec_from_plan` copies the plan's `materials` and
`identitiesSha256` into its own audit.

A resolved grade or lot is not the shipped product, so its `record['id']` is
distinct: `<catalogue id>+<grade_id>`, `<catalogue id>+<grade_id>+<lot_id>`,
or `<catalogue id>+lot:<lot_id>` for a lot without a grade. `record['name']`
stays the shipped product name. To formulate with a grade or blend, pass
`resolved.record` in the product list given to `recommend`. That recipe's
chemistry goes through `calculate_irrigation_ec(..., materials=)`.
`plan_equilibrium_delivery` accepts shipped catalogue products only: a recipe
carrying a resolved record fails closed with `product_chemistry_mismatch`
instead of silently using the shipped assay.

A blend grade (no identity) records `identityId: None` and
`hostProduct` (the catalogue name it is dosed under) in its provenance, and
its record has `formula: None`, so the host product's formula is never
checked against the blend's analysis.

## Delivered-nutrient band

`nutrient_band(doses_g_per_litre, materials=)` re-evaluates the *same* doses
with the nominal and band-end assays (mg/L = g/L x % x 10). The solver is never
re-run, and chemistry (pH, precipitation, EC) is reported at the nominal assay
only. A lot with stated uncertainty gives its own band; otherwise the grade's
minimum and maximum apply. An open bound (a grade with a minimum only) gives
`None` for that end. FlahaX shows the band; it does not pick a "safe" end.
For pH, precipitation and EC at the band ends, use `calculate_irrigation_ec_band`
(below).

## Undisclosed blends

A grade with `composition: "undisclosed"` has a declared analysis but unknown
ingredients and counterions.

- Mass balance (formulation) works: the declared analysis supplies nutrients.
- Any chemistry call (speciation, pH, precipitation, EC) with such a blend in
  the mix raises `DeliveryError('composition_undisclosed')`;
  `calculate_irrigation_ec` reports `not_supported` /
  `composition_undisclosed`. The blend is never dropped while the rest is
  computed.
- A `disclosed` blend lists component identities with proportions and
  proceeds through chemistry normally. Its declared analysis is reconciled
  with the components: for each declared nutrient, implied % = sum of mass
  fraction x the component's shipped catalogue assay. If |implied − declared|
  exceeds max(5 % of declared, 0.05 % points) for any nutrient, the material
  gets `blend_analysis_unreconciled` and the implied analysis is recorded in
  provenance (`blendImpliedAnalysis`). The blend is never rejected for this;
  the flag reaches the irrigation EC audit.
- An undisclosed blend is accepted by `recommend` (its record) and by
  `nutrient_band`.

(decisions)=
## Catalogue composition assumptions

- **D1:** Mg Nitrate is Mg(NO3)2.6H2O theoretical (N 10.93 %, Mg 9.48 %).
- **D2:** Chelates are their defined sodium salts (Fe-EDTA 1, Mn/Zn/Cu-EDTA 2,
  Fe-DTPA 2, Fe-o,o-EDDHA 1 sodium per formula unit). Sodium enters chemistry
  totals only; it is not added to formulation `elements`, because Na is a
  restricted ion there. The owner-declared Micro Combi Mix 1 and 2 chelates carry
  the same sodium.
- **D3:** Reference grades may name commercial products with attribution and a
  document reference.

Phosphoric Acid (75%) now lists P 23.71 % (75 % w/w, dosed by product mass) and
borax carries the Na2B4O7.10H2O ion forms.

## Example

A data-sheet grade (stated as K2O) and a lot certificate, resolved and used in
`nutrient_band`:

```python
from flahax import make_grade, make_lot, resolve_material, nutrient_band

doc = {"supplier": "Example Fertilisers Ltd", "title": "Potassium nitrate TDS rev 3",
       "issued": "2026-03-01", "entered": "2026-10-19"}
grade = make_grade({
    "grade_id": "example-kno3-tds", "identity_id": "idn-potassium-nitrate",
    "supplier": "Example Fertilisers Ltd", "product": "KNO3 crystal", "document": doc,
    "analysis": {"N_NO3": {"minimum": 13.5, "typical": 13.85, "maximum": 13.9},
                 "K2O": {"minimum": 45.5, "typical": 46.6, "maximum": 46.8}},
})
lot = make_lot({
    "lot_id": "L-2026-0412", "grade_id": "example-kno3-tds",
    "document": {"supplier": "Example Fertilisers Ltd", "title": "CoA lot L-2026-0412",
                 "issued": "2026-09-30", "entered": "2026-10-19"},
    "measured": {"N_NO3": 13.85},
})
material = resolve_material("Potassium Nitrate", grade=grade, lot=lot)
print("basis:", material.basis)
print("flags:", material.flags)
band = nutrient_band({"Potassium Nitrate": 0.5}, materials={"Potassium Nitrate": material})
for key, row in band["nutrients"].items():
    print(key, row)
print(band["note"])
```

Output:

```text
basis: {'N_NO3': 'lot_measured', 'K': 'grade_typical'}
flags: ()
N_NO3 {'nominal_mg_per_l': 69.25, 'minimum_mg_per_l': 67.5, 'maximum_mg_per_l': 69.5}
K {'nominal_mg_per_l': 193.4252534088641, 'minimum_mg_per_l': 188.8594212468523, 'maximum_mg_per_l': 194.25540471104807}
Band applies to nutrient amounts only; chemistry is reported at the nominal assay.
```

The lot supplies N-NO3 (`lot_measured`); K comes from the grade typical. The
lot gave no uncertainty, so the band is the grade's minimum to maximum.

## Provenance, counterion sodium and band-end chemistry

**Provenance on formulation results.** `recommend` results (and so the
workflow recommendation) attach `provenance` to every salt entry: `recordId`,
`identityId`, `analysisBasis`, `documents` and `flags`, taken from the record
that produced the salt. A record without provenance reports
`analysisBasis: "unattributed"`; a basis is never guessed. `analysisBasis` is a
string for shipped records and a per-nutrient dict for resolved materials. The
result also carries `identitiesSha256`, which pins the shipped catalogue.
`solve_weights` and `forward` use the shared nutrient inventory.

**Counterion sodium in formulation rows.** Supported formula counterion sodium
not already assayed as elemental Na (chelate sodium and the molybdate sodium of
the Micro Combi blends) enters the matrix before fitting. It affects the selected doses
and the resulting Na row, including a supplied Na target or maximum. The source
`elements` and existing eligibility/permission policy remain unchanged. A warning
identifies the selected products' counterion sodium contribution.

**Chemistry at the band ends.** `calculate_irrigation_ec_band` takes the
arguments of `calculate_irrigation_ec` and returns `nominal`, `minimum` and
`maximum` results (each with its own pH, warnings and EC) plus a `note`. The
minimum end sets every dosed product to its band minimum and the maximum end
to its band maximum.

- The ends are corner cases (every product at its minimum, or every product at
  its maximum), not statistical bounds.
- A non-proportional grade (nutrients that do not move together) can leave an
  end charge-unbalanced, so that end returns `assay_charge_residual_too_large`.
- Each end's `audit['materials']` shows the nominal provenance; `audit['band_end']`
  tells which end it is.
- An end where any dosed product has an open band end (a shipped product has
  none) returns `not_supported` / `band_end_open`. Nothing is substituted.

```python
from flahax import make_grade, resolve_material, calculate_irrigation_ec_band
from flahax.irrigation_ec import DeclaredPureWater

doc = {"supplier": "Example Fertilisers Ltd", "title": "Potassium nitrate TDS rev 3",
       "issued": "2026-03-01", "entered": "2026-10-19"}
grade = make_grade({
    "grade_id": "example-kno3-tds", "identity_id": "idn-potassium-nitrate",
    "supplier": "Example Fertilisers Ltd", "product": "KNO3 crystal", "document": doc,
    "analysis": {"N_NO3": {"minimum": 13.8, "typical": 13.85, "maximum": 13.9},
                 "K2O": {"minimum": 46.4, "typical": 46.6, "maximum": 46.8}},
})
material = resolve_material("Potassium Nitrate", grade=grade)
band = calculate_irrigation_ec_band(
    {"Potassium Nitrate": 0.5}, materials={"Potassium Nitrate": material},
    recipe_id="band-example", water=DeclaredPureWater("ro-1"),
    ph_mode="calculated", phase_policy="dissolved")
for end in ("minimum", "nominal", "maximum"):
    r = band[end]
    print(end, r.status, r.ec25_ms_cm, r.ph, r.audit.get("band_end"))
print(band["note"])
```

Output:

```text
minimum estimated 0.6892812265428483 6.515030771493912 minimum
nominal estimated 0.6924419215785783 8.454879373311996 None
maximum estimated 0.6957751961226507 8.77560493350029 maximum
Band ends are corner cases (every product at its minimum, or every product at its maximum), not statistical bounds.
```

In unbuffered pure water the pH follows the assay charge residual, so the small
residual differences between the ends move pH strongly (6.52, 8.45 and 8.78
here). This is not a buffered-solution prediction.

## Check material contributions before fitting

The fit includes supported formula counterions, including chelate sodium. Inspect
`recommend(...)["materialInventory"]` to see each selected material's assay,
derived nutrients, conserved components and limitations. For a source record,
use `material_inventory(record)`; supply `material=resolved` for a resolved
supplier grade or lot. Check `assay_component_difference_percent` when a blend's
label and ingredients disagree. An `assay_only` result cannot qualify chemistry.
See the [inventory contract](../models/material-inventory.md).
