# Method

A salt is not a knob for one element. Potassium nitrate carries potassium and nitrate-nitrogen. Monopotassium phosphate carries phosphorus and potassium. Monoammonium phosphate carries phosphorus and ammonium. Stacking those salts by hand can leave phosphorus and potassium hundreds of percent away from the formula while the micronutrients, which each have their own salt, look perfect.

FlahaX answers a different question: given this formula and this water, which subset of the library, at which grams per litre, makes the percentage error as small as those compositions allow?

Every real salt in the library is a candidate. Non-negative grams decide which salts stay in the mix. No salt is given a role by name.

## Equation

For one litre of working solution:

```text
final[element] = water[element] + Σ grams[salt] × percent[salt, element] × 10
```

`percent` is the element percentage stored on the salt (0–100). Multiplying by 10 converts one gram per litre at 1% into 10 ppm.

The gap for an element that has a target is:

```text
gap = target − water
```

Grams are constrained to be greater than or equal to zero. The solver is Lawson–Hanson non-negative least squares. Each element row is scaled so the residual is a fraction of the target:

```text
Δ% = (final − target) / target × 100
loss = Σ (Δ% / 100)²
```

Only strictly positive targets contribute to this primary loss. Missing nutrients are
reported as incidental contributions; they do not create an implicit preference.
Explicit zero targets prohibit contribution and stated maxima constrain the fit,
including maxima on targeted nutrients. Water remains part of every final concentration.
Dose magnitude, product count, and incidental concentrations have no primary penalty.

For a single product with target-normalized rates `a` and water-adjusted gaps `b`,
the unconstrained optimum is `max(0, sum(a*b)/sum(a*a))`. Exact attainable targets
therefore have zero primary loss. `score` uses this same objective and retains rows
for zero and missing targets without adding penalties. Numerical ceiling search
retains its documented interior margin; it is not an exact symbolic optimizer.

The least-squares step uses cached Gram solves with refinement and a Householder QR
fallback for poorly conditioned blocks. Equivalent best-fit allocations are allowed.

**Migration:** `recommend` now defaults to `ridge=0`. Both fitting APIs reject nonzero
`ridge` rather than silently accepting a preference that degrades target accuracy.
Remove old explicit nonzero arguments. Incidental review and maximum policies remain
explicit caller decisions; a lower numerical loss is not agronomic approval.

After the primary fit, a product can be removed only when every positive-target
absolute percentage error is no worse than in that original fit, primary loss does
not increase from the best accepted result, and all zero requirements and maxima
remain satisfied. Every attempt uses the same original accuracy reference, even
after several removals. The 1% feasibility band is not permission to degrade a fit.

These are conservative binary64 comparisons with no added error allowance.
Numerically unequal representations of equivalent optima may retain more products;
this greedy pass does not promise a globally minimal product count. All positive
internal doses participate; published dose precision remains separately tracked.


`recommend` does not dose every row in the file. A salt whose formula cannot contain an assayed element is left out. Carbonate formulas are left out of a default recipe. Sodium and chloride are left out unless the formula asks for them, the caller allows them, or a requested ion stays outside 1% without the salt that carries them. The result then says whether the recipe is feasible, the largest absolute Δ%, the unrequested ions added, the total grams per litre, and any warnings.

## Library file

`load_library()` reads `flahax/data/library.json`, which is installed with the package. It is an export of the production database.

| Key | Count | Contents |
|---|---:|---|
| `salts` | 28 | Example fertilizers used by the tests. A live recommendation receives the saved rows instead. |
| `waters` | 3 | `Default Water Profile` (no ions), `WC1` (Ca 20), `WC2` (N, Mg, Ca, Fe) |
| `formulas` | 21 | Name, targets, linked water, salt names stored on the formula |

The file is an example for the tests. `python -m flahax` does not read it. The caller passes the fertilizer rows. A name that starts with `test` or a formula of `Input Formula Here` is still rejected if one is passed. Nothing in the solver prefers a salt because its name is MAP, MKP, or SOP.

The formulas stored in that file are the library rows. Pepper (Howard Resh) there is nitrate-N 190, P 40, K 340, Ca 170, S 360, ammonium 18. The edited pepper targets in the proof below are a separate case.

## Historical example: edited pepper, water calcium 20

Targets: nitrate-N 128, P 58, K 211, Ca 104, Mg 40, S 54. Water: Ca 20, so the calcium gap is 84.

The following allocation was recorded with the earlier fitting policy. It is retained
as historical context, not a current recipe or acceptance result. Current regression
tests preserve these targets but allow equivalent allocations:

| Salt | g/L |
|---|---:|
| Potassium nitrate | 0.546 |
| Magnesium nitrate | 0.415 |
| Calcium sulfate | 0.290 |
| Phosphoric acid (75%) | 0.146 |
| Calcium nitrate (ag grade) | 0.046 |
| Calcium monobasic phosphate | 0.048 |

A hand mix that forces large weights of both ammonium phosphate and potassium phosphate still produces about +216% phosphorus. That mix is the regression case in `tests/test_pepper.py`. The solver is not told to avoid it. The loss is simply higher, so those weights are not chosen.

## Outside this version

This version does not split tanks, adjust pH, price the mix, or apply a concentration factor. Grams are for one litre of the solution the plant sees. Stock-tank grams are those grams multiplied by the concentration factor, and that step belongs to the recipe screen.

The package does not write to the FlahaFAST database and it does not change a saved run. How the application can call it is described in [INTEGRATION.md](https://github.com/rafatahmed/Flahax/blob/main/INTEGRATION.md).
