# Using FlahaX

FlahaX chooses fertilizer salts and the grams of each salt for one litre of working solution. The crop formula stays fixed. This season’s water is subtracted from it. The remaining gap is what the salts must cover.

Python 3.11 or newer is required. The package has no third-party dependencies.

FlahaX is open source under the Apache License 2.0 from version 0.4.0.

## Install

From PyPI, inside a virtual environment (pin the version for reproducible
work):

```powershell
python -m pip install flahax==0.4.0
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

```python
from flahax import gap_for, load_library, recommend, solve_weights

load_library() -> dict
gap_for(targets, water) -> dict
recommend(salts, targets, water=None, *, allow_ions=None, allow_carbonates=False, ridge=0.02,
          maximum_concentrations=None, max_ammonium_fraction=0.10) -> dict
solve_weights(salts, targets, water=None, ridge=0.0) -> dict
```

`solve_weights` fits a set of salts you already chose and raises `InputError` when an assay disagrees with a formula that cannot contain that element. `recommend` applies the default exclusions, then calls the fit with `ridge=0.02`. `ridge` shrinks grams. It is not a count of salts.

`forward(salts, grams, water=None)` and `score(achieved, targets)` live in `flahax.engine`. `forward` applies the ppm equation. `score` returns the loss and the percentage-error rows.

## Inputs

Targets and water are maps of element symbol to ppm. Use the database symbols:

`N_NO3`, `N_NH4`, `P`, `K`, `Ca`, `Mg`, `S`, `Fe`, `Mn`, `Zn`, `B`, `Cu`, `Mo`, `Na`, `Cl`, `Si`.

A missing target means the formula does not ask for that element. That is different from a target of zero. Any ppm the salts still produce for an unrequested element is penalized, unless that element has a ceiling (see [Incidental ions and ceilings](#incidental-ions-and-ceilings)).

A salt is a dictionary:

```python
{
    "id": "…",
    "name": "Potassium Nitrate",
    "formula": "KNO3",
    "elements": {"N_NO3": 13.856, "K": 38.67},
}
```

`elements` values are percentages from 0 to 100.

## Result

```python
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
`incidentalContributions` and `requiresReview` report zero/omitted-target
nutrients separately. Explicit `maximum_concentrations` in the workflow or
acid adapters enforce absolute nutrient limits, including a true zero limit.
See [water-to-delivery](water-to-delivery.md).

## Tolerance, formula balance and unmet targets

`feasible` means every positive target is within 1% of the formula value (an
absolute 0.01 mg/L floor applies in the benchmark evaluator). The 1% is a FlahaX
assumption: no published standard gives a per-ion tolerance for preparing a feed
solution. Dutch practice corrects only when root-zone analyses deviate by 25% or
more (De Kreij et al. 2003).

A real nutrient solution is electrically neutral (Steiner 1961). `recommend`
reports `targetIonBalance`: the cation and anion meq/L implied by the formula
itself, counting P as H2PO4- and S as SO4 2- and excluding urea, Si and
micronutrients. When the two sums differ by more than 10% of the larger, a
warning explains that no salt combination can meet every target exactly. The
10% follows the window used by Steiner-type software (Martinez-Corral et al.
2009). Several shipped formulas exceed it, including Pepper (Howard Resh) at
-39.5% and the U of Florida tomato clusters at +19% to +30%.

Every positive target missed by more than 1% appears in `unmetTargets` with a
reason:

| Reason | Meaning |
|---|---|
| `no_source` | No catalogue product supplies the element (for example Si). |
| `limited_by_ceiling` | The targets are reachable, but an incidental ceiling binds; `bindingLimits` names it. |
| `incidental_tradeoff` | The targets are reachable, but the incidental-ion penalty chose otherwise. |
| `conflicting_targets` | Dropping one of the `conflictsWith` targets makes the rest reachable; `reachableWithChloride` says whether chloride products (which need a Cl ceiling) would reach it. |

The diagnosis is a least-squares check on the target rows alone. It names a
likely cause; it does not prove infeasibility.

## Incidental ions and ceilings

An incidental ion is one the products add but the formula does not ask for.
Without a ceiling, each mg/L of it is penalized in the fit. With a ceiling in
`maximum_concentrations` (mg/L), the ion is free up to that value, is pulled
back if the fit exceeds it, and any remaining excess is reported in
`limitViolations` with `feasible` false. A ceiling on `Cl` or `Na` also admits
the products that carry it; chloride products are never used without one.

**Ammonium default.** When the targets omit `N_NH4` and no `N_NH4` ceiling is
given, incidental NH4-N may reach the smaller of 10% of the formula's total
target N (`N_NO3 + N_NH4 + N_UREA`) and 1.5 mmol/L NH4 (21.01 mg/L N). Calcium
nitrate (ag grade) always carries some ammonium, so without this allowance the
fit under-doses calcium to avoid it. `result["ammoniumLimit"]` reports the limit
applied. Raise the share with `max_ammonium_fraction` (for example `0.15`), or
pass `None` for the previous penalty-only fit. An explicit `N_NH4` target,
including `0` ("none wanted"), keeps its own fit and is never relaxed.

The values are the project owner's decisions (2026-10-20), grounded in Dutch
soilless practice. Recommended NH4 is 5-15% of total N, with at most about
1-1.5 mmol/L (Van der Lugt et al., following De Kreij, Voogt et al.). Voogt's
WUR lecture gives "heavy fruit bearing - max 90:10" NO3:NH4. The Dutch standard
solutions carry 5.9-8.8% NH4-N for most crops (gerbera 12.8%). The often-quoted
"5-10% in hydroponics, 10-15% in substrate" is Dickson and Fisher's (2019)
attribution to Sonneveld and Voogt (2009) without a page reference, and it
describes the pH-neutral share rather than a limit. That primary text has not
been checked.

References:

- De Kreij, C., Voogt, W. and Baas, R. (2003). *Nutrient solutions and water
  quality for soilless cultures*. Brochure 191, PPO Glasshouse Horticulture,
  Naaldwijk. <https://edepot.wur.nl/456342>
- Voogt, W. Lecture slides on nutrient solutions, Wageningen UR.
  <https://edepot.wur.nl/13081>
- Sonneveld, C. and Voogt, W. (2009). *Plant Nutrition of Greenhouse Crops*.
  Springer, Dordrecht. <https://doi.org/10.1007/978-90-481-2532-6>
  (chapters 12-13, pp. 257-312; not consulted directly).
- Dickson, R. W. and Fisher, P. R. (2019). Quantifying the acidic and basic
  effects of vegetable and herb species in peat-based substrate and
  hydroponics. *HortScience* 54(6): 1093-1100.
  <https://doi.org/10.21273/HORTSCI13959-19>

## Feed pH and residual bicarbonate

`plan_fertilizer_workflow` adds a note when the target pH lies outside 5.3-5.8,
the feed range of Dutch soilless practice (root zone about 5.5-6.0; Van der Lugt
et al.; Savvas). A stronger note appears outside 5.0-7.0. FlahaX doses acid to the
target pH, so the bicarbonate left afterwards is an outcome. The equilibrium acid
plan reports it in `audit["residualBicarbonateMmolPerKg"]` and warns when it is
below the 0.5 mmol/L that Dutch practice leaves as a pH buffer (0.5-0.75 mmol/L).

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
See [site inputs and schemas](site-planning.md), [source-sheet review](source-sheet-review.md)
and [current development status](https://github.com/rafatahmed/Flahax/blob/main/docs/development-status.md).

## Source water chemistry from a laboratory analysis (0.4.0)

`feasible` says nothing about pH or precipitation. For that, the water's
complete analysis goes into the equilibrium model. A real analysis is never
exactly charge-balanced, and solving pH from charge balance alone turns that
small error into a large pH error. Start from the measured pH instead:

```python
from flahax import balance_water_analysis

# mol/kg water; CO3-2 is total inorganic carbon
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

`test_pepper.py` checks water subtraction, the edited pepper fit, and the forced double-phosphate miss. `test_library.py` checks that the example export has 28 salts, 3 waters, and 26 formulas, then calls `recommend` once per formula. `test_measured_water.py` checks measured-pH water balancing on a published Qatar well. Set `FLAHAX_REQUIRE_PHREEQC=1` to make the live PHREEQC replay fail rather than skip when the pinned executable is missing.
