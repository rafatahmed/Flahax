# Traceable Material Catalogue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the catalogue into chemical identity, supplier grade and batch lot. Record the analysis basis of every assay. Add a delivered-nutrient band. Refuse chemistry for undisclosed blends. Apply the audit's data corrections (Mg Nitrate, phosphoric acid, chelate sodium, borax declared form).

**Architecture:**
- **Identities:** a new shipped file `material_identities.json` holds the 28 identities plus the CH - micro assumed blend. `library.json` products become reference grades linked by `identityId`, with an `analysisBasis` and a document reference.
- **One new module:** `materials.py` loads identities, validates user `Grade`/`Lot` records, resolves which assay to use, and computes the band.
- **Opt-in:** `catalogue_dose_totals` and `calculate_irrigation_ec` gain an optional `materials` mapping, so user grades and lots flow into chemistry. With no mapping, existing behaviour is unchanged.
- **Chemistry corrections:** chelate sodium is added in `product_conversion.convert_product_dose`.

**Tech Stack:** Python 3.13, standard library only, `unittest`. PHREEQC 3.8.6 is installed locally at `%TEMP%/flahax-phreeqc/installed/phreeqc-3.8.6-17100-x64` and is used only if a product fixture must be recaptured.

**Spec:** [docs/superpowers/specs/2026-10-18-traceable-catalogue-design.md](../specs/2026-10-18-traceable-catalogue-design.md)

## Global Constraints

- No new runtime dependency; FlahaX stays stateless (no storage of user grades/lots).
- Layers: identity (shipped), grade (data sheet), lot (certificate). A lot may point at a grade or directly at an identity.
- Every grade and lot needs a document reference: `supplier`, `title`, `issued` (ISO date), optional `url`, optional `sha256`, `entered` (ISO date). Without one the record is rejected with `DeliveryError('missing_document_reference')`.
- Assay selection order and recorded basis: `lot_measured` > `grade_typical` > `grade_minimum` (flag `lower_bound_grade_assay`) > `identity_theoretical`. Shipped catalogue analyses not yet confirmed have the basis `declared_catalogue`.
- Analyses are elemental mass % keyed by form (`N_NO3`, `N_NH4`, `N_UREA`, `P`, `K`, `Ca`, `Mg`, `S`, `Fe`, `Mn`, `Zn`, `Cu`, `B`, `Mo`, `Na`). Oxide input (`P2O5`, `K2O`, `CaO`, `MgO`, `SO3`) is converted at load, and each factor is recorded.
- Band: re-evaluate the *same* doses with band-end assays; never re-solve. Open bound → `None`.
- Undisclosed blend in any chemistry call → `DeliveryError('composition_undisclosed')`. `calculate_irrigation_ec` maps it to `not_supported` / `composition_undisclosed`. Formulation still works.
- D1: Mg Nitrate becomes Mg(NO₃)₂·6H₂O theoretical (`N_NO3` 10.92564, `Mg` 9.47931; formula `Mg(NO3)2.6H2O`).
- D2: chelate sodium counterions per formula unit: Fe-EDTA 1, Mn/Zn/Cu-EDTA 2, Fe-DTPA 2, Fe-o,o-EDDHA 1. Applied in chemistry totals only, never added to `elements`, because Na is a restricted ion in formulation. CH - micro's assumed chelates get the same sodium.
- D3: reference grades may name commercial products with attribution and a document reference.
- Product `name` and `id` values for the 28 products never change (they are keys). Corrected display text goes in a new `displayName`.
- `catalogueSha256` keeps hashing `library.json`; new `identitiesSha256` hashes `material_identities.json`.
- Every change that alters recipe numbers gets a `CHANGELOG.md` before/after line. Changed golden tests are updated in the same commit as the change that moves them.
- Work on branch `feat/traceable-catalogue`, cut from `feat/irrigation-ec-m1`. Stage only the files each task names.

## Review Focus

1. **A user grade with oxide input and no typical value (minimum only).** Expect basis `grade_minimum`, flag `lower_bound_grade_assay`, and a band open above. Pinned in Task 2.
2. **A lot with a measured value for only some nutrients.** For example, a CoA giving N only for a calcium nitrate grade. Expect the unmeasured nutrients to fall back to the grade's typical value, with per-nutrient basis recorded, not dropped. Pinned in Task 2.
3. **`materials` naming a product the recipe doesn't use, or a resolved material whose identity differs from the product name.** Expect `DeliveryError('material_mismatch')`. Pinned in Task 5.
4. **Phosphoric acid dosed with a recipe written before the correction.** Expect the same grams to deliver about 25 % less P, stated in the changelog. Pinned in Task 3's regression test.
5. **Chelate recipes in calculated-mode EC after D2.** Expect the declared charge residual within 0.1 %, so the result is no longer `not_supported` for that reason. Pinned in Task 4.

---

### Task 0: Branch and commit the inputs

- [ ] **Step 1:** `git switch -c feat/traceable-catalogue` from `feat/irrigation-ec-m1`.
- [ ] **Step 2:** Commit the materials audit, the review edits and the design:

```bash
git add docs/audit/2026-10-18-materials-identity docs/audit/README.md docs/audit/2026-10-17-flahax-vs-horticalc/review.md docs/superpowers/specs/2026-10-18-traceable-catalogue-design.md docs/superpowers/plans/2026-10-18-traceable-catalogue.md
git commit -m "Add materials identity audit and traceable catalogue design and plan"
```
Expected: one commit. README, the publication drafts, the SWOT doc and `outputs/` stay unstaged.

---

### Task 1: Identity file and loader

**Files:**
- Create: `src/flahax/data/material_identities.json`
- Create: `src/flahax/materials.py` (identity part)
- Create: `tests/fixtures/materials/audit_theory.json` (copied from the audit CSV's `catalogue_formula_theory` and `alternative_theory` columns)
- Test: `tests/test_materials.py` (class `IdentityTests`)

**Interfaces:**
- Produces:
  - `load_identities() -> dict` keyed by identity id (cached).
  - `IDENTITIES_SHA256: str`.
  - `identity_for_product(name: str) -> dict`, which raises `DeliveryError('unknown_product')`.
  - `IDENTITY_STATUSES = frozenset({'identity_consistent', 'chelate_salt_defined', 'commercial_double_salt', 'aqueous_solution', 'assumed_blend'})`.

**Identity record keys** (all required unless noted):
- `id`: a new id `idn-<slug>`, for example `idn-potassium-nitrate`.
- `products`: the catalogue product names it covers.
- `name`, `formula`, `hydration`, `molecular_weight` (number or `null` for blends and solutions), `cas` (string or `null`).
- `ion_forms`: dissolved components with stoichiometry per formula unit, for example `{"K+": 1, "NO3-": 1}`. For NaFeEDTA: `{"Na+": 1, "Fe(III)-EDTA": 1}`. For borax: `{"Na+": 2, "B(OH)4-": 2, "B(OH)3": 2}`.
- `theoretical_analysis`: from `composition.theoretical_assay(formula)` where it parses; otherwise taken from the audit.
- `comparator`: `{product, url, accessed}`, taken from the audit CSV.
- `status`: one of `IDENTITY_STATUSES`.
- `notes`.

Identity choices: Mg Nitrate maps to Mg(NO₃)₂·6H₂O (D1). Chelates map to the sodium salts in D2. Phosphoric acid maps to H₃PO₄ with status `aqueous_solution`. Calcium nitrate maps to `5Ca(NO3)2.NH4NO3.10H2O` with status `commercial_double_salt`. CH - micro gets status `assumed_blend`, with `ion_forms` listing its assumed chelates, borax and molybdate.

- [ ] **Step 1: Write failing tests**

```python
def test_every_catalogue_product_has_exactly_one_identity(self):
    names = [s['name'] for s in load_library()['salts']]
    covered = [p for i in load_identities().values() for p in i['products']]
    self.assertEqual(sorted(names), sorted(covered))

def test_theoretical_analysis_matches_independent_audit_values(self):
    audit = json.loads((FIXTURES / 'audit_theory.json').read_text())   # name -> {formula, analysis}
    for name, ref in audit.items():
        ident = identity_for_product(name)
        if ident['formula'] == ref['formula']:
            for key, value in ref['analysis'].items():
                self.assertAlmostEqual(ident['theoretical_analysis'][key], value, places=6, msg=(name, key))

def test_mg_nitrate_identity_is_hexahydrate(self):
    ident = identity_for_product('Mg Nitrate')
    self.assertEqual(ident['formula'], 'Mg(NO3)2.6H2O')
    self.assertAlmostEqual(ident['theoretical_analysis']['N_NO3'], 10.92564, places=4)

def test_ion_forms_are_charge_neutral(self):
    charges = {...}   # test-local table: Na+ 1, K+ 1, NH4+ 1, Ca+2 2, Mg+2 2, Fe+2 2, Cu+2 2, Zn+2 2, NO3- -1, SO4-2 -2,
                      # H2PO4- -1, HPO4-2 -2, CO3-2 -2, MoO4-2 -2, B(OH)4- -1, citrate -3, Fe(III)-EDTA -1,
                      # Mn-EDTA -2, Zn-EDTA -2, Cu-EDTA -2, Fe(III)-DTPA -2, Fe(III)-o,o-EDDHA -1; neutral: H3PO4, B(OH)3, CO(NH2)2
    for ident in load_identities().values():
        if ident['status'] == 'assumed_blend': continue
        self.assertEqual(sum(charges[c]*n for c, n in ident['ion_forms'].items()), 0, ident['id'])

def test_identities_file_is_pinned(self):
    self.assertEqual(IDENTITIES_SHA256, '<literal digest of the committed file>')
```

The `audit_theory.json` fixture is typed from the CSV's theory columns by the controller-dispatched transcriber, never generated by the implementer's code. Ammonium calcium nitrate (calcium nitrate) is exercised by the formula-equality branch.

- [ ] **Step 2: Run and confirm failure.** `PYTHONPATH=src python -m unittest tests.test_materials -v` gives an ImportError.
- [ ] **Step 3: Implement** the JSON and the loader. Load the JSON with `importlib.resources`, as `aqueous_model.chemistry()` does, and use `composition.theoretical_assay` to fill `theoretical_analysis` where it parses.
- [ ] **Step 4: Run and confirm pass.**
- [ ] **Step 5: Commit** `src/flahax/data/material_identities.json src/flahax/materials.py tests/fixtures/materials/audit_theory.json tests/test_materials.py` with the message "Add chemical identity records for the catalogue".

---

### Task 2: Grades, lots and assay resolution

**Files:**
- Modify: `src/flahax/materials.py`
- Test: `tests/test_materials.py` (class `GradeLotTests`)

**Interfaces:**
- Consumes: `load_identities`, `identity_for_product` (Task 1).
- Produces:
  - `DocumentReference` (frozen): `supplier`, `title`, `issued`, `entered`, `url=None`, `sha256=None`.
  - `Grade` (frozen): `grade_id`, `identity_id: str | None`, `supplier`, `product`, `typical: dict`, `minimum: dict`, `maximum: dict`, `impurity_limits: dict`, `composition: str` (`single` | `disclosed` | `undisclosed`), `components: tuple` (`(identity_id, mass_fraction)` pairs when disclosed), `oxide_conversions: dict`, `document: DocumentReference`, `flags: tuple`.
  - `Lot` (frozen): `lot_id`, `grade_id: str | None`, `identity_id: str | None`, `measured: dict`, `uncertainty: dict`, `document: DocumentReference`.
  - `make_grade(record: Mapping) -> Grade` and `make_lot(record: Mapping) -> Lot`. Both validate raw dicts.
  - `ResolvedMaterial` (frozen): `name`, `identity_id`, `record: dict` (library-compatible `id`/`name`/`formula`/`elements`), `basis: dict` (nutrient → basis string), `band_minimum: dict`, `band_maximum: dict` (open bound → key present with `None`), `composition: str`, `provenance: dict` (identity id, grade id, lot id, document references, `identitiesSha256`), `flags: tuple`.
  - `resolve_material(product_name: str, *, grade: Grade | None = None, lot: Lot | None = None) -> ResolvedMaterial`.

**Rules:**
- **Oxide factors** (elemental = oxide × factor), recorded in `oxide_conversions`: P₂O₅→P 0.436421, K₂O→K 0.830148, CaO→Ca 0.714701, MgO→Mg 0.603036, SO₃→S 0.400496. Compute them in code from atomic masses in `composition.ATOMIC` and assert the values above to 6 places in a test.
- **Required fields:** a `single` grade must name an `identity_id`. A `disclosed` blend must list `components` whose fractions sum to ≤ 1. An `undisclosed` blend has no components.
- **Lot linkage:** a lot must name a `grade_id` or an `identity_id`, not both. With a grade, the lot's `grade_id` must equal `grade.grade_id`, otherwise `DeliveryError('material_mismatch')`.
- **Per-nutrient assay selection:** use the lot's measured value; else the grade's typical; else the grade's minimum (flag `lower_bound_grade_assay`); else the identity's theoretical value. With no grade and no lot, the shipped `library.json` record is used, with basis taken from its `analysisBasis` (Task 3).
- **Band:** the minimum is the lot value − uncertainty, else the grade minimum, else `None`. The maximum is the lot value + uncertainty, else the grade maximum, else `None`. A nominal of `identity_theoretical` or `declared_catalogue` has `None` for both ends.
- **`identity_inconsistent` flag:** set when a grade's typical value (or minimum if no typical) lies outside the identity theoretical value ±0.1 % relative. Also set when the grade's own min–max range excludes the theoretical value. Recorded, never rejected.
- **Validation codes:** `missing_document_reference`, `invalid_value` (non-finite, negative, > 100 %), `invalid_composition`, `unknown_identity`, `material_mismatch`.

- [ ] **Step 1: Write failing tests:**
  - `test_oxide_factors`;
  - `test_grade_requires_document_reference`;
  - `test_minimum_only_grade_is_lower_bound` (Review Focus 1): a grade `{'P2O5': {'minimum': 52.0}}` on the MKP identity gives basis `grade_minimum`, flag `lower_bound_grade_assay`, `record['elements']['P']` ≈ 22.6939 and `band_maximum['P'] is None`;
  - `test_partial_lot_falls_back_per_nutrient` (Review Focus 2): a calcium nitrate grade with typical N_NO3 14.4 / N_NH4 1.1 / Ca 19 and a lot measuring only N_NO3 14.6 gives basis `{'N_NO3': 'lot_measured', 'N_NH4': 'grade_typical', 'Ca': 'grade_typical'}`;
  - `test_lot_against_identity_without_grade`;
  - `test_lot_grade_mismatch_raises`;
  - `test_identity_inconsistent_flag_on_old_mg_nitrate_analysis`: a grade typical of N_NO3 11 / Mg 9.65 on the hexahydrate identity is flagged;
  - `test_disclosed_blend_fractions_validated`;
  - `test_undisclosed_blend_has_composition_undisclosed`.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement** per the rules.
- [ ] **Step 4: Run and confirm pass.**
- [ ] **Step 5: Commit** `src/flahax/materials.py tests/test_materials.py` with the message "Add grade and lot records with per-nutrient assay resolution".

---

### Task 3: Migrate `library.json` to reference grades and apply data corrections

**Files:**
- Modify: `src/flahax/data/library.json`
- Modify: any test or example golden value moved by the corrections (discovered in Step 4)
- Modify: `CHANGELOG.md` (`## Unreleased`)
- Test: `tests/test_materials.py` (class `CatalogueMigrationTests`)

**Interfaces:**
- Each salt gains:
  - `identityId`;
  - `analysisBasis`: one of `declared_catalogue`, `identity_theoretical` or `grade_typical`;
  - `source`: a document reference dict or `null`;
  - `displayName`, which is optional.
- `id`, `name` and `elements` key spelling are unchanged.

**Data changes:**
- **Mg Nitrate:** formula `Mg(NO3)2.6H2O`; elements = identity theoretical (N_NO3 10.92564, Mg 9.47931); basis `identity_theoretical`.
- **Phosphoric Acid (75%):** P = 31.608046 × 0.75 = 23.706035; basis `declared_catalogue`; `source` null. `notes`: "75 % w/w aqueous solution; product-mass dosing".
- **Calcium Nitrate (ag grade):** elements unchanged; basis `grade_typical`; `source` set to the Haifa Cal NG technical data sheet (URL from the audit CSV, issued 2018-10).
- **Urea:** formula `CO(NH2)2`.
- **Iron II Sulfate (Hepahydrate):** `displayName` "Iron(II) Sulfate (Heptahydrate)".
- **Potassium Citrate:** `displayName` "Potassium Citrate (anhydrous)".
- **All other products:** basis `declared_catalogue`.

- [ ] **Step 1: Write failing tests:**
  - `test_every_salt_links_to_identity`;
  - `test_phosphoric_acid_is_75_percent_basis` (P ≈ 23.706035);
  - `test_mg_nitrate_uses_hexahydrate`;
  - `test_phosphoric_regression` (Review Focus 4): `catalogue_dose_totals({'Phosphoric Acid (75%)': 1.0})['PO4-3']` equals 0.75 × the pre-change value, captured as a literal in the test before the edit.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Edit `library.json`** per the data changes.
- [ ] **Step 4: Run the full suite.** `PYTHONPATH="src;." python -m unittest discover -s tests -t .`
  - List every failing test.
  - For each, confirm that the failure is caused only by the Mg Nitrate or phosphoric acid change.
  - Update the expected value, adding a comment `# 2026-10-18 catalogue correction (Mg Nitrate D1 / phosphoric 75 %)`.
  - Any failure not explained by those two changes: stop and report `DONE_WITH_CONCERNS`.
- [ ] **Step 5: CHANGELOG.** Under `## Unreleased`, add one line per correction with before/after analysis values. Add one line listing the shipped formulas whose recommended doses change, with old and new grams for Mg Nitrate and phosphoric acid in the pepper regression recipe, if it uses them.
- [ ] **Step 6: Run the full suite again; all OK.**
- [ ] **Step 7: Commit** `library.json`, the tests, the examples and `CHANGELOG.md` with the message "Link catalogue products to identities and correct Mg Nitrate and phosphoric acid".

---

### Task 4: Chelate sodium counterions and borax declared form

**Files:**
- Modify: `src/flahax/product_conversion.py` (`convert_product_dose`, `catalogue_dose_totals` mapping)
- Modify: `src/flahax/catalogue_chemistry.py` (chelate and borax `components` tuples)
- Modify: `src/flahax/irrigation_ec.py` (`assay_charge_residual` declared charges)
- Modify: PHREEQC product fixtures only if Step 4 requires it
- Test: `tests/test_product_conversion.py`, `tests/test_irrigation_ec.py`

**Rules:**
- **`convert_product_dose`:**
  - `edta_chelate`: `counterions['sodium']` = 1 × Fe + 2 × (Mn + Zn + Cu).
  - `dtpa_chelate`: 2 × Fe.
  - `eddha_chelate`: 1 × Fe.
  - `edta_borax_molybdate_blend`: the same chelate sodium added to the existing borax and molybdate sodium.
- **Chelate `components`** gain `"Na+"`, for example `("Na+", "Fe(III)-EDTA")`.
- **Borax:**
  - `components` become `("Na+", "B(OH)4-", "B(OH)3")`.
  - Equilibrium totals do not change: boron stays the `H3BO3` basis, and pH charge balance forms borate.
  - `assay_charge_residual` gives borax boron a declared charge of −0.5 per B.
- **`assay_charge_residual` chelates:** sodium counterions come from the conversion result, so chelate residuals fall to about 0.

Steps:
- [ ] **Step 1: Write failing tests:**
  - `test_chelate_sodium_counterions`, for example Iron EDTA 1 g/kgw → Na equals Fe moles, and Zn EDTA → 2 × Zn;
  - `test_borax_declared_residual_near_zero`;
  - `test_chelate_residuals_within_limit` (Review Focus 5): every chelate and CH - micro has |percent| ≤ 0.1, and calculated-mode `calculate_irrigation_ec({'Iron EDTA': 0.05, 'Potassium Nitrate': 0.5}, ...)` no longer has reason `assay_charge_residual_too_large`.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `tests.test_product_phreeqc` and the full suite.
  - **If product-fixture runtime equivalence fails** (water Na by difference turning negative, or residual checks failing):
    - recapture the affected cases with `tools/phreeqc_evidence.py` and the locally installed PHREEQC;
    - commit the regenerated fixtures;
    - record the recapture in the report.
  - **Other expected-value changes** caused by chelate sodium: update them with a comment, as in Task 3. Unexplained failures: `DONE_WITH_CONCERNS`.
- [ ] **Step 5: CHANGELOG** line: "Chelates now carry their sodium counterions in chemistry totals (D2); recipes with chelates show incidental Na in equilibrium and EC results".
- [ ] **Step 6: Commit** with the message "Declare chelate sodium counterions and the borax ion forms".

---

### Task 5: User materials in chemistry, undisclosed blends and provenance

**Files:**
- Modify: `src/flahax/product_conversion.py` (`catalogue_dose_totals`)
- Modify: `src/flahax/irrigation_ec.py` (`calculate_irrigation_ec`, `assay_charge_residual`, audit)
- Test: `tests/test_materials.py` (class `ChemistryUseTests`)

**Interfaces:**
- `catalogue_dose_totals(doses, *, materials: Mapping[str, ResolvedMaterial] | None = None)`. A product in `materials` is converted from `materials[name].record`, using the chemistry profile of its identity's catalogue product.
- `calculate_irrigation_ec(..., materials=None)` passes the mapping through, and adds `audit['materials']` = {name: provenance with per-nutrient basis} for every dosed product (shipped products use their `library.json` basis and `identityId`).
- `plan_equilibrium_delivery` adds the same `audit['materials']` for its shipped products, plus `identitiesSha256`. Its signature is unchanged.
- *(Planner's call, spec §8 partial:)* provenance on `recommend` and `forward` formulation results is out of scope here. `docs/materials.md` states it as a follow-up.

**Rules:**
- `materials` keys must be dosed product names, and each `ResolvedMaterial.name` must equal its key. Otherwise `DeliveryError('material_mismatch')` (Review Focus 3).
- A `ResolvedMaterial` with `composition == 'undisclosed'` raises `DeliveryError('composition_undisclosed')` in `catalogue_dose_totals`. `calculate_irrigation_ec` catches that code and returns `not_supported` / `composition_undisclosed`. Other codes propagate.
- A disclosed blend converts each component through its identity's catalogue chemistry, at dose × fraction.

Steps:
- [ ] **Step 1: Write failing tests:**
  - `test_user_lot_changes_chemistry_totals`: a calcium nitrate lot with Ca 18.5 % changes `Ca+2` proportionally;
  - `test_undisclosed_blend_refuses_chemistry`;
  - `test_irrigation_ec_reports_material_provenance`;
  - `test_materials_key_mismatch`;
  - `test_no_materials_is_unchanged`: the result equals the pre-change call on the same doses.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run and confirm pass**, plus `tests.test_irrigation_ec` and `tests.test_product_conversion`.
- [ ] **Step 5: Commit** with the message "Accept resolved materials in chemistry and refuse undisclosed blends".

---

### Task 6: Delivered-nutrient band

**Files:**
- Modify: `src/flahax/materials.py`
- Test: `tests/test_materials.py` (class `BandTests`)

**Interfaces:**
- Produces `nutrient_band(doses_g_per_litre: Mapping[str, float], *, materials: Mapping[str, ResolvedMaterial] | None = None) -> dict`. It returns:
  - `nutrients`: {symbol: {`nominal_mg_per_l`, `minimum_mg_per_l` | None, `maximum_mg_per_l` | None}};
  - `basis`: {product: {nutrient: basis}};
  - `note`: "Band applies to nutrient amounts only; chemistry is reported at the nominal assay."

**Rules:** mg/L = g/L × % × 10. Sum contributions per nutrient across products. If any contributor to a nutrient has an open end, that end of the total is `None`. Products without materials use the shipped record with no band (`None`, `None`). The solver is never called.

- [ ] **Step 1: Write failing tests:**
  - `test_band_is_linear_reevaluation`, using two products with known min/max and hand-computed mg/L;
  - `test_open_bound_propagates`;
  - `test_shipped_only_has_no_band`;
  - `test_band_does_not_call_solver`: patch `flahax.engine.recommend` to raise; the call still succeeds.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run and confirm pass.**
- [ ] **Step 5: Commit** with the message "Add delivered-nutrient band from grade and lot ranges".

---

### Task 7: Exports, docs and full verification

**Files:**
- Modify: `src/flahax/__init__.py`. Export `DocumentReference`, `Grade`, `Lot`, `ResolvedMaterial`, `make_grade`, `make_lot`, `resolve_material`, `nutrient_band`, `load_identities` and `identity_for_product`.
- Regenerate: `src/flahax/data/API_REFERENCE.md`
- Create: `docs/materials.md`. It covers the three layers, the document-reference rule, the basis table, the band, undisclosed blends with the owner's position wording (spec §1, verbatim), the D1–D3 decisions, and one runnable example: a user grade from a data sheet plus a lot, resolved and used in `nutrient_band`.
- Modify: `docs/index.md` (link), `docs/development-status.md` (row), `docs/water-to-delivery.md` (replace the phosphoric acid and Mg Nitrate warning paragraph with a pointer to the corrections), `docs/audit/2026-10-18-materials-identity/review.md` (a "Resolved by" line under Consequences naming this change).
- Test: none new (docs are checked by `tests.test_release_hygiene` link checks).

- [ ] **Step 1:** Exports, then regenerate the API reference and run `--check`.
- [ ] **Step 2:** Docs. Run the example in `docs/materials.md` and paste its real output.
- [ ] **Step 3: Full checks:**

```bash
PYTHONPATH=src python tools/generate_api_reference.py --check
PYTHONPATH=src python -m unittest tests.test_release_hygiene
PYTHONPATH="src;." python -m unittest discover -s tests -t .
python -m compileall -q src tools examples
git diff --check
```
Expected: all exit 0 and all tests OK.
- [ ] **Step 4: Commit** with the message "Export material traceability API and document it".
