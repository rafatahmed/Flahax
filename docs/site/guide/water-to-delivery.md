# Water, nutrient targets and acid selection

Released in 0.3.1; measured-pH water balancing added in 0.4.0. This workflow
plans; it does not operate equipment or certify agronomic suitability.

## Separate inputs and separate acceptance

Crop targets and source-water contributions are nutrient concentrations in
mg/L of final working solution. For the pepper example, Ca target 104 minus
water contribution 20 gives an 84 mg/L fertilizer gap. Neither number is an
alkalinity measurement. `water={}` explicitly declares zero nutrient
contributions; omitting water is an error.

A zero nutrient target means no intentional requirement, not a prohibition on
counterions present in real fertilizers. `recommend` and `solve_weights` retain
their positive-target fit calculation and report additional fields:

- `incidentalContributions`: zero/omitted-target nutrients, actual ppm and review status.
- `limitViolations`: final ppm exceeding caller-supplied absolute maxima.
- `requiresReview`: incidental additions without a declared maximum.

Percentage deviation from zero remains `None`, not infinity or a fabricated
percentage. An explicit `maximum_concentrations={'N_NH4': 0}` does prohibit
ammonium. Without that maximum, incidental ammonium is reported for separate
assessment; the package does not invent a safe threshold or call it harmless.
The optimizer's existing objective is unchanged; maxima are post-solve checks,
not a new constrained optimization algorithm. A rejected recipe is not proof
that every alternative recipe is infeasible.

With the supplied pepper targets, twelve selected catalogue products and
water Ca 20 mg/L, the regression recipe has approximately 4.845193 mg/L NH4-N
and 0.047919 mg/L Na. Positive targets fit within 1%, but these incidental
amounts require review. These are catalogue-assay calculations, not a dosing
authorization. Since the 2026-10-18 catalogue correction, `Phosphoric Acid (75%)`
lists 23.706035% P (a 75% w/w aqueous product, dosed by product mass) and
Mg Nitrate is Mg(NO3)2·6H2O theory; the actual grade of each product still
requires confirmation before physical use.
See [traceable materials](materials.md) for supplying that grade or lot.

## Public orchestration

```python
from flahax import load_library, plan_fertilizer_workflow

library = {p['name']: p for p in load_library()['salts']}
result = plan_fertilizer_workflow(
    [library['Calcium Nitrate (ag grade)']],
    targets={'Ca': 104, 'N_NO3': 84 * 14.4 / 19, 'N_NH4': 0},
    water={'Ca': 20}, target_ph=6.5,
)
assert result.nutrient_gap['Ca'] == 84
assert result.stages['formulation'].status == 'requires_review'
assert result.stages['chemistry'].status == 'needs_input'
```

Each `WorkflowStage` exposes `status`, `value`, `required_inputs`, `error_code`
and `message`. Status is `calculated`, `requires_review`, `needs_input` or
`blocked`. A calculated stage is not a validated hardware delivery plan.
Earlier calculated stages remain available when a later stage is blocked.

`final_volume=VolumeLitres(...)` enables batch conversion. Additional keyword
configurations are mappings:

| Configuration | Required entries | Meaning |
|---|---|---|
| `equilibrium` | `water_totals`, `water_mass_kg`, `water_analysis_id`, `complete_analysis`, `carbon_boundary`, `temperature_c`, `phases` | Complete fixed-valence analytical component totals in mol/kg-water; explicit final solvent inventory, 25 C, closed carbon, explicit phase list ; optional `measured_ph` (with `alkalinity_eq_per_kg`, `balance_ion`, `maximum_imbalance_percent`) speciates the water at its measured pH and closes the charge on one ion instead of solving pH from charge balance |
| `acids` | `products`, `maximum_nutrient_error_percent`, `maximum_reagent_volume_litres` | Evaluate single-acid candidates; optional `preferred_product_id` forbids automatic fallback |
| `nitric` | `reagent`, `reagent_channel_id`, `maximum_reagent_volume`, `maximum_nutrient_error_percent` | Existing assay-qualified HNO3 delivery adapter; volume is `VolumeLitres` |
| `titration` | `water_analysis`, `curve`, `reagent`, `maximum_reagent_volume` | Existing matched-record measured-curve API; optional positive-target tolerance defaults to 1% |
| `stocks` | `injection_ratio`, `tanks`, `compatibility_rules`, `solubility_limits`, `temperature` | Existing typed stock planner, with sourced records and temperature-qualified limits |

`maximum_concentrations` is a separate top-level mapping of nutrient symbol to
maximum final mg/L. Checks include reagent nutrient contributions. Stock
compatibility calculations remain possible for an unapproved formulation;
they do not approve that formulation. A measured water titration curve is not
a measurement of the final fertilizer mixture; post-mix verification remains
mandatory. Nitric equilibrium plans with unreviewed incidental additions
cannot pass `validated_equilibrium` delivery composition.

## Measured-pH water balancing

`balance_water_analysis(totals, measured_ph=..., alkalinity_eq_per_kg=None,
balance_ion='Cl-', maximum_imbalance_percent=5, phases=(), temperature_c=25)`
speciates a laboratory analysis at its measured pH. Inorganic carbon comes
from `totals['CO3-2']` or from titrated alkalinity (carbonate alkalinity:
each carbon species counts 2 x C - H+ relative to H2CO3, plus OH- - H+), never
both. The charge left at the measured pH is closed by changing `Cl-` or `Na+`,
as PHREEQC's `charge` option does. The result records the analysed and
adjusted balance-ion totals and the imbalance in percent of total
equivalents. An imbalance above the limit is rejected
(`charge_imbalance_exceeded`); the balance ion is never driven to zero
(`balance_ion_exhausted`).

Why: calculated pH from charge balance alone is extremely sensitive to
analytical error in brackish water. For Shomar et al. (2024) station 104
(measured pH 7.80), charge balance alone gives pH 3.8. Matching the measured
pH needs 9.5% less chloride, and after that a further 0.5% change in chloride
still moves the calculated pH by about 0.45 units. Routine analyses carry
errors of that size, so only the measured pH can anchor the water.

## Calculated pH and model boundary

`calculate_equilibrium_ph(totals, complete_analysis=True,
carbon_boundary='closed', phases=[], temperature_c=25)` solves charge balance
using the existing coupled aqueous solver. It does not infer missing chloride,
carbon, alkalinity, oxidation states or balancing salts. Completeness is the
caller's declaration, not an inference from the nutrient list. Complete water
totals must also agree with the independently supplied water nutrient ppm on
the declared mass/volume basis. Catalogue identity, formula and assay must
match before the chemistry stage converts fertilizer doses.

The 25 C reaction set, Davies ionic-strength bound, phase allocation and
convergence errors remain enforced. `phases=[]` means aqueous-only modelling,
not proof that precipitation is impossible. Target supersaturation or solids
prevent acid-plan acceptance. Calculated pH is restricted to [0,14], with a
charge residual of at most 1e-12 mol-charge/kg-water. The present complete
mixed reference is checked within 0.01 pH units at initial and acidified states.

Solvent mass and final volume are explicit fixed-final-inventory quantities;
include reagent carrier water in that inventory. Do not interpret them as
an arbitrary initial tank mass followed by unaccounted dilution. Gas exchange,
redox evolution, temperatures other than 25 C and concentrated-stock activity
models are not added here.

USGS documents concentration units and `pH ... charge` in the
[PHREEQC SOLUTION reference](https://water.usgs.gov/water-resources/software/PHREEQC/documentation/phreeqc3-html/phreeqc3-48.htm).
That charge-balance method does not make a nutrient-only water table complete.

## Acid candidates

The standard `plan_fertilizer_workflow` accepts **HNO3 and H3PO4 only**.
The lower-level `plan_acid_options` retains aqueous HNO3, H3PO4, H2SO4 and
C6H8O7 support for compatibility with existing scientific fixtures; sulfuric
and citric acids are not offered by the standard site workflow.
Each record supplies `id`, `source`, `revision`, `recordedAt`,
`chemicalFormula`, `massFraction` (pure acid/product mass, 0–1) and
`densityKgPerL`. Hydrated citric solids must first be represented by a defined
aqueous stock; no density or purity is guessed.

Demand is solved against the same mixed model by adding conserved nitrate,
phosphate, sulfate or citrate respectively. Citric acid is not inorganic
carbon, and its complexes remain part of the model. Commercial mass/volume
and nitrate-N/P/S additions are calculated and rescored against the crop
targets. Candidates may be accepted, rejected or require incidental review.
Only accepted candidates can be selected. Automatic ranking minimizes final
nutrient loss, with input order breaking ties; this is not a recommendation
that the lowest-loss acid is operationally or agronomically best. No acid
blending, cost optimization, handling protocol or autonomous dosing is added.

## Reproducible evidence

`tests/test_water_workflow.py` covers water subtraction, incidental review and
explicit maxima, calculated pH against the existing mixed PHREEQC reference,
synthetic end-to-end stock/acid planning and rejection boundaries.
`tests/test_acid_reference.py` checks four additional independent acid cases,
charge balance, component conservation, hashes and live replay.

Captures are under `tests/fixtures/phreeqc/acid_selection/{HNO3,H3PO4,H2SO4,C6H8O7}`.
Each contains input, full output, screen output, selected output and expected
JSON with hashes/provenance/tolerances. These are synthetic NaCl-background
references, not validation of every possible real-water acid combination.
Dose tolerance is 3% relative plus 1e-9 mol/kg-water, pH tolerance 0.01, and
PHREEQC charge error must not exceed 0.1%. The existing database and all prior
product/phase/failure captures are preserved.

Regenerate only the new captures using `python tools/acid_selection_evidence.py`.
It uses the pinned external 3.8.6-17100 installation and temporarily merges
unchanged `minteq.v4.dat` with the existing chelate and phase extensions. No
executable or merged database is checked in.

(local-validation-2026-09-28)=
## Historical validation

Dated development checks are preserved in the
[planning validation history](../evidence/planning-validation-history.md#water-to-delivery-validation).
They record those runs only and do not establish current release validation.
