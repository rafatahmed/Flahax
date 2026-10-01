# FlahaX

Unreleased site-input additions: [interactive CLI, calculated EC screening and
injector flow sizing](docs/site-planning.md). Source water is user-specific;
standard workflow acids are nitric and phosphoric. Manufacturer EC screening
does not claim validated concentrated-stock prediction or select an equipment
model without operating data.

See the [unreleased capability/status matrix](docs/development-status.md) for
the exact implemented boundaries, source handling and next development steps.

**Preparing 0.3.1 - not yet published** · [User manual](src/flahax/data/USER_GUIDE.md) · [Changelog](CHANGELOG.md) · [Release checklist](docs/publishing.md)

Fertilizer formulation, bounded aqueous chemistry, and auditable delivery planning.

[![PyPI](https://img.shields.io/pypi/v/flahax)](https://pypi.org/project/flahax/)
[![Python](https://img.shields.io/pypi/pyversions/flahax)](https://pypi.org/project/flahax/)
[![License](https://img.shields.io/badge/license-Flaha%20Free%20Use-blue)](https://github.com/rafatahmed/Flahax/blob/main/LICENSE)

FlahaX selects a fertilizer combination and the grams of each salt for a fixed crop formula. The formula stays as written. This season’s water is subtracted from it, and the salts cover the gap that remains. Every real salt in the shipped library is a candidate. Non-negative grams decide which salts stay in the mix.

The package is separate from the FlahaFAST application. FlahaFAST does not import it.

The 0.3.0 chemistry and delivery APIs are retained. The 0.3.1 preparation adds site-input planning commands while preserving the no-argument recommendation CLI.

## Chemistry and delivery planning

| Capability | Verified boundary |
|---|---|
| Mixed fertilizer equilibrium (P2/P3) | All 28 catalogue conversions feed one model with 197 aqueous entries and 28 phases; 25 °C, Davies ionic strength <= 0.1 mol/kg water, fixed oxidation states. |
| Catalogue trace products | Fe-DTPA and Fe-o,o-EDDHA are Fe-only 1:1 products; Fe/Mn/Zn/Cu-EDTA retain their declared forms. CH-micro adds those EDTA forms, borax and sodium molybdate. |
| Nitric-acid target pH | Initial and target states use the same mixed solver, with added nitrate and closed analytical inorganic carbon. The result is an initial dose estimate requiring post-mix measurement. |
| Equilibrium-to-delivery adapter (P5.5) | `plan_equilibrium_delivery` returns `EquilibriumPhPlan`: explicit water mass, catalogue doses, HNO3 assay/density, bounded reagent volume, nutrient rescoring and auditable source hashes. |
| Reviewed delivery composition | Both equilibrium and measured-curve pH plans compose with stock and calibrated pump-planning values. Missing inputs, incompatible commands, target supersaturation or formed solids prevent validation. No hardware is operated. |

Recipes use **g/L of final solution**; chemistry uses **g/kg water** and molal analytical totals. They are not interchangeable. The delivery adapter requires explicit final solvent mass and make-up volume, including reagent carrier water. Stock rules, solubility limits, water records and reagent assays are caller-supplied evidence—not universally certified catalogue data.

See the [runnable equilibrium-delivery example and API contract](https://github.com/rafatahmed/Flahax/blob/main/docs/package-verification.md), [chemistry coverage matrix](https://github.com/rafatahmed/Flahax/blob/main/docs/chemistry-coverage-matrix.md), and [reference fixtures](https://github.com/rafatahmed/Flahax/blob/main/docs/reference-fixtures.md).

## Verification status and next steps

Local verification on Python 3.13 passes **110 tests with zero skips**, including pinned PHREEQC live replay, release-hygiene checks and all four shipped-manual examples. Clean wheel and source-distribution installs pass outside the checkout, including manual/data hashes, public imports, numerical examples and both CLI entry points. PHREEQC is an external verification tool, not a runtime dependency or bundled executable.

**Assessor: Rafat Al Khashan.** The owner-amended G6 assessment concerns bounded computational evidence without laboratory work. It is not an independent review, a formal proof for arbitrary inputs, or operational certification. See the [computational assessment](https://github.com/rafatahmed/Flahax/blob/main/docs/computational-review.md) and [release evidence](https://github.com/rafatahmed/Flahax/blob/main/docs/release-evidence.md).

Version **0.3.0 is published on [PyPI](https://pypi.org/project/flahax/0.3.0/)** (2026-09-27). The release used the owner's documented local-evidence exception; hosted verification remains open.

Next priorities are supported-version CI, broader numerical and input-boundary testing, and stable consumer contracts. The [development roadmap](https://github.com/rafatahmed/Flahax/blob/main/docs/development-roadmap.md) defines proposed milestones, acceptance gates and expansion opportunities. The [implementation ledger](https://github.com/rafatahmed/Flahax/blob/main/docs/implementation-roadmap.md) preserves P0–P7 evidence and historical decisions.

## Install

For reproducible use, pin the package version: `python -m pip install flahax==0.3.0`. The unpinned command below installs the latest available release. Source checkouts and verified wheel files can also be installed directly.

Python 3.11 or newer. There are no required third-party runtime dependencies. Distribution verification uses development-only build tooling.

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

The CLI requires an explicit nonempty `salts` array. This example selects the packaged catalogue deliberately and sends one JSON object on standard input:

```powershell
py -c "import json; from flahax import load_library; print(json.dumps({'salts': load_library()['salts'], 'targets': {'N_NO3': 128, 'P': 58, 'K': 211, 'Ca': 104, 'Mg': 40, 'S': 54}, 'water': {'Ca': 20}}))" | flahax
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

The ppm equation, the Lawson–Hanson solve, the library counts, and the regression case are in [docs/method.md](https://github.com/rafatahmed/Flahax/blob/main/docs/method.md).

## Citation

Please cite FlahaX when the package, or a recommendation it produced, is used in a report or a paper.

Al Khashan, R. A. (2026). *FlahaX* (Version 0.3.1, release preparation) [Computer software]. Cite the version actually used; 0.3.0 remains the previous published baseline.

```bibtex
@software{alkhashan2026flahax,
  author  = {Al Khashan, Rafat A.},
  title   = {FlahaX: fertilizer salt selection for a fixed crop formula},
  year    = {2026},
  version = {0.3.1},
  url     = {https://pypi.org/project/flahax/},
  license = {Flaha Free Use License}
}
```

GitHub reads [`CITATION.cff`](https://github.com/rafatahmed/Flahax/blob/main/CITATION.cff) for the “Cite this repository” button. That file carries the same record.

## Documentation

Runnable examples for the current checkout are in `examples/`. From the repository
root, set `PYTHONPATH=src` and run `python -m examples.run_all --output build/my-examples`
to generate HTML, JSON and Markdown capability reports. See `examples/README.md`
for individual scenarios and the distinction between pepper inputs and synthetic evidence.

Unreleased development: `docs/water-to-delivery.md` in this checkout
separates crop targets, source-water contributions and incidental nutrients,
and documents calculated-pH and standard nitric/phosphoric candidate planning. These additions
are not included in the published 0.3.0 artifacts.

Start with the [0.3.1 preparation manual](src/flahax/data/USER_GUIDE.md) for installation, tested examples, units, chemistry, pH/delivery planning, troubleshooting and upgrades. It ships inside the wheel and source distribution and can be read offline with `importlib.resources`. The [documentation index](docs/index.md) separates user guidance, scientific evidence, contributor tools and historical notes.

| Document | Contents |
|---|---|
| [docs/usage.md](https://github.com/rafatahmed/Flahax/blob/main/docs/usage.md) | Library call, command line, inputs, and result fields |
| [docs/method.md](https://github.com/rafatahmed/Flahax/blob/main/docs/method.md) | ppm equation, solver, library file, and the pepper proof |
| [INTEGRATION.md](https://github.com/rafatahmed/Flahax/blob/main/INTEGRATION.md) | Package consumer boundary; integration owned by the separate FlahaFAST project |
| [docs/delivery-control-design.md](https://github.com/rafatahmed/Flahax/blob/main/docs/delivery-control-design.md) | Technical frame for future stock tanks, pH, and dosing control |
| [docs/implementation-roadmap.md](https://github.com/rafatahmed/Flahax/blob/main/docs/implementation-roadmap.md) | Trackable delivery-system implementation plan and acceptance gates |
| [docs/delivery-contracts.md](https://github.com/rafatahmed/Flahax/blob/main/docs/delivery-contracts.md) | P0 versioned delivery-planning input contracts and audit records |
| [docs/delivery-quantities.md](https://github.com/rafatahmed/Flahax/blob/main/docs/delivery-quantities.md) | P1 unit-safe batch adaptation and reagent nutrient contributions |
| [docs/stock-planning.md](https://github.com/rafatahmed/Flahax/blob/main/docs/stock-planning.md) | P2 conservative stock-tank planning and bench-validation protocol |
| [docs/ph-planning.md](https://github.com/rafatahmed/Flahax/blob/main/docs/ph-planning.md) | P3 titration-bounded pH planning and mandatory verification |
| [docs/reference-fixtures.md](https://github.com/rafatahmed/Flahax/blob/main/docs/reference-fixtures.md) | Dependency-free PHREEQC golden-fixture verification baseline |
| [docs/equilibrium-kernel.md](https://github.com/rafatahmed/Flahax/blob/main/docs/equilibrium-kernel.md) | First internal activity/speciation kernel verified against PHREEQC |
| [docs/full-fertilizer-chemistry.md](https://github.com/rafatahmed/Flahax/blob/main/docs/full-fertilizer-chemistry.md) | Current mixed chemistry coverage plus explicitly historical development notes |
| [docs/fertilizer-equilibrium-model.md](https://github.com/rafatahmed/Flahax/blob/main/docs/fertilizer-equilibrium-model.md) | Unified macro/trace equilibrium, PHREEQC evidence and frozen catalogue boundary |
| [docs/release-evidence.md](https://github.com/rafatahmed/Flahax/blob/main/docs/release-evidence.md) | Automated delivery-planner evidence, explicit scientific gates, and release boundary |
| [docs/package-verification.md](https://github.com/rafatahmed/Flahax/blob/main/docs/package-verification.md) | Clean wheel/sdist verification, pinned live reference tooling, and runnable equilibrium-delivery API example |
| [docs/computational-review.md](https://github.com/rafatahmed/Flahax/blob/main/docs/computational-review.md) | Owner-amended G6 computational assessment, named assessor and limits of acceptance |
| [docs/chemistry-coverage-matrix.md](https://github.com/rafatahmed/Flahax/blob/main/docs/chemistry-coverage-matrix.md) | Exact aqueous/phase coverage, naming aliases and source-backed definitions |
| [docs/publishing.md](https://github.com/rafatahmed/Flahax/blob/main/docs/publishing.md) | Building and releasing a new version |
| [docs/release-readiness.md](https://github.com/rafatahmed/Flahax/blob/main/docs/release-readiness.md) | Cleanup findings, publication status and outstanding verification |

From a checkout, the tests are:

```powershell
$env:PYTHONPATH = 'src'
py -m unittest discover -s tests -t .
```

For required live-reference verification on Windows, provision the pinned external tool and fail rather than skip if unavailable:

```powershell
./tools/provision_phreeqc.ps1
$env:FLAHAX_REQUIRE_PHREEQC = '1'
$env:PYTHONPATH = 'src'
py -3.13 -m unittest discover -s tests -t .
py -m compileall -q src tools
git diff --check
```

For isolated distribution checks, use a development virtual environment with `build` installed and run `python tools/verify_distribution.py`. It creates temporary wheel/sdist installations and writes `build/distribution-verification.json`; nothing is published. Without PHREEQC, ordinary runs still execute checked-in golden regressions but may skip live replay.

## Core formulation scope

This version returns grams for one litre of working solution. A salt is dosed from the shipped library only when its assay uses known ions and its formula does not rule the assay out. Default recipes leave out carbonate salts, and they leave out sodium and chloride unless the formula asks for that ion or the caller allows it. The result reports whether every requested ion landed inside 1%, plus warnings.

The core `recommend` and no-argument CLI contract does not split tanks, adjust pH, price the mix, or apply a concentration factor. Separate planning APIs and explicit planning subcommands provide the bounded capabilities documented above. They do not physically adjust pH, execute dosing commands or write to the FlahaFAST database.

## License

Use of FlahaX is free of charge, including commercial use, under the [Flaha Free Use License](https://github.com/rafatahmed/Flahax/blob/main/LICENSE). That license permits installation and running of an official copy. Modification, forking, republishing, and giving copies to anyone else require permission from the copyright holder. The license is a proprietary free-use license.
