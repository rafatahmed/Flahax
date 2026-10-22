# Competitor comparison (#40)

Development-only harness that compares FlahaX with other open tools on the same
inputs. None of these packages is a FlahaX runtime dependency.

## Tools and pins

| Tool | Version | Role | Licence |
|---|---|---|---|
| Horticalc | tag v0.6.7, commit db4e68c76639df2920f43be06c77dd4c16498863 | formulation (as shipped and aligned), EC | GPL-3.0-or-later |
| PhreeqPython (embedded IPhreeqc) | 1.6.2 | chemistry reference, EC (specific conductance) | Apache-2.0 |
| pyEQL | 1.7.0 | EC | LGPL-3.0-or-later |
| Irriblend-DSW | commit a046d5c (code 197d650), `code/irriblend_dsw_funs.py` SHA-256 2a3c06f8…732e, unmodified | formulation: the authors' optimiser `ferti_eco_min` | MIT, Copyright (c) 2026 irriblend-dsw |
| Irriblend-DSW method | independent LP after Gallego-Elvira et al. (2021) | formulation baseline beside the authors' code | FlahaX's own code (Apache-2.0) |

pyfarm-nutrients is excluded: it calibrates EC heuristically and is not a formulation engine.

Irriblend-DSW is Gallego-Elvira, B., Reca, J., Martin-Gorriz, B., Maestre-Valero, J. F. and
Martinez-Alvarez, V. (2021), *Agricultural Water Management* 255, 107012,
doi:10.1016/j.agwat.2021.107012, published at https://github.com/irriblend-dsw/irriblend-dsw-v1.
The authors added the MIT licence on 2026-10-20 at our request; nothing of theirs is
redistributed here. Its Colab notebook mounts Google Drive, so `irriblend_adapter.py`
imports the unmodified module (hash-checked) and calls its optimiser directly; through the
same calls it reproduces all 97 water blends of the authors' two published case-study
outputs exactly. The adapter's docstring records the catalogue translation and the neutral
settings (equal prices, non-binding EC cap, residual HCO3- 0).

## Tracks

**Formulation** (`formulation_track.py`). Every engine gets the nutrient catalogue (30 products at the published run; pH reagents excluded)
(products with an assay conflict excluded), the 26 shipped formulas and two waters.
Each returned recipe is re-scored by the Benchmark v1 evaluator (catalogue assays,
max(0.01 mg/L, 1 %) per target), so no engine's own reporting enters the score. A
second scoreboard, *acceptable*, also requires that incidental ions stay within
agronomic limits:
- Cl ≤ 3 mmol/L and Na ≤ 3 mmol/L (De Kreij, Voogt & Baas 2003);
- NH4-N ≤ min(10 % of N, 1.5 mmol/L);
- no micronutrient above 2× its target.

Timing compares like with like: one FlahaX fit against one Horticalc fit, with the
`recommend()` pipeline reported separately.

Irriblend-DSW models no micronutrients, so every engine is also scored on macronutrients
only (`whole_recipes_passing_macro`, `macro_targets_passing`).

**Chemistry** (`chemistry_track.py`). Each PHREEQC golden fixture's own input runs
through PhreeqPython on the pinned minteq.v4.dat (SHA-256 checked) merged with the
FlahaX extensions. Two checks follow:
- **Replay:** the live rows are checked against the stored PHREEQC 3.8.6 rows. Log
  quantities are compared absolutely; molalities relatively above 1e-20; the charge
  and percent-error residuals are not compared.
- **FlahaX:** FlahaX is solved at the live prescribed pH and scored with Benchmark
  v1's `evaluate_chemistry`.

The database is reloaded for every fixture, because IPhreeqc keeps species and phase
definitions between inputs.

**EC** (`ec_track.py`). Accuracy is scored against the IUPAC molality-based KCl
primary standards: Pratt et al. 2001, transcribed in
`tests/fixtures/conductivity/iupac2001_kcl_table1.json` and checked against that
paper's own polynomial. The catalogue recipes have no measured EC, so they are
compared for agreement only. Every tool gets the same macronutrient totals.
PHREEQC conductivity uses PhreeqPython's bundled phreeqc.dat, because minteq.v4.dat
has no diffusion coefficients.

## Run

```bash
python -m venv competitors-venv
competitors-venv/Scripts/python -m pip install -r tools/competitors/requirements.txt -c tools/competitors/constraints.txt
git clone --branch v0.6.7 https://github.com/onethree7/Horticalc.git horticalc
git clone https://github.com/irriblend-dsw/irriblend-dsw-v1.git irriblend
git -C irriblend checkout a046d5c
IRRIBLEND_DSW_CODE=irriblend/code PYTHONPATH="src;.;horticalc/src" competitors-venv/Scripts/python -m tools.competitors.formulation_track --output out/formulation.json
PYTHONPATH="src;." competitors-venv/Scripts/python -m tools.competitors.chemistry_track --database path/to/minteq.v4.dat --output out/chemistry.json
PYTHONPATH="src;.;horticalc/src" competitors-venv/Scripts/python -m tools.competitors.ec_track --output out/ec.json
```

Use `:` instead of `;` in PYTHONPATH on Linux and macOS. minteq.v4.dat must match
SHA-256 ab0a8f7c…5ae7: upstream phreeqc3-database commit
26398a442446dc31463fb08c3d1cd06df609b633, with CRLF line endings.

Timings are best of three on one machine. Compare them only within a single run.
