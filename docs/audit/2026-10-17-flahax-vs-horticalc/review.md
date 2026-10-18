# Maintainer review of the 2026-10-17 audit

Reviewed 2026-10-18. The [audit report](report.md) is kept as received
(only its two image links were pointed at the local figures). This page
records what was re-checked against the raw data in `data/` and the
repository, and what the report gets wrong or leaves out. Where the two
disagree, this page takes precedence.

## Reproduced from the raw data

Every headline figure below was recomputed from the CSV files and agrees
with the report:

- Formulation, all four engine variants (634 targets each): RMS, median and
  maximum deviation, RMSE in mg/L, ±5 % and ±10 % coverage, exact hits,
  mean products and solve time
  ([bench_formulation_variants.csv](data/bench_formulation_variants.csv)).
- Equilibrium against PHREEQC 3.8.6 / minteq.v4: 1,274 species over 108
  solutions, median deviation 0.048 %, maximum 6.48 %; ionic strength maximum
  0.093 % ([bench_speciation.csv](data/bench_speciation.csv)).
- Saturation indices: 100 values over 13 phases, maximum deviation 0.0035
  log units ([bench_si.csv](data/bench_si.csv)).
- FlahaX scope counts: 36 library modules, 162 test functions, 28 catalogue
  products.

## Errata

| Report statement | Correction |
|---|---|
| Exported public API names: 80 | `flahax.__all__` has **103** names, as recorded in [release evidence](../../release-evidence.md). |
| Worst deviation on any species above 10⁻¹⁰ mol/kgw is 3.7 % | It is **4.0 %** (HMo₇O₂₄⁵⁻, 1.35 × 10⁻¹⁰ mol/kgw, sodium molybdate at pH 5). 3.7 % is CaNH₃²⁺. |

## EC section: method problems

1. **PHREEQC conductivity column.** PHREEQC calculates specific conductance
   from species diffusion coefficients. Those coefficients are carried by
   `phreeqc.dat`; `minteq.v4.dat` is an equilibrium database and is
   expected to lack them for many species. This is consistent with the
   pattern in [bench_ec.csv](data/bench_ec.csv) (SOP −31 %, Magsul −60 %,
   nitrates within about 2 %) and with the KCl error growing with
   concentration in [bench_ec_kcl.csv](data/bench_ec_kcl.csv). Not yet
   confirmed against the database file; re-run the conductivity column with
   `phreeqc.dat` before citing it. Until then, "beats PHREEQC's own
   specific-conductance routine" is unsupported.
2. **"Validated … accurate to +0.7 %".** The test covers KCl only, a single
   1:1 electrolyte, and shows a constant +0.7 % bias across concentrations.
   It does not test sulfate, phosphate, divalent ion pairs or mixtures.
   Accurate wording: within 0.7 % on KCl standards.
3. **Brochure values as the reference.** The SQM values are rounded to
   0.1 mS/cm, so MKP at 0.7 carries ±7 % from rounding alone. The table
   shows agreement or disagreement; it cannot score accuracy.
4. **Magsul.** The brochure table was re-read at full zoom on 2026-10-18.
   It prints 1.2 mS/cm and every column is transcribed correctly in
   `calculated_ec.py`, including MKP 0.7 and MAP 0.9. The brochure's own
   analysis (16.2 % MgO, 13.2 % S) is MgSO₄·7H₂O. At 1 g/L (4.06 mmol/L)
   with full dissociation at infinite dilution the conductivity cannot exceed
   **1.08 mS/cm**; with Davies activity and MgSO₄⁰/KSO₄⁻ pairing an
   independent calculation gives about 0.73. The **source value** is
   physically impossible, not the transcription. The plausible range is
   0.73–1.08 mS/cm.
5. **McCleskey needs speciation.** McCleskey et al. (2012) is explicitly
   coupled to a geochemical speciation model: neutral pairs such as MgSO₄⁰
   carry no current, and it provides conductivities for HSO₄⁻, NaSO₄⁻,
   NaCO₃⁻ and KSO₄⁻ pairs. It has no phosphate species, so Horticalc's
   H₂PO₄⁻ values come from a CRC fallback (`fallback_ions` in
   [bench_ec.csv](data/bench_ec.csv)). Horticalc has no speciation
   ([bench_scope.csv](data/bench_scope.csv)), so its 0.88 mS/cm for Magsul
   omits the pairing the method assumes and is likely high.
6. **Omission.** FlahaX also has the measured-profile EC method
   (`plan_ec_delivery`, see [EC planning](../../conductivity.md)). "No
   ion-based model" is correct; "brochure anchors only" is not.

## Consequences for FlahaX

- The anchor tests in `tests/test_site_planning.py` and the 1.15 mS/cm smoke
  check in `tools/verify_distribution.py` test transcription and arithmetic
  only. They cannot detect a wrong source value such as Magsul.
- Six of the seven anchors agree with an independent ion-conductivity
  calculation within the brochure's rounding; Magsul does not.
- Additive anchors drift from a mixture calculation as loading rises (about
  9 % high on a Magsul-containing 1 g/L mix).
- The route the audit recommends, McCleskey (2012) implemented from the
  paper, fits FlahaX better than Horticalc because the required speciation
  already exists and is verified against PHREEQC. Phosphate and chelate
  species need a cited source outside McCleskey.

## Source

McCleskey, R. B.; Nordstrom, D. K.; Ryan, J. N.; Ball, J. W. A new method of
calculating electrical conductivity with applications to natural waters.
*Geochimica et Cosmochimica Acta* 2012, 77, 369–382.
<https://doi.org/10.1016/j.gca.2011.10.031>. Stated range: effective ionic
strength 0.0004–0.7 mol/kg, 0–95 °C, pH 1–10, 30–70,000 µS/cm; mean
difference −0.7 ± 5 % over 1,593 natural waters.

Local copy: `docs/sources/mccleskey_nordstrom_etal_2012.pdf`, SHA-256
`17002c4eeedef68ddb62048f3b1b0c77a96b03d5f9dc51b167fc05e9f145ce1f`. Not
versioned or distributed (publisher copyright), under the same rule as the
other files in `docs/sources/`.
