# FlahaX

**Plant-nutrient chemistry engine in Python: fertilizer formulation, aqueous
equilibrium chemistry and auditable delivery planning.**

FlahaX turns a crop's nutrient formula and the grower's actual water into a
fertilizer recipe, then checks what that recipe does in solution: which ions
pair up, whether anything precipitates, what the pH will be, how much acid
reaches a target pH, and how the recipe splits into stock tanks and injector
flows. Every plan carries its units, model identifiers and source hashes, so
a result can be reviewed and reproduced.

## What sets it apart

- **Verified against PHREEQC.** Every catalogue product, phase and acid case
  is replayed live against pinned PHREEQC 3.8.6 (USGS).
- **Traceable materials.** Material identity, grade, lot and nutrient band
  are carried through the calculation.
- **Every result with its source and stated limit.** Explicit units, model
  identifiers, source hashes and `needs_input` instead of guessed values.
  Plans are reviewable records, not operating authorizations.

FlahaX has no third-party runtime dependencies. The evidence is
computational: it has not been validated in the laboratory or in the field.

## Install

Python 3.11 or newer.

```bash
python -m pip install flahax
```

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

## Where to go next

- **Developers:** start with the [user manual](guide/manual.md)
  and the [API reference](api/reference.md).
- **Growers and agronomists:** read the
  [guide for growers and agronomists](growers.md).

```{toctree}
:caption: User guide
:hidden:

guide/manual
guide/usage
guide/water-to-delivery
guide/site-planning
guide/source-sheet-review
guide/delivery-quantities
guide/delivery-contracts
guide/stock-planning
guide/ph-planning
guide/conductivity
guide/materials
```

```{toctree}
:caption: For growers and agronomists
:hidden:

growers
```

```{toctree}
:caption: API reference
:hidden:

api/reference
api/package-verification
```

```{toctree}
:caption: Models and chemistry
:hidden:

models/method
models/fertilizer-equilibrium-model
models/equilibrium-kernel
models/full-fertilizer-chemistry
models/chemistry-coverage-matrix
models/reference-fixtures
models/flahax-chelate-thermodynamic-profile
```

```{toctree}
:caption: Evidence and audits
:hidden:

evidence/computational-review
evidence/release-evidence
evidence/audit/README
evidence/audit/2026-10-17-flahax-vs-horticalc/report
evidence/audit/2026-10-17-flahax-vs-horticalc/review
evidence/audit/2026-10-18-materials-identity/review
```

```{toctree}
:caption: Changelog
:hidden:

changelog
```
