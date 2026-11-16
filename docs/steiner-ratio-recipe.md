# Fixed-ratio pure-salt recipes

Reports include [Steiner source uncertainties and applicability warnings](steiner-source-context.md).
The `historical_context` field distinguishes source observations, expectations,
historical limits and extrapolation from FlahaX's numerical acceptance.

Use the public Python function flahax.plan_ratio_recipe or pipe examples/steiner-ratio.json into the ratio command.

    python -m flahax ratio < examples/steiner-ratio.json

PowerShell accepts the same input through Get-Content.

    Get-Content examples/steiner-ratio.json -Raw | python -m flahax ratio

Cation shares are K, Ca and Mg equivalents. Anion shares are nitrate, total phosphate on the H2PO4 reporting basis, and sulfate equivalents. Each list is independently normalized. counted_mmol_l sums the six analytical amounts. pH, batch volume, explicit water input and final water mass are required. The example explicitly approximates 10 litres of final dilute solution as containing 10 kg water.

The supported preparation uses pure KH2PO4, Ca(NO3)2.4H2O, MgSO4.7H2O, Mg(NO3)2.6H2O, KNO3 and KOH. Amounts are calculated from each chemical formula using the existing atomic-weight table. A target requiring negative amounts or other sources returns ratio_allocation_infeasible. An explicit measured-water inventory and optional HNO3 are now supported as described below.

The aqueous model calculates the cation and anion group totals at the requested strength and pH. Final ingredient reconstruction verifies charge and preserves analytical ratios. KOH potassium contributes to the final potassium target. The calculation uses 25 C and no gas exchange; inorganic carbon is zero for demineralized water or comes from the supplied water analysis. The result includes all mineral saturation indices and the existing saturation assessment. It provides full-precision quantities and calls for rechecking rounded delivered doses.

Steiner's pH 6.30 example gives 50:30:20 and 5:3:1, 30 mmol/L and about 1.316738 mmol/L potassium supplied by KOH in this model. The original empirical curve gives a different base dose. The solution is supersaturated with respect to calcium phosphate phases, which is visible in the output.

Historical validation remains qualified. Solution 1a measured 5.33, 6.45 and 6.58 after aeration, while the model gives about 5.06, 6.66 and 6.66. Matched PHREEQC differs by less than 0.002 pH unit, but both fail to reproduce the measured 0.13 rise. Temperature and common equilibrium air-exposure scenarios did not resolve it. Physical pH accuracy and nutrient retention require additional experimental evidence.

Primary source: https://edepot.wur.nl/309364, pp. 145-153.

## Rounded-dose saturation verification

Add ph_range, selected_phases and mass_decimals to the ratio request. For example:

    "ph_range": [6.28, 6.32],
    "selected_phases": ["Brushite", "Monetite", "Hydroxyapatite"],
    "mass_decimals": 5

The verification first rounds every ingredient mass in grams and reconstructs all nutrient amounts from the chemical formula. Output includes the rounded ingredient list, ratios, concentration and nutrient errors. Each nutrient must remain within 0.1% of its target plus 1e-10 mmol/L numerical allowance. The independently solved pH of the rounded batch (preserving any measured-water charge residual) must lie inside the requested interval.

The calculation checks endpoints, the target pH and interior points at maximum spacing 0.001 pH. For each mineral it reports the largest index and the pH at which it occurred. Every selected mineral must have SI below -1e-7, a numerical guard around saturation. The status passed means the rounded batch met the nutrient, pH and selected mineral tests on the disclosed grid. This is a sampled numerical check, with no mathematical bound for unsampled points. Failed solves or unavailable phase values return incomplete.

This sensitivity holds rounded analytical nutrient totals fixed while imposing each pH. Off-target charge residuals are visible. An actual acid/base addition or gas-exchange scenario requires including the resulting composition change.

At 6.30 the 11.392 mmol/L mixture passes the monetite point check, but it fails at 6.32. Likewise, the 1.94968 mmol/L mixture passes the hydroxyapatite point check but fails at 6.32. At 1.8 mmol/L the rounded mixture passes all three selected mineral checks over the stated grid.

The ordinary full-precision recipe remains available alongside rounded_verification. Command exit zero indicates successful calculation; inspect rounded_verification.status to determine whether the requested checks passed.

## Strongest verified rounded candidate

### Nutrient ceiling reserve

`examples/steiner-nutrient-reserve-search.json` provides the synthetic 10-litre
demonstration with all nine nutrient ceilings, preparation uncertainty and adaptive
pH sampling across 6.28–6.32. Its 5% reserve is an illustrative user-selected policy.

Both fixed recipes and searches accept `nutrient_ceiling_reserve` as a fraction
from 0 (default) to less than 1. A positive reserve requires explicit
`maximum_concentrations`. For example, `0.05` reserves 5% below every declared
ceiling: nitrate-N 6 mg/L becomes an effective operating ceiling of 5.7 mg/L.
This applies equally to Na, Cl and every other declared supported nutrient.

The effective ceilings apply to source water, allocation, rounded delivery and
the full uncertain inventory. Preparation uncertainty cannot consume the reserve.
The separate saturation margin and pH checks are unchanged. The recipe's
`nutrient_ceiling_reserve` report preserves the fraction, declared ceilings and
effective ceilings; `maximum_concentrations` contains the effective ceilings used
by verification. When replaying the original request, use the original declared
ceilings with the reserve to avoid applying the reserve twice.

This is an explicitly chosen operating policy, not a validated crop safety
threshold or allowance for unmodeled impurities. A strongest-found result can
approach the effective ceiling closely while retaining the requested reserve
below the original ceiling. Model, sampling and measurement limitations remain.

Use `flahax.search_ratio_recipe` or replace `counted_mmol_l` with `strength_range` in the ratio command. A search requires `ph_range`.

    Get-Content examples/steiner-ratio-search.json -Raw | python -m flahax ratio

The example searches 1â€“30 mmol/L, keeping Steiner's equivalent ratios and targeting pH 6.30. Each candidate is allocated to the six ingredients, rounded to five decimal places in grams for 10 litres, reconstructed, and checked using the pH interval verification above. KOH potassium remains included. The strongest passing requested concentration found is returned with the actual rounded concentration and ratios in `recipe.rounded_verification`.

The search evaluates a uniform strength grid (default 33 points), then refines every observed passing-to-failing transition to `strength_tolerance` (default 0.00001 mmol/L). It independently recalculates the selected recipe before returning it. Rounding can cause discontinuous feasibility, so this reports the strongest verified candidate found, without claiming a global optimum. Narrow disconnected feasible regions can escape the initial scan. Transition brackets, evaluated strengths and pH coverage are disclosed. Increase `scan_points` to inspect more of the requested strength interval.

`status: found` means a verified candidate was found and all observed transitions were refined. `search_cap_reached` means the upper strength bound itself passed; the search has then supplied no saturation-limited maximum. `no_feasible_candidate_found` describes the evaluated candidates only. Failed chemistry calculations or unfinished refinement return `incomplete`, possibly with a lower verified candidate.

`highest_si_phase` and `highest_si_ph` identify the selected mineral with the smallest SI margin in the delivered candidate. The compatibility fields `limiting_phase` and `controlling_ph` retain those same values; they do not necessarily identify what stops the strength search.

`observed_strength_limit` separately reports the adjacent evaluated failing candidate, its strength bracket, and available constraint violations. Nutrient records give the rounded concentration or uncertain analytical upper bound, the effective ceiling after the nutrient reserve, and units. Mineral records give the sampled SI, required threshold and available pH/scenario witness. Several violations can coexist; this evidence does not prove a unique active constraint. A local allocation failure without a reconstructed value remains `unknown`, and an accepted upper search bound is reported as `search_cap`. Per-evaluation `error_code` and `constraint_violations` retain the evidence without changing recipe acceptance or implying global feasibility.

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

For the example's 1â€“30 mmol/L search, the requested strength is approximately
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
at all effective-dose corners and both volume bounds: normally 64 Ã— 2 = 128
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
when supplied. Rejected strengths retain failure reasons. The 129-point 1â€“30 mmol/L
example found no passing candidate under these preparation bounds. At 1.7 mmol/L,
all 128 scenarios passed the 0.30 SI margin on the imposed pH grid (worst HAP SI
approximately -0.31262), but equilibrium pH escaped the interval and ratio deviations
reached 1.9063%, exceeding the 1% allowance. The concentration range was
1.666283â€“1.717079 mmol/L. This is a failed preparation case, not a deliverable recipe.

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
Â±0.1% and each delivered volume to Â±0.02 mL, with doses rounded to 0.01 mL.
These are declared specifications, not measured assays or calibration records.
The numerical result is conditional on verifying them for actual stocks and dispensers.

The `uncertainty` object retains final-volume error, ratio and concentration
tolerances, and the inert-impurity model. Raw `weighing_error_g` and `purity_fraction`
are rejected in stock mode to avoid ambiguous double counting. Their effects must
instead be included in the verified stock-concentration interval, along with stock
preparation and stability errors. A 99â€“100% reagent label cannot alone support a
Â±0.1% active stock concentration. KOH alkalinity alone is insufficient if reactive
carbonate or other contaminants invalidate the declared pure-compound accounting.

For each ideal compound mass, the calculator rounds its stock dose in mL and
reconstructs nominal compound mass as `dose_ml * concentration_g_l / 1000`.
It does not round that equivalent mass a second time. Uncertainty endpoints are
`(dose_ml Â± dose_error_ml) * concentration_g_l * (1 Â± relative_error) / 1000`.
All stocks vary independently. The same 128 preparation corners and pH grid are
used. Stock-volume overflow and negative possible doses are rejected. Potassium
from the KOH stock enters both nominal and uncertain nutrient accounting.

Use six separate stocks and include all delivered stock volumes when making up
the final 10 L batch. This feature checks final diluted-solution chemistry;
stock solubility, storage stability and concentrate mixing compatibility are not
certified. The existing density approximation, 25 C assumption, excluded gas
exchange and unresolved historical pH discrepancy remain applicable.

For this example's 1â€“30 mmol/L bounded search, the strongest passing candidate
found requests 1.709473610 mmol/L. Rounded stock delivery gives 1.709479411 mmol/L
at nominal volume. Doses in source order are 44.88, 36.60, 13.55, 12.40, 14.45
and 24.70 mL, totaling 146.58 mL. The nominal modeled pH is 6.300028.
All 128 preparation corners pass; concentration ranges from 1.697906 to 1.721172
mmol/L and the largest relative equivalent-share deviation is 0.39925%.
Worst brushite, monetite and hydroxyapatite SI values are -1.715176, -1.435150
and -0.300258 respectively, all at imposed pH 6.32. This remains a sampled,
conditional calculation rather than measured stability or a proven global maximum.

Stock delivery now has a separate [assay and calibration evidence gate](stock-assay-calibration-records.md).
`verified` remains false without applicable records, even if every numerical check
passes. The stock-search example intentionally supplies no measurements and therefore
remains unverified. Supply `stock_evidence` from actual stock assays and dispenser
calibrations to enable record-gated search and delivery verification. The blank
`examples/stock-evidence-template.json` documents the required structure.

Final-volume calibration is also required in `stock_evidence.final_volume`. The
assigned vessel's contained-volume calibration must match the 10 L mark and 25 C
condition, apply to the finished solution including all stocks, and support the
declared Â±0.05 L volume bound after combining measured bias and uncertainty.
Stock assays and dispenser records alone no longer permit `verified: true`.
The numerical recipe, ratios and saturation limits are unchanged by this evidence gate.

Verification additionally requires [measured batch pH and meter calibration](measured-batch-ph-records.md).
The reading's full error interval must remain within 6.28â€“6.32, and its preparation
fingerprint must match the rounded stock delivery and uncertainty assumptions.
The existing example has no real measurement records and therefore remains unverified.

`stable` is separately gated by [measured batch stability records](measured-batch-stability.md).
The explicit example policy checks unfiltered turbidity and dissolved Ca/P mass at
preparation, 24 h, 72 h and seven days, including measurement uncertainty and pH at
each observation. Use `examples/batch-stability-template.json` for `batch_stability`;
its empty measurements do not establish stability. Preparation verification alone
never sets `stable: true`.

The [10-litre laboratory worksheet](steiner-10-litre-lab-worksheet.md) collects
actual preparation, stock assays, calibration and longitudinal measurements for
this candidate. Its companion JSON contains planned settings and blank measured
fields; neither file is laboratory evidence until completed from real records.

## Real-water accounting

`examples/steiner-real-water.json` is a synthetic 10-litre accounting example,
not a measured water analysis or a saturation-passing preparation recommendation.

Replace `water: "demineralized"` with an object containing `analysis_id`,
`totals_mol_kg`, `measured_ph`, `temperature_c: 25` and
`source_water_mass_kg`. Specify all six basis totals (`K+`, `Ca+2`, `Mg+2`,
`NO3-`, `PO4-3`, `SO4-2`) plus `Na+` and `Cl-`, including explicit zeros.
Totals are mol/kg **source water**, not mg/L or mol/L. Supply either total
inorganic carbon as `CO3-2` (including explicit zero), or titrated
`alkalinity_eq_per_kg` beside the totals; never both. Carbon inferred from
alkalinity uses the existing measured-water inorganic model at measured pH.
Unknown components and omitted required totals are rejected.

`source_water_mass_kg` must not exceed final `water_mass_kg`. Their difference
represents ion-free water in this inventory, not a guessed water density or
automatic volume additivity. Final solution volume is independently supplied.
For example, 0.0004 mol Ca/kg in 8 kg source water contributes
0.0004 × 8 × 1000 / 10 = **0.32 mmol Ca/L** to a 10-litre batch.

The planner fits the **final** six nutrient totals, subtracts the source-water
contributions, then allocates the remaining pure compounds. Water exceeding any
final target produces `ratio_water_exceeds_target`; the strength search treats
this as an infeasible candidate. Other impossible allocations are refused.

KOH remains the default permitted pH reagent. Explicitly allow
`ph_reagents: ["KOH", "HNO3"]` for water requiring acid. Both KOH potassium and
HNO3 nitrate consume their final nutrient targets; neither is appended after
fitting. HNO3 quantities represent pure compound equivalent, not a commercial
acid solution dose. For commercial assays and declared solvent, use the explicit product allocation below;
the original pure-compound path remains restricted to KOH/HNO3.

Reports separate `nutrient_accounting.water_mmol_l`, `salts_mmol_l` and
`ph_reagents_mmol_l`. Their sum is `analytical_mmol_l`; its six components sum
to `counted_mmol_l`. Sodium, chloride and carbon enter the full
`aqueous_totals_mol_kg` and saturation chemistry but not Steiner's six-nutrient
count. That count is not total dissolved particles or ionic strength.

The source analysis remains unchanged. Its measured-pH charge imbalance is
reported and scaled by source/final water mass. The final and rounded pH solves
preserve this reference residual, following the existing measured-water model.
`charge_residual_mol_kg` is the raw modeled charge;
`charge_closure_error_mol_kg` is the departure from the measured-water reference.
A small closure error does not establish that the water analysis is accurate.

Rounded verification includes water, salts and pH reagents and retains the
fixed-carbon and disclosed pH-grid assumptions. Combined water/product uncertainty is available through the explicit mode below.
The legacy preparation-uncertainty and stock-verification contracts remain
restricted to their original inputs.
No real-water recipe is marked experimentally verified or stable. Commercial allocation and Na/Cl ceilings are described below. Water-analysis
and product uncertainty remain open stage-3 work. Historical solution 1a's
unresolved +0.13 pH rise remains reported.


## Commercial products and sodium/chloride ceilings

The optional `products` list replaces the default pure-salt/reagent set. Every
entry must declare:

```json
{
  "product": {
    "name": "Example potassium nitrate solution",
    "formula": "KNO3",
    "elements": {"K": 19.336066546655854, "N_NO3": 6.927014302387688}
  },
  "role": "fertilizer",
  "solvent_fraction": 0.5
}
```

`elements` uses **elemental mass percent**, including nitrate N as `N_NO3`,
phosphate P as `P` and sulfate S as `S`. The example is a synthetic 50% KNO3
assay. It is not a supplier certificate or a stock-solubility claim. Supply the
complete existing FlahaX material record: formula, ions, identity or supported
grade/disclosed blend. Unknown chemistry fails explicitly. Product names must be
unique. A `ph_reagent` role identifies acid/base product contributions separately;
supply those products in the same list. Do not also supply `ph_reagents`.

`solvent_fraction` is kg solvent/kg product, explicitly declared for each entry;
zero means no supplied solvent is being counted. The caller must account for
carrier/hydrate water in the declared final solvent inventory. It is never
inferred from the label remainder. The total source-water mass plus declared
product solvent cannot exceed `water_mass_kg`; the remainder is ion-free water.
Masses are **grams of the commercial product**, not grams of pure active compound.
No liquid volume dose is inferred without a density/delivery contract.

Supply limits separately, for example:

```json
"maximum_concentrations": {"Na": 10, "Cl": 20}
```

These are user-chosen elemental mg/L ceilings, not recommended crop limits.
Ceilings support K, Ca, Mg, N_NO3, P, S, Na, Cl and N_NH4. Omitted limits remain
unspecified and incidental ions require review; explicit zero permits no addition
of that ion. Water, fertilizers, pH reagents and derived counterions all count.
The fit includes these ceilings, and final reconstruction and rounded verification
compare actual totals directly against them without a tolerance that permits an
exceedance. A water-only exceedance is refused before allocation.

The allocator uses the existing material inventory and nonnegative least-squares
engine, with local linearization of the full aqueous charge equation at target pH.
It solves equivalent shares, six-nutrient concentration and charge together with
Na/Cl and solvent constraints. It does not assume commercial products have the
stoichiometry or assay of a pure Steiner salt. It returns a locally found,
independently reconstructed candidate; unsuccessful fitting does not prove global
infeasibility. No global optimum or minimum-cost claim is made.

Reports include:

- `elemental_accounting_mg_l`: water, fertilizers and pH reagents separately.
- `elemental_mg_l`: their final analytical sum, including additional nutrients.
- `nutrient_accounting`: the six-nutrient molar contributions used by Steiner ratios.
- `aqueous_totals_mol_kg`: the complete supported chemistry inventory.
- `analytical_minus_chemistry_mg_l`: differences between the declared assay and
  chemistry components under FlahaX's existing label-reconciliation rules.
- `limit_assessment`: supplied ceilings, violations and unspecified incidental ions.
- `declared_product_solvent_kg` and `solvent_inventory_passed`.

The label inventory remains authoritative for ratios and nutrient ceilings; the
chemistry inventory supplies speciation and saturation. Reconciliation differences
are disclosed, not fitted away. For example, agricultural-grade calcium nitrate
contains ammonium: it is retained in analytical and chemical reports but excluded
from the six-nutrient Steiner count. That count is neither total nitrogen nor
ionic strength, and satisfying it does not establish agronomic adequacy.

Rounded verification reconstructs every product using its material assay and
chemistry profile, then rechecks ratios, total concentration, pH, Na/Cl ceilings,
solvent inventory and selected mineral SIs. The strength search uses these checks
for every candidate and its final replay. Its reported highest-SI mineral is not
necessarily the constraint controlling strength; Na/Cl or allocation can control.

`examples/steiner-commercial-ratio.json` demonstrates synthetic water, fertilizer
and base contributions at pH 6.30. Its 30 mmol/L recipe is an accounting case and
fails phosphate saturation checks. Commercial-product uncertainty is available under the explicit model below.
Stock/lab evidence verification for these inputs remains unsupported and is refused. Neither a successful
allocation nor a sampled SI pass marks a commercial recipe verified or stable.


## Water-analysis and commercial-assay uncertainty

Use `uncertainty.mode: "water_product"` with explicit `products` and a `ph_range`.
This opt-in contract is separate from the legacy pure-compound purity/stock mode.
The complete example is `examples/steiner-commercial-uncertainty.json`.

Required fields:

| Field | Meaning / demonstration value |
|---|---|
| `weighing_error_g` | Independent absolute error on each nonzero rounded product dose; 0.001 g |
| `volume_error_litres` | Final solution volume error; 0.05 L |
| `water_relative_error` | Independent relative bounds on each stated water concentration and alkalinity, if supplied; 0.01 |
| `water_ph_error` | Absolute uncertainty of measured **source-water** pH; 0.02 |
| `product_assay_factors` | Every product name, including pH reagents, mapped to `[0.99, 1.0]` |
| `ratio_relative_tolerance` | Maximum relative departure of each equivalent share; 0.01 |
| `concentration_relative_tolerance` | Maximum relative departure from requested six-nutrient count; 0.02 |
| `impurity_model` | Must be `inert` |
| `water_mass_model` | Must explicitly be `scale_with_final_volume` |
| `max_scenarios` | Chemistry sampling budget; 128 in the demonstration |

The assay factor scales **the whole declared product composition together**,
including all counterions and any assay/chemistry discrepancy. For a product with
2% nominal active composition, `[0.99, 1]` represents 1.98-2.00% active composition,
not 99-100% pure product. Each product has its own independent factor. The missing
active fraction is modeled as inert; it is not assumed to become solvent. This
mode does not cover independent element-assay changes, changing blend proportions,
unknown reactive impurities or carbonate contamination of a base.

The recipe is fitted once. Checks then hold its rounded doses fixed; they never
refit salts or add acid/base to make a scenario pass. Weighing and active-content
bounds combine into effective inventory-dose intervals. Zero-dose products are
not dispensed. Source-water quantity is fixed. Final water mass scales with final
volume using the declared nominal water-mass/volume approximation; no density
measurement or solvent uncertainty is inferred. The maximum supplied product
solvent is checked separately against the minimum final water inventory.

Every sampled water analysis is speciated again at its perturbed measured pH.
Carbon inferred from alkalinity and the source charge reference are recalculated,
then diluted onto the scenario's final-water basis. The nominal charge reference
is not silently reused. Water pH uncertainty is not final-batch pH-meter uncertainty.

Analytical reporting and nonlinear chemistry have different coverage:

- Concentration and Na/Cl maxima/minima are calculated over the full declared
  independent inventory intervals and final-volume bounds.
- Equivalent-share bounds retain the correlation between each product's nutrient
  contributions. A linear-fractional endpoint calculation avoids enumerating the
  full Cartesian product. These are floating-point analytical bounds for this
  stated composition model, not a guarantee for unspecified impurity chemistry.
- Chemistry evaluates axes, mixed extremes, ratio-bound witnesses and deterministic
  corner/interior samples (seed 1961). Small boxes include all corners when the
  budget permits. Each selected scenario evaluates every nominal pH-grid point.
  Even checking all corners does not prove continuous nonlinear extrema.
- `dimensions`, `dimension_units`, `corner_count`, `corners_evaluated`,
  `all_corners_evaluated`, `required_scenarios`, `planned_scenarios` and
  `scenario_count` disclose coverage. A budget too small for the required axes and
  witnesses returns `incomplete`; missing phases or failed solves cannot pass.

`uncertainty_verification.status: passed` means analytical bounds meet the stated
ratio/concentration tolerances and Na/Cl ceilings, solvent inventory passes, and
all evaluated chemistry scenarios meet the modeled pH bracket and selected SI
margin. It is a sampled numerical result, not a probabilistic confidence level,
proof over every continuous chemistry state, or experimental verification.
`verified` and `stable` remain false without applicable physical evidence.
The strength search uses this result, so failed/incomplete uncertainty cannot
produce a passing candidate.

The illustrative 10-L example uses 0.1 kg of synthetic source water, final water
mass 10 kg, six-nutrient count 1.3 mmol/L and 2% active-composition product solutions.
It is not the earlier 30 mmol/L mixture, which fails phosphate saturation. The
50% product version at 1.3 mmol/L fails the 1% ratio tolerance under the selected
weighing bounds; diluting product assays increases weighed masses without relaxing
acceptance. The 2% example passes the declared analytical bounds and 128 sampled
chemistry scenarios over pH 6.28-6.32 at SI margin 0.3. No maximum-strength claim is
made, and these synthetic product solutions are not verified supplier assays,
stock-solubility measurements or preparation recommendations.


## Independent elemental-assay uncertainty

Use `uncertainty.mode: "water_product_elemental"` to vary declared elements
independently. Replace `product_assay_factors` with `product_element_factors`;
all other preparation, water, tolerance and sampling fields remain unchanged.
Provide every product, including pH reagents, and every element in its declared
`elements` record, with no extra entries. For example:

```json
"product_element_factors": {
  "Example potassium nitrate": {
    "K": [0.99, 1.0],
    "N_NO3": [0.99, 1.0]
  }
}
```

These are fractions of each declared elemental mass percentage, not elemental
purity percentages. Bounds must be finite and satisfy `0 < low <= high`. A fixed assay is
`[1,1]`. They replace, rather than multiply, the whole-composition factors. A
stated zero remains zero; this mode does not invent contamination of absent
components. The selected illustrative bounds retain 99-100% for each declared
element; actual laboratory/certificate limits must replace these assumptions.

All elements from a product share its weighing error. Analytical extrema use
local product dose/assay endpoint combinations while retaining this common dose.
They do not incorrectly treat each element as independently weighed. Water,
fertilizers and pH reagents still contribute to the final analytical ratios,
six-nutrient count and direct Na/Cl ceiling checks. Values for additional declared
elements also vary in chemistry even when outside the six-nutrient count.

Each sampled hypothetical product record is rebuilt through `material_inventory`
and the existing label/charge-reconciliation rules. Source records and the rounded
recipe are unchanged. Analytical labels remain authoritative for nutrient limits;
reconciled components determine speciation. The report includes
`maximum_abs_assay_chemistry_difference_mg_l`: the largest **sampled** absolute
difference for each element. Such a difference is not experimental error removed
by the checker, nor proof that the hypothetical label represents a realizable lot.

Independent-assay checks support explicit flat material records with formula,
ions or identity, and supported single-identity nested grades. A grade is first
resolved normally. Its hypothetical flat identity adapter must reproduce the
nominal analytical and chemistry inventories before any sampling is allowed.
Each sample uses a separate hypothetical assay; the original grade document and
its provenance remain in the recipe unchanged. Factors may be supplied explicitly
or converted from complete documents using the opt-in selectors below. Supported
factors remain greater than zero. Above-one factors are allowed
for elemental content above the nominal label: `[0.99, 1.01]` means 99-101% of the
declared elemental amount, not more than 100% product purity. The simultaneous
upper elemental assays plus declared solvent must not exceed total product mass
(numerical allowance `1e-12` in mass fraction); otherwise the request raises
`invalid_elemental_mass_bounds`. This necessary mass bound does not guarantee a
physically realizable salt at every independent assay combination. Unknown
reactive remainder and changing solvent fractions remain excluded. Whole-product
`water_product` purity factors still cannot exceed one.
Blend grades remain refused in independent-element factor mode; the disclosed
ingredient mode below is a separate model. Declared-ion grades remain unsupported.
If a six-nutrient or Na/Cl contribution is inferred but not
declared in the product assay, analytical certification is refused with
`unsupported_elemental_counterion_bounds`. Supply defensible measurements/bounds
or use a supported uncertainty model; do not insert fabricated zero assays.

The complete input `examples/steiner-elemental-uncertainty.json` reuses the prior
rounded 10-litre, 1.3 mmol/L example, nominal 2% product formulations, 0.1 kg
synthetic source water, Na/Cl limits of 10/20 mg/L and pH 6.28-6.32 with SI margin
0.3. It replaces shared content scaling with independent factors on all 14
product element assays. Alongside water, weighing and volume this gives 30 varying
dimensions and 1,073,741,824 endpoint combinations. The demonstration checks 128
scenarios, not that full chemistry box. The analytical interval calculations cover
the declared inventory bounds, but chemistry extrema remain sampled.

Do not interpret a lower maximum sampled SI than in the correlated-assay example
as reduced risk: the sampling points differ in the larger uncertainty space.
The recipe has not been refitted or experimentally verified; unknown reactive
impurities, continuous chemistry extrema, blend uncertainty, actual stock
solubility and Steiner's unresolved experimental pH difference remain open.

`examples/steiner-grade-uncertainty.json` repeats the 10-litre check with the MKP
source represented as an illustrative single-identity grade. Its document is a
synthetic test fixture, not a supplier certificate or measured stock assay. The
same rounded doses, uncertainty bounds and mineral limits apply.

### Documented grade and lot bounds

In `water_product_elemental` mode, each entry in `product_element_factors`
can remain an explicit element-to-factor mapping, or select one of these sources:

```json
{"source": "grade"}
```

```json
{"source": "lot", "lot": {
  "lot_id": "example-lot",
  "grade_id": "the-product-grade-id",
  "measured": {"K": 14.0, "P": 11.0},
  "uncertainty": {"K": 0.05, "P": 0.04},
  "document": {
    "supplier": "Example only", "title": "Illustrative certificate",
    "issued": "2026-11-01", "entered": "2026-11-15"
  }
}}
```

These values illustrate the schema; they are not measured supplier data. Both
selectors require the product's supported single-identity `grade` record.
Documents with nonempty `impurity_limits` are refused with
`unsupported_assay_impurity_bounds`: those limits need explicit composition and
bounded inventories, and cannot be silently treated as zero contamination.
Grade mode requires explicit minimum and maximum values for **every** nominal
element. Lot mode requires a correctly linked lot, a measurement and explicitly
stated uncertainty for every element; it never substitutes grade bounds when a
lot uncertainty is missing. Extra measured elements must be modeled in the
nominal product before use. Blends and standalone identity-only lots remain
unsupported here.

The existing material schema uses mass percent, including oxide percentages.
Lot uncertainty is an absolute percentage-point amount, not a relative percent.
Existing conversions transform oxide values and their uncertainties to elemental
mass percent. Grade factors are `[minimum / nominal, maximum / nominal]`; lot
factors are `[(measured - uncertainty) / nominal, (measured + uncertainty) / nominal]`.
The original nominal recipe is not refitted to the lot center. Bounds at or below
zero and zero nominal assays cannot be represented by this positive-factor mode
and are refused, not clipped. No probability or confidence coverage is inferred.

`uncertainty_verification.assumptions` contains the resolved numeric factors;
`assay_bound_sources` retains the original grade/lot records, converted elemental
intervals, oxide conversions and units. Documents are inputs, not independent
authentication or verification of measurement accuracy. Independent element
intervals still assume no correlations and must pass the upper mass bound.

`examples/steiner-documented-assay-uncertainty.json` replays the illustrative
99-101% case with MKP grade bounds. It correctly fails the 1% nutrient-ratio
tolerance, even though sampled pH and mineral checks pass. Document conversion
does not relax acceptance limits or turn failed recipes into verified batches.

### Disclosed blend ingredient bounds

An entry in `product_element_factors` can instead select:

```json
{"source": "blend_ingredients", "mass_fraction_bounds": {
  "idn-potassium-nitrate": [0.01940004, 0.019596],
  "idn-monopotassium-phosphate": [0.000396, 0.0004],
  "idn-sodium-iron-edta": [0.00000396, 0.000004]
}}
```

This mode requires a supported `disclosed` grade, no unmodeled impurity limits,
and explicit bounds for every ingredient (up to eight). Values are absolute
ingredient mass fractions of the commercial product. They must contain the
nominal fractions, lie within 0-1, and their simultaneous upper sum plus declared
solvent cannot exceed one. The remaining mass is assumed inert; solvent remains
fixed. Ingredient fractions vary independently, while each ingredient's elemental
assays and inferred counterions vary **together** with that fraction. Catalogue
ingredient assays are fixed inputs, not measured lot assays. Arbitrary assay
covariance, constant-sum exchange constraints and undisclosed ingredients are not
supported by this box model.

Nominal declared blend assays must match the ingredient-weighted catalogue assay
inventory; chemical components must also reproduce the nominal material inventory.
An inconsistent blend is refused with `blend_assay_mismatch`, rather than silently
discarding its label. Existing catalogue label/chemistry differences remain
separate and reported. Unstated nutrients are derived from the same ingredient
chemistry that provides speciation inputs; they are not assumed zero or fixed.

Analytical vertices combine a shared product weighing error with ingredient
fraction endpoints. This bounds the final equivalent ratios, concentration and
Na/Cl inventory while retaining ingredient correlations. Each sampled chemistry
case is reconstructed from those same ingredient fractions. Reports include
`blend_bound_sources`, ingredient inventory snapshots, inferred nutrient names,
fraction dimensions, and sampling coverage. Nominal source documents stay intact.

`examples/steiner-blend-uncertainty.json` is an illustrative 10-litre demonstration
with a disclosed nitrate/MKP/iron-EDTA formulation replacing the earlier synthetic
contaminated nitrate. It is a new composition and is fitted and rounded again.
It retains the original ratio, concentration, Na/Cl, pH-range and mineral-margin
checks. This is not a new supplier certificate, strongest-recipe search, physical
stability result or continuous uncertainty guarantee. Other products still use
their explicitly stated independent element factors. Inferred-counterion bounds
outside this ingredient model remain unsupported.

### Density, solvent and source-water quantity

In `water_product_elemental` mode with an explicit source-water analysis, opt in
to `water_mass_model: "closed_batch_mass_balance"` and supply
`physical_preparation` with exactly these fields:

| Field | Meaning |
|---|---|
| `solution_density_kg_l` | Positive lower/upper final solution density, kg/L |
| `source_water_mass_kg` | Positive lower/upper source **solvent-water** mass, kg; includes nominal quantity |
| `source_water_solvent_fraction` | Positive lower/upper water mass fraction of the source solution, at most 1 |
| `product_solvent_fractions` | Every product name mapped to lower/upper water mass fractions, including its nominal fraction |

These are absolute intervals. They do not describe temperature coefficients or
probability distributions. The previous `scale_with_final_volume` model remains
unchanged when explicitly selected. Physical preparation currently requires
elemental uncertainty mode; whole-product effective-dose mode is not supported.

For each fixed rounded recipe scenario, with final volume V, density rho,
source solvent-water mass W, source solvent fraction f, product masses m in kg,
and product solvent fractions s:

```
total solution mass = rho * V
source solution mass = W / f
final solvent-water mass = rho * V - W * (1/f - 1) - sum(m * (1-s))
pure make-up water mass = rho * V - W/f - sum(m)
```

The mass balance assumes retained inputs and pure make-up water; it does not add
liquid volumes. The calculated solvent-water mass is the denominator for mol/kg
chemistry. Nutrient amount per litre still uses final volume. Density alone
therefore cannot change the analytical ratios or mg/L inventory. Product solvent
changes the chemistry denominator while its stated nutrient assay remains fixed.
The supplied solvent fractions must account for all water intended to act as
solvent; hydrate release is not inferred automatically.

All source-water constituents share one quantity variable, including its charge
reference and carbon inventory. Analytical vertices retain that correlation with
the independently bounded source concentrations. Solvent fractions and density
also enter chemistry sampling. Reports expose `final_water_mass_kg_range`,
`minimum_pure_makeup_water_kg`, units and sampled phase maxima.

The complete interval box must permit positive final solvent mass and nonnegative
make-up water. Upper ingredient/element inventories plus upper product solvent
fractions must fit each product's mass. Source non-solvent mass must at least
cover its known elemental inventory; this necessary lower bound is not a full
dissolved-solids reconstruction. Missing constituents, density-composition
correlations, evaporation, gas exchange and physical stability remain outside
this model. No measured density or solvent fraction is invented.

`examples/steiner-physical-uncertainty.json` retains the previous rounded blend
recipe and uses user-approved illustrative density 0.9991-1.0011 kg/L, source
water 0.099-0.101 kg, product solvent fractions 0.9799-0.9800 and fixed source
solvent fraction 0.9999. Existing weighing, volume, assay, Na/Cl, ratio and
saturation limits remain unchanged. These are demonstration assumptions, not
validated preparation specifications or proof of continuous chemistry extrema.

### Expanded analytical nutrient ceilings

`maximum_concentrations` accepts K, Ca, Mg, N_NO3, P, S, Na, Cl and N_NH4,
all as elemental mg/L. `N_NO3` and `N_NH4` mean nitrate-nitrogen and
ammonium-nitrogen, respectively, not nitrate or ammonium ion mass. P and S are
elemental amounts, not phosphate and sulfate mass. Oxide limits, total nitrogen,
micronutrient ceilings, activity limits and lower-bound targets are not supported
by this entry point. Unknown keys fail validation; no limits are inferred from crops.

Allocation includes supported commercial-product ceilings; nominal and rounded
inventories use direct ceiling comparisons. A pure-salt nominal exceedance raises
`ratio_limit_exceeded`. Uncertainty includes limits on all supported quantities:
`elemental_mg_l_ranges` now reports all nine analytical ranges in material modes.
`nutrient_limits` identifies a non-Na/Cl exceedance; `sodium_chloride_limits`
remains the compatibility code for Na/Cl failures. Existing pure-salt/stock
uncertainty paths also check the six-nutrient ceilings at their preparation
corners. Search cannot accept a failed uncertainty result.

Explicit source-water `NH4+` in `totals_mol_kg` is supported. It enters full
chemistry, nitrogen accounting and limits, while remaining outside Steiner's
six-nutrient count and equivalent-share groups. If an N_NH4 ceiling is requested
with real water, NH4+ must be supplied explicitly, including a justified zero;
otherwise `missing_water_ammonium` is raised. Steiner did not validate ammonium
in his historical ratio/pH method. Product ammonium and ingredient-derived
ammonium are included through existing material inventories. Independent assay
mode refuses an inferred ammonium contribution without explicit bounds; disclosed
ingredient mode retains its correlation with the ingredient.

`examples/steiner-nutrient-limits.json` uses illustrative ceilings K 16, Ca 5,
Mg 2, nitrate-N 6, P 8, S 1.4, Na 10, Cl 20 and ammonium-N 0.01 mg/L. Its
source-water NH4+ is an explicit synthetic zero, not an actual laboratory result.
The previous physical preparation bounds and pH interval 6.28-6.32 are retained.
These values exercise software acceptance and are not crop recommendations.

### Adaptive pH refinement

Rounded-recipe checks now keep the endpoint/target/interior grid (maximum initial
spacing 0.001 pH) and adaptively bisect intervals around observed mineral maxima,
every observed local peak, and crossings of SI = 0 or the requested guarded SI
limit. Each selected phase contributes refinement intervals. Refinement stops
when these detected features have adjacent intervals no wider than `1e-5` pH.
This local resolution is not the maximum spacing everywhere in the interval.

The policy allows at most 16 rounds and 256 additional points per chemistry
scenario. Unfinished refinement or missing/nonfinite selected phase data gives
an incomplete check; search cannot accept it as a passing recipe. A single-pH
request remains a single evaluation. Existing limits and the `1e-7` SI comparison
guard are unchanged; an actual detected exceedance still fails.

`rounded_verification.base_evaluated_ph` records the initial grid, while
`evaluated_ph` includes the added samples. `ph_refinement` reports resolution,
rounds, budgets, completion, unresolved intervals, maximum-neighbour intervals
and SI crossing brackets. Charge residuals stay aligned with the sorted evaluated
pH values. The separately calculated equilibrium pH bracket is unchanged.

Both uncertainty workflows independently refine **each** preparation scenario
from the coarse grid; they do not assume nominal-recipe refinement is sufficient
for every uncertain composition. `uncertainty_verification.ph_refinement` records
per-scenario completion/evaluated points and total pH evaluations. Worst mineral
SIs include all refined points. Preparation scenario count/budget, source-water,
assay, density, solvent, weighing and final-volume bounds remain visible.

Refinement follows features detected at sampled points. A narrow unsampled peak
can still be missed. Neither local refinement nor a sampled uncertainty pass is
a mathematical bound over continuous pH/composition, a global optimum or proof
of physical stability. The existing `examples/steiner-nutrient-limits.json` uses
this policy without changing its rounded 10-litre recipe or acceptance limits.


### Volumetric product stocks with real-water uncertainty

`examples/steiner-volumetric-product-stocks.json` extends the synthetic 10-litre
case with **grams of supplied product per litre of final stock**. This is different
from the legacy pure-compound/hydrate stock basis. Each stock is separate; its
carrier must be demineralized water. Source water is still accounted separately.

Use `stock_dosing` with these fields, keyed by every declared product name:

```json
{
  "basis": "product_mass",
  "concentrations_g_l": {"product name": 100},
  "concentration_relative_error": 0.0001,
  "dose_error_ml": 0.001,
  "dose_decimals": 4,
  "density_kg_l": {"product name": [0.999, 1.001]},
  "carrier": "demineralized_water"
}
```

The complete example supplies all products, including the pH reagent. These stock
specifications are illustrative assumptions, not measured concentrations,
dispenser performance or stock-solubility evidence. The example retains the 5%
reserve, all original water/product/physical bounds, and all three selected mineral
checks across pH 6.28–6.32 with adaptive refinement and 128 preparation scenarios.

This integration requires `water_product_elemental` uncertainty and
`closed_batch_mass_balance`, including explicit source-water analysis and quantity,
final density/volume and product solvent intervals. Independent element assays,
documented assay bounds and correlated disclosed-blend ingredients retain their
existing interpretation. Legacy pure-compound stocks remain unchanged.

For stock concentration C g/L and rounded dose D mL, delivered product mass is
C × D / 1000 grams. Its interval uses both stock concentration and dispenser bounds;
the declared weighing allowance is retained **in addition** to that interval.
Product elemental/ingredient assays are then applied to delivered product mass.
Stock concentration error must therefore describe product loading per stock litre,
not an active-nutrient assay already counted by the separate product bounds. Reports
expose this convention and the resulting product-mass intervals. The supplied
weighing allowance is a conservative absolute product-mass allowance per delivered
aliquot; a stock preparation's balance error must be propagated to this basis or
included in the concentration bound. Avoid counting the same source of error twice.

Rounded mL doses feed the existing rounded-inventory replay without a second gram
rounding. Source water, fertilizers and pH reagents all count toward final ratios,
total concentration, Na/Cl and reserved nutrient ceilings. Bounds on stock density
also constrain the maximum input mass and the minimum pure make-up water available.
Stock carrier replaces pure make-up water: it is not an additional nutrient source.
Final solvent mass is final density × final volume minus bounded non-solvent mass.
The check conservatively encloses combinations of dose and concentration errors;
it does not claim arbitrary density/composition correlations.

Inconsistent carrier mass, overfilled preparations, coarse rounding, exceeded
nutrient/saturation limits and incomplete chemistry sampling cannot pass. Only
finite sampled chemistry is established; continuous extrema remain unproved.
Product-stock measurement records are not integrated: supplying stock evidence or
batch stability records for this mode is rejected. `verified` and `stable` remain
false. Lab testing stays deferred, and Steiner's unexplained +0.13 pH rise remains
visible in the historical context.
