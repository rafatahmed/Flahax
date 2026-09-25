# Using FlahaX

FlahaX chooses fertilizer salts and the grams of each salt for one litre of working solution. The crop formula stays fixed. This season’s water is subtracted from it. The remaining gap is what the salts must cover.

Python 3.11 or newer is required. The package has no third-party dependencies.

## Install

From a checkout of this repository, inside a virtual environment:

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

The same solve is available as a program. It reads one JSON object from standard input and writes the `recommend` result to standard output.

```powershell
@'
{"targets": {"N_NO3": 128, "P": 58, "K": 211, "Ca": 104, "Mg": 40, "S": 54}, "water": {"Ca": 20}}
'@ | python -m flahax
```

After installation, `flahax` is the same program. A missing or empty `targets` object exits with status 1 and a message on standard error. `water` is optional and defaults to an empty map. Invalid JSON exits with status 1.

## Public functions

```python
from flahax import gap_for, load_library, recommend, solve_weights

load_library() -> dict
gap_for(targets, water) -> dict
recommend(salts, targets, water=None) -> dict
solve_weights(salts, targets, water=None, sparsity=0.0) -> dict
```

`solve_weights` fits a set of salts you already chose. `recommend` calls it with `sparsity=0.02` after dropping unusable rows.

`forward(salts, grams, water=None)` and `score(achieved, targets)` live in `flahax.engine`. `forward` applies the ppm equation. `score` returns the loss and the percentage-error rows.

## Inputs

Targets and water are maps of element symbol to ppm. Use the database symbols:

`N_NO3`, `N_NH4`, `P`, `K`, `Ca`, `Mg`, `S`, `Fe`, `Mn`, `Zn`, `B`, `Cu`, `Mo`.

A missing target means the formula does not ask for that element. That is different from a target of zero. Any ppm the salts still produce for an unrequested element is penalized.

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

`grams` lines up with the salt list that entered the solve, and it includes the zeros. `salts` contains only the salts that received a positive weight. `deltaPct` is `None` when the formula has no target for that symbol.

## Tests

From the repository root, after the package is installed:

```powershell
python -m unittest discover -s tests -t .
```

`test_pepper.py` checks water subtraction, the edited pepper fit, and the forced double-phosphate miss. `test_library.py` checks that the export still has 37 salts, 3 waters, and 26 formulas, then calls `recommend` once per formula.
