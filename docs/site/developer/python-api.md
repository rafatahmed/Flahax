# Using FlahaX

FlahaX chooses fertilizer salts and the grams of each salt for one litre of working solution. The crop formula stays fixed. This season’s water is subtracted from it. The remaining gap is what the salts must cover.

Python 3.11 or newer is required. The package has no third-party dependencies.

FlahaX is open source under the Apache License 2.0 from version 0.4.0.

## Install

From PyPI, inside a virtual environment (pin the version for reproducible
work):

```powershell
python -m pip install flahax==0.6.0
```

From a checkout of this repository:

```powershell
python -m pip install -e .
python -c "import flahax; print(flahax.__version__)"
```

An editable install registers the `flahax` command and ships `data/library.json` with the package.

## Library call

```python
from flahax import load_library, recommend

library = load_library()
salts = library["salts"]
result = recommend(
    salts,
    targets={"N_NO3": 128, "P": 58, "K": 211, "Ca": 104, "Mg": 40, "S": 54},
    water={"Ca": 20},
)
for salt in result["salts"]:
    print(salt["name"], salt["gramsPerLitre"])
```

`recommend` drops placeholder rows itself. You can pass the full `salts` list from `load_library()`.

## Command line

The same solve is available as a program. It requires an explicit nonempty `salts` array, reads one JSON object from standard input and writes the `recommend` result to standard output. Select the shipped catalogue deliberately when that is the intended source:

```powershell
py -c "import json; from flahax import load_library; print(json.dumps({'salts': load_library()['salts'], 'targets': {'N_NO3': 128, 'P': 58, 'K': 211, 'Ca': 104, 'Mg': 40, 'S': 54}, 'water': {'Ca': 20}}))" | python -m flahax
```

After installation, `flahax` is the same program. A missing or empty `targets` object exits with status 1 and a message on standard error. `water` may be omitted. A `water` value that is present and is not a JSON object exits with status 1. Unknown ions, total `N`, negative ppm, and non-finite ppm exit with status 1. Optional `allowIons` is a list such as `["Cl"]`. Optional `allowCarbonates` is true or false.

## Public functions

Signature summary (not executable Python):

```text
from flahax import gap_for, load_library, recommend, solve_weights

load_library() -> dict
gap_for(targets, water) -> dict
recommend(salts, targets, water=None, *, allow_ions=None, allow_carbonates=False, ridge=0.0,
          maximum_concentrations=None, max_ammonium_fraction=0.1) -> dict
solve_weights(salts, targets, water=None, ridge=0.0, *, max_ammonium_fraction=0.1) -> dict
```

`solve_weights` fits a set of salts you already chose and raises `InputError` when an assay disagrees with a formula that cannot contain that element. `recommend` applies the default exclusions, then fits positive targets by squared relative error. Both APIs retain `ridge` for compatibility but require zero; nonzero or invalid values raise `InputError`. Remove an old explicit `ridge=0.02` argument to migrate. Dose magnitude and untargeted nutrient concentrations do not enter the primary objective. Equivalent best-fit allocations need not use identical products.

`forward(salts, grams, water=None)` and `score(achieved, targets)` live in `flahax.engine`. `forward` applies the ppm equation. `score` returns the loss and the percentage-error rows.

## Inputs

Targets and water are maps of element symbol to ppm. Use the database symbols:

`N_NO3`, `N_NH4`, `P`, `K`, `Ca`, `Mg`, `S`, `Fe`, `Mn`, `Zn`, `B`, `Cu`, `Mo`, `Na`, `Cl`, `Si`.

A missing target means the formula does not ask for that element. That is different from a target of zero. Untargeted contributions are reported without a fitting penalty; explicit maxima remain hard constraints (see [Incidental ions and ceilings](#incidental-ions-and-ceilings)).

A salt is a dictionary:

```json
{
    "id": "…",
    "name": "Potassium Nitrate",
    "formula": "KNO3",
    "elements": {"N_NO3": 13.856, "K": 38.67},
}
```

`elements` values are percentages from 0 to 100.

## Result

```json
{
    "salts": [{"id": "…", "name": "…", "gramsPerLitre": 0.5458}],
    "saltIds": ["…"],
    "grams": [0.0, 0.5458],
    "loss": 0.0,
    "rows": [
        {"symbol": "K", "target": 211, "final": 211.0, "deltaPct": 0.0}
    ],
}
```

For `solve_weights`, `grams` follows the supplied salt list, including zeros.
For `recommend`, filtering and recovery change that order: do not zip its raw
`grams` vector with the original catalogue. Use the identity-bearing `salts`
records and their `gramsPerLitre` for downstream mapping. `salts` contains only
products with a retained positive weight. `deltaPct` is `None` when the formula
has no target for that symbol or its target is zero.

In the water-to-delivery workflow, `feasible` measures positive-target
fit; it is not an assertion that every incidental addition is acceptable.
`incidentalContributions` and `requiresReview` report omitted-target
nutrients separately. Explicit zero targets are hard zero limits. Explicit `maximum_concentrations` in the workflow or
acid adapters enforce absolute nutrient limits, including a true zero limit.
See [water-to-delivery](water-to-delivery.md).

## Tolerance, formula balance and unmet targets

`feasible` means every positive target is within 1% of the formula value (an
absolute 0.01 mg/L floor applies in the benchmark evaluator). The 1% is a FlahaX
assumption: no published standard gives a per-ion tolerance for preparing a feed
solution. It is a numerical recipe-fit criterion, not a crop-response threshold.

`targetIonBalance` is a conventional charge check on requested nutrient entries,
not the whole solution. `recipeIonBalance` applies the same convention to all
emitted nutrient concentrations, including supported counterions and source water.
Both expose `scope="nutrient_subset_convention"`, `provesInfeasibility=False`
and `unrepresentedNutrients`. The existing 10% warning is informational: it
cannot rule out an exact nutrient fit. P is represented as H2PO4- and S as SO4 2-;
this convention does not perform speciation.

`chargeAssessment.status="partial_charge_inventory"` explicitly records the
boundary. `assayOnlyProducts` identifies emitted products without supported
analytical components. `materialInventory` records available components, including
ligands; even supported components do not establish full water chemistry or the
pH-dependent species charge. A balanced nutrient subtotal is not proof of a
chemically complete solution.

Every positive target missed by more than 1%, and every violated zero target,
appears in `unmetTargets`. Relative error remains null for zero targets.

| Reason | Meaning |
|---|---|
| `water_exceeds_target` | Source water already exceeds the missed target; nonnegative product additions cannot subtract it. |
| `target_above_maximum` | The requested target contradicts its explicit hard maximum. |
| `no_source` | No admitted nutrient product supplies the deficient nutrient. |
| `prohibited_by_zero_requirement` | Every source of the deficient nutrient carries a prohibited nutrient; `zeroRequirements` and `blockedProducts` identify the witness. |
| `limited_by_ceiling` | A relaxed target-only fit succeeds and a limit is observed binding; this is a possible cause, not proof the ceiling forces this miss. |
| `fit_degradation` | Relaxed fitting succeeds but no binding ceiling is identified. |
| `conflicting_targets` | The relaxed search still misses targets; `conflictsWith` lists successful drop-one searches and `reachableWithChloride` reports a relaxed chloride search. Neither establishes feasibility under the original constraints. |

The first four reasons carry `status="proven_infeasible"` and an explicit
`proofScope`: the declared nonnegative nutrient inventory and caller constraints.
The remaining reasons carry `status="search_incomplete"` and null `proofScope`.
`searchScope` discloses the relaxed zero/maximum constraints. No failed numerical
search or partial charge sum is promoted to an impossibility proof. Feasibility
and hard-limit assessment of the actual emitted recipe remain separate.

## Incidental ions and ceilings

An incidental ion is one the products add but the formula does not ask for.
Without a ceiling, it is reported for review and does not affect fitting loss.
With a ceiling in `maximum_concentrations` (mg/L), it is allowed up to that value. If the fit
would exceed it, the ceiling is applied as a constraint: the best fit to the
targets with the ion held on its limit (less one part per million). Any excess
that cannot be removed is reported in `limitViolations` with `feasible` false. A ceiling on `Cl` or `Na` also admits
the products that carry it; chloride products are never used without one.

**Nitrogen forms and the ammonium allowance.** `N_NO3`, `N_NH4` and `N_UREA` are
each their own fitted target; `result["totalN"]` reports their sum and is never
fitted. An absent `N_UREA` is a declared zero. An absent or zero `N_NH4` is no
ammonium requirement (no row, no ban): incidental NH4-N is then held within
min(`max_ammonium_fraction` × total target N, 1.5 mmol/L NH4 = 21.01 mg/L N).
The default fraction 0.10 follows Dutch soilless practice (De Kreij, Voogt et
al.); `result["ammoniumLimit"]` records the limit, fraction, cap and basis, and
`None` adds no ammonium maximum. A positive `N_NH4` target or a
`maximum_concentrations` entry takes precedence. `solve_weights` applies the
same allowance and reports `ammoniumLimit` and `totalN` the same way.
Explicit zeros and targeted ceilings are enforced independently of the objective.
`score` retains all nutrient rows but sums only positive-target squared relative errors.
Binding-limit diagnostics use the same numerical aim and convergence tolerance as
the ceiling search; hard-limit acceptance still compares directly with the stated limit.
Secondary product removal uses the original error reference throughout:
no positive-target error may increase from that fit, primary loss may not increase
from the best accepted trial, and zeros/maxima are rechecked. No additional
numerical allowance is granted; equal fits may retain extra products because of
floating-point differences. Published dose rounding remains separately tracked.
The coupled pH search treats an opposite-direction trial as a bound, never as an
accepted dose. At a product switch it can blend the two bracketing product recipes,
solve charge balance on the mixture, and rebuild nutrient and limit assessments at
the verified reagent dose. Initial wrong-direction products remain not applicable.
This bounded repair does not certify global joint optimality; issue #158 remains open.

## Caller-defined agronomic requirements

FlahaX does not prescribe feed-pH bands, a residual-bicarbonate minimum,
or an ammonium fraction. Supply the target pH and any nutrient limits explicitly.
The equilibrium acid plan reports residual bicarbonate in
`audit["residualBicarbonateMmolPerKg"]` without a crop-suitability warning.
Numerical feasibility establishes agreement with supplied inputs only.

## Additional planning commands (since 0.3.1)

The no-argument JSON recommendation command remains backward compatible.
Site planning has explicit commands; prompts go to stderr and JSON results
go to stdout:

```powershell
python -m flahax workflow --interactive
python -m flahax ec --interactive
python -m flahax size --interactive
```

Each command also accepts its documented JSON object on stdin without
`--interactive`. The workflow requires user-specific water and offers nitric
or phosphoric acid. EC is bounded manufacturer-anchor screening, not a
general concentrated-stock model. Equipment sizing gives flow/volume
requirements, not a manufacturer model or actuator commands.
For a grower report and printable batch sheet from one formula and one water,
use `flahax batch` (see [batch report, sheet and tanks](../agronomist/reading-results.md)).
See [site inputs and schemas](site-planning.md), [source-sheet review](../evidence/source-sheet-review.md)
and [current development status](https://github.com/rafatahmed/Flahax/blob/main/docs/development-status.md).

## Source water chemistry from a laboratory analysis (0.4.0)

`feasible` says nothing about pH or precipitation. For that, the water's
complete analysis goes into the equilibrium model. A real analysis is never
exactly charge-balanced, and solving pH from charge balance alone turns that
small error into a large pH error. Start from the measured pH instead:

```python
from flahax import balance_water_analysis

# Fully specified synthetic electrolyte; not a site prescription.
analysis_totals = {"Na+": 0.002, "Cl-": 0.002, "CO3-2": 0.0}
balanced = balance_water_analysis(analysis_totals, measured_ph=7.8)
print(balanced.imbalance_percent, balanced.balance_ion, balanced.balance_adjustment_molal)
```

The remaining charge is closed on `Cl-` (or `Na+`) and reported. An imbalance
above 5% is rejected. Titrated alkalinity can replace inorganic carbon via
`alkalinity_eq_per_kg`. In `plan_fertilizer_workflow`, add `measured_ph` to the
`equilibrium` record. See the user manual, section 11, and
[water-to-delivery](water-to-delivery.md#measured-ph-water-balancing).

## Tests

From the repository root, after the package is installed:

```powershell
python -m unittest discover -s tests -t .
```

`test_pepper.py` checks water subtraction, the edited pepper fit, and the forced double-phosphate miss. `test_library.py` checks that the packaged catalogue (Flaha Agri Tech Analysis Ver 0.0, owner-supplied, not independent laboratory verification) has 29 products (24 fertilizers and 5 pH products), 3 waters, and 13 formulas, then calls `recommend` once per formula. `test_measured_water.py` checks measured-pH water balancing on a published Qatar well. Set `FLAHAX_REQUIRE_PHREEQC=1` to make the live PHREEQC replay fail rather than skip when the pinned executable is missing.

### Chemistry failure and compatibility contract

`solve_fertilizer_equilibrium`, `solve_mixed_fertilizer_equilibrium` and
`solve_ch_micro_equilibrium` expose views of the current simultaneous model.
The explicitly named legacy macro/acid functions and isolated reference kernels
retain narrower reaction sets. Use the [model scope](../models/fertilizer-equilibrium-model.md)
to distinguish them; the historical nitric helper uses a reduced alkalinity
expression, while the current nitric target conserves added nitrate.

Callers must handle `DeliveryError` with code `nonconvergent` from retained
iterative kernels as well as the current solver. A failed iteration budget is
not a usable last-iterate result. Fixed-pH solutions do not automatically imply
charge neutrality, and equilibrium phase amounts do not predict kinetics.


## Zero requirements and hard maxima

A missing target leaves a nutrient unspecified. A target of `0` prohibits its
positive contribution. Because product contributions are nonnegative, fitting
excludes every product carrying that nutrient, including formula counterions and
arbitrarily small positive assays. This also applies to `solve_weights`.
A positive maximum or `allow_ions` permission cannot override an explicit zero.

`maximum_concentrations` applies whether the nutrient has a target or is
incidental. Positive target rows remain in the objective when a ceiling binds;
the ceiling is an additional constraint. The existing solver uses an interior
numerical aim one millionth below a binding positive limit. This does not change
the requested maximum or authorize exceeding it. Classification uses the actual
reported concentration and maximum directly, without an absolute slack.

`requirementConflicts` records `target_above_maximum` and
`water_above_maximum`, with the nutrient and original mg/L values. Such results
are not feasible. Water already at a maximum permits no further addition of
that nutrient; water above it cannot be corrected by adding fertilizer. Review
`limitViolations` as well as `feasible`. All-zero targets can be satisfied by an
empty recipe when water complies. The positive-target feasibility tolerance and trace-dose reporting remain
separately tracked solver work.

## Automatic search within available products

Pass only available product records to `recommend` or `plan_fertilizer_workflow`.
The engine fits nonnegative mixtures of the eligible pool, then automatically
reconsiders supplied sodium-bearing sources for deficient nutrients under the
existing recovery policy. Recovery also works when the initial pool is empty.
After each substitution it checks for new deficits and repeats until no new
permitted source is found. Every successful pass adds a supplied product ID, so
the recovery process terminates on a finite inventory. Product input order breaks
numerical ties; no manual solver mode is needed.

`substitutionSearch` records `availableProductIds`, `attemptedProductIds`, method
and scope. `candidate_found` means the resulting nutrient recipe passes the
existing nutrient acceptance checks. `search_incomplete` means no acceptable
candidate was found by this search, not that every possible mixture is impossible.
Scoped structural proofs remain in `unmetTargets`. Coupled blends disclose their
endpoint product sets and reassess the status for their actual final recipe.

Targets, nitrogen forms, water and hard limits are never changed. Chloride still
requires explicit permission (target, positive ceiling or `allow_ions`); carbonate
and pH-reagent restrictions still apply. No absent catalogue product is loaded.
If no admissible source remains after recovery, the existing `InputError` contract
is preserved. An available-stock failure is not permission to use a catalogue-only
alternative or change the pH target. Chemical/stock suitability is assessed later.

## Joint fertilizer/reagent contract

See [the joint problem contract](joint-problem.md) for `JointSource`, `JointProblem`
and `make_joint_problem`, including residuals, units, zero-dose boundaries and
the distinction between evaluating a candidate and finding an accepted solution.
