# Traceable materials: identity, grade and lot

Every number FlahaX calculates with can be traced to a **chemical identity**
and a **source document**. Design: [traceable catalogue
design](superpowers/specs/2026-10-18-traceable-catalogue-design.md). Evidence:
[materials identity audit](audit/2026-10-18-materials-identity/review.md).

**Position (owner's wording):** Catalogue size does not measure chemical
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
`identity_inconsistent` (the grade's charge residual exceeds 0.1 % or its range
excludes the identity's theory; chemistry stages then apply the existing
assay-residual rule, nothing is rejected silently) and `assumed_composition`
(the shipped CH - micro project-assumed blend).

## Using materials in calculations

`catalogue_dose_totals(..., materials=)` and `calculate_irrigation_ec(...,
materials=)` accept a mapping of product name to `ResolvedMaterial`. The
provenance (identity, grade and lot ids, documents, basis, identities hash)
appears in the irrigation EC audit and in `plan_equilibrium_delivery` audits.

## Delivered-nutrient band

`nutrient_band(doses_g_per_litre, materials=)` re-evaluates the *same* doses
with the nominal and band-end assays (mg/L = g/L x % x 10). The solver is never
re-run, and chemistry (pH, precipitation, EC) is reported at the nominal assay
only. A lot with stated uncertainty gives its own band; otherwise the grade's
minimum and maximum apply. An open bound (a grade with a minimum only) gives
`None` for that end. FlahaX shows the band; it does not pick a "safe" end.

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
  proceeds through chemistry normally.

## Decisions

- **D1:** Mg Nitrate is Mg(NO3)2.6H2O theoretical (N 10.93 %, Mg 9.48 %).
- **D2:** Chelates are their defined sodium salts (Fe-EDTA 1, Mn/Zn/Cu-EDTA 2,
  Fe-DTPA 2, Fe-o,o-EDDHA 1 sodium per formula unit). Sodium enters chemistry
  totals only; it is not added to formulation `elements`, because Na is a
  restricted ion there. CH - micro's assumed chelates carry the same sodium.
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

## Follow-ups (not in this release)

- Provenance on `recommend` and forward formulation results.
- Reporting chelate sodium in formulation rows.
- Chemistry (pH, precipitation, EC) at the band ends.
