# Steiner source uncertainties and applicability

Every successful fixed-ratio calculation now includes `historical_context`.
Strength-search reports include it even when no deliverable is found. The context
is advisory source evidence: it does not adjust chemistry, fit a pH offset, change
saturation margins, alter laboratory acceptance or certify experimental accuracy.
The fixed-recipe `qualifications` list also includes the applicable warning text.

## Evidence retained in reports

The packaged source record is
[`steiner_1961_evidence.json`](../src/flahax/data/steiner_1961_evidence.json).
It cites [Steiner (1961)](https://edepot.wur.nl/309364), with page references for
each evidence group. The supplied article transcription and prior figure audit
were used; contradictory statements are preserved, not repaired by inference.

| Evidence group | What the report preserves |
|---|---|
| Experimental design | 20 anion ratios × 16 cation ratios × five pH targets = 1,600 nominal conditions at the main strength. Later printed 360 versus earlier 320, plus 80 additional intermediate combinations; resolved curve-development sample count remains unknown. Precipitating mixtures were excluded from reformulation. |
| Figure 6 | Printed curve-A K:Ca 80:20 versus solution 1a's normalized 88.9:11.1; unresolved mapping, unavailable raw fitted points, fit uncertainty and reproducible extrapolation rule. OH-dose percentage is distinct from Figure 1's HPO4 species fraction. |
| Worked example and measurements | The pH 6.30 example's approximately 6.37 is a **stated expectation**. Solution 1a's 5.33, 6.45 and 6.58 are reported measurements. The +0.13 rise remains unresolved. |
| Water statement | The inconsistent printed conductivity clause is retained verbatim. The inequality is not silently reversed or converted to a water-quality specification. |
| Concentration and charge | Historical mg-ions/L means the six-nutrient analytical mmol/L sum here, not ionic strength, actual species count, measured osmolality or EC. The ideal 0.71 atm estimate assumes 15 °C and complete dissociation without hydrolysis/precipitation. Total phosphate uses the H2PO4 reporting basis; full species determine electroneutrality. |
| Historical domain | Main study at 30 mmol/L; limited tests at 20; no reported tests below 20; no demonstrated continuous 20–30 domain. Few combinations around 42 are not general validation. Calcium-free, phosphate-free and extreme ratios are excluded. Na substitution is exploratory; NH4 is untested. |
| Historical precision | ±0.20 at pH 5–5.5, ±0.15 at 5.5–6, ±0.10 at 6–7 and ±0.20 above 7 **within feasible curve coverage**. These are author-reported method claims, not FlahaX error bounds or measured instrument uncertainty. |
| Empirical screens | Ca × sulfate 60 and Ca × HPO4 approximately 2.2, interpreted dimensionally as (mmol/L)² for mmol/L inputs. Preserve the inconsistent printed units, approximate Figure 1 fraction and composition-dependent borderlines. These are not activity-based Ksp values or phase-specific SI thresholds. |

## Recipe-specific warnings

`historical_context` contains:

- `article`: independent copy of the source evidence;
- `assessed_strength_range_mmol_l` and `assessed_ph_range`;
- `warnings`: stable codes and explanatory messages;
- `establishes_experimental_validation: false`;
- `affects_numerical_acceptance: false`.

For a fixed recipe, the strength envelope includes full-precision amounts, rounded
delivery and the available uncertainty concentration range. The pH envelope uses
the requested verification interval, or just the target when no interval was
requested. For a search, the top-level context describes the **search range**;
the returned recipe's context describes that particular deliverable. Do not
confuse search-domain extrapolation with the selected recipe's strength.

| Warning code | Trigger / interpretation |
|---|---|
| `below_historical_tested_strength` | Strength envelope extends below 20 mmol/L; no low-strength experiments reported in this paper. |
| `limited_20_mmol_l_evidence` | Envelope includes 20 mmol/L; only limited additional historical testing. |
| `untested_strength_interpolation` | Envelope overlaps the interior between 20 and 30 mmol/L; the study does not establish continuous coverage. |
| `above_main_historical_strength` | Envelope extends above the main 30 mmol/L study. |
| `ph_below_investigated_curves` | Any requested pH is below 5, where Figure 6 relationships were not investigated. |
| `reduced_precision_above_ph_7` | Any requested pH exceeds 7; the precision statement does not establish universal upper-pH applicability. |
| `historical_calcium_phosphate_exclusion` | Calcium or phosphate share is exactly zero, an explicit exclusion from the historical method. |
| `curve_specific_coverage_unverified` | Always present: applicability depends on curve and composition; no universal upper-pH or numeric extreme-ratio cutoff is invented. |
| `historical_precision_not_model_uncertainty` | Always present: historical precision cannot be used to relax current model, pH or saturation requirements. |

A 1.71 mmol/L recipe can pass FlahaX's separately stated numerical constraints and
still warn that Steiner did not test that low-strength domain. Conversely, being
at 30 mmol/L and pH 6.3 does not prove historical applicability, absence of
precipitation, crop suitability or physical stability. No automatic source
"validated" badge is produced.

The solution 1a regression fixture links to the same packaged evidence resource;
its diagnostic report includes `article_evidence`. Published observations stay
separate from pinned numerical regression values. The packaged evidence is not a
thermodynamic database and does not modify equilibrium constants.
