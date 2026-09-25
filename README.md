# FlahaX

FlahaX chooses a fertilizer combination and the grams of each salt for a fixed crop formula. Version 0.1.0. It is a separate Python package. The FlahaFAST application does not import it.

The crop formula does not change. This season’s water is subtracted from it. The gap that remains is what the salts must cover. Every real salt in the library is a candidate. Non-negative grams decide which salts stay in the mix.

## License

Use of FlahaX is free of charge, including commercial use. The [Flaha Free Use License](LICENSE) allows you to install and run the package. It does not allow you to modify the software, and it does not allow you to give copies of it to anyone else. Downloading an official release for your own use is covered. Republishing, forking, or shipping your own copy is not.

Because modification and redistribution are withheld, this is a proprietary free-use license. It is outside the Open Source Definition, which requires those permissions.

## Install

Python 3.11 or newer. No third-party dependencies.

From this repository, in a virtual environment:

```powershell
python -m pip install -e .
python -c "import flahax; print(flahax.__version__)"
```

The package is not on a public index yet. Building a release is described in [docs/publishing.md](docs/publishing.md).

## Quick start

```python
from flahax import load_library, recommend

result = recommend(
    load_library()["salts"],
    targets={"N_NO3": 128, "P": 58, "K": 211, "Ca": 104, "Mg": 40, "S": 54},
    water={"Ca": 20},
)
```

The same call from the command line, reading JSON on standard input:

```powershell
@'
{"targets": {"N_NO3": 128, "P": 58, "K": 211, "Ca": 104, "Mg": 40, "S": 54}, "water": {"Ca": 20}}
'@ | python -m flahax
```

`result["salts"]` lists each chosen salt with `gramsPerLitre`. `result["rows"]` lists each element with its target, the final ppm, and `deltaPct`.

## Proof

Edited pepper targets, with 20 ppm calcium already in the water, fit inside 1% on every targeted element using six salts:

| Salt | g/L |
|---|---:|
| Potassium nitrate | 0.546 |
| Magnesium nitrate | 0.415 |
| Calcium sulfate | 0.290 |
| Phosphoric acid (75%) | 0.146 |
| Calcium nitrate (ag grade) | 0.046 |
| Calcium monobasic phosphate | 0.048 |

The mathematics, the library counts, and the regression case are in [docs/method.md](docs/method.md).

## Documentation

- [docs/usage.md](docs/usage.md) — install, library call, command line, inputs, and result fields
- [docs/method.md](docs/method.md) — ppm equation, solver, library file, and the pepper proof
- [docs/publishing.md](docs/publishing.md) — build the sdist and wheel
- [INTEGRATION.md](INTEGRATION.md) — how FlahaFAST can call the package without changing the current flow

## Tests

After `pip install -e .`, from the repository root:

```powershell
python -m unittest discover -s tests -t .
```

## Scope of this version

Grams are for one litre of the solution the plant sees. This version does not split tanks, adjust pH, price the mix, or apply a concentration factor. It does not write to the FlahaFAST database.
