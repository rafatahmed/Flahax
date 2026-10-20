# Competitor comparison

**Measured snapshot: 2026-10-21-competitors-ed568c5.** One run on one Windows
laptop, at FlahaX commit `ed568c5`. Every tool is pinned. Failures, refusals and
results unfavourable to FlahaX are retained. This is a comparison of software on
shared inputs, not physical validation of any nutrient solution.

| Download | Contents |
|---|---|
| [evidence.zip](../_static/benchmarks/2026-10-21-competitors-ed568c5/evidence.zip) | Everything below plus checksums; SHA-256 `046c39ccf6d0a6d62b98df01fce2913de31fd71f0e0b2091ed1b6b587be19698` |
| [formulation.json](../_static/benchmarks/2026-10-21-competitors-ed568c5/formulation.json) | Per-recipe doses, scores and incidental ions for every engine |
| [chemistry.json](../_static/benchmarks/2026-10-21-competitors-ed568c5/chemistry.json) | Live PHREEQC replay and FlahaX checks per fixture |
| [ec.json](../_static/benchmarks/2026-10-21-competitors-ed568c5/ec.json) | EC25 per standard and per recipe for every tool |
| [environment.json](../_static/benchmarks/2026-10-21-competitors-ed568c5/environment.json) | Interpreter, platform and the full package list |

The harness, its protocol and the run commands are in `tools/competitors/`
in the repository (`benchmarks/competitors/` at the measured commit). Timings are the best of three calls on one machine; compare
them only within this page.

## Tools

| Tool | Pin | Used for |
|---|---|---|
| Horticalc | v0.6.7, commit `db4e68c` (GPL-3.0-or-later) | Formulation, as shipped and aligned; EC |
| PHREEQC through PhreeqPython | PhreeqPython 1.6.2 (embedded IPhreeqc) | Chemistry reference; EC as specific conductance |
| pyEQL | 1.7.0 | EC |
| Irriblend-DSW method | Independent linear program after Gallego-Elvira et al. (2021) | Formulation baseline. Not the authors' code: their repository declares no licence |

pyfarm-nutrients is not included. It calibrates EC heuristically and does not
formulate recipes.

## Formulation

Every engine received the same 30-product catalogue (products with an assay
conflict excluded), the 26 shipped formulas, and two waters (no nutrients; 20 mg/L
calcium), giving 52 recipes. The Benchmark v1 evaluator re-scores every returned
recipe from catalogue assays, so no engine's own reporting enters a score. A
target passes within max(0.01 mg/L, 1 %).

A recipe can meet every target and still be unusable. The **acceptable** column
also requires that ions nobody asked for stay within agronomic limits:
- chloride and sodium each at most 3 mmol/L, the raw-water limits for open
  systems in De Kreij, Voogt and Baas (2003);
- ammonium N at most the smaller of 10 % of total N and 1.5 mmol/L;
- no micronutrient above twice its target.

| Engine | Recipes meeting every target | Acceptable | Targets passing (of 636) | Max incidental Cl (mg/L) | Max incidental NH4-N (mg/L) | Worst micronutrient ratio | Median time |
|---|---:|---:|---:|---:|---:|---:|---:|
| FlahaX `recommend`, Cl ceiling 3 mmol/L | 41 | **41** | 598 | 106.35 | 18.0 | 1.01 | 56.5 ms |
| FlahaX `recommend` (default, no chloride) | 34 | 34 | 571 | 0 | 19.1 | 1.01 | 60.1 ms |
| Irriblend method (LP) | 48 | 34 | 630 | 315.8 | 88.5 | 1.00 | 1.5 ms |
| FlahaX single fit (`solve_weights`) | 23 | 23 | 557 | 9.9 | 18.4 | 1.01 | 3.5 ms |
| Horticalc aligned | 47 | 7 | 613 | 707.6 | 281.8 | 330 | 3.4 ms |
| Horticalc as shipped | 0 | 0 | 522 | 707.6 | 46.6 | 1.00 | 4.5 ms |

What the table shows:
- Engines that chase every target exactly get there by adding ions nobody asked
  for. The Irriblend-method LP meets 48 recipes, but 14 of them exceed a limit:
  8 on ammonium, 4 on chloride and 2 on both.
- Horticalc aligned meets 47 recipes but only 7 are acceptable. Its worst case
  (Pepper, 20 mg/L calcium water) doses copper at 330 times the target.
- FlahaX does not use chloride unless asked. With a 3 mmol/L chloride ceiling it
  has the most acceptable recipes (41).
- 6 of FlahaX's 11 misses are on the three formulas whose target cations and
  anions differ by more than 10 % (Pepper −39 %, Tomato Stage 3 +29 %, Generic
  Grow −17 %). `recommend()` reports this through `targetIonBalance` and each
  miss through `unmetTargets`.
- Horticalc's default configuration targets total N (`n_total_only`) and leaves
  sulfur out of the objective, so as shipped it cannot meet per-form N and S
  targets. "Aligned" sets `n_forms_only` and enables sulfur.
- The salt-assay translation into Horticalc's oxide convention reproduces the
  catalogue to 3.6e-16 relative.

Timing compares like with like. One FlahaX fit (3.5 ms) and one Horticalc fit
(3.4–4.5 ms) take about the same time. The `recommend()` pipeline (57–60 ms) does
more: incidental-ion limits, simplification and miss diagnosis.

## Chemistry against live PHREEQC

Each PHREEQC golden fixture's own input was run through PhreeqPython on the
pinned `minteq.v4.dat` (SHA-256 `ab0a8f7c…5ae7`), merged with the FlahaX chelate
and phase extensions (merged SHA-256 `cbd26857…`). The database is reloaded for
every fixture.

- **Replay.** All 21 live runs match the stored PHREEQC 3.8.6 rows. The largest
  difference is 1.9e-9 (gypsum pH); everything else is within 9e-12.
- **FlahaX.** FlahaX passes all 21 fixtures: 1,534 quantity checks under the
  Benchmark v1 tolerances.
- **Speed.** FlahaX is faster than PHREEQC through PhreeqPython on 14 of the 21
  fixtures (median 1.2 ms vs 1.6 ms). It is slower on the three chelate-rich
  mixtures:

| Fixture | PHREEQC | FlahaX |
|---|---:|---:|
| Mixed products | 4.1 ms | 51.9 ms |
| Mixed products, nitric acid to pH 6 | 3.9 ms | 54.5 ms |
| Mixed products with phases | 13.2 ms | 55.7 ms |

A cold-start solve of these mixtures still needs about 68 Newton iterations.

## EC

### Accuracy against primary standards

The reference is the IUPAC molality-based primary standards of electrolytic
conductivity: KCl at 25 °C (Pratt, Koch, Wu and Berezansky 2001, *Pure Appl.
Chem.* 73, 1783, Table 1). The transcription is checked in the test suite against
the paper's own polynomial (Table 2). These replace the per-litre commercial
standard values (1413 and 12 880 µS/cm), for which no primary source was found.

| KCl | IUPAC (µS/cm) | FlahaX | Horticalc | PHREEQC | pyEQL |
|---|---:|---:|---:|---:|---:|
| 0.01 mol/kg | 1408.23 ± 0.42 | +1.08 % | +1.08 % | −0.86 % | −1.28 % |
| 0.1 mol/kg | 12 824.6 ± 5.1 | not supported | +1.17 % | −2.60 % | −0.12 % |
| 1.0 mol/kg | 108 620 ± 43 | not supported | +2.59 % | −12.8 % | −4.11 % |

- FlahaX and Horticalc agree to the digit at 0.01 mol/kg, because both use the
  McCleskey et al. (2012) ionic conductivities.
- FlahaX declines both stronger standards. Its activity model is limited to
  ionic strength 0.1, and the 0.1 mol/kg standard lands just above it once water
  self-ionisation is counted.
- PHREEQC here uses the `phreeqc.dat` bundled with PhreeqPython (SHA-256
  `6bb5ebc1…bdf5`), because `minteq.v4.dat` has no diffusion coefficients.

### Agreement on catalogue recipes

There is no measured EC for these solutions, so this part shows only how far the
tools disagree, not which is right. FlahaX's recommended recipe for each of the
26 formulas was given, in ion-free water, to every tool as the same
macronutrient totals. Phosphate was given as H2PO4- to the tools that do not
speciate. With no acid added, the charge-balance pH ranges from 2.9 to 9.3.

| Tool | Difference from FlahaX | Median time |
|---|---:|---:|
| PHREEQC | −3.5 % to +0.3 % | 0.33 ms |
| Horticalc | −11.2 % to +17.2 % | 0.03 ms |
| pyEQL | −11.0 % to +16.9 % | 230 ms |
| FlahaX (calculated pH) | — | 31 ms |

FlahaX and PHREEQC both speciate, including ion pairs such as CaSO4 and MgSO4,
and they agree within 3.5 %. The two tools that work from free-ion totals differ
in both directions, by up to 17 %. Micronutrients and chelates were left out
because not every tool has them; their share of FlahaX's full-recipe EC reaches
7.6 % for one formula and is recorded per recipe.

## What this page does not show

- Physical accuracy on fertilizer mixtures: no measured EC or pH of these
  recipes is included.
- Speed on other machines. The timings are best of three on one laptop.
- The Irriblend-DSW notebook itself: only an independent implementation of its
  published method.
