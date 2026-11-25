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

**Acceptable deviation range**:
A range a user declares around a positive target (a symmetric percentage, with per-nutrient shortage and excess in percent or
mg/L). None is a default. Assess classifies the result against it; Require constrains the search by it. It never relaxes a zero
target or a declared maximum, and a miss is reported, not widened.
_Avoid_: Tolerance, allowance, default range

**Acceptable pH interval**:
A pair `(low, high)` given as the target pH. It is judged against its bounds: a mix inside needs no reagent, a mix outside
is moved to the nearest bound. No midpoint is ever used.
_Avoid_: Target range midpoint, pH setpoint range

**Total nitrogen target**:
Elemental N (`N`, mg/L) summed over nitrate, ammonium and urea; urea that is not asked for is a zero requirement, not an
unknown. Alone it imposes no form split. With a nitrate target and a positive ammonium target the forms determine it and it
must agree with their sum; otherwise both are scored and the overlap is reported. It is a target only, never water, a maximum
or an assay.
_Avoid_: Total N conversion, N split

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
phosphates in B. This is a usual layout, not a limit: the assignment may use more than two tanks (named A, B, C and so on),
and the effective assignment is in the result (`tanks.tanks`). Layouts depend on separation constraints and mixture evidence.
_Avoid_: Part A / Part B, Stock 1 / Stock 2

**Stock assignment**:
The grouping of a recipe's products into concentrate tanks so that no separation rule is broken, found without any
mixture approval. It uses the fewest tanks and does not depend on how many tanks the grower has.
_Avoid_: Tank grouping, Tank assignment, Separation assignment

**Required tanks**:
The number of tanks the stock assignment needs (`tanks.required_tanks`), set by the separation rules alone.
_Avoid_: Tank count, Tanks needed

**Available tanks**:
The tanks the grower declares (`--available-tanks`, `tanks.available_tanks`). When none are declared two are assumed
and the summary says so (`available_tanks_declared` false).
_Avoid_: Tank count, Owned tanks

**Equipment fit**:
Whether the available tanks, and their declared capacities, hold the required tanks' stock (`tanks.equipment.fit`).
A mismatch is reported and blocks; the recipe and the equipment are never changed to make it fit.
_Avoid_: Tank check, Capacity gate

**Single-product solubility**:
A product's own recorded solubility compared with its stock concentration. It is never mixed-stock approval, and its
qualification lists what stays unverified: the mixture, and the temperature when the value was recorded at another one.
_Avoid_: Solubility check, Mixture solubility

**Sonneveld target design**:
The A–D calculation from a crop/system baseline, explicit nutrient corrections and irrigation
EC to finished-feed targets.

**Root-zone feedback**:
A dated sample and guide comparison reviewed with explicit feed corrections approved by
the grower for the exact preview.

**Rounded preparation**:
The dry weights, separate product-stock volumes and reagent dose checked after rounding
under declared uncertainty and preparation tolerances.
