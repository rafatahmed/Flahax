# Water, nutrient targets and acid selection

Development API, not part of the published 0.3.0 artifacts. This workflow plans;
it does not operate equipment or certify agronomic suitability.

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
water Ca 20 mg/L, the regression recipe has approximately 4.845114 mg/L NH4-N
and 0.047919 mg/L Na. Positive targets fit within 1%, but these incidental
amounts require review. These are catalogue-assay calculations, not a dosing
authorization. In particular, `Phosphoric Acid (75%)` currently lists 31.61%
P, approximately the pure-acid fraction rather than a 75% aqueous product
fraction. That commercial-grade ambiguity and the Mg nitrate formula/assay
warning require confirmation before physical use. This change does not alter
the catalogue or silently replace its materials.

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
| `equilibrium` | `water_totals`, `water_mass_kg`, `water_analysis_id`, `complete_analysis`, `carbon_boundary`, `temperature_c`, `phases` | Complete fixed-valence analytical component totals in mol/kg-water; explicit final solvent inventory, 25 C, closed carbon, explicit phase list |
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

### Local validation, 2026-09-28

During water-to-delivery development, Windows / Python 3.14.0:

| Command / check | Observed result |
|---|---|
| `PYTHONPATH=src FLAHAX_REQUIRE_PHREEQC=1 python -m unittest discover -s tests -t .` | 121 tests passed in 261.424 seconds; no skips |
| Two subsequently added tests: changed catalogue assay and non-mapping maxima (`tests.test_water_workflow.WaterWorkflowTests`) | Both passed; 123 distinct tests exercised across these runs, not a claimed 123-test single run |
| `python -m unittest tests.test_acid_reference -v` with required PHREEQC | Both golden comparison and live replay passed |
| `.venv-verification/Scripts/python.exe tools/verify_distribution.py --report build/water-workflow-distribution-verification.json` | Clean wheel and sdist installs passed, including four existing manual examples, exports and CLI checks |
| `python -m compileall -q src tools`; `git diff --check` | Passed |

The distribution check preceded final documentation-only edits. Its report is
local build evidence, not a release artifact manifest. No new version was
published, no hosted acceptance was claimed and the published 0.3.0 files were
not replaced. Run the current complete suite again before release; these local
results do not waive the normal supported-version/hosted verification gates.
