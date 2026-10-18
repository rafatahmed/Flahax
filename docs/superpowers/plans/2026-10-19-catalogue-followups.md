# Catalogue Follow-ups (F1–F3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three documented follow-ups of the traceable catalogue: provenance on formulation results, chelate sodium in formulation rows, and chemistry at the nutrient-band ends.

**Architecture:** Small changes to existing modules. `resolve_material` attaches `record['provenance']`. `engine.recommend` reports per-salt provenance and chelate sodium after the fit. `irrigation_ec` gains `calculate_irrigation_ec_band`, which builds the minimum and maximum corner records from `ResolvedMaterial` band ends and reuses `calculate_irrigation_ec`.

**Tech Stack:** Python 3.13, standard library, `unittest`.

**Spec:** [docs/superpowers/specs/2026-10-18-traceable-catalogue-design.md](../specs/2026-10-18-traceable-catalogue-design.md), §12.

## Global Constraints

- No new runtime dependency. Existing signatures stay unchanged; every addition is optional or additive.
- `forward()` is unchanged.
- Chelate sodium (D2) never enters `elements`, eligibility or the fit. Na stays in `RESTRICTED_IONS`.
- Records lacking provenance report `analysisBasis: "unattributed"`, never a guessed basis.
- An open band end returns `not_supported` / `band_end_open`; no substitution.
- Work on branch `feat/catalogue-followups`, cut from `feat/traceable-catalogue`. Stage only named files. Never use `git stash`. Never stage `README.md`, `docs/publication/*`, `docs/landscape-comparison-swot.md` or `outputs/`.

## Review Focus

1. **`recommend` with a mix of shipped and resolved records.** Each salt entry carries its own provenance; no entry borrows another product's. Pinned in Task 1.
2. **A recipe with no chelates.** The `Na` row and `incidentalContributions` are byte-identical to before. Pinned in Task 2.
3. **Band ends with only shipped products.** Both ends are `not_supported` / `band_end_open`, and the nominal equals `calculate_irrigation_ec`. Pinned in Task 3.
4. **A band end that pushes ionic strength over 0.1.** That end alone is `not_supported` / `ionic_strength_outside_domain`. Pinned in Task 3.

---

### Task 0: Branch

- [ ] `git switch -c feat/catalogue-followups` from `feat/traceable-catalogue`. Commit the spec addendum and this plan: `git add docs/superpowers/specs/2026-10-18-traceable-catalogue-design.md docs/superpowers/plans/2026-10-19-catalogue-followups.md && git commit -m "Plan catalogue follow-ups F1-F3"`.

### Task 1: Provenance on formulation results (F1)

**Files:** Modify `src/flahax/materials.py` (`resolve_material` sets `record['provenance']`) and `src/flahax/engine.py` (`recommend` output). Test: `tests/test_materials.py` (class `FormulationProvenanceTests`).

**Interfaces:**
- Each `recommend(...)['salts'][i]` gains a `provenance` dict with these keys:
  - `recordId`
  - `identityId`
  - `analysisBasis`: a string, or a per-nutrient dict for resolved materials
  - `documents`: a list of document-reference dicts
  - `flags`: a list
- `recommend(...)` gains `identitiesSha256`.

**Rules:**
- **Source of provenance:** use the record's own `provenance` key when present; else its `identityId`, `analysisBasis` and `source` keys (shipped `library.json`); else `analysisBasis: "unattributed"`, `identityId: None`.
- **Isolation:** provenance must be built from the record that produced that salt entry, matched by `id`.

- [ ] **Step 1: Failing tests.**
  - `test_shipped_recommend_has_catalogue_provenance`: every salt entry has an `identityId` starting `idn-`. Calcium Nitrate has `analysisBasis` `grade_typical` and a Haifa document.
  - `test_resolved_record_provenance_flows` (Review Focus 1): mix the shipped library with one resolved KNO3 grade record. The KNO3 entry carries the grade's per-nutrient basis and `recordId` `<cuid>+<grade>`; the other entries keep catalogue provenance.
  - `test_unattributed_record`: a hand-built `{id, name, formula, elements}` gives `analysisBasis` `unattributed`.
  - `test_identities_hash_on_result`.
- [ ] **Step 2: Run** `PYTHONPATH="src;." python -m unittest tests.test_materials -v`. Expect FAIL.
- [ ] **Step 3: Implement.** Then regenerate the API reference if docstrings changed.
- [ ] **Step 4: Run** `tests.test_materials` and the full suite. Expect OK.
- [ ] **Step 5: Commit** with the message "Report material provenance on formulation results".

### Task 2: Chelate sodium in formulation rows (F2)

**Files:** Modify `src/flahax/engine.py` (post-fit reporting only), reusing `product_conversion`'s counterion rule through a small helper `chelate_sodium_mg_per_l(salts_with_doses) -> float`, defined in `product_conversion.py`. Test: `tests/test_materials.py` (class `ChelateSodiumReportTests`).

**Rules:**
- Sodium (mg/L) = Σ over chosen chelate and CH - micro products of the D2 counterion moles at dose g/L, treated as g/kg water, × 22.98977 × 1000.
- Add it to the `Na` row's `final`; create the row with `target: None` if it is absent.
- Add it to the `incidentalContributions` `Na` entry. Re-run the existing incidental assessment so `requires_review` and limit checks see it.
- Append the warning `"Incidental Na includes chelate sodium counterions (D2): {x:.4f} mg/L."` only when x > 0.
- No change to eligibility, `_fit` or grams.

- [ ] **Step 1: Failing tests.**
  - `test_chelate_sodium_reported_not_fitted`: the pepper/Chilli formula with Mn EDTA chosen. Assert the `Na` row increases by exactly the helper value, grams are identical to a run with the reporting disabled (patch the helper to return 0), and chelates remain chosen.
  - `test_no_chelate_recipe_unchanged` (Review Focus 2): a formula with no chelates. `rows` and `incidentalContributions` equal the pre-change output, captured as a literal.
  - `test_helper_matches_chemistry`: the helper value equals Na+ from `catalogue_dose_totals` × 22.98977 × 1000 for the same chelate doses.
- [ ] **Steps 2–4:** run, implement, run, then the full suite.
- [ ] **Step 5: Commit** with the message "Report chelate sodium counterions in formulation rows".

### Task 3: Chemistry at the band ends (F3)

**Files:** Modify `src/flahax/irrigation_ec.py`. Test: `tests/test_irrigation_ec.py` (class `BandChemistryTests`).

**Interfaces:** `calculate_irrigation_ec_band(doses_g_per_kg_water, *, materials=None, **same keyword args as calculate_irrigation_ec) -> dict` with keys `nominal`, `minimum` and `maximum`, each an `IrrigationECResult`, plus `note`: "Band ends are corner cases (every product at its minimum, or every product at its maximum), not statistical bounds."

**Rules:**
- **Nominal:** `calculate_irrigation_ec(...)` with the given materials.
- **Building an end:** for each dosed product, take its `ResolvedMaterial` from `materials`, or `resolve_material(name)` for shipped products. Build a copy of its record whose `elements` are the band end for every nutrient.
- **Open end:** if any band end needed is `None`, that end is an `IrrigationECResult` with status `not_supported`, reason `band_end_open`, all numbers `None`, and audit `band_end`.
- **Computing an end:** otherwise call `calculate_irrigation_ec` with the end materials and add audit `band_end`: `minimum` or `maximum`.
- **Error codes** from an end's call are mapped exactly as in `calculate_irrigation_ec`.

- [ ] **Step 1: Failing tests.**
  - `test_shipped_only_band_ends_open` (Review Focus 3).
  - `test_band_ends_bracket_ec`: a KNO3 grade with min/max plus a K2SO4 grade with min/max, in declared pure water, calculated mode. Expect min EC < nominal EC < max EC, and each audit's `band_end` is correct.
  - `test_band_end_outside_domain` (Review Focus 4): doses near I = 0.1 so only the maximum end exceeds it.
  - `test_note_text`.
- [ ] **Steps 2–4:** run, implement, run, then the full suite.
- [ ] **Step 5: Commit** with the message "Evaluate irrigation chemistry at nutrient band ends".

### Task 4: Exports, docs, verification

**Files:**
- `src/flahax/__init__.py`: export `calculate_irrigation_ec_band`.
- Regenerate `API_REFERENCE.md`.
- `docs/materials.md`: move the three follow-ups from "follow-up" to documented behaviour, with one runnable band-chemistry example and its real output.
- `CHANGELOG.md`: one `## Unreleased` line per follow-up.

- [ ] **Run the full checks:** API `--check`, `tests.test_release_hygiene`, full suite, `compileall`, `git diff --check`. All must pass.
- [ ] **Commit** with the message "Document and export catalogue follow-ups".
