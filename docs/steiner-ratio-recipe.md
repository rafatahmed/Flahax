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
