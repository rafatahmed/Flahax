# FlahaX

FlahaX turns crop-feed targets, source-water analyses and available products into candidate
batch recipes with pH-reagent accounting and preparation checks. Growers and agronomists
review the achieved nutrients, modeled chemistry, rounded doses and remaining qualifications.

## Language

**Formula**:
A crop's target nutrient concentrations in the finished feed (mg/L).
_Avoid_: Nutrient solution, program, mix

**Recipe**:
The fertilizer quantities calculated for a formula and a given water, with achieved nutrient
concentrations and residuals retained for review.
_Avoid_: Blend, result, plan

**Catalogue**:
The packaged products and formulas.
_Avoid_: Library, database

**pH reagent**:
A supplied acid or base product offered for pH adjustment. Its nutrient contributions enter
the finished-feed accounting.
_Avoid_: Acid, base, adjuster

**Label reconciliation**:
The charge a product label's ions cannot balance, reported and not refused.
_Avoid_: Label check, identity check, charge gate

**Ammonium allowance**:
An optional preset, off by default, that caps incidental NH₄-N when the NH₄ target is absent or zero at the smaller
of 10% of total target nitrogen and 1.5 mmol/L ammonium. An absent or zero NH₄ target is otherwise no requirement and no
maximum. A declared NH₄-N maximum takes precedence over the preset.
_Avoid_: Ammonium ban, zero ammonium

**Precipitation risk**:
A warning label from a phase known to form readily (brushite, gypsum, calcite) above saturation, or from an allocated solid.
_Avoid_: Saturation block, precipitation gate

**Phase information**:
A supersaturated phase that is not a precipitation risk, reported with the basis of its constant.
_Avoid_: Review finding, saturation review

**EC range**:
The low–high conductivity estimate, with no midpoint.
_Avoid_: EC value, mean EC, estimated EC

**Stated model condition**:
A limit reported with the result, such as closed carbon, 25 °C or 1 L of solution taken as 1 kg of water.
_Avoid_: Declaration, assumption to confirm

**Tank A / Tank B**:
The usual nutrient stock channels, with calcium and micronutrients in A and sulfates and
phosphates in B. Actual layouts depend on separation constraints, equipment and mixture evidence.
_Avoid_: Part A / Part B, Stock 1 / Stock 2

**Sonneveld target design**:
The A–D calculation from a crop/system baseline, explicit nutrient corrections and irrigation
EC to finished-feed targets.

**Root-zone feedback**:
A dated sample and guide comparison reviewed with explicit feed corrections approved by
the grower for the exact preview.

**Rounded preparation**:
The dry weights, separate product-stock volumes and reagent dose checked after rounding
under declared uncertainty and preparation tolerances.
