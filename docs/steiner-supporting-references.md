# Supporting references for Steiner recipe validation

These sources motivate validation work. They do not certify the numerical safety
margin, preparation bounds, or exact Steiner recipe used by FlahaX.

| Reference | Evidence and use | Boundary |
|---|---|---|
| Kaneko, F. and Ohashi, T. (1993). The Preventive Measures of Calcium Phosphate Precipitation in Nutrient Solution for Hydroponic Cultivation. Japanese Journal of Soil Science and Plant Nutrition 64(3), 312–318. [DOI](https://doi.org/10.20710/dojo.64.3_312) | Direct nutrient-solution precipitation study; supports tracking pH, time, composition and nutrient retention. | Japanese full text; assessment uses the publisher's English abstract. Its preventive pH recommendation is composition-specific. |
| Nancollas, G. H., Tomazic, B. and Tomson, M. (1976). The Precipitation of Calcium Phosphates in the Presence of Magnesium. Croatica Chemica Acta 48(4), 431–438. [Publisher](https://hrcak.srce.hr/196436) | Seeded experiments show magnesium-dependent precursor transformations and crystallization kinetics. | Physiological-pH experiments do not calibrate precipitation time at pH 6.3. Retain equilibrium SI separately from kinetic predictions. |
| Inskeep, W. P. and Silvertooth, J. C. (1988). Kinetics of hydroxyapatite precipitation at pH 7.4 to 8.4. Geochimica et Cosmochimica Acta 52(7), 1883–1893. [DOI](https://doi.org/10.1016/0016-7037(88)90012-9) | Seed surface area, activities and temperature are inputs to precipitation-rate interpretation. | Abstract reviewed; full text not downloaded. Extrapolation to pH 6.3 is unvalidated. |
| Buck, R. P. et al. (2002). Measurement of pH. Definition, standards, and procedures (IUPAC Recommendations 2002). Pure and Applied Chemistry 74(11), 2169–2200. [DOI](https://doi.org/10.1351/pac200274112169) | Framework for pH traceability, calibration and uncertainty. | Official record reviewed; PDF download returned HTTP 403. It does not identify the cause of Steiner's 0.13-unit discrepancy. |

The first two PDFs and a provenance manifest are stored in the user's FlahaX
Articles/References/Calcium phosphate safety collection. They are reading references,
not executable reference fixtures or replacements for the pinned thermodynamic database.

The 0.30 SI allowance, 1% relative ratio tolerance and 2% relative concentration
tolerance are explicit engineering acceptance choices, not values established by
these papers. The preparation example uses user-specified bounds of ±0.001 g,
99–100% assay and ±0.05 L final volume. It assumes the unassayed fraction is inert;
reactive contaminants require separate component accounting.
