# Predicting nutrient-solution chemistry from irrigation water analysis: field evaluation of an open-source Python engine for tomato in Qatar

<!--
DRAFT. Status: Introduction and Methods written; protocol and acceptance
thresholds fixed BEFORE any measurement (see decisions.md, decision 17).
Results, Discussion and Conclusion are placeholders until field data exist.
Target journals: Computers and Electronics in Agriculture, Agricultural Water
Management, or Horticulturae. Reformat to the chosen journal's template at
submission.
Do not loosen any threshold after data collection starts. If a threshold
must change, record the change and the reason before seeing the data it
affects.
-->

**Authors:** Rafat A. Al Khashan (Flaha Agri Tech, Qatar)
<!-- TODO: co-authors and affiliations, decided before the trial starts -->

## Abstract

<!-- PLACEHOLDER: write last, from the results. Structure: problem (recipes
that are right on paper but fail in the tank on hard water); what FlahaX
predicts; design (two Qatar sites, tomato, contrasting waters, thresholds
fixed in advance); key numbers; one-line conclusion. ~250 words. -->

## 1. Introduction

Fertigation and hydroponic production depend on nutrient solutions mixed
from water-soluble fertilizers and the farm's own irrigation water. The
standard way to design these solutions is a mass balance: choose salts and
quantities so that, after the nutrients already in the water are subtracted,
each element reaches its target concentration (Sonneveld and Voogt, 2009).

A mass balance assumes that every gram of fertilizer stays dissolved and
available. In practice the irrigation water and the fertilizers react. In
hard or alkaline water, calcium can precipitate with phosphate or sulfate,
bicarbonate buffers the solution and sets how much acid is needed, and the
acid itself adds nitrogen or phosphorus. These effects matter most where
irrigation water is hard or brackish, as in much of the Arabian Peninsula,
where groundwater is often high in calcium, sulfate, sodium and chloride
<!-- TODO cite: Shomar 2024 and a regional source -->.

Equilibrium chemistry codes such as PHREEQC (Parkhurst and Appelo, 2013)
can predict these effects, but they are general geochemical tools and are
rarely used in day-to-day recipe design. Decision support systems such as
NUTRISENSE have shown the value of calculating and readjusting nutrient
solutions from analyses in closed systems <!-- TODO cite NUTRISENSE -->.
To our knowledge, no openly available tool combines fertilizer formulation
against the actual water with fertilizer-specific equilibrium chemistry,
acid planning and stock-tank planning, and none has been evaluated in the
field for that combination.

FlahaX is an open-source (Apache-2.0) Python engine that does this
<!-- TODO cite JOSS paper when published -->. Its predictions so far are
verified only computationally, against PHREEQC. This study asks whether
those predictions hold on real farms.

**Objective.** To evaluate, at two commercial tomato farms in Qatar with
contrasting irrigation waters, how closely FlahaX's predictions of solution
pH, acid requirement, precipitation and delivered nutrient concentrations
match field and laboratory measurements, against acceptance thresholds set
before any data were collected.

## 2. Materials and methods

### 2.1 Software

FlahaX version <!-- TODO: exact released version, Apache-2.0 --> was used
unchanged throughout the trial. The version, the input files and the source
hashes recorded by FlahaX for every plan are archived with the data
<!-- TODO: Zenodo DOI -->. The software's stated validity range is 25 °C,
ionic strength up to 0.1 mol/kg, fixed oxidation states and closed inorganic
carbon. A prediction outside that range is reported as "not supported" and
is excluded from the accuracy statistics but counted and reported.

### 2.2 Sites

| | Site A | Site B |
|---|---|---|
| System | Open-field drip | Greenhouse hydroponic |
| Crop | Tomato (*Solanum lycopersicum*) | Tomato |
| Cultivar | <!-- TODO --> | <!-- TODO --> |
| Water source | On-farm well | Delivered irrigation water |
| Location | Qatar, anonymised | Qatar, anonymised |
| Season | <!-- TODO --> | <!-- TODO --> |
| Area / lines / substrate | <!-- TODO --> | <!-- TODO --> |
| Fertigation equipment | <!-- TODO: injector or dosing type --> | <!-- TODO --> |

The two sites were chosen for contrast: the well water at Site A is expected
to be hard and saline, and the delivered water at Site B soft and weakly
buffered. <!-- TODO: confirm from the lab analyses in 2.3 -->

**Scope check before the trial.** Each site's water analysis and recipe will
be run through FlahaX before planting. If the resulting solution exceeds the
model's ionic strength limit, that site cannot test in-range predictions.
This will be reported, and the site's role in the study will be decided
before measurements begin. <!-- See decisions.md, open item 2. A median
well in the Shomar (2024) survey stays inside the limit, but already exceeds
tomato's Ca and S targets; saltier wells exceed the limit. -->

### 2.3 Irrigation water analysis

Before the trial, each water source is sampled and analysed by an accredited
laboratory for measured pH, total alkalinity by titration, EC, Ca, Mg, Na, K, HCO₃, CO₃, Cl, SO₄, NO₃, NH₄, P and B,
with Fe, Mn, Zn and Cu where available. Bicarbonate is required: without it,
pH and acid cannot be predicted. Sampling is repeated <!-- TODO: frequency,
e.g. monthly --> to capture variation in the water over the season.

| | Laboratory | Method reference | Sampling dates |
|---|---|---|---|
| Site A | <!-- TODO --> | <!-- TODO --> | <!-- TODO --> |
| Site B | <!-- TODO --> | <!-- TODO --> | <!-- TODO --> |

### 2.4 Nutrient targets and recipes

Both sites use tomato nutrient targets from <!-- TODO: cite the target
source, e.g. Sonneveld and Voogt (2009), by growth stage -->. For each site,
FlahaX computes the recipe from the targets, the water analysis and the
fertilizer products actually available on the farm, with their labelled
assays. The farm then prepares stock tanks and injects according to that
plan. Any deviation by the farm (substituted product, different volume) is
recorded and the prediction is recomputed for what was actually done.

### 2.5 Measurements

| Measurement | Where | Instrument / method | Frequency |
|---|---|---|---|
| pH | Drip solution at the emitter | <!-- TODO: meter model, calibration (2-point, buffers) --> | <!-- TODO --> |
| EC (25 °C compensated) | Drip solution at the emitter | <!-- TODO: meter model, calibration --> | <!-- TODO --> |
| Acid requirement | Titration of the mixed solution to the target pH | <!-- TODO: acid grade, burette or dosing method --> | Per recipe |
| Precipitation | Each stock tank, after 24 h | Visual: sediment, cloudiness; filter and emitter checks | Per tank preparation |
| N-NO₃, N-NH₄, P, K, Ca, Mg, S | Drip solution sample | Accredited laboratory <!-- TODO: methods --> | <!-- TODO --> |

### 2.6 Acceptance thresholds

These thresholds were fixed on 2026-10-17, before any field measurement.

| FlahaX prediction | Measured value | Threshold for agreement |
|---|---|---|
| pH of the drip solution | pH at the emitter | within ±0.3 pH units |
| Acid to reach the target pH | Titrated acid | within ±15% |
| Precipitation in each stock tank (yes/no) | Observation after 24 h | Prediction matches observation |
| N, P, K, Ca, Mg, S in the drip solution | Laboratory analysis | within ±10% of target |
| EC of the drip solution | EC meter | Reported with error statistics; no threshold, because FlahaX's EC accuracy is not yet established |

### 2.7 Analysis

For each continuous variable, the study reports the mean error (bias), the
mean absolute error and the share of observations within the threshold, per
site and pooled. For precipitation, it reports a confusion table (predicted
versus observed). Predictions marked "not supported" by FlahaX are counted
separately. All data, inputs, FlahaX outputs and analysis scripts will be
published <!-- TODO: repository and DOI -->.

## 3. Results

<!-- PLACEHOLDER. Fill only from measured data. Suggested structure:
3.1 Water analyses at both sites (table), and whether each site was in scope.
3.2 pH: predicted versus measured, per site; bias, MAE, % within ±0.3.
3.3 Acid requirement: predicted versus titrated; % within ±15%.
3.4 Precipitation: confusion table per site.
3.5 Delivered nutrients: predicted versus lab, per element; % within ±10%.
3.6 EC: predicted versus measured, error statistics only.
Report failures as plainly as successes. -->

## 4. Discussion

<!-- PLACEHOLDER. Write after Results. Cover: where predictions held and
failed and why (water hardness, ionic strength, product assays, mixing
practice); comparison with mass-balance-only recipe design; what the hard
versus soft water contrast shows; limits of the study (two sites, one
season, one crop); what it means for growers and advisers; next steps
(validated EC, more crops and waters). -->

## 5. Conclusion

<!-- PLACEHOLDER. Three to five sentences, only claims the results support. -->

## Data and software availability

FlahaX is open source under the Apache License 2.0, at
https://github.com/rafatahmed/Flahax and on PyPI. <!-- TODO: exact version
and archived DOI; data DOI. -->

## AI usage disclosure

Generative AI coding assistants were used in developing FlahaX and in
drafting this manuscript. <!-- TODO: tools, versions and where used. --> The
author designed the study, made all scientific decisions, collected and
analysed the data, and reviewed and is responsible for all content.

## Acknowledgements

<!-- TODO: the two farms (anonymised if required), the laboratory, anyone
who took measurements and is not a co-author, funding. -->

## References

<!-- TODO: format to the journal's style. To cite:
- Parkhurst, D.L., Appelo, C.A.J. (2013). PHREEQC version 3. USGS
  Techniques and Methods 6-A43. https://doi.org/10.3133/tm6A43
- Sonneveld, C., Voogt, W. (2009). Plant Nutrition of Greenhouse Crops.
  Springer. (verify edition and DOI)
- Shomar, B. (2024). Groundwater contamination in arid coastal areas: Qatar
  as a case study. Groundwater. https://doi.org/10.1111/gwat.13411
  (verify authors)
- NUTRISENSE, Acta Horticulturae 1317 (verify)
- FlahaX JOSS paper (when published)
-->
