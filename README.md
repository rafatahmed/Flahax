# FlahaX

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/rafatahmed/Flahax/main/docs/site/_static/brand/v2/flahax-banner-white.png">
  <img src="https://raw.githubusercontent.com/rafatahmed/Flahax/main/docs/site/_static/brand/v2/flahax-banner-color.png" alt="FlahaX — water and nutrients become chemistry calculations and traceable plans, with units, model identifiers and sources." width="100%">
</picture>

**Plant-nutrient chemistry engine in Python: fertilizer formulation, aqueous
equilibrium chemistry and auditable delivery planning.**

[![PyPI](https://img.shields.io/pypi/v/flahax)](https://pypi.org/project/flahax/)
[![Python](https://img.shields.io/pypi/pyversions/flahax)](https://pypi.org/project/flahax/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](https://github.com/rafatahmed/Flahax/blob/main/LICENSE)
[![Tests](https://github.com/rafatahmed/Flahax/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/rafatahmed/Flahax/actions/workflows/test.yml)
[![Documentation](https://readthedocs.org/projects/flahax/badge/?version=latest)](https://flahax.readthedocs.io/en/latest/)
[![codecov](https://codecov.io/gh/rafatahmed/Flahax/branch/main/graph/badge.svg)](https://codecov.io/gh/rafatahmed/Flahax)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23605678.svg)](https://doi.org/10.5281/zenodo.23605678)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/flahax?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/flahax)

FlahaX turns a crop's nutrient formula and the grower's actual water into a fertilizer recipe,
then checks what that recipe does in solution: which ions pair up, whether anything
precipitates, what the pH will be, how much acid reaches a target pH, and how the recipe splits
into stock tanks and injector flows. Every plan carries its units, model identifiers and source
hashes, so a result can be reviewed and reproduced.

To our knowledge, FlahaX is the first Python package to unite fertilizer formulation,
fertilizer-specific aqueous equilibrium chemistry and auditable delivery planning in one
dependency-free library. Equilibrium speciation, saturation indices and acid titration
cases are checked against pinned PHREEQC 3.8.6; that evidence does not cover NNLS salt
selection, crop-formula nitrogen semantics or measured EC accuracy.

**Who it is for**

- **Growers and agronomists**: `flahax mix` asks five questions and gives tank A, tank B and the
  acid, with no code.
- **Consultants and researchers**: reproducible nutrient-solution chemistry with stated validity
  limits, against real water analyses and real commercial products.
- **Developers**: a tested, dependency-free engine for nutrition and fertigation software.

For changes from published recipes to this development checkout, see the
[migration guide](https://flahax.readthedocs.io/en/latest/start/migration.html).
Recalculate and review saved results; acceptance does not transfer to changed inputs or sources.

## Installation

Python 3.11 or newer. There are no third-party runtime dependencies.

```bash
python -m pip install flahax==0.6.0
```

Pin the version for reproducible work; `python -m pip install flahax` installs the latest
release. To upgrade, and to check what is installed:

```bash
python -m pip install --upgrade flahax
flahax --version
```

One version lives in each Python environment; to keep an older one for comparison, install it in
its own virtual environment.

To try unreleased changes from GitHub, reinstall rather than upgrade: between releases every
commit on `main` has the same development version, so `--upgrade` can keep the files you already
have (#134):

```bash
python -m pip install --force-reinstall --no-deps "git+https://github.com/rafatahmed/Flahax.git@main"
```

## Quick start

### Growers and agronomists: `flahax mix`

`flahax mix` asks five things in order: tank sizes and injection ratio, the water analysis as
printed by the lab, the crop formula, the fertilizers you have, and the target pH. It shows what
to weigh into tank A and tank B and how much acid goes in the acid container, writes a batch
sheet, and saves the answers so the next batch is one command:

```bash
flahax mix                          # first time: answer the five steps
flahax mix sessions/my-tomato       # next time: no questions
```

In a terminal it opens full screen: arrow keys and Enter choose, typing filters a long list,
Space ticks your fertilizers, and the result has three views (Tanks, Nutrients, Notes) switched
with Tab. `flahax mix --plain` asks line by line instead, and scripts and pipes get the
line-by-line mode automatically. See
[For growers and agronomists](https://flahax.readthedocs.io/en/latest/growers.html).

### One command: `flahax batch`

The same from files, for scripts:

```bash
flahax batch --formula "Tomato (Howard Resh)" --water ro --ph 5.8 --acid HNO3:0.60:1.37 --output tomato
```

It writes `batch-sheet.html`, `report.html` and `summary.json`. `flahax batch --help` lists every
option, including a measured water analysis and `--water-share` for blending it with RO water.

### Python

Select salts for a crop formula, with 20 mg/L of calcium already in the water:

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

`result["salts"]` lists each chosen salt with grams per litre of the solution the plant receives.
`result["rows"]` gives each element's target, final concentration (mg/L) and percentage
difference. Element keys are `N_NO3`, `N_NH4`, `P`, `K`, `Ca`, `Mg`, `S`, `Fe`, `Mn`, `Zn`, `B`,
`Cu` and `Mo`.

## Commands

| Command | What it does |
|---|---|
| `flahax mix` | Five questions to tank A, tank B and the acid, with a batch sheet (growers, agronomists) |
| `flahax batch` | The same from files in one command, for scripts |
| `flahax` (or `flahax recommend`) | Reads a JSON request (`salts`, `targets`, `water`) on stdin and writes a recipe |
| `flahax workflow` | Plans a full workflow from a JSON request, or with `--interactive` |
| `flahax ec` | Screens the EC of supported products before acid |
| `flahax size` | Sizes injector channel volumes and flows |

`flahax --help` shows every command with examples. Commands plan; they never operate pumps,
valves or other hardware.
`recommend` accepts the Python API's explicit `maximum_concentrations` and other
fit options; unknown JSON fields are rejected. Exit 0 means a calculation was
returned, not that it is feasible or physically validated. `batch` and `mix` use
exit 3 for a blocked result. Always inspect the returned qualifications and limits.


## What it does

| Layer | Capability | Boundary |
|---|---|---|
| Formulation | Chooses salts and grams from the full shipped library to meet a fixed crop formula after subtracting the source water | Non-negative least squares; the formula is not altered |
| Equilibrium chemistry | One mixed aqueous model for all 32 catalogue products: 197 aqueous species, 28 solid phases, ion pairs, chelates and saturation indices | 25 °C, Davies activities up to ionic strength 0.1 mol/kg, fixed oxidation states, closed inorganic carbon |
| pH and acid | Calculated initial pH; nitric-acid dose to a target pH; standard workflow with nitric and phosphoric acid, using supplied assay and density | An initial dose estimate; measure after mixing |
| Delivery planning | Stock-tank grouping with compatibility and solubility checks, reagent volumes, pump and injector flow sizing, composed delivery plans | Uses caller-supplied product, compatibility and equipment records; no equipment model selection |
| Conductivity | Approximate EC screening for supported products; EC from a measured calibration profile | Dilute, pre-acid screening with unknown accuracy; no validated concentrated-stock model yet |
| Audit trail | Explicit units (g/L of final solution versus g/kg water), model identifiers, source hashes, `needs_input` instead of guessed values | Plans are reviewable records, not operating authorizations |

## Documentation

| Document | For |
|---|---|
| [Documentation site](https://flahax.readthedocs.io/) | Guides for growers, agronomists and developers |
| [User manual](https://github.com/rafatahmed/Flahax/blob/main/src/flahax/data/USER_GUIDE.md) | Installation, tested examples, units, chemistry, pH, delivery planning and troubleshooting |
| [API reference](https://github.com/rafatahmed/Flahax/blob/main/src/flahax/data/API_REFERENCE.md) | Every public function and result record, with signatures |
| [Chemistry model](https://github.com/rafatahmed/Flahax/blob/main/docs/fertilizer-equilibrium-model.md) | Equilibrium model, PHREEQC evidence and boundaries |
| [Formulation method](https://github.com/rafatahmed/Flahax/blob/main/docs/method.md) | The ppm equation, solver and worked pepper example |
| [Changelog](https://github.com/rafatahmed/Flahax/blob/main/CHANGELOG.md) | Changes by release |

The manual can also be read offline from an installed package through `importlib.resources`
(`flahax/data/USER_GUIDE.md`).

## Troubleshooting

| Problem | Fix |
|---|---|
| A feature is missing after installing from GitHub | Reinstall with `--force-reinstall --no-deps` (see Installation above) and check `flahax --version`. |
| `flahax` is not recognised as a command | Run `python -m flahax`, or add the folder pip names in its "user installation" warning to your PATH. |
| `flahax mix` asks line by line instead of full screen | Run it in Windows Terminal, PowerShell, `cmd` or a Linux or macOS terminal; an editor's output panel or Git Bash is not a full-screen console. |
| An error code such as `invalid_json` or `charge_imbalance_exceeded` | Every code is explained in the manual's [error reference](https://github.com/rafatahmed/Flahax/blob/main/src/flahax/data/USER_GUIDE.md#error-code-reference). |

More in the manual's
[troubleshooting section](https://github.com/rafatahmed/Flahax/blob/main/src/flahax/data/USER_GUIDE.md#8-errors-and-troubleshooting).
If something still looks wrong, [open an issue](https://github.com/rafatahmed/Flahax/issues) with
`flahax --version` and the command you ran.

## Verification and limits

The [Benchmark v1 protocol](https://flahax.readthedocs.io/en/latest/evidence/benchmark-v1.html)
separates formulation fit, numerical chemistry, runtime and memory, and physical validation; the
[measured results](https://flahax.readthedocs.io/en/latest/evidence/benchmark-results.html) come
with tables, charts, provenance and their limitations.

- The automated test suite includes live replay of every catalogue product, phase and acid
  equilibrium case against pinned PHREEQC 3.8.6 (USGS). That agreement is for the mixed
  aqueous model only; formulation fit, total-N catalogue policy and McCleskey EC are separate
  contracts and are not PHREEQC-verified.
- Hosted checks run on Python 3.11, 3.12, 3.13 and 3.14 on Linux, and on Windows and macOS,
  with clean wheel and source installations.
- Evidence is recorded per release in the
  [release evidence](https://github.com/rafatahmed/Flahax/blob/main/docs/release-evidence.md).

This is computational evidence. FlahaX has not been validated in the laboratory or in the field
(a [validation protocol](https://github.com/rafatahmed/Flahax/issues/41) is in draft), and its
owner's [computational assessment](https://github.com/rafatahmed/Flahax/blob/main/docs/computational-review.md)
is not an independent review. Results are calculations for planning, not dosing instructions:
measure pH and EC after mixing. No recipe, pH or EC value is an authorization to operate
equipment. Do not treat PHREEQC agreement as measured EC accuracy.

**Roadmap.** Broader numerical and input-boundary testing, stable consumer contracts, physical
validation, and a validated
[conductivity model](https://github.com/rafatahmed/Flahax/blob/main/docs/stock-conductivity-service-design.md)
for irrigation-strength solutions first and concentrated stock tanks second. See the
[development roadmap](https://github.com/rafatahmed/Flahax/blob/main/docs/development-roadmap.md).
FlahaX is developed as the chemistry engine for the FlahaFAST application; that integration is
not yet in place, and FlahaX stays a standalone package with its own releases.

## Contributing

Contributions are welcome. Read [CONTRIBUTING](https://github.com/rafatahmed/Flahax/blob/main/CONTRIBUTING.md)
for branch names, code style, the changelog format and the validation each change needs, and the
[code of conduct](https://github.com/rafatahmed/Flahax/blob/main/CODE_OF_CONDUCT.md). Report
security problems privately, as [SECURITY.md](https://github.com/rafatahmed/Flahax/blob/main/SECURITY.md)
explains.

From a source checkout:

```bash
python -m pip install -e .
python -m unittest discover -s tests -t .
```

Live PHREEQC replay and distribution verification are described in
[package verification](https://github.com/rafatahmed/Flahax/blob/main/docs/package-verification.md).

## Citation

Al Khashan, R. A. (2026). *FlahaX* (Version 0.6.0) [Computer software]. Zenodo.
https://doi.org/10.5281/zenodo.23605679

```bibtex
@software{alkhashan2026flahax,
  author  = {Al Khashan, Rafat A.},
  title   = {FlahaX: plant-nutrient chemistry engine for fertilizer formulation and delivery planning},
  year    = {2026},
  version = {0.6.0},
  doi     = {10.5281/zenodo.23605679},
  url     = {https://pypi.org/project/flahax/},
  license = {Apache-2.0}
}
```

To cite whichever version you used, the concept DOI [10.5281/zenodo.23605678](https://doi.org/10.5281/zenodo.23605678) always
resolves to the latest release. GitHub's "Cite this repository" button reads
[`CITATION.cff`](https://github.com/rafatahmed/Flahax/blob/main/CITATION.cff).

## Author and credits

FlahaX is written and maintained by Rafat A. Al Khashan
([ORCID 0009-0009-4692-4552](https://orcid.org/0009-0009-4692-4552),
rafat.khashan82@gmail.com) at Flaha Agri Tech.

It builds on published data, each value cited where it is used:
thermodynamic constants from USGS PHREEQC 3.8.6 (Parkhurst and Appelo 2013,
[doi:10.3133/tm6A43](https://doi.org/10.3133/tm6A43)), converted and extended
for FlahaX; conductivity from McCleskey et al. (2012) and Pethybridge et al.
(2006); stock solubility from the CRC Handbook of Chemistry and Physics, Yara
and the U.S. Coast Guard CHRIS database; supplier assays from Haifa,
Sigma-Aldrich and ChemicalBook; concentrate-tank rules from Yara; and crop
formulas from the authors named in the library. The full list, the
modifications and the USGS User Rights Notice are in
[`NOTICE`](https://github.com/rafatahmed/Flahax/blob/main/NOTICE); the
references are also in `CITATION.cff`.

## License

FlahaX is open source under the
[Apache License 2.0](https://github.com/rafatahmed/Flahax/blob/main/LICENSE).
You may use, modify and redistribute it for any purpose, including commercial
products and research. Redistributions must keep the copyright notice and the
[`NOTICE`](https://github.com/rafatahmed/Flahax/blob/main/NOTICE) file. If you
use FlahaX in published work, please cite it as shown above.

Releases up to and including 0.3.1 were published under the Flaha Free Use
License 1.0; later releases use Apache-2.0.
