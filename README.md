# FlahaX

[![PyPI](https://img.shields.io/pypi/v/flahax)](https://pypi.org/project/flahax/)
[![Python](https://img.shields.io/pypi/pyversions/flahax)](https://pypi.org/project/flahax/)
[![License](https://img.shields.io/badge/license-Flaha%20Free%20Use-blue)](LICENSE)

FlahaX selects a fertilizer combination and the grams of each salt for a fixed crop formula. Version 0.2.0. The formula stays as written. This season’s water is subtracted from it, and the salts cover the gap that remains. Every real salt in the shipped library is a candidate. Non-negative grams decide which salts stay in the mix.

The package is separate from the FlahaFAST application. FlahaFAST does not import it.

## Install

Python 3.11 or newer. There are no third-party dependencies.

```powershell
py -m pip install flahax
```

A checkout of this repository can be installed for local work:

```powershell
py -m pip install -e .
```

## Quick start

```python
from flahax import load_library, recommend

result = recommend(
    load_library()["salts"],
    targets={"N_NO3": 128, "P": 58, "K": 211, "Ca": 104, "Mg": 40, "S": 54},
    water={"Ca": 20},
)

for salt in result["salts"]:
    print(f"{salt['name']}: {salt['gramsPerLitre']} g/L")
```

The same solve accepts one JSON object on standard input:

```powershell
@'
{"targets": {"N_NO3": 128, "P": 58, "K": 211, "Ca": 104, "Mg": 40, "S": 54}, "water": {"Ca": 20}}
'@ | flahax
```

`result["salts"]` lists each chosen salt and its `gramsPerLitre`. `result["rows"]` lists each element with its target, the final concentration in ppm, and `deltaPct`. Grams are for one litre of the solution the plant sees.

Element symbols follow the formula database: `N_NO3`, `N_NH4`, `P`, `K`, `Ca`, `Mg`, `S`, `Fe`, `Mn`, `Zn`, `B`, `Cu`, `Mo`.

## Worked example

Edited pepper targets, with 20 ppm calcium already in the water, stay inside 1% on every targeted element. The fit uses six salts:

| Salt | g/L |
|---|---:|
| Potassium nitrate | 0.546 |
| Magnesium nitrate | 0.415 |
| Calcium sulfate | 0.290 |
| Phosphoric acid (75%) | 0.146 |
| Calcium nitrate (ag grade) | 0.046 |
| Calcium monobasic phosphate | 0.048 |

The ppm equation, the Lawson–Hanson solve, the library counts, and the regression case are in [docs/method.md](docs/method.md).

## Citation

Please cite FlahaX when the package, or a recommendation it produced, is used in a report or a paper.

Al Khashan, R. A. (2026). *FlahaX* (Version 0.2.0) [Computer software]. https://pypi.org/project/flahax/

```bibtex
@software{alkhashan2026flahax,
  author  = {Al Khashan, Rafat A.},
  title   = {FlahaX: fertilizer salt selection for a fixed crop formula},
  year    = {2026},
  version = {0.2.0},
  url     = {https://pypi.org/project/flahax/},
  license = {Flaha Free Use License}
}
```

GitHub reads [`CITATION.cff`](CITATION.cff) for the “Cite this repository” button. That file carries the same record.

## Documentation

| Document | Contents |
|---|---|
| [docs/usage.md](docs/usage.md) | Library call, command line, inputs, and result fields |
| [docs/method.md](docs/method.md) | ppm equation, solver, library file, and the pepper proof |
| [INTEGRATION.md](INTEGRATION.md) | Calling FlahaX from FlahaFAST without changing the current flow |
| [docs/publishing.md](docs/publishing.md) | Building and releasing a new version |

From a checkout, the tests are:

```powershell
py -m unittest discover -s tests -t .
```

## Scope of version 0.2.0

This version returns grams for one litre of working solution. A salt is dosed from the shipped library only when its assay uses known ions and its formula does not rule the assay out. Default recipes leave out carbonate salts, and they leave out sodium and chloride unless the formula asks for that ion or the caller allows it. The result reports whether every requested ion landed inside 1%, plus warnings.

It does not split tanks, adjust pH, price the mix, or apply a concentration factor. It does not write to the FlahaFAST database.

## License

Use of FlahaX is free of charge, including commercial use, under the [Flaha Free Use License](LICENSE). That license permits installation and running of an official copy. Modification, forking, republishing, and giving copies to anyone else require permission from the copyright holder. The license is a proprietary free-use license.
