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

An element that the formula does not ask for still has a light penalty: its ppm is divided by 100 and squared. A ridge term of `0.02` on each gram shrinks weights. That term is L2 regularization. It does not count salts, and it does not by itself produce a short recipe.

The least-squares step inside Lawson–Hanson is a Householder QR solve. The normal equations are not formed.

After that fit, a salt is removed only when a refit still keeps every requested ion inside the tolerance already achieved, and inside 1% when the first fit was already inside 1%. Grams above 0.000001 g/L are the recipe.

`recommend` does not dose every row in the file. A salt whose formula cannot contain an assayed element is left out. Carbonate formulas are left out of a default recipe. Sodium and chloride are left out unless the formula asks for them, the caller allows them, or a requested ion stays outside 1% without the salt that carries them. The result then says whether the recipe is feasible, the largest absolute Δ%, the unrequested ions added, the total grams per litre, and any warnings.

## Library file

`load_library()` reads `flahax/data/library.json`, which is installed with the package. It is an export of the production database.

| Key | Count | Contents |
|---|---:|---|
| `salts` | 30 | Name, formula, element percentages |
| `waters` | 3 | `Default Water Profile` (no ions), `WC1` (Ca 20), `WC2` (N, Mg, Ca, Fe) |
| `formulas` | 26 | Name, targets, linked water, salt names stored on the formula |

Two rows are placeholders, not fertilizers: `Si_test` and `test_all`, both with formula text `Input Formula Here`. Unusable rows are those placeholders, salts whose name starts with `test_`, and salts with no elements. The other salts all enter the solve. Nothing in the solver prefers a salt because its name is MAP, MKP, or SOP.

The formulas stored in that file are the library rows. Pepper (Howard Resh) there is nitrate-N 190, P 40, K 340, Ca 170, S 360, ammonium 18. The edited pepper targets in the proof below are a separate case.

## Proof: edited pepper, water calcium 20

Targets: nitrate-N 128, P 58, K 211, Ca 104, Mg 40, S 54. Water: Ca 20, so the calcium gap is 84.

The fit from the full library keeps six salts and holds every targeted element inside 1%:

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

The package does not write to the FlahaFAST database and it does not change a saved run. How the application can call it is described in [INTEGRATION.md](../INTEGRATION.md).
