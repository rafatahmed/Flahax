# Fertilizer source-sheet review - 2026-09-30

These are user-supplied product references, not a standard source-water
analysis, a lot certificate, a hydraulic equipment catalogue, or measured
evidence for an arbitrary mixed stock. The PDFs were preserved unchanged.
Scanned SQM tables were read from rendered pages; no OCR-derived coefficients
were accepted without visual review. No shipped fertilizer or thermodynamic
database was changed.

## File identity

| File | SHA-256 |
|---|---|
| `04_Fertilizer.pdf` | `3ba275fa3e3a7011e5a3f93f046e2c84a2656656b772b656778dc66e5110242e` |
| `165357805552.pdf` | `28a15230851581f66255fe45f67f6e3b580d88f5cfbbc65a7cb97a9c5171ad48` |
| `215057776303.pdf` | `fff47a7e24dd86edf605b2d2b61802fa881b65e9f1dabf3f134b72a2e4870c07` |
| `215726931002.pdf` | `1f1a6200c54883b24d55a41bfee559fe8bd56f52c716a4c5654a563cb634d6ee` |

All files are under `docs/sources/`. They are local review inputs; permission
to redistribute manufacturer PDFs in a release has not been established.
Runtime calculation does not require these PDFs to be installed.

## Findings and use

| Source | Useful evidence | Boundary / action |
|---|---|---|
| Yara training slides, `04_Fertilizer.pdf`, dated 2005-01-13 | Product assays, general dissolution and tank incompatibilities. Page 40 identifies calcium nitrate containing 14.4% nitrate-N and 1.1% ammonium-N. | Supports treating NH4 as an actual product contribution, not an invented ingredient. EC tables label 1% at 20 C (page 40: 1.2 dS/m); these cannot be substituted for the SQM 1 g/L at 25 C figures. No automatic import of ambiguous units. |
| SQM macronutrients, `165357805552.pdf`, page 2 | Guaranteed analysis, single-product solubility at 20 C, EC at 1 g/L and 25 C, pH of 1% solution. Calcium/sulfate/phosphate stock incompatibility warnings. | Source of exact-brand EC anchors below. Single-product solubility is not a mixed-stock solubility limit. Product pH is not the final recipe pH. |
| SQM micro Rexene, `215057776303.pdf`, pages 1-2 | FeD12: 11.6% Fe-DTPA; FeE13: 13.3% Fe-EDTA; Cu15: 15% Cu-EDTA; Mn13: 13% Mn-EDTA; Zn15: 15% Zn-EDTA. FeD6 liquid: 6.1% Fe, density 1.30 g/mL. | These are distinct commercial grades, not generic catalogue replacements. FeQ48: 6% Fe but 4.8% specified as ortho-ortho EDDHA; do not treat all 6% as pure o,o-EDDHA. FeXQ58 contains HBED/EDDHA: outside frozen chemistry. No micronutrient EC table. |
| SQM micro Rexene Combi, `215726931002.pdf`, pages 1-2 | XMZ, ABC and APN blend compositions and pH stability ranges. | XMZ includes Fe-HBED; APN uses Fe-DTPA; ABC includes MgO and different trace ratios. None establishes the existing CH-micro recipe or its borax/molybdate forms. No substitution or expansion of the frozen boundary. |

The brochures disclaim site-specific performance. Metal assay alone does not
fully establish counterions, hydration or active-isomer distribution.
The acid slide is not a certificate of analysis for the user's industrial
nitric/phosphoric products: their assay, density and provenance remain inputs.

## Clarification: Yara compatibility and the A/B report

Pages 63, 65 and 66 were additionally reviewed as full rendered pages.
Page 65's triangular table is pairwise: follow a product's row to the other
product's column on the diagonal. CALCINIT/KRISTA-MAG and CALCINIT/KRISTA-K are
marked Yes; CALCINIT with SOP, MKP, MAP, phosphoric acid or AS is No.
KRISTA-MAG (magnesium nitrate) with MKP/MAP/phosphoric acid is No in this
table, even though page 63 gives a pH-qualified magnesium/phosphate warning.
For a conservative draft separation, use the explicit No, not an assumption
that a target irrigation pH approves the concentrate.

The single-star cells are limited by SOP solubility; double-star cells by
MgS solubility. A Yes is therefore not unlimited concentration or a complete
multicomponent stock guarantee. Page 66 illustrates Ca/K/Mg/chelates on one
side and P/K/S/acids on the other. Magnesium nitrate belongs on the calcium
side of this illustration; magnesium sulfate must not be inferred to do so.

The pepper report now shows candidate A: calcium nitrate, magnesium nitrate,
potassium nitrate and Mn-EDTA; candidate B: potassium sulfate and MKP.
These are chemical-form analogies to the source, not a declaration that the
generic catalogue products are the named Yara grades. KNO3's choice of A is
a layout choice, not a requirement. The table does not resolve boric acid,
sodium molybdate or the Fe/Cu/Zn sulfate mixture with phosphate. Those remain
explicitly unassigned. The source's chelate grouping must not be applied to
iron sulfate as if it were chelated iron.

A dedicated acid channel is proposed for independent pH control; page 66
actually illustrates acids with the B-side concept, so a separate channel
is **not** attributed to the source as a requirement. Phosphoric acid cannot
go into the calcium concentrate; page 63 warns against acidifying chelate
tanks. A B-side acid arrangement still needs grade/mixture/operating review.
Existing recipe phosphoric-acid mass is not an additional pH-correction dose.
No new compatibility database entries or approved StockPlan were generated.

## Visually verified SQM anchors

`165357805552.pdf`, page 2: EC of **1 g product/L at 25 C**, in mS/cm.

| Exact commercial product | EC anchor |
|---|---:|
| Ultrasol K Plus | 1.3 |
| Ultrasol SOP | 1.5 |
| Ultrasol MKP | 0.7 |
| Ultrasol MAP | 0.9 |
| Ultrasol Calcium | 1.2 |
| Ultrasol Magsul | 1.2 |
| Ultrasol Magnit | 0.9 |

The brochure also lists Magnum P44 at 1.5; this acidifying urea-phosphate
product is not included in the pre-acid screening implementation. Acid/base
reactions require more than an additive conductivity assumption. Magsul is
**1.2**, not 0.9. Headline grades can differ from detailed guaranteed analysis:
e.g. Magnit's nitrate-N table is 10.7%, not the rounded headline 11.

## What can now be calculated without new measurements

`estimate_manufacturer_ec` uses `water EC25 + sum(product g/L * anchor)` for
exact named products, pre-acid, at 25 C. Linear scaling, additive conductivity,
and negligible interactions are **explicit unvalidated screening assumptions**.
Total fertilizer loading is capped at 1 g/L by software policy, not claimed as
a manufacturer-validated mixture range. Error bounds remain unknown.
Unknown trace products, acid additions, other temperatures and concentrated
stock channels produce no total EC. Therefore the full pepper recipe does
**not** acquire an unsupported EC number from these sheets.

No new site measurements are required to use this screening path. The older
measured-profile API remains available as an optional separate method; its
synthetic example values are not field evidence. A predictive concentrated
electrolyte conductivity model is still unimplemented, not replaced by a
linear extrapolation. See [site planning](site-planning.md).

## Equipment source boundary

Flow sizing is dimensional arithmetic. Equipment approval additionally needs
manufacturer operating data. Mazzei's [liquid-injection selection guidance](https://mazzei.net/support/performance-data-drawings/performance-data-drawings-venturi-injectors/)
and [agricultural injector brochure](https://mazzei.net/wp-content/uploads/2020/08/Injector-Ag-Brochure_2020-01-17_LR.pdf)
describe pressure-dependent venturi suction. Air/gas suction tables must not
be used as fertilizer-liquid curves. None of the four fertilizer PDFs can
select a pump, venturi or Dosatron model from farm area or tank capacity alone.
