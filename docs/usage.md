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
recommend(salts, targets, water=None, *, allow_ions=None, allow_carbonates=False, ridge=0.02) -> dict
solve_weights(salts, targets, water=None, ridge=0.0) -> dict
```

`solve_weights` fits a set of salts you already chose and raises `InputError` when an assay disagrees with a formula that cannot contain that element. `recommend` applies the default exclusions, then calls the fit with `ridge=0.02`. `ridge` shrinks grams. It is not a count of salts.

`forward(salts, grams, water=None)` and `score(achieved, targets)` live in `flahax.engine`. `forward` applies the ppm equation. `score` returns the loss and the percentage-error rows.

## Inputs

Targets and water are maps of element symbol to ppm. Use the database symbols:

`N_NO3`, `N_NH4`, `P`, `K`, `Ca`, `Mg`, `S`, `Fe`, `Mn`, `Zn`, `B`, `Cu`, `Mo`, `Na`, `Cl`, `Si`.

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

For `solve_weights`, `grams` follows the supplied salt list, including zeros.
For `recommend`, filtering and recovery change that order: do not zip its raw
`grams` vector with the original catalogue. Use the identity-bearing `salts`
records and their `gramsPerLitre` for downstream mapping. `salts` contains only
products with a retained positive weight. `deltaPct` is `None` when the formula
has no target for that symbol or its target is zero.

In the unreleased water-to-delivery workflow, `feasible` measures positive-target
fit; it is not an assertion that every incidental addition is acceptable.
`incidentalContributions` and `requiresReview` report zero/omitted-target
nutrients separately. Explicit `maximum_concentrations` in the workflow or
acid adapters enforce absolute nutrient limits, including a true zero limit.
See [water-to-delivery](water-to-delivery.md). This does not change the
optimizer's existing penalties or invent different fertilizer materials.

## Additional planning commands (unreleased checkout)

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
and [current development status](development-status.md).

## Tests

From the repository root, after the package is installed:

```powershell
python -m unittest discover -s tests -t .
```

`test_pepper.py` checks water subtraction, the edited pepper fit, and the forced double-phosphate miss. `test_library.py` checks that the example export has 28 salts, 3 waters, and 26 formulas, then calls `recommend` once per formula. A live call passes the salts saved in FlahaFAST.
