# Traceable material catalogue: design

Status: design for owner review, 2026-10-18. Nothing here is implemented.
Evidence: the [materials identity audit](../../audit/2026-10-18-materials-identity/review.md)
and its [CSV](../../audit/2026-10-18-materials-identity/data/materials-audit.csv).

## 1. Intent

Every number FlahaX calculates with can be traced to a **chemical identity**
and a **source document**.

**Position (owner's wording):** Catalogue size does not measure chemical
coverage or model accuracy. FlahaX's chemistry approach uses explicit
chemical identities and composition assumptions. Its raw-material catalogue
should distinguish chemical identity from supplier grade and batch assay,
with traceable specifications and impurity information. Multiple commercial
products may represent the same underlying chemical source.

A factory blend has a declared nutrient analysis, but its exact ingredients,
proportions, counterions or additives may be incomplete or undisclosed. Some
manufacturers do disclose ingredients, so this varies by product.

### Why now
- The 2026-10-17 benchmark scored Horticalc's 253 commercial products
  against FlahaX's 28 as a library win. The answer is traceability, not
  count.
- The materials audit found that none of the 28 products has a supplier
  grade or batch assay. It also found four data errors that change recipe
  numbers (section 7).
- The irrigation EC module's assay charge residual independently flags the
  same products. Products the audit marks consistent all pass, and every
  named identity problem fails.

## 2. Goals, non-goals, anti-goals

**Goals**
- Three explicit layers: identity, grade and lot.
- Every calculation records which layer and which value supplied each
  assay: its **analysis basis**.
- Technical-data-sheet ranges produce a delivered-nutrient band.
- Factory blends with undisclosed composition are usable for mass balance
  and refused for chemistry, with a stated reason.
- Fix the identity-level data errors the audit found, with regression
  evidence.

**Non-goals**
- A large commercial product database shipped with FlahaX.
- Storing user grades or lots inside FlahaX. The library stays stateless:
  records are passed in, as water analyses and pump calibrations already are.
- Price, availability or supplier recommendation.
- In the first release, chemistry (pH, precipitation, EC) evaluated at both
  ends of the band (section 6).

**Anti-goals**
- A supplier's typical value silently presented as a measured lot value.
- A reference comparator (Sigma, Merck and similar) presented as the
  material the grower bought.
- A blend's declared analysis turned into invented ingredients or
  counterions.
- A data correction that changes recipe numbers without a changelog entry
  and regression evidence.

## 3. The three layers

| Layer | Holds | Source document | Shipped? |
|---|---|---|---|
| **Identity** | Name, formula, hydration, molecular weight, CAS, ion forms in water (including counterions), comparator reference, audit status | Reference material (audit comparators) | Yes |
| **Grade** | Owning identity, or a blend declaration; supplier and product name; typical, minimum and maximum analysis; impurity limits; concentration basis for liquids (w/w, density versus temperature) | **Technical data sheet** | A few reference grades only; users supply their own |
| **Lot** | Owning grade, lot number, measured assay, certificate uncertainty if stated, date | **Certificate of analysis** | No; user supplied |

- A grade belongs to exactly one identity, unless it is a blend. A lot
  belongs to exactly one grade. Many grades may share one identity.
- **Document reference** on every grade and lot: supplier, document title
  or id, issue date, URL if public, file SHA-256 if available, and the date
  entered. A record without a document reference is rejected.
- **Blend grade:** a declared analysis, plus either a list of disclosed
  component identities with proportions (`composition: "disclosed"`) or
  `composition: "undisclosed"`.

## 4. How a calculation picks its assay

| Available | Value used | Analysis basis recorded |
|---|---|---|
| Lot certificate | Measured lot value | `lot_measured` |
| Grade with typical value | Typical | `grade_typical` |
| Grade with minimum only | Minimum, flagged "lower-bound grade assay" | `grade_minimum` |
| Identity only | Theoretical analysis from the formula | `identity_theoretical` |

- The existing 28 catalogue analyses become reference grades with basis
  `declared_catalogue` until each is replaced or confirmed. This keeps
  current behaviour until a reviewed change says otherwise.
- The basis appears per product in the audit record of every formulation,
  equilibrium, delivery and EC result.

## 5. Undisclosed blends

- **Mass balance (formulation):** allowed. The declared analysis supplies
  nutrients.
- **Speciation, pH, precipitation, EC and stock compatibility:**
  `not_supported` / `composition_undisclosed`, never a number. This follows
  the existing rule that FlahaX does not invent counterions.
- A disclosed blend is expanded into its component identities, and
  chemistry proceeds normally.
- CH - micro becomes an explicitly labelled **project-assumed blend**. Its
  current EDTA, borax and molybdate composition is kept as a disclosed
  composition marked `assumed`, so results that use it carry that label.

## 6. Delivered-nutrient band (first release)

- **Nominal recipe:** computed from the selected value (section 4).
- **Band:** the minimum and maximum grade values (lot uncertainty, where
  given) produce a per-nutrient delivered range in mg/L. Example:
  "N-NO₃ 180 mg/L nominal, 172–184 mg/L across the guaranteed range".
- **Grade gives only a minimum:** the band is open above: "≥ 180 mg/L".
- **Chemistry at the band ends** (pH, precipitation, EC) is deferred
  *(designer's call)*. The nominal chemistry is reported with a note that
  the band applies to nutrient amounts only.
- **No choice of a "safe" end:** FlahaX shows the band, and the grower or
  agronomist decides.

## 7. Identity-level data corrections (from the audit)

Each correction changes numbers. Each gets its own commit, a changelog
entry, and a before/after regression on the shipped formulas.

| Product | Problem | Correction |
|---|---|---|
| Phosphoric Acid (75%) | P 31.61 % is the pure-acid value | Identity H₃PO₄; reference grade "75 % w/w" with P ≈ 23.71 %; concentration basis and density required for volume dosing |
| Borax | Declared as Na⁺ + B(OH)₃, leaving sodium unbalanced (+100 % charge residual) | Ion forms per Na₂B₄O₇·10H₂O: 2 Na⁺ + 2 B(OH)₄⁻ + 2 B(OH)₃ |
| Mg Nitrate | Formula is anhydrous; analysis looks hydrated; N:Mg ratio fits neither | **Owner decision D1** |
| Six chelates | No counterions; metal % is a grade assay | Identity names the salt form (for example NaFeEDTA, Na₂ZnEDTA). The catalogue % becomes a reference grade. Counterions per **owner decision D2** |
| Iron II Sulfate, Urea, Potassium Citrate | Name typo, formula text, hydration not explicit | Metadata fixes. The old name stays as an alias, because code uses exact names |
| Calcium Nitrate (ag grade) | Commercial analysis, not the ideal double salt | Identity: ammonium calcium nitrate double salt. Reference grade carries the attributed commercial analysis (Haifa Cal NG typical) |

## 8. Audit and provenance

Each result's audit gains, per product, the identity id, grade id and lot
id (when used), analysis basis, document reference and catalogue file
SHA-256 (identities and reference grades). The materials audit CSV stays
the evidence for the shipped identities. Changing an identity requires an
update to that evidence.

## 9. Compatibility

- Existing product names keep resolving: each becomes an alias to its
  identity plus its reference grade.
- Existing public functions keep their signatures. New optional parameters
  accept user grades and lots.
- Results whose numbers change because of section 7 are listed in the
  changelog with before and after values for the shipped formulas.

## 10. Owner decisions (decided 2026-10-18)

| Id | Decision |
|---|---|
| D1 | **Mg Nitrate becomes pure Mg(NO₃)₂·6H₂O** (N 10.93 %, Mg 9.48 %, theoretical). The current N 11 / Mg 9.65 analysis is retired with its before/after values recorded. |
| D2 | **Chelates are their defined sodium salts:** NaFeEDTA, Na₂MnEDTA, Na₂ZnEDTA, Na₂CuEDTA. For Fe-DTPA and Fe-o,o-EDDHA, the sodium salt that balances the ligand charge (Na₂FeDTPA, NaFeEDDHA). The catalogue metal % stays as the reference-grade assay. Sodium enters the chemistry totals as a declared counterion, so pH, precipitation and EC keep working and account for it. *(Designer's call:)* the formulation solver's `elements` are not given Na, because Na is a restricted ion there and adding it would exclude every chelate by default. Reporting chelate sodium in formulation rows is a follow-up. |
| D3 | **Shipped reference grades may name commercial products with attribution** (for example Haifa Cal NG for calcium nitrate, Yara Rexolin Q48 for Fe-EDDHA), with the data sheet's document reference. They are examples, not endorsements. |

## 10a. Designer's calls (owner may override)

- **Band:** a re-evaluation of the *same* doses with the band-end assays.
  The solver is not re-run. Each product's band end is applied
  independently per nutrient form, and contributions add linearly. If a
  grade states only total N, the form split comes from the identity's
  theoretical ratio, recorded as such.
- **Analysis units:** stored as elemental mass % keyed by form (`N_NO3`,
  `N_NH4`, `N_UREA`, `P`, `K`, ...), the library's existing convention. Grade
  input may be given as oxides (P₂O₅, K₂O, CaO, MgO, SO₃). It is converted at
  load with the factor recorded in the grade record.
- **Grade checked against identity:** load accepts the grade and computes its
  declared-form charge residual and its deviation from the identity's
  theoretical analysis. Residual > 0.1 % or deviation beyond the grade's own
  min–max range sets a recorded `identity_inconsistent` flag. Chemistry
  stages then apply the existing O5 rule; nothing is rejected silently.
- **Lot without a data sheet:** a lot may point directly at an identity. Its
  certificate of analysis is its document reference.
- **Phosphoric acid:** mass dosing only in this work. Volume dosing with
  density versus temperature stays with the existing reagent-delivery path.
  Golden-value tests that change are updated in the same commit as the
  correction, with before/after values in `CHANGELOG.md`.
- **Ids:** the 28 existing cuids stay as the ids of the reference grades.
  Identities get new ids. Product names stay resolvable, so recipe hashes
  built from names (for example `plan-recipe:`) do not change.
- **Hashes:** `catalogueSha256` keeps hashing `library.json`, which remains
  the reference-grade file. A new `identitiesSha256` covers the identity file.
- **Undisclosed blend in a mix:** the whole chemistry result is
  `not_supported` / `composition_undisclosed`. The blend is never dropped
  while the rest is computed. Formulation still runs.
- **Impurity limits:** stored as metadata and reported. They do not enter
  calculations in this work.

## 11. Left to the builder

File layout and JSON schema of identity, grade and lot records; the
validation error codes; the alias mechanism; how the band is attached to
existing result types.

## 12. Follow-ups (addendum, 2026-10-19)

The three follow-ups listed below are now in scope. These are designer's
calls, made for owner review.

**F1. Provenance on formulation results.** Each entry in `recommend()`'s
`salts` list gains `provenance`: `recordId`, `identityId`, `analysisBasis`
(the per-nutrient `basis` for resolved materials), `source` or the
document references, and `flags`. Shipped records take these from
`library.json`. Resolved materials carry them in `record['provenance']`,
which `resolve_material` now sets. A record with neither is recorded as
`analysisBasis: "unattributed"`, never guessed. The `recommend` result also
gains `identitiesSha256`. `forward()` stays a pure mapping of achieved
nutrients, because its inputs are the caller's own records. Documented, not
changed.

**F2. Chelate sodium in formulation rows.** After the fit, `recommend` adds
the D2 chelate sodium for the chosen doses to the `Na` row and to
`incidentalContributions`. It is computed with the same counterion rule as
the chemistry, treating dose g/L as g/kg water for this report only. It
never enters eligibility or the fit, so Na stays a restricted ion and
chelates stay eligible. A warning line names the sodium source.

**F3. Chemistry at the band ends.** `calculate_irrigation_ec_band(...)` has
the same inputs as `calculate_irrigation_ec`. It returns `nominal`,
`minimum` and `maximum` results, each a full `IrrigationECResult` with pH,
supersaturation warnings and EC.
- The minimum end sets **every** product to its band minimum, and the
  maximum end sets every product to its band maximum. These are corner
  cases, not statistical bounds, and the docs say so.
- If any dosed product has an open band end, that end returns
  `not_supported` / `band_end_open`. It is never computed from a
  substituted value.
- Each end's audit records which end it is.

## Related, out of scope

- Chemistry evaluated at band ends (pH, precipitation, EC).
- A methods-article section on traceable materials, after this ships.
