# FlahaX

FlahaX chooses a fertilizer combination and the grams of each salt for a fixed crop formula. Version 0.1.0. It is a separate Python package. The FlahaFAST application does not import it.

The crop formula does not change. This season’s water is subtracted from it. The gap that remains is what the salts must cover. Every real salt in the library is a candidate. Non-negative grams decide which salts stay in the mix. No salt is given a role by name.

## Install

From the repository root, in a virtual environment:

```powershell
python -m pip install -e .
python -c "import flahax; print(flahax.__version__)"
```

`pip install -e` installs the package and the library file. There are no third-party dependencies. Python 3.11 or newer is required. The package is not on a public index yet.

```python
from flahax import load_library, recommend

library = load_library()
salts = [salt for salt in library["salts"] if salt.get("formula") != "Input Formula Here"]
```

## The problem

A salt is not a knob for one element. Potassium nitrate carries potassium and nitrate-nitrogen. Monopotassium phosphate carries phosphorus and potassium. Monoammonium phosphate carries phosphorus and ammonium. If those salts are stacked by hand, phosphorus and potassium can land hundreds of percent away from the formula while the micronutrients, which each have their own salt, look perfect.

FlahaX answers a different question: given this formula and this water, which subset of the library, at which grams per litre, makes the percentage error as small as those compositions allow?

## Mathematics

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

An element that the formula does not ask for, such as ammonium or chloride, still has a light penalty: its ppm is divided by 100 and squared. That stops a salt from looking free when it dumps an element nobody requested. A sparsity term of `0.02` on each gram pushes salts that do not improve the fit back to zero, so the result is a short combination rather than a dusting of every salt.

`recommend` runs that solve on every usable salt at once. The salts with grams above 0.000001 g/L are the combination, so zinc, copper, and molybdenum stay in the result.

## Public functions

```python
from flahax import gap_for, load_library, recommend

load_library() -> dict
gap_for(targets, water) -> dict
recommend(salts, targets, water=None) -> dict
```

`solve_weights(salts, targets, water=None, sparsity=0.0)` is the same fit for a set you already chose. `recommend` calls it with `sparsity=0.02`.

`forward(salts, grams, water=None)` applies the ppm equation. `score(achieved, targets)` returns the loss and the Δ% rows. Both live in `flahax.engine`.

### Inputs

Targets and water are maps of element symbol to ppm. Use the database symbols: `N_NO3`, `N_NH4`, `P`, `K`, `Ca`, `Mg`, `S`, `Fe`, `Mn`, `Zn`, `B`, `Cu`, `Mo`. A missing target means the formula does not ask for that element. It is not the same as a target of zero, but any ppm the salts still produce is penalized.

A salt is a dictionary:

```python
{
  "id": "…",
  "name": "Potassium Nitrate",
  "formula": "KNO3",
  "elements": {"N_NO3": 13.856, "K": 38.67},
}
```

### Result

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

`grams` lines up with the input salt list and includes the zeros. `salts` is only the salts that received a positive weight. `deltaPct` is `None` when the formula has no target for that symbol.

## Library file

`load_library()` reads `flahax/data/library.json`, which is installed with the package. It is an export of the production database.

| Key | Count | Contents |
|---|---:|---|
| `salts` | 37 | Name, formula, element percentages |
| `waters` | 3 | `Default Water Profile` (no ions), `WC1` (Ca 20), `WC2` (N, Mg, Ca, Fe) |
| `formulas` | 26 | Name, targets, linked water, salt names stored on the formula |

Two rows are placeholders, not fertilizers: `Si_test` and `test_all`, both with formula text `Input Formula Here`. `_usable` drops those, and any salt whose name starts with `test_`. The other 35 salts all enter the solve. Nothing in the solver prefers a salt because its name is MAP, MKP, or SOP.

The formulas stored in that file are the library rows. Pepper (Howard Resh) there is nitrate-N 190, P 40, K 340, Ca 170, S 360, ammonium 18. The edited pepper targets used in the proof below are a separate case.

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

## Tests

After `pip install -e .`, from this repository root:

```powershell
python -m unittest discover -s tests -t .
```

The discover path starts at this repository so `flahax` imports. Each test file can also be run on its own once the package is installed.

`test_pepper.py` checks the water subtraction, the edited pepper fit, and the forced double-phosphate miss.

`test_library.py` checks that the export still has 37 salts, 3 waters, and 26 formulas, then calls `recommend` once per formula. Each call must return salts that belong to that library and a numeric loss.

## What this version does not do

It does not split tanks, adjust pH, price the mix, or apply a concentration factor. Grams are for one litre of the solution the plant sees. Stock-tank grams are those grams multiplied by the concentration factor, and that step belongs to the recipe screen, not to this package.

It does not write to the FlahaFAST database and it does not change a saved run. How it can be connected later without changing the current flow is in [INTEGRATION.md](INTEGRATION.md).
