# Fixed-ratio pure-salt recipes

Use the public Python function flahax.plan_ratio_recipe or pipe examples/steiner-ratio.json into the ratio command.

    python -m flahax ratio < examples/steiner-ratio.json

PowerShell accepts the same input through Get-Content.

    Get-Content examples/steiner-ratio.json -Raw | python -m flahax ratio

Cation shares are K, Ca and Mg equivalents. Anion shares are nitrate, total phosphate on the H2PO4 reporting basis, and sulfate equivalents. Each list is independently normalized. counted_mmol_l sums the six analytical amounts. pH, batch volume, demineralized water and final water mass are required. The example explicitly approximates 10 litres of final dilute solution as containing 10 kg water.

The supported preparation uses pure KH2PO4, Ca(NO3)2.4H2O, MgSO4.7H2O, Mg(NO3)2.6H2O, KNO3 and KOH. Amounts are calculated from each chemical formula using the existing atomic-weight table. A target requiring negative amounts or other sources returns ratio_allocation_infeasible. Non-demineralized water is outside this first workflow's input contract.

The aqueous model calculates the cation and anion group totals at the requested strength and pH. Final ingredient reconstruction verifies charge and preserves analytical ratios. KOH potassium contributes to the final potassium target. The calculation uses 25 C, zero added inorganic carbon and no gas exchange. The result includes all mineral saturation indices and the existing saturation assessment. It provides full-precision quantities and calls for rechecking rounded delivered doses.

Steiner's pH 6.30 example gives 50:30:20 and 5:3:1, 30 mmol/L and about 1.316738 mmol/L potassium supplied by KOH in this model. The original empirical curve gives a different base dose. The solution is supersaturated with respect to calcium phosphate phases, which is visible in the output.

Historical validation remains qualified. Solution 1a measured 5.33, 6.45 and 6.58 after aeration, while the model gives about 5.06, 6.66 and 6.66. Matched PHREEQC differs by less than 0.002 pH unit, but both fail to reproduce the measured 0.13 rise. Temperature and common equilibrium air-exposure scenarios did not resolve it. Physical pH accuracy and nutrient retention require additional experimental evidence.

Primary source: https://edepot.wur.nl/309364, pp. 145-153.

## Rounded-dose saturation verification

Add ph_range, selected_phases and mass_decimals to the ratio request. For example:

    "ph_range": [6.28, 6.32],
    "selected_phases": ["Brushite", "Monetite", "Hydroxyapatite"],
    "mass_decimals": 5

The verification first rounds every ingredient mass in grams and reconstructs all nutrient amounts from the chemical formula. Output includes the rounded ingredient list, ratios, concentration and nutrient errors. Each nutrient must remain within 0.1% of its target plus 1e-10 mmol/L numerical allowance. The independently charge-balanced pH of the rounded batch must lie inside the requested interval.

The calculation checks endpoints, the target pH and interior points at maximum spacing 0.001 pH. For each mineral it reports the largest index and the pH at which it occurred. Every selected mineral must have SI below -1e-7, a numerical guard around saturation. The status passed means the rounded batch met the nutrient, pH and selected mineral tests on the disclosed grid. This is a sampled numerical check, with no mathematical bound for unsampled points. Failed solves or unavailable phase values return incomplete.

This sensitivity holds rounded analytical nutrient totals fixed while imposing each pH. Off-target charge residuals are visible. An actual acid/base addition or gas-exchange scenario requires including the resulting composition change.

At 6.30 the 11.392 mmol/L mixture passes the monetite point check, but it fails at 6.32. Likewise, the 1.94968 mmol/L mixture passes the hydroxyapatite point check but fails at 6.32. At 1.8 mmol/L the rounded mixture passes all three selected mineral checks over the stated grid.

The ordinary full-precision recipe remains available alongside rounded_verification. Command exit zero indicates successful calculation; inspect rounded_verification.status to determine whether the requested checks passed.

## Strongest verified rounded candidate

Use `flahax.search_ratio_recipe` or replace `counted_mmol_l` with `strength_range` in the ratio command. A search requires `ph_range`.

    Get-Content examples/steiner-ratio-search.json -Raw | python -m flahax ratio

The example searches 1–30 mmol/L, keeping Steiner's equivalent ratios and targeting pH 6.30. Each candidate is allocated to the six ingredients, rounded to five decimal places in grams for 10 litres, reconstructed, and checked using the pH interval verification above. KOH potassium remains included. The strongest passing requested concentration found is returned with the actual rounded concentration and ratios in `recipe.rounded_verification`.

The search evaluates a uniform strength grid (default 33 points), then refines every observed passing-to-failing transition to `strength_tolerance` (default 0.00001 mmol/L). It independently recalculates the selected recipe before returning it. Rounding can cause discontinuous feasibility, so this reports the strongest verified candidate found, without claiming a global optimum. Narrow disconnected feasible regions can escape the initial scan. Transition brackets, evaluated strengths and pH coverage are disclosed. Increase `scan_points` to inspect more of the requested strength interval.

`status: found` means a verified candidate was found and all observed transitions were refined. `search_cap_reached` means the upper strength bound itself passed; the search has then supplied no saturation-limited maximum. `no_feasible_candidate_found` describes the evaluated candidates only. Failed chemistry calculations or unfinished refinement return `incomplete`, possibly with a lower verified candidate. `limiting_phase` identifies the selected mineral with the smallest SI margin in the delivered candidate; at a search cap it need not set the strength limit.

The numerical SI guard is only a numerical margin. A candidate close to saturation has no allowance for weighing error, impurity, temperature, carbon uptake or uncertain reaction constants. Physical clarity remains unvalidated, and the unresolved solution 1a experimental pH difference remains in every returned recipe's qualifications.

## Explicit saturation safety margin

Searches now default to `saturation_margin: 0.3`. Every selected phase must satisfy
`SI < -saturation_margin - 1e-7` at every sampled pH after mass rounding. Since
`SI = log10(IAP/K)`, a margin of 0.30 limits IAP/K to approximately 0.5012.
This is an engineering allowance chosen for this workflow, not a validated physical
uncertainty bound. SI uses the pinned reaction normalization; compare margins only
after matching reaction stoichiometry and thermodynamic conventions.

Fixed-strength requests retain a default margin of zero for compatibility; pass
`saturation_margin: 0.3` with `ph_range` to apply the same acceptance policy.
Explicit zero in a search reproduces the earlier numerical-boundary search.
Negative, nonfinite and boolean margins are rejected. The margin and activity-product
fraction are recorded in the rounded verification; the independent final check uses
the same policy as candidate selection.

For the example's 1–30 mmol/L search, the requested strength is approximately
1.720861 mmol/L and the delivered rounded concentration is 1.720848 mmol/L.
The worst indices, all at pH 6.32, are brushite -1.715116, monetite -1.435089
and hydroxyapatite -0.300021. The rounded batch's modeled pH is 6.299946.
This result preserves the six nutrient targets within the stated rounding tolerance,
including KOH potassium. It is the strongest passing candidate found on the disclosed
search, not a global optimum or a crop nutrition recommendation.

Five decimal places in grams specify the numerical recipe, not attainable weighing
accuracy. Dose precision, reagent assay, final volume and source-water composition
must be measured before claiming practical robustness. In particular, changing the
base dose or aeration can move pH outside the checked range. No uncertainty model
or precipitation-rate model is inferred from this margin.

## Preparation uncertainty

The optional `uncertainty` object applies to fixed recipes and searches. See
`examples/steiner-ratio-uncertainty.json` for the user-selected preparation bounds:

```json
{
  "weighing_error_g": 0.001,
  "purity_fraction": [0.99, 1.0],
  "volume_error_litres": 0.05,
  "ratio_relative_tolerance": 0.01,
  "concentration_relative_tolerance": 0.02,
  "impurity_model": "inert"
}
```

These are bounded errors, not standard deviations or confidence intervals. The
same weighing and assay bounds apply independently to all six ingredients, including
KOH. Purity is the mass fraction of the specified hydrate or compound, with the
remainder assumed chemically inert. No compensation for nominal assay is applied.
KOH containing reactive carbonate is outside this contract. Water mass scales with
volume using the explicitly supplied nominal water-mass/volume approximation.

For each rounded dose `g`, the effective compound interval is
`[(g - weighing_error_g) * purity_low, (g + weighing_error_g) * purity_high]`.
Negative possible weighed mass is rejected. The checker reconstructs nutrient amounts
at all effective-dose corners and both volume bounds: normally 64 × 2 = 128
preparation scenarios. Every scenario is checked on the same disclosed pH grid,
with the same saturation margin. Charge-balance endpoint signs must bracket an
equilibrium pH inside the requested interval. No unaccounted acid/base correction is
assumed to restore pH. This pH condition is separate from imposing pH for SI sensitivity.

Independent errors cannot preserve exact ratios. The example permits 1% relative
change in each equivalent share and 2% in the total analytical concentration.
These are explicit engineering tolerances, separate from the existing nominal
rounding check. Reported ratio and concentration ranges disclose actual deviations.
For positive dose intervals these linear/fractional quantities attain their extrema
at corners. The nonlinear chemistry is a scenario check; it supplies no continuous
interior bound or mathematical global optimum. Missing phases or failed solves
return `incomplete`. A nominal failure skips uncertainty calculations and remains failed.

Search acceptance and final delivery verification both use `uncertainty_verification`
when supplied. Rejected strengths retain failure reasons. The 129-point 1–30 mmol/L
example found no passing candidate under these preparation bounds. At 1.7 mmol/L,
all 128 scenarios passed the 0.30 SI margin on the imposed pH grid (worst HAP SI
approximately -0.31262), but equilibrium pH escaped the interval and ratio deviations
reached 1.9063%, exceeding the 1% allowance. The concentration range was
1.666283–1.717079 mmol/L. This is a failed preparation case, not a deliverable recipe.

See [supporting references](steiner-supporting-references.md) for research context.
The unresolved solution 1a pH discrepancy remains visible. Tighter balance/assay
bounds or verified stock dosing should be evaluated explicitly before promising a
passing preparation; relaxing a tolerance requires a stated decision.

## Assayed-stock delivery specifications

`stock_dosing` replaces direct weighing with six independent single-compound stock
deliveries. See `examples/steiner-ratio-stock-search.json`. It requires a concentration
map (`concentrations_g_l`) with all six formula keys, `concentration_relative_error`,
`dose_error_ml` and `dose_decimals`. Concentrations are active mass equivalents of
the specified hydrate or compound per litre of final stock. They are not elemental
concentrations or unspecified commercial fertilizer grades.

The example specifies 10 g/L for KH2PO4, Ca(NO3)2.4H2O, MgSO4.7H2O,
Mg(NO3)2.6H2O and KNO3, and 1 g/L for KOH. Stock concentrations are bounded to
±0.1% and each delivered volume to ±0.02 mL, with doses rounded to 0.01 mL.
These are declared specifications, not measured assays or calibration records.
The numerical result is conditional on verifying them for actual stocks and dispensers.

The `uncertainty` object retains final-volume error, ratio and concentration
tolerances, and the inert-impurity model. Raw `weighing_error_g` and `purity_fraction`
are rejected in stock mode to avoid ambiguous double counting. Their effects must
instead be included in the verified stock-concentration interval, along with stock
preparation and stability errors. A 99–100% reagent label cannot alone support a
±0.1% active stock concentration. KOH alkalinity alone is insufficient if reactive
carbonate or other contaminants invalidate the declared pure-compound accounting.

For each ideal compound mass, the calculator rounds its stock dose in mL and
reconstructs nominal compound mass as `dose_ml * concentration_g_l / 1000`.
It does not round that equivalent mass a second time. Uncertainty endpoints are
`(dose_ml ± dose_error_ml) * concentration_g_l * (1 ± relative_error) / 1000`.
All stocks vary independently. The same 128 preparation corners and pH grid are
used. Stock-volume overflow and negative possible doses are rejected. Potassium
from the KOH stock enters both nominal and uncertain nutrient accounting.

Use six separate stocks and include all delivered stock volumes when making up
the final 10 L batch. This feature checks final diluted-solution chemistry;
stock solubility, storage stability and concentrate mixing compatibility are not
certified. The existing density approximation, 25 C assumption, excluded gas
exchange and unresolved historical pH discrepancy remain applicable.

For this example's 1–30 mmol/L bounded search, the strongest passing candidate
found requests 1.709473610 mmol/L. Rounded stock delivery gives 1.709479411 mmol/L
at nominal volume. Doses in source order are 44.88, 36.60, 13.55, 12.40, 14.45
and 24.70 mL, totaling 146.58 mL. The nominal modeled pH is 6.300028.
All 128 preparation corners pass; concentration ranges from 1.697906 to 1.721172
mmol/L and the largest relative equivalent-share deviation is 0.39925%.
Worst brushite, monetite and hydroxyapatite SI values are -1.715176, -1.435150
and -0.300258 respectively, all at imposed pH 6.32. This remains a sampled,
conditional calculation rather than measured stability or a proven global maximum.
