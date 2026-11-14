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
