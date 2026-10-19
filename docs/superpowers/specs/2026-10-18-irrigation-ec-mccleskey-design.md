# Irrigation EC from speciation (McCleskey 2012): design

Status: design for owner review, 2026-10-18. Nothing here is implemented.
No accuracy figure in this document is a validated result.

## 1. Intent

**Product promise:** estimate what you expect before mixing, then compare it
with what you measure.

The grower's main question is "what EC should this recipe produce?", asked
before salts are weighed. After mixing, the same prediction becomes the
reference for interpreting the meter reading. EC agreement never establishes
that each nutrient concentration is correct.

| Stage | Grower's question | What FlahaX shows |
|---|---|---|
| Before mixing (primary) | What EC should this recipe produce? | Predicted final irrigation EC at 25 °C, from recipe, source-water composition, pH basis and explicit reagent additions |
| After mixing | Does my measured EC agree with this recipe? | Predicted EC25, measured EC25 and their difference; no verdict |
| Stock preparation | What EC should tank A/B have? | Existing recipe-matched measured calibration (`plan_ec_delivery`), labelled empirical; this design does not cover stocks |

### Why now

The [2026-10-17 audit](../../audit/2026-10-17-flahax-vs-horticalc/report.md)
and its [maintainer review](../../audit/2026-10-17-flahax-vs-horticalc/review.md)
found EC to be FlahaX's weakest component. The current no-measurement path
(`calculated_ec.py`) adds manufacturer brochure values for seven named
products; its tests check transcription and arithmetic only. FlahaX's
speciation reproduces PHREEQC/minteq.v4 closely, so the missing piece is a
conductivity calculation on top of that speciation, the coupling McCleskey
et al. (2012) prescribe.

### Feasibility evidence (throwaway spike, 2026-10-18, not product code)

McCleskey Table 1 at 25 °C applied to FlahaX speciation:

| Case | Spike, mS/cm | Comparison |
|---|---|---|
| KCl 0.001 / 0.01 mol/kgw | 0.148 / 1.423 | Standards 0.1469 / 1.413 (+0.8 / +0.7 %); identical to Horticalc, which uses the same equations |
| KCl 0.1 mol/L | not computed | About 0.1006 mol/kgw, so I ≈ 0.1006 > 0.1: outside the Davies domain |
| SOP, Calcium, Magnit at 1 g/L | 1.508, 1.191, 0.892 | Brochure 1.5, 1.2, 0.9 |
| Magsul at 1 g/L | 0.725 | Brochure 1.2, correctly transcribed but physically impossible: the brochure's own analysis (16.2 % MgO, 13.2 % S) is MgSO₄·7H₂O, and full dissociation at infinite dilution of 1 g/L cannot exceed 1.08 mS/cm. Settled; see the [maintainer review](../../audit/2026-10-17-flahax-vs-horticalc/review.md) |
| MKP, MAP | incomplete | H₂PO₄⁻ carries about a third of the conductivity and has no McCleskey coefficient |
| Macro mix at pH 5.8, I ≈ 0.025 | 2.04 from covered species only | Uncovered: H₂PO₄⁻, HPO₄²⁻, CaNO₃⁺, CaH₂PO₄⁺, MgH₂PO₄⁺, NH₄SO₄⁻. This is **not** a complete prediction; a charge-carrier fraction is not an EC error bound |

## 2. Goals, non-goals, anti-goals

**Goals**
- A complete, auditable EC25 prediction for irrigation-strength fertilizer
  solutions inside a stated computational envelope.
- Explicit `partial` results naming every uncovered charged species.
- Provenance strong enough to reproduce every number.
- A validation suite that separates verification from accuracy, so the
  "unknown accuracy" qualifier can be narrowed on evidence.

**Non-goals**
- Stock-tank conductivity, temperatures other than 25 °C, open CO₂ systems.
- Automatic pass/fail, dosing correction or equipment control.
- Replacing the measured stock-calibration path or the brochure-anchor
  screening path.

**Anti-goals (failure even if it "works")**
- A number shown as a prediction while charged species are omitted.
- A target pH silently implying an unrecorded acid dose.
- A brochure value silently overriding or "correcting" the calculation.
- Any claim of accuracy from transcription tests, implementation agreement or
  brochure comparisons.

## 3. Constraints

- Pure Python, no new runtime dependency.
- 25 °C only: the reaction set is pinned at 25 °C (`aqueous_model.solve`).
- **Computational envelope:** speciated I ≤ 0.1 mol/kgw (Davies; equality
  allowed). The **validated envelope** is empty until measured evidence exists
  (section 8). Documentation must keep the two separate.
- Closed inorganic carbon only, as `calculate_equilibrium_ph` already requires.
- McCleskey's numbers are implemented from the paper, never from Horticalc's
  GPL code. The paper PDF stays local (`docs/sources/`, not versioned).

## 4. The physical solution being predicted (input contract)

The calculation runs on **molal analytical totals** (mol per kg of water),
never on g/L.

- **Recipe:** product doses in g per kg of final solvent water, as
  `product_conversion` already uses. Product assay and hydration basis come
  from the catalogue record. Changing either requires a new record.
- **Source water:** analytical totals from a complete water analysis
  (`balance_water_analysis`), with its identifier, **or** a declared pure
  water (RO or distilled): a named zero-composition water with its
  identifier and an explicit `declared_pure: true`. A partial laboratory
  report stays invalid; an empty mapping without the declaration is
  rejected.
- **Reagents:** explicit molal additions with their counterions, such as HNO₃
  giving H⁺ and NO₃⁻. From an `EquilibriumPhPlan` the reagent dose is taken
  from that plan and its identifier is recorded.
- **Solvent and volume:** final water mass is an explicit input, including
  reagent carrier water. Any molarity-to-molality conversion (for example,
  KCl standards) is an explicit, recorded step with its density source, never
  an assumed g/L = g/kg.
- **Dilution:** the input is the final irrigation solution. Injection ratios
  are resolved before this call.

## 5. pH basis, precipitation and carbon (required, recorded choices)

**pH basis**, exactly one, required:

| Mode | Meaning | Rule |
|---|---|---|
| `calculated` | pH from charge balance of declared complete totals, including reagent additions | Uses `calculate_equilibrium_ph` (complete analysis declared, closed carbon). Charge balance is exact by construction. |
| `supplied` | A stated final pH (measured or target) used for conditional speciation | Uses the fixed-pH solve. The resulting charge imbalance is reported. Above 0.1 % of total equivalents (O5 below) it means unrecorded counterions (acid or base) whose conductivity is unknown, so the result is `partial` with `unrecorded_counterions` and the imbalance in eq/kgw. It is never charge-balanced silently. |

**From an `EquilibriumPhPlan`** *(designer's call)*: the EC is calculated on
that plan's own target equilibrium state, treated as `supplied` at the plan's
target pH with the plan's reagent dose. It is not re-solved in `calculated`
mode, which would move the pH away from the plan's target. The plan's
residual charge goes through the same imbalance rule as any `supplied` input.

**Assay charge residual:** catalogue products are built from rounded label
assays, so a recipe is not exactly charge-neutral (Mg Nitrate is about 1 %
off). **Owner decision (O5, 2026-10-18):** the existing 0.1 % precedent of
`plan_equilibrium_delivery` applies.
- **Definition:** the assay charge residual is the charge sum of the
  catalogue totals using each product's *declared* ion forms (for example,
  H₂PO₄⁻ for MKP), divided by the sum of absolute equivalents. It does not
  depend on pH. In `supplied` mode, speciated imbalance beyond this residual
  is counted as unrecorded counterions, never as assay rounding.
- A residual of up to 0.1 % of total equivalents is reported as
  `assay_charge_residual` (eq/kgw and percent) and does not block an
  estimate. In `supplied` mode it is not treated as unrecorded counterions.
- Above 0.1 %, a `supplied` result is `partial`
  (`unrecorded_counterions`), and a `calculated` result is `not_supported`
  (`assay_charge_residual_too_large`), because forcing charge balance through
  pH alone would let assay rounding set the pH.

**Phase policy**, required:
- `dissolved`: speciation with no solids (`phases=()`). This is the recipe as
  fully dissolved. Any SI > 0 is reported as a warning without kinetic
  interpretation.
- `equilibrated`: an explicit list of phases allowed to precipitate. The
  prediction is for the remaining solution, and precipitated amounts are
  recorded.

**Carbon:** closed boundary only. Any other choice is `not_supported`.

## 6. Calculation

*Amended by §13 (O2, M2a, 2026-10-19): species-only gaps give a bounded `estimated` result; see §13 for the range fields and post-mix `within_range`.*

κ₂₅ (mS/cm) = Σ λᵢ(25 °C, I) · mᵢ over charged species, where
λ = λ°(T) − A(T)·I^½ / (1 + B·I^½) (McCleskey Eq. 8 with the Table 1
polynomials), mᵢ is the speciated molality and I is the speciated ionic
strength from the same solve.

**Units, stated and recorded.** McCleskey Table 1 gives λ as an *ionic molal
conductivity* in mS·kg·cm⁻¹·mol⁻¹, fitted to measurements on molal
solutions. With m in mol/kgw the product is directly in mS/cm, and FlahaX
applies no density conversion: any density effect is inside the paper's
fitted coefficients. This is recorded in every result
(`conductivity_units: "mS kg cm-1 mol-1 x mol/kgw"`). Any parameter from
another source expressed as a *molar* conductivity (S·cm²·mol⁻¹, per litre)
needs an explicit molal conversion with a stated density, recorded per
parameter. At irrigation strength taking the density as 1 kg/L changes the
result by a few tenths of a percent; it is never applied silently.

- Neutral species and neutral pairs (MgSO₄⁰, CaSO₄⁰, CaHPO₄⁰) carry no current
  but stay in the speciation.
- **Coefficient data** is a shipped JSON file holding the full Table 1
  polynomials (all temperatures, used only at 25 °C), the source citation,
  the paper SHA-256 and a species mapping from FlahaX species names to
  Table 1 ions. Its SHA-256 is pinned like the minteq subset's.
- **Coverage rule:** every charged species with molality above the numerical
  reporting tolerance and no coefficient is listed by name, charge and
  molality. Any such species makes the result `partial`. Low molality or a
  small charge fraction is not a reason to ignore one. An `estimated` result
  despite omissions is allowed only through an owner-approved contribution
  bound (decision O2).

## 7. Output contract

*Amended by §13 (O2, M2a, 2026-10-19): species-only gaps give a bounded `estimated` result; see §13 for the range fields and post-mix `within_range`.*

| Status | `ec25_ms_cm` | Also carried |
|---|---|---|
| `estimated` | calculated EC25 | Per-species contributions, transport numbers, envelope checks, warnings |
| `partial` | `null` | `known_species_subtotal_ms_cm` (explicitly named), `missing_species[]` (name, charge, molality), `unrecorded_counterions` if any |
| `not_supported` | `null` | Reason: `temperature_outside_reference`, `ionic_strength_outside_domain`, `unsupported_carbon_boundary`, ... |
| Invalid input / solver failure | no result | `DeliveryError` with a distinct code, never a status |

**Every result carries** the temperature reference (25 °C), the pH mode and
pH, the phase policy, the carbon boundary, the input identifiers (recipe,
water analysis, reagent plan), the chemistry dataset SHA-256, the coefficient
file SHA-256, the equation id (`mccleskey2012-eq8`), the species-mapping
version, unit conversions applied, solver iterations and charge balance, the
model version, and the fixed qualifier: "Accuracy on this fertilizer
mixture has not yet been established."

**Display wording** (example from a fully covered case, 0.01 mol/kgw KCl in
declared pure water; spike value): "Estimated irrigation EC25: 1.42 mS/cm.
Based on the specified recipe, water analysis and pH. Accuracy on this fertilizer mixture
has not yet been established." A `partial` result is shown as "Partial
calculation: missing species contributions" followed by the named species.

**Post-mix comparison:** accepts only an `estimated` prediction plus a
measured EC25 (the caller declares the meter's temperature-compensation
reference). It returns the measured value, the predicted value and their
signed and relative difference. No pass/fail, no tolerance, no dosing
suggestion. A `partial` prediction is refused (`incomplete_prediction`).

**Relationship to existing EC paths:**
- `estimate_manufacturer_ec` stays a separately labelled comparison. Where
  every product has an anchor, the CLI may show it beside the calculated
  value, never in its place, labelled "brochure value, rounded to 0.1 mS/cm".
  The Magsul anchor (1.2 mS/cm) is physically impossible and is **never shown**
  beside a calculation; the other six anchors may be.
- `plan_ec_delivery` (measured calibration) stays the only stock path,
  labelled empirical.

## 8. Validation, in three separate categories

| Category | What it establishes | Content |
|---|---|---|
| Verification | The code implements the paper | Table 1 transcription test against the paper (independently re-read); Eq. 8 unit test; contribution sums; coverage-rule tests; envelope boundary tests (I just below, at and above 0.1 mol/kgw) |
| Implementation comparison | Agreement with other implementations | Horticalc numbers from the audit CSVs; PHREEQC SC re-run with `phreeqc.dat` (not minteq.v4) as the Appelo-method cross-check. Agreement is not accuracy. |
| Accuracy against measurements | The basis for narrowing "unknown accuracy" | KCl standards inside the envelope (0.001 to about 0.05 mol/kgw), with primary citations and recorded molality conversion; measured single-salt and mixed fertilizer solutions with documented protocol and meter calibration (to be acquired) |

Brochure comparisons are recorded as evidence, with rounding to 0.1 mS/cm
noted, but never set an accuracy bound. Acceptance criteria for any accuracy
claim are written down before any coefficient choice is tuned.

## 9. Milestones

| Milestone | Delivers | Exit |
|---|---|---|
| M1 Development preview | McCleskey coefficients plus speciation, full input and output contract, provenance, coverage rule, verification tests. Marked experimental. Phosphate recipes return `partial`. | Verification category passes. Not grower-facing. |
| M2 Coverage | Individually sourced parameters for H₂PO₄⁻, HPO₄²⁻ and every materially contributing charged complex (CaNO₃⁺, CaH₂PO₄⁺, MgH₂PO₄⁺, NH₄SO₄⁻, KHPO₄⁻), each with its own source and test. A species with no defensible parameter stays `partial`. Nearly every catalogue recipe also carries micromolar charged chelate and trace complexes (FeEdta⁻, ZnEdta²⁻, NaEdta³⁻ and others): the M2 exit is reachable only if they are covered too, or an O2 contribution bound is approved. | Typical catalogue recipes return `estimated`; implementation comparison recorded. |
| M3 Measured validation | Measured fertilizer solutions and an accuracy statement for a stated envelope | Accuracy category recorded as measured, including failures |

**M2 exit gates, counted 2026-10-18** (26 shipped formulas, RO water,
`recommend` doses; throwaway count, not product code; speciated I 0.016 to
0.045, all inside the Davies domain):

| Gate | Passes | Why the rest fail |
|---|---|---|
| Assay charge residual ≤ 0.1 % (declared forms) | **26 of 26** (recount 2026-10-19; was 15 of 26) | All pass after the traceable-catalogue corrections: Mg Nitrate D1, chelate sodium D2, borax declared form. Worst −0.05 % (Tropical Lettuce). The 2026-10-18 count was 15 of 26, worst −0.32 %, from rounded label assays and undeclared chelate counterions. |
| `supplied` pH 5.8 with no recorded reagent | 0 of 26 | Speciated imbalance 0.3–6 %: the target pH implies an acid or base dose that was not recorded. Correct `partial` behaviour, and a reason for `EquilibriumPhPlan` input. |
| Charged chelate and trace complexes covered | 0 of 26 without O2 | Micromolar FeEdta⁻ and others make nearly every recipe `partial` unless covered or bounded under O2. |

So the M2 exit ("typical catalogue recipes return `estimated`") also needs
the reagent dose recorded. The catalogue corrections have now met the
`calculated`-mode assay condition. In a 2026-10-19 recount in declared RO
water at calculated pH, all 26 formulas are still `partial` /
`missing_species_contributions`. Since M2a, these are bounded `estimated` results (widest range 14.4 % of the midpoint, Generic Wet Season; 5.4 % since M2b, see §13). The causes are phosphate species, citrate
pairs, CaNO₃⁺, MgH₂PO₄⁺/CaH₂PO₄⁺, NH₄SO₄⁻, Fe-EDTA species and trace
MgOH⁺/CaOH⁺, which await O1 and O2. McCleskey's −0.7 ± 5 % over 1,593 natural waters is
literature context, never an accuracy claim for these mixtures.

**Grower-facing release requires M2.** If M2 evidence is unavailable, the
module ships as clearly scoped experimental, rather than manufacturing
complete phosphate predictions. "Unknown accuracy" is narrowed only after M3.

## 10. Supersedes

For irrigation-strength EC, this design supersedes these parts of the
[stock conductivity service design](../../stock-conductivity-service-design.md):
- the statement that the Davies model is sound to about 0.5 mol/kg (FlahaX
  enforces I ≤ 0.1 mol/kgw);
- deferring acid-adjusted solutions (here, reagent additions are part of the
  input contract);
- decision D3 (mobility law: McCleskey Eq. 8) and decision D5 for irrigation
  (25 °C only).

It also supersedes the **T1 Irrigation** tier of the
[landscape comparison's route to accurate EC](../../landscape-comparison-swot.md#tiered-model-matched-to-the-scope):
the Fuoss–Onsager / Lee–Wheaton law is replaced by McCleskey Eq. 8 on FlahaX
speciation, and its proposed "±5 % or ±0.1 mS/cm" target is withdrawn until
measured evidence sets one (section 8).

The stock design stays the reference for stock strength, which remains out
of scope here.

## 11. Owner decisions

| Id | Decision |
|---|---|
| O1 | **Decided 2026-10-19, amended the same day:** λ° and A for H₂PO₄⁻ and HPO₄²⁻ are fitted to the measured 25 °C KH₂PO₄ and K₂HPO₄ conductivities of Pethybridge, Talbot & House (2006), Table III, through FlahaX speciation, with B fixed at 1.5. The cross-checks, which report but do not block, are CRC λ°, Pethybridge's Lee–Wheaton λ° and λ° derived from `phreeqc.dat`. PO₄³⁻ stays under the O2 bound. See §13. |
| O2 | **Decided 2026-10-19:** a one-sided bound of 80 S·cm²/mol per unit charge at infinite dilution, times molality, for each uncovered charged species. Published with the result as an EC range; species are never dropped and mobilities are never fitted. See §13. |
| O3 | Measurement programme for M3: who measures, which solutions, which meter and calibration protocol |

**Designer's calls (owner may override):**
- The first implementation plan covers **M1 only**. M2 and M3 are planned once
  O1–O3 are decided.
- M1 is a **Python API only**; no CLI flag until M2 (former O4).
- **Table 1 transcription check:** the shipped coefficient JSON is compared in
  CI with a second, independently typed fixture in `tests/`, and the owner
  signs off once against the paper (recorded with the paper SHA-256). CI
  cannot read the unversioned PDF.

## 13. O1 and O2 decisions and audit (2026-10-19)

### Audit on the 26 shipped formulas
These numbers come from a throwaway script, not product code. Inputs: recommend doses with g/L taken as g/kgw, declared RO water, calculated pH. Speciated I ranges from 0.016 to 0.046.

| Quantity | Range over the 26 formulas |
|---|---|
| Phosphate share of EC (CRC λ°, crude I correction) | 0.025–0.100 mS/cm, about 1–8 % of EC |
| Difference between CRC and `phreeqc.dat` λ° for phosphate | at most 0.7 % of EC |
| O2 bound for all other uncovered species (80 S·cm²/eq at infinite dilution) | 0.5–5.5 % of EC; worst is Generic Wet Season, from citrate pairs |

The largest uncovered non-phosphate species are Ca(Citrate)⁻ (4.7×10⁻⁴ mol/kgw), Mg(Citrate)⁻, CaNO₃⁺, MgH₂PO₄⁺, CaH₂PO₄⁺, CaPO₄⁻, NH₄SO₄⁻ and FeOH(Edta)²⁻.

λ° derived from `phreeqc.dat` diffusion coefficients (z²F²D/RT) are 31.8 for H₂PO₄⁻, 103.6 for HPO₄²⁻ and 206.8 for PO₄³⁻ S·cm²/mol. The owner checked the CRC 85th edition table "Ionic Conductivity and Diffusion at Infinite Dilution" (Vanýsek, opening p. 5-92; phosphate rows on the following page). It gives 36 for H₂PO₄⁻, 57 for ½HPO₄²⁻ (114 molar) and 92.8 for ⅓PO₄³⁻ (278.4 molar). The earlier recalled PO₄³⁻ figure of 207 was wrong.

### O1: phosphate coefficients (amended 2026-10-19)
- **Why the source changed:** Muccitelli & DiAngelo (1994) has no lawful open copy: Unpaywall lists it as closed and OSTI holds only the abstract. Tsurko et al. (1999) is also closed.
- **Data:** Pethybridge, Talbot & House, *J. Solution Chem.* 35, 381–393 (2006), doi 10.1007/s10953-005-9003-z, Table III. It gives 25 °C molar conductivities of KH₂PO₄ (12 points, 0.0447–6.7214 mmol/dm³) and ½K₂HPO₄ (10 points, 0.0484–9.5533 mmol/dm³ of the half-formula). Speciated I runs from 5×10⁻⁵ to 0.014 mol/kgw.
- **Fit:** each point is speciated with FlahaX at calculated pH. K⁺, H⁺, OH⁻ and the other covered species use McCleskey. λ° and A for H₂PO₄⁻ and HPO₄²⁻ are free, and B is fixed at 1.5, the McCleskey B of K⁺ and Cl⁻. The fit is linear in λ° and A; the residuals are published.
- **Why λ° is fitted, not fixed:** Pethybridge's λ° (33.33 and 115.14) comes from a Lee–Wheaton analysis with its own ion pairing. Holding it fixed in FlahaX speciation biased the dilute points by +1.3 % and pushed A and B to unphysical values. A throwaway feasibility fit with λ° free gave:

  | B | λ°(H₂PO₄⁻) | A | λ°(HPO₄²⁻) | A | RMS |
  |---|---|---|---|---|---|
  | 0.5 | 31.70 | 33.3 | 109.2 | 212.6 | 0.16 % |
  | 1.5 | 31.73 | 35.9 | 109.7 | 238.9 | 0.13 % |
  | 3.0 | 31.77 | 39.9 | 110.4 | 279.3 | 0.11 % |

- **Using the fit above the data range:** the data reach I = 0.014, while shipped formulas reach 0.046. Across B = 0.5–3 the H₂PO₄⁻ λ at I = 0.046 moves by about 5 %. With phosphate at no more than 8 % of EC, that is under 0.4 % of EC. The audit records `phosphate_fit_max_ionic_strength` = 0.014 so readers can see when the fit is being used beyond its data.
- **Cross-checks** (reported, never blocking):

  | Source | H₂PO₄⁻ | HPO₄²⁻ |
  |---|---|---|
  | CRC | 36 | 114 |
  | Pethybridge (Lee–Wheaton) | 33.33 | 115.14 |
  | `phreeqc.dat` | 31.8 | 103.6 |

  The fitted values must be within 15 % of each, or the gap is stated.
- **M2b fit (shipped, `tools/fit_phosphate_conductivity.py`):** λ°(H₂PO₄⁻) = 31.730, A = 35.926; λ°(HPO₄²⁻) = 109.669, A = 238.888; B = 1.5. RMS 0.127 % over 22 points, worst −0.274 % (½K₂HPO₄ 9.5533 mmol/dm³), I up to 0.01396. Uncovered minor species (KHPO₄⁻, PO₄³⁻) are left out of the model κ; their O2 bound is up to 1.69 % of κ at the most concentrated ½K₂HPO₄ point (KHPO₄⁻ 2.0×10⁻⁴ mol/kgw, 4.4 % of phosphate), so the fitted HPO₄²⁻ coefficients absorb that pair's current. KHPO₄⁻ is not covered; the fitted HPO₄²⁻ coefficients absorb part of its current, so when FlahaX bounds KHPO₄⁻ as uncovered in a mixture the upper end of the range counts that current twice — small (≤ 1.7 % of κ at the most concentrated fit point) and conservative. The shipped block carries this as `fit.note`. Cross-check gaps: CRC −11.9 % / −3.8 %, Lee–Wheaton −4.8 % / −4.8 %, `phreeqc.dat` −0.2 % / +5.9 % (H₂PO₄⁻ / HPO₄²⁻), all within 15 %.
- **M2b recount (2026-10-19):** all 26 formulas `estimated` and bounded (recommend doses, g/L as g/kgw, declared RO water, calculated pH; I 0.016–0.046). Range width as % of the midpoint (midpoint mS/cm): Generic Wet Season 5.40 (1.619); Tomatoes Third Cluster 2.74 (1.418); Tomatoes Fourth Cluster 2.53 (1.550); Lettuce General 2.14 (1.959); Tomato Stage 3 1.81 (2.782); Generic Dry Season 1.81 (2.413); Cucumber 1.49 (2.288); Tomatoes till First Cluster 1.43 (1.202); Melons 1.41 (2.614); Tomatoes Second Cluster 1.40 (1.267); Rice 1.33 (2.711); Chilli 1.33 (4.069); Strawberry Fruiting 1.28 (1.596); Tropical Lettuce 1.18 (1.807); Generic for Berries 1.03 (2.347); Tomato 0.91 (2.303); Lettuce 2 0.89 (2.253); Strawberry Drip 0.73 (1.925); Tomato Stage 2 0.72 (1.943); DEFAULT 0.72 (2.201); Hoagland 0.72 (2.201); Tomatoes to termination 0.71 (1.781); Generic Bloom 0.68 (1.724); Tomato Stage 1 0.67 (1.353); Pepper 0.60 (2.926); Generic Grow 0.48 (1.961). **Maximum 5.40 %** (was 14.38 % under M2a), still from citrate pairs; the remaining bound comes from Ca/Mg citrate, CaNO₃⁺, Ca/Mg H₂PO₄⁺, CaPO₄⁻ and Fe-EDTA species. The all-formulas test ceiling is 0.060.
- **PO₄³⁻:** no measurement exists (Pethybridge assumed 80 per charge), so PO₄³⁻ stays under the O2 bound. It is negligible at irrigation pH.
- **Transcription:** the owner's transcription of Table III is the first copy. A second, independent copy is typed from the PDF in `docs/sources/` (which is not versioned), and a test compares them, as was done for Table 1. **Merging the coefficients requires both copies to agree.**

### O2: one-sided bound
- **λ_max:** 80 S·cm²/mol per unit charge, at infinite dilution, with no ionic-strength reduction. In the limiting-conductivity table (Adamson 1973, p. 512, as reproduced in standard tables), no ion except H⁺ and OH⁻ exceeds this per unit charge; the highest are SO₄²⁻ at 79.8 and Br⁻ at 78.4. H⁺ and OH⁻ are always covered by McCleskey.
- **Bound:** bound = Σ |zᵢ| · 80 · mᵢ over every uncovered charged species above 1×10⁻¹² mol/kgw. Every uncovered species is still listed.
- **Result:** when uncovered species exist and every other rule passes, the status is `estimated` and `bounded: true`.
  - `ec25_range_ms_cm` = (known subtotal, known subtotal + bound). The range is one-sided because missing contributions cannot be negative.
  - `ec25_ms_cm` is the midpoint and `uncertainty_ms_cm` is half the bound.
  - The audit records `uncovered_bound_ms_cm`.
- **Unchanged rules:** unrecorded counterions, the assay-residual gate and the domain checks still produce `partial` or `not_supported` as before. O2 never applies to them.
- **Post-mix comparison:** accepts a bounded estimate. It reports the difference to the midpoint and whether the measurement falls inside the range, as a fact, not a verdict.

### M2 staging
- **M2a:** the O2 bound, with no new data. Shipped formulas become `estimated` with a published range.
- **M2b:** phosphate coefficients fitted to Pethybridge et al. (2006) Table III (O1 as amended; the Muccitelli & DiAngelo source was replaced). The range narrows by the phosphate share.
- **Exit:** "typical catalogue recipes return `estimated`" is met by M2a. M2b reduces their uncertainty.

## 12. Left to the builder

Function and module names; JSON layout of the coefficient file; the numerical
reporting tolerance for molality and charge imbalance (state and test the
values chosen); CLI flag naming; how contributions are ordered in output;
the exact error codes beyond those named here.

## Related, out of scope

A separate methods article on extending McCleskey's method to fertilizer
solutions (phosphate coverage, speciation coupling) follows M2/M3, because its
claims depend on that evidence.

## Reference

McCleskey, R. B.; Nordstrom, D. K.; Ryan, J. N.; Ball, J. W. A new method of
calculating electrical conductivity with applications to natural waters.
*Geochimica et Cosmochimica Acta* 2012, 77, 369–382.
<https://doi.org/10.1016/j.gca.2011.10.031>
