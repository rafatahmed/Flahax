# Irrigation EC M2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make shipped recipes return `estimated` irrigation EC. M2a publishes an O2 bound on uncovered species. M2b adds phosphate coefficients fitted to measured data (O1).

**Architecture:**
- **M2a:** changes `irrigation_ec._ec_from_state`. Uncovered charged species no longer force `partial`. They add a one-sided bound and the result carries an EC range.
- **M2b:** adds a phosphate section to the conductivity data file. The coefficients are produced by a fitting tool from owner-supplied measured data, so phosphate species become covered and the range narrows.
- **Shared:** both stages reuse the existing statuses, audit record and post-mix comparison.

**Tech Stack:** Python 3.13, standard library only (the fit uses a small Gauss–Newton or grid search written in `tools/`, not SciPy), `unittest`.

**Spec:** [docs/superpowers/specs/2026-10-18-irrigation-ec-mccleskey-design.md](../specs/2026-10-18-irrigation-ec-mccleskey-design.md), §11 and §13.

## Global Constraints

- **λ_max:** 80 S·cm²/mol per unit charge, at infinite dilution, with no ionic-strength reduction. The constant `LAMBDA_MAX_PER_CHARGE = 80.0` carries its citation: limiting-conductivity table, Adamson 1973 p. 512; max non-H⁺/OH⁻ is SO₄²⁻ 79.8.
- **Bound:** Σ |zᵢ|·80·mᵢ over uncovered charged species above 1e-12 mol/kgw, in mS/cm (the same units identity as Eq. 8). Every uncovered species is still listed.
- **Bounded estimate:** `status='estimated'`, `bounded=True`, `ec25_range_ms_cm=(known, known+bound)`, `ec25_ms_cm=known+bound/2`, `uncertainty_ms_cm=bound/2`, audit `uncovered_bound_ms_cm`.
- **Rules O2 does not override:** unrecorded counterions, the O5 assay gate, temperature, carbon and the ionic-strength domain keep their existing statuses.
- **Post-mix comparison:** reports `within_range` as a fact, with no pass/fail and no tolerance.
- **No invented parameters:** phosphate coefficients exist only after M2b runs on owner-supplied data. Until then phosphate stays under the bound.
- **Qualifier unchanged:** "Accuracy on this fertilizer mixture has not yet been established."
- **Branch:** `feat/ec-m2`, stacked on `docs/m1-signoff` (rafatahmed/Flahax#28). Stage only named files. Never `git stash`. Never stage README.md, docs/publication/*, docs/landscape-comparison-swot.md or outputs/.
- **Python path:** use `PYTHONPATH="src;."`, never `src` alone, which picks up an installed old package.

## Review Focus

1. **A recipe whose only problem is uncovered species** gives `estimated` with a range, never `partial`. A recipe with unrecorded counterions *and* uncovered species stays `partial` (unrecorded_counterions). Pinned in Task 1.
2. **No uncovered species.** `bounded=False`, `ec25_range_ms_cm=None` and the EC is identical to M1 (KCl 0.01 still 1.42349). Pinned in Task 1.
3. **Post-mix comparison on a bounded estimate.** The difference is to the midpoint, `within_range` is reported, and partial is still refused. Pinned in Task 2.
4. **Band ends:** each end carries its own bound and range. Pinned in Task 2.

---

### Task 1 (M2a): O2 bound in the EC result

**Files:** Modify `src/flahax/irrigation_ec.py`. Test: `tests/test_irrigation_ec.py` (class `BoundTests`, plus existing tests updated where `partial` / `missing_species_contributions` becomes bounded `estimated`).

**Interfaces:**
- `LAMBDA_MAX_PER_CHARGE: float = 80.0`.
- `IrrigationECResult` gains `bounded: bool = False`, `ec25_range_ms_cm: tuple | None = None`, `uncertainty_ms_cm: float | None = None` and `uncovered_bound_ms_cm: float | None = None`.
- The audit gains `uncovered_bound_ms_cm` and `lambda_max_per_charge`.

- [ ] **Step 1: Failing tests.**
  - `test_kh2po4_is_bounded_estimate`: totals K+ = PO4-3 = 1/136.09 mol/kgw, calculated mode.
    - Status `estimated` and `bounded`.
    - Range lower equals the M1 known subtotal (≈0.524, delta 0.002).
    - Upper = lower + Σ|z|·80·m over the reported missing species, recomputed in the test from `missing_species`.
    - Midpoint and uncertainty are consistent.
  - `test_unbounded_result_unchanged` (Review Focus 2): KCl 0.01 gives `bounded=False`, `ec25_range_ms_cm=None` and EC 1.42349 (places 4).
  - `test_unrecorded_counterions_still_partial` (Review Focus 1): KH₂PO₄ totals at supplied pH 4.0 stay `partial` / `unrecorded_counterions`.
  - `test_all_shipped_formulas_estimated`: all 26 shipped formulas (recommend doses, g/L as g/kgw, DeclaredPureWater, calculated mode) return `estimated`, and each range width / midpoint is ≤ 0.12. The audit's worst case is about 5.5 % for others plus about 8 % for phosphate. The test asserts the measured maximum with margin; record the actual values in the report.
- [ ] **Step 2:** Update the existing tests that asserted `partial` / `missing_species_contributions` on species-only cases (for example the Mg/SO₄ pair test and the phosphate test). Assert the bounded estimate and keep the missing-species assertions. Mark each change with a comment `# M2a O2 bound`.
- [ ] **Step 3:** Implement. Run `tests.test_irrigation_ec`, then the full suite.
- [ ] **Step 4:** Commit with the message "Publish an O2 bound so species-only gaps give a bounded EC estimate".

### Task 2 (M2a): Comparison and band ends with bounded estimates

**Files:** Modify `src/flahax/irrigation_ec.py` (`compare_measured_ec`, `calculate_irrigation_ec_band`). Test: `tests/test_irrigation_ec.py`.

**Rules:**
- `compare_measured_ec` adds the keys `ec25_range_ms_cm` and `within_range` (bool or None for unbounded), and keeps the difference to `ec25_ms_cm`.
- Band ends need no logic change; add tests that each end carries its own bound.

- [ ] **Failing tests:**
  - `test_compare_bounded`: inside and outside the range.
  - `test_compare_unbounded_has_none_within_range`.
  - `test_band_ends_carry_own_bounds` (Review Focus 4): a graded KH₂PO₄-like case where the ends differ.
- [ ] **Implement, run, full suite, then commit** with the message "Report range membership for bounded EC estimates".

### Task 3 (M2b): Phosphate coefficients from Pethybridge et al. 2006 (amended O1)

**Inputs:**
- `tests/fixtures/conductivity/pethybridge2006_table3.json` is the owner's first transcription. The controller writes it from the owner's message, with the citation, doi, units and the ½K₂HPO₄ heading convention.
- `..._independent.json` is typed by a separate agent from the PDF in `docs/sources/` (step 3b). **Merge gate:** both copies must agree.

**Files:**
- Create `tools/fit_phosphate_conductivity.py`.
  - **Inputs:** the fixture. Concentrations in mmol/dm³ convert to mol/kgw using a water density of 0.997047 kg/dm³ at 25 °C, a recorded constant.
  - **Conductivity:** κ (mS/cm) = Λ × c(mmol/dm³) / 1000. The K₂HPO₄ rows use ½-formula units, so salt molarity = c/2.
  - **Speciation:** each point uses `calculate_equilibrium_ph({'K+': n·m, 'PO4-3': m}, complete_analysis=True, carbon_boundary='closed', phases=[])`.
  - **Fit:** weighted linear least squares (weight 1/κ²) for λ° and A of H2PO4- and HPO4-2, with B = 1.5 fixed.
  - **Output:** the supplementary block, JSON on stdout, written with `--write`.
- Modify `src/flahax/data/conductivity_mccleskey2012.json`. Add a top-level `"supplementary"` block: `{"H2PO4-": {"lambda0_25c", "A_25c", "B": 1.5}, "HPO4-2": {...}, "source": {citation, doi, table: "III"}, "fit": {rms_percent, points, max_ionic_strength, density_kg_dm3}, "cross_checks": {...}}`. The McCleskey `ions` table stays untouched. Update `COEFFICIENTS_SHA256` / the literal pin test.
- Modify `irrigation_ec.py`. `ionic_molal_conductivity` and `covered_species` include the supplementary ions (25 °C only; any other temperature raises). The audit gains `phosphate_fit_max_ionic_strength` and `supplementaryCoefficients: true` whenever a supplementary ion contributes. Bump `MODEL_VERSION` to `irrigation-ec-mccleskey2012-m2b-experimental`.

- [ ] **3a. Failing tests** (class `PhosphateCoefficientTests`):
  - `test_fit_reproduces_table3`: running the tool on the fixture reproduces the shipped supplementary block to 1e-9, and every point is within 0.5 %.
  - `test_cross_checks_reported`: fitted λ° vs CRC (36, 114), Pethybridge (33.33, 115.14) and phreeqc.dat (31.8, 103.6). Report the percent gaps and assert ≤ 15 %, or document a larger gap in the block.
  - `test_kh2po4_now_mostly_covered`: KH₂PO₄ totals (1/136.09 mol/kgw) are bounded only by minor pairs, and the range width is below 5 % of the midpoint (it was ±36 % under M2a).
  - `test_supplementary_not_in_mcCleskey_table`.
  - `test_all_shipped_formulas_estimated`: tighten the width ceiling to the new observed maximum plus margin, and record the numbers.
- [ ] **3a. Implement, run the tool, commit its output, run the full suite** (in the background, waiting for it). Recount the 26 formulas into design §13. Commit with the message "Add phosphate conductivity coefficients fitted to Pethybridge et al. 2006".
- [ ] **3b (needs the PDF):** a separate agent types `pethybridge2006_table3_independent.json` from the PDF. Add `test_table3_transcriptions_agree`. If any value disagrees, stop and report to the owner. Commit with the message "Check Pethybridge Table III against an independent transcription".

### Task 4: Docs, exports, verification

**Files:**
- `docs/conductivity.md`: the bounded estimate, its meaning and the range fields. Include one runnable example, pasting the real output.
- `CHANGELOG.md`: one `## Unreleased` line per stage.
- `src/flahax/data/API_REFERENCE.md`: regenerate.

- [ ] **Full checks:** API `--check`, `tests.test_release_hygiene`, the full suite (foreground, timeout 600000 ms, never two concurrent runs), `compileall` and `git diff --check`.
- [ ] **Commit** with the message "Document bounded irrigation EC estimates".
