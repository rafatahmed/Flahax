# Resh cucumber nitrogen provenance (2026-10-28)

## Decision (go / no-go)

**GO** — remap of packaged `Cucumber (Howard Resh)` nitrogen from
`N_NO3: 140` to aggregate elemental **`N: 140`** is warranted by primary /
matched secondary provenance.

**No catalogue change in this task.** `library.json` keeps cucumber
`N_NO3`-only until the owner flips that gate. Witness
`tests.test_core_cucumber_witness` continues to assert the shipped keys.

Related: GitHub issue #201 (“Original Resh primary-source mapping remains
unconfirmed and must be audited before changing it”). UF tomato mislabel is
documented separately in
[`docs/audit/2026-10-28-uf-nitrogen-provenance/`](../2026-10-28-uf-nitrogen-provenance/README.md);
cucumber was out of scope there by design.

## Packaged record (unchanged)

Formula name: `Cucumber (Howard Resh)`  
Catalogue id: `cmbpfud9f00eaq8z92ve3zic0`  
File: `src/flahax/data/library.json`

| Key | Value (mg/L) |
|---|---|
| `N_NO3` | 140 |
| `P` | 50 |
| `K` | 350 |
| `Ca` | 200 |
| `Mg` | 50 |
| `S` | 150 |
| `Fe` | 3 |
| `Mn` | 0.8 |
| `Zn` | 0.1 |
| `Cu` | 0.07 |
| `B` | 0.3 |
| `Mo` | 0.03 |

No `N`, `N_NH4`, or `N_UREA` target is stored.

## Primary reference used by the packaged formula

Author attribution on the catalogue name is Howard M. Resh. The numeric
macronutrient set matches Resh’s published cucumber formulation as transcribed
in secondary sources that reproduce the same Ca / N / P / K / Mg / S / Fe /
micronutrient figures:

- Calcium 200 ppm (source salt: calcium nitrate)
- **Nitrogen (N) 140 ppm** (source salt: calcium nitrate)
- Phosphorus 50 ppm
- Potassium 350 ppm
- Sulfur 150–250 ppm (catalogue uses 150)
- Magnesium 50 ppm
- Iron 3 ppm; Mn 0.8; Cu 0.07; Zn 0.1; B 0.3; Mo 0.03

Canonical book for Resh formulations and nitrogen terminology:

- Resh, H. M. *Hydroponic Food Production: A Definitive Guidebook for the
  Advanced Home Gardener and the Commercial Hydroponic Grower*, 7th ed.,
  CRC Press, 2013 (ISBN 978-1-4398-7867-5 / DOI 10.1201/b12500).  
  Nutrient-formulation chapter (Ch. 3) and Table 3.6 (“Composition of Nutrient
  Solutions”).

A matching home-grower cucumber salt recipe with the same ppm set appears in
secondary transcriptions of Resh’s cucumber formulation (e.g.
<https://izmarhamid.wordpress.com/2014/11/13/formula-howard-resh/>). That page
is not the primary book; it is used here only because its numbers equal the
packaged row and its nitrogen **label** is explicit.

No Resh PDF is versioned under `docs/sources/` in this worktree. Claims below
cite the book’s published terminology pattern (verified via the 7th-edition
text OCR on Internet Archive) plus the matched secondary label for the
cucumber row.

## Published N basis: total elemental N, not nitrate-N alone

1. **Label on the matched cucumber row.** Secondary transcription of the Resh
   cucumber formulation names the 140 ppm target **“Nitrogen (N-140 ppm)”**,
   not “Nitrate-N” / “NO3-N”. The listed fertilizer source is calcium nitrate
   (nitrate form), which does not change the published concentration label
   from elemental N to a nitrate-only constraint.

2. **Same document distinguishes form splits when present.** On the same
   secondary page, lettuce is labeled **Ammonium-N: 15 ppm** and
   **Nitrate-N: 165 ppm** — the form-aware vocabulary Resh uses when a split
   is intended. Cucumber is not labeled that way.

3. **Resh book terminology.** *Hydroponic Food Production* 7th ed. states that
   nutrient formulations express nitrogen as **N**, **NH4+**, or **NO3−**.
   Worked Ca(NO3)2 examples that yield 200 ppm Ca and 140 ppm product call the
   product **“nitrogen” / “N”**, not “NO3-N”. Where Table 3.6 publishes both
   ammonium and nitrate columns, the FlahaX catalogue already stores both
   (`N_NH4` + `N_NO3`) for those rows (see below).

4. **Catalogue consistency check (other Resh rows).** Packaged Resh formulas
   that inherit an NH4/NO3 split from Table 3.6 keep both keys:

   | Formula | `N_NO3` | `N_NH4` |
   |---|---|---|
   | Generic Dry Season (Howard Resh) | 177 | 53 |
   | Generic Wet Season (Howard Resh) | 115 | 32 |
   | Lettuce General / Lettuce 2 (Howard Resh) | 165 | 15 |
   | Pepper (Howard Resh) | 190 | 18 |
   | **Cucumber (Howard Resh)** | **140** | *(absent)* |
   | Tomato (Howard Resh) | 140 | *(absent)* |

   Absence of `N_NH4` on cucumber is therefore not evidence that Resh forbade
   ammonium; it tracks a source row published as elemental **N** and then
   stored under the nitrate key.

## Mislabel relative to source semantics

Storing the Resh cucumber **N = 140** figure as `N_NO3` misclassifies total
elemental nitrogen as a nitrate-only target — the same defect class as the
retired UF tomato stages vs CV216 (see sibling UF audit). Consequences called
out in #201:

- Scoring treats incidental NH4 (e.g. from calcium nitrate ag-grade assay) as
  untargeted rather than counting toward the 140 N aim.
- Feasibility / excess percentages differ if the objective is total N versus
  nitrate-only (cucumber witness: nitrate excess vs total-N excess).

## Future remap rule (owner-gated)

If / when the owner flips the gate:

1. Change cucumber targets from `N_NO3: 140` to aggregate elemental **`N: 140`**
   (Task 2 nutrient ledger). Do **not** invent an NH4/NO3 split.
2. Leave form-specific keys only where Resh (or another primary) states a
   split (Dry/Wet, Lettuce, Pepper, staged Florida cucumber rows if ever
   shipped separately).
3. Refresh `tests/fixtures/core_spine/cucumber_ro_witness.json` and
   `tests.test_core_cucumber_witness` in the same change.
4. Tomato (Howard Resh) `N_NO3: 140` looks like the same pattern; it is **out of
   scope** of this cucumber audit and needs its own primary check before any
   remap.

Until that flip: cucumber remains `N_NO3`-only in `library.json`, and the
witness test below is the executable pin.

## Executable pin

`tests.test_core_cucumber_witness.CucumberRoWitnessTests.test_formula_targets_nitrate_only_nitrogen`
asserts packaged + fixture targets still have `N_NO3 == 140` and neither `N`
nor `N_NH4`.
