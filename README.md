# FlahaX

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/site/_static/brand/v2/flahax-banner-white.png">
  <img src="docs/site/_static/brand/v2/flahax-banner-color.png" alt="FlahaX — water and nutrients become chemistry calculations and traceable plans, with units, model identifiers and sources." width="100%">
</picture>

**Plant-nutrient chemistry engine in Python: fertilizer formulation, aqueous
equilibrium chemistry and auditable delivery planning.**

[![PyPI](https://img.shields.io/pypi/v/flahax)](https://pypi.org/project/flahax/)
[![Python](https://img.shields.io/pypi/pyversions/flahax)](https://pypi.org/project/flahax/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](https://github.com/rafatahmed/Flahax/blob/main/LICENSE)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/flahax?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/flahax)

FlahaX turns a crop's nutrient formula and the grower's actual water into a
fertilizer recipe, then checks what that recipe does in solution: which ions
pair up, whether anything precipitates, what the pH will be, how much acid
reaches a target pH, and how the recipe splits into stock tanks and injector
flows. Every plan carries its units, model identifiers and source hashes, so
a result can be reviewed and reproduced.

To our knowledge, FlahaX is the first Python package to unite fertilizer
formulation, fertilizer-specific aqueous equilibrium chemistry and auditable
delivery planning in one dependency-free library, verified against PHREEQC.

**Who it is for**

- **Researchers** who need reproducible nutrient-solution chemistry with
  stated validity limits.
- **Agronomists and consultants** who design recipes against real water
  analyses and real commercial products.
- **Growers** with technical support, through the interactive command line.
- **Developers** building nutrition and fertigation software on a tested,
  dependency-free engine.

**FlahaX and FlahaFAST.** FlahaX is developed as the chemistry engine for
the FlahaFAST application, where it is planned to provide formulation, pH
and conductivity planning. That integration is not yet in place: FlahaFAST
does not currently import FlahaX, and FlahaX stays a standalone package
with its own releases.

## Install

Python 3.11 or newer. There are no third-party runtime dependencies.

```bash
python -m pip install flahax==0.4.0
```

Pin the version for reproducible work. `python -m pip install flahax`
installs the latest release.

## Quick start

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

`result["salts"]` lists each chosen salt with grams per litre of the
solution the plant receives. `result["rows"]` gives each element's target,
final concentration (mg/L) and percentage difference. Element keys are
`N_NO3`, `N_NH4`, `P`, `K`, `Ca`, `Mg`, `S`, `Fe`, `Mn`, `Zn`, `B`, `Cu`
and `Mo`.

## Command line

```bash
flahax --help
flahax workflow --interactive   # water + crop targets -> recipe, pH and acid plan
flahax ec --interactive         # approximate EC screening for supported products
flahax size --interactive       # stock-channel volume and injector flow sizing
```

With no subcommand, `flahax` reads one JSON object (`salts`, `targets`,
`water`) on standard input and writes the recommendation as JSON. Commands
plan; they never operate pumps, valves or other hardware.

## What it does

| Layer | Capability | Boundary |
|---|---|---|
| Formulation | Chooses salts and grams from the full shipped library to meet a fixed crop formula after subtracting the source water | Non-negative least squares; the formula is not altered |
| Equilibrium chemistry | One mixed aqueous model for all 28 catalogue products: 197 aqueous species, 28 solid phases, ion pairs, chelates and saturation indices | 25 °C, Davies activities up to ionic strength 0.1 mol/kg, fixed oxidation states, closed inorganic carbon |
| pH and acid | Calculated initial pH; nitric-acid dose to a target pH; standard workflow with nitric and phosphoric acid, using supplied assay and density | An initial dose estimate; measure after mixing |
| Delivery planning | Stock-tank grouping with compatibility and solubility checks, reagent volumes, pump and injector flow sizing, composed delivery plans | Uses caller-supplied product, compatibility and equipment records; no equipment model selection |
| Conductivity | Approximate EC screening for supported products; EC from a measured calibration profile | Dilute, pre-acid screening with unknown accuracy; no validated concentrated-stock model yet |
| Audit trail | Explicit units (g/L of final solution versus g/kg water), model identifiers, source hashes, `needs_input` instead of guessed values | Plans are reviewable records, not operating authorizations |

## Verification

The [Benchmark v1 protocol](docs/site/evidence/benchmark-v1.md) separates
formulation fit, numerical chemistry, runtime/memory measurements, and physical
validation. Its reproducible reports include input hashes and failed cases;
timings are informational, and physical validation remains separate.
See the [measured results and downloadable evidence](docs/site/evidence/benchmark-results.md)
for tables, charts, provenance, and retained limitations.

- 153 automated tests, including live replay of every catalogue product,
  phase and acid case against pinned PHREEQC 3.8.6 (USGS).
- Hosted checks on Python 3.11, 3.12 and 3.13, plus clean wheel and source
  installation checks.
- Evidence is versioned per release in the
  [release evidence](https://github.com/rafatahmed/Flahax/blob/main/docs/release-evidence.md).

This is computational evidence. FlahaX has not been validated in the
laboratory or in the field, and its owner's
[computational assessment](https://github.com/rafatahmed/Flahax/blob/main/docs/computational-review.md)
is not an independent review. No recipe, pH or EC value is an authorization
to operate equipment.

## Roadmap

Next work, in order: broader numerical and input-boundary testing, stable
consumer contracts, and a validated
[conductivity model](https://github.com/rafatahmed/Flahax/blob/main/docs/stock-conductivity-service-design.md)
covering irrigation-strength solutions first and concentrated stock tanks
second. See the
[development roadmap](https://github.com/rafatahmed/Flahax/blob/main/docs/development-roadmap.md)
and [current status](https://github.com/rafatahmed/Flahax/blob/main/docs/development-status.md).

## Documentation

| Document | For |
|---|---|
| [User manual](https://github.com/rafatahmed/Flahax/blob/main/src/flahax/data/USER_GUIDE.md) | Installation, eight tested examples, units, chemistry, pH and delivery planning; also ships inside the package |
| [API reference](https://github.com/rafatahmed/Flahax/blob/main/src/flahax/data/API_REFERENCE.md) | Every public function and result record, with signatures |
| [Site planning and CLI](https://github.com/rafatahmed/Flahax/blob/main/docs/site-planning.md) | Water, acid, EC and injection inputs |
| [Chemistry model](https://github.com/rafatahmed/Flahax/blob/main/docs/fertilizer-equilibrium-model.md) | Equilibrium model, PHREEQC evidence and boundaries |
| [Formulation method](https://github.com/rafatahmed/Flahax/blob/main/docs/method.md) | The ppm equation, solver and worked pepper example |
| [Documentation index](https://github.com/rafatahmed/Flahax/blob/main/docs/index.md) | All user, scientific and contributor documents |
| [Changelog](https://github.com/rafatahmed/Flahax/blob/main/CHANGELOG.md) | Changes by release |

The manual can be read offline from an installed package through
`importlib.resources` (`flahax/data/USER_GUIDE.md`).

## Development

From a source checkout:

```bash
python -m pip install -e .
PYTHONPATH=src python -m unittest discover -s tests -t .
```

Live PHREEQC replay, distribution verification and branch conventions are in
[package verification](https://github.com/rafatahmed/Flahax/blob/main/docs/package-verification.md)
and [CONTRIBUTING](https://github.com/rafatahmed/Flahax/blob/main/CONTRIBUTING.md).

## Citation

Al Khashan, R. A. (2026). *FlahaX* (Version 0.4.0) [Computer software].
https://pypi.org/project/flahax/

```bibtex
@software{alkhashan2026flahax,
  author  = {Al Khashan, Rafat A.},
  title   = {FlahaX: plant-nutrient chemistry engine for fertilizer formulation and delivery planning},
  year    = {2026},
  version = {0.4.0},
  url     = {https://pypi.org/project/flahax/},
  license = {Apache-2.0}
}
```

GitHub's "Cite this repository" button reads
[`CITATION.cff`](https://github.com/rafatahmed/Flahax/blob/main/CITATION.cff).

## License

FlahaX is open source under the
[Apache License 2.0](https://github.com/rafatahmed/Flahax/blob/main/LICENSE).
You may use, modify and redistribute it for any purpose, including commercial
products and research. Redistributions must keep the copyright notice and the
[`NOTICE`](https://github.com/rafatahmed/Flahax/blob/main/NOTICE) file. If you
use FlahaX in published work, please cite it as shown above.

Releases up to and including 0.3.1 were published under the Flaha Free Use
License 1.0; later releases use Apache-2.0.
