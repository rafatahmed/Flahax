# Competitor comparison

> Historical benchmark inputs include five presets retired under #202. Their
> inclusion tested numerical behavior; it did not validate crop recommendations.
> Raw captures are preserved. The current catalogue contains 21 formulas.


**Measured snapshot: 2026-10-22-competitors-1ade5b6.** One run on one Windows
laptop, at FlahaX commit `1ade5b6`. Every tool is pinned. Failures, refusals and
results unfavourable to FlahaX are retained. This is a comparison of software on
shared inputs, not physical validation of any nutrient solution.

| Download | Contents |
|---|---|
| [evidence.zip](../_static/benchmarks/2026-10-22-competitors-1ade5b6/evidence.zip) | Everything below plus checksums; SHA-256 `12c98e03c1468cde1c056353b5e097e438b3300898e4eec1742cf6173fd9f7c0` |
| [formulation.json](../_static/benchmarks/2026-10-22-competitors-1ade5b6/formulation.json) | Per-recipe doses, scores and incidental ions for every engine |
| [chemistry.json](../_static/benchmarks/2026-10-22-competitors-1ade5b6/chemistry.json) | Live PHREEQC replay and FlahaX checks per fixture |
| [ec.json](../_static/benchmarks/2026-10-22-competitors-1ade5b6/ec.json) | EC25 per standard and per recipe for every tool |
| [environment.json](../_static/benchmarks/2026-10-22-competitors-1ade5b6/environment.json) | Interpreter, platform and the full package list |

The harness, its protocol and the run commands are in `tools/competitors/` in
the repository. Timings are the best of three calls on one machine; compare
them only within this page. Every tool, PHREEQC included, ran three to four times
slower in this run than in the previous snapshot
([2026-10-21-competitors-ed568c5](../_static/benchmarks/2026-10-21-competitors-ed568c5/README.txt),
FlahaX `ed568c5`), so the machine was under more load. Every accuracy figure
that both snapshots measure is unchanged.

## Tools

| Tool | Pin | Used for |
|---|---|---|
| Horticalc | v0.6.7, commit `db4e68c` (GPL-3.0-or-later) | Formulation, as shipped and aligned; EC |
| PHREEQC through PhreeqPython | PhreeqPython 1.6.2 (embedded IPhreeqc) | Chemistry reference; EC as specific conductance |
| pyEQL | 1.7.0 | EC |
| Irriblend-DSW | commit `a046d5c` (code `197d650`), MIT, Copyright (c) 2026 irriblend-dsw | Formulation: the authors' fertiliser optimiser, unmodified |
| Irriblend-DSW method | Independent linear program after the same paper, in FlahaX's harness | Formulation baseline, kept beside the authors' code |

Irriblend-DSW is Gallego-Elvira, Reca, Martin-Gorriz, Maestre-Valero and
Martinez-Alvarez (2021), *Agricultural Water Management* 255, 107012,
doi:10.1016/j.agwat.2021.107012, with code at
[irriblend-dsw/irriblend-dsw-v1](https://github.com/irriblend-dsw/irriblend-dsw-v1).
Its authors added the MIT licence on 2026-10-20 so that it could be included;
the earlier snapshot could use only the independent baseline.

pyfarm-nutrients is not included. It calibrates EC heuristically and does not
formulate recipes.

## Formulation

Every engine received the same 29-product catalogue (pH reagents and products
with an assay conflict excluded), the 26 shipped formulas, and two waters (no
nutrients; 20 mg/L calcium), giving 52 recipes. The Benchmark v1 evaluator
re-scores every returned recipe from catalogue assays, so no engine's own
reporting enters a score. A target passes within max(0.01 mg/L, 1 %).

A recipe can meet every target and still be unusable. The **acceptable** column
also requires that ions nobody asked for stay within agronomic limits:
- chloride and sodium each at most 3 mmol/L, the raw-water limits for open
  systems in De Kreij, Voogt and Baas (2003);
- ammonium N at most the smaller of 10 % of total N and 1.5 mmol/L;
- no micronutrient above twice its target.

Irriblend-DSW models no micronutrients, so the **macronutrients only** column
scores every engine on N, P, K, Ca, Mg and S alone.

| Engine | Recipes returned | Meeting every target | Macronutrients only | Acceptable | Targets passing (of 636) | Max incidental Cl (mg/L) | Max incidental NH4-N (mg/L) | Worst micronutrient ratio | Median time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FlahaX `recommend`, Cl ceiling 3 mmol/L | 52 | 42 | 44 | **42** | 599 | 106.35 | 18.0 | 1.01 | 226 ms |
| FlahaX `recommend` (default, no chloride) | 52 | 34 | 36 | 34 | 571 | 0 | 19.1 | 1.01 | 178 ms |
| Irriblend-DSW method (LP) | 52 | 48 | 50 | 34 | 630 | 315.8 | 88.5 | 1.00 | 5.2 ms |
| FlahaX single fit (`solve_weights`) | 52 | 23 | 23 | 23 | 557 | 9.9 | 18.4 | 1.01 | 11.0 ms |
| Horticalc aligned | 52 | 47 | 50 | 4 | 613 | 1070.3 | 281.8 | 330 | 12.2 ms |
| Horticalc as shipped | 52 | 0 | 0 | 0 | 522 | 995.9 | 46.6 | 1.00 | 15.0 ms |
| Irriblend-DSW (authors' code) | 30 | 0 | 2 | 0 | 156 (of 368 scored) | 707.6 | 0 | — | 80.1 ms |

What the table shows:
- Engines that chase every target exactly get there by adding ions nobody asked
  for. The Irriblend-method LP meets 48 recipes, but 14 of them exceed a limit:
  8 on ammonium, 4 on chloride and 2 on both.
- Horticalc aligned meets 47 recipes but only 4 are acceptable. Its worst case
  (Pepper, 20 mg/L calcium water) doses copper at 330 times the target.
- FlahaX does not use chloride unless asked. With a 3 mmol/L chloride ceiling it
  has the most acceptable recipes (42).
- 6 of FlahaX's 10 misses are on the three formulas whose target cations and
  anions differ by more than 10 % (Pepper −39 %, Tomato Stage 3 +29 %, Generic
  Grow −17 %). `recommend()` reports this through `targetIonBalance` and each
  miss through `unmetTargets`.
- Horticalc's default configuration targets total N (`n_total_only`) and leaves
  sulfur out of the objective, so as shipped it cannot meet per-form N and S
  targets. "Aligned" sets `n_forms_only` and enables sulfur.
- The salt-assay translations reproduce the catalogue to 3.6e-16 relative for
  Horticalc's oxide convention and 1.6e-16 for Irriblend-DSW's mmol/g.

### Irriblend-DSW: what the authors' optimiser does on these inputs

Irriblend-DSW is a decision-support tool for blending desalinated and
conventional waters at the lowest cost. Its fertiliser step,
`ferti_eco_min`, minimises fertiliser cost (SciPy SLSQP, 0–3 g/L per product)
subject to:
- exact NO3-, NH4+, H2PO4-, K+ and residual HCO3-;
- Ca, Mg, SO4, Cl and Na at or above need;
- an EC cap.

The harness imports the authors' module unmodified (SHA-256 checked) and calls
that function, because the notebook around it needs Google Colab and Google
Drive. Through the same calls it reproduces all 97 water blends of the authors'
two published case-study outputs exactly.

The catalogue is written in the authors' convention:
- mmol/g, with phosphate as H2PO4-;
- an acid's H+ equals minus its anion, and dibasic phosphates carry +1 H+.

Fifteen products the model cannot represent are left out, each with the reason
recorded: micronutrient products, chelates, urea and potassium citrate. The
settings are neutral. The catalogue has no prices, so every product costs the
same and the objective becomes total grams. The EC cap is non-binding, because
no other engine applies one, and the residual HCO3- target is 0.

The scores follow from that design, not from a defect:
- **It returns 30 of the 52 recipes.** Its own filter rejects the other 22. In
  18 of those the formula has no ammonium target, so NH4+ must be exactly zero.
  That rules out the only calcium nitrate in the catalogue, which carries some
  ammonium.
- **Every returned recipe meets its N, P, K and S targets within tolerance.**
  All 30 macro misses are overshoots, Mg in 26 recipes and Ca in 4, which its
  lower-bound constraints allow. So only 2 recipes pass on macronutrients alone.
- **None passes every target,** because micronutrients are outside its scope.
- **Chloride reaches 708 mg/L.** Calcium and potassium chloride are cheap
  sources at equal prices, and the model sets no chloride upper bound.

With real fertiliser prices, other ideal-solution choices or its water-blend
search, the result would differ. This table measures one call of its optimiser
on the benchmark's fixed inputs, not the tool's intended use.

Timing compares like with like. One FlahaX fit (11.0 ms) and one Horticalc fit
(12.2–15.0 ms) take about the same time. The `recommend()` pipeline (178–226 ms)
does more: incidental-ion limits, simplification and miss diagnosis.

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
  fixtures (median 1.3 ms vs 1.8 ms). It is slower on the three chelate-rich
  mixtures:

| Fixture | PHREEQC | FlahaX |
|---|---:|---:|
| Mixed products | 4.0 ms | 63.3 ms |
| Mixed products, nitric acid to pH 6 | 6.0 ms | 65.4 ms |
| Mixed products with phases | 14.8 ms | 66.9 ms |

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
| PHREEQC | −3.5 % to +0.3 % | 1.2 ms |
| Horticalc | −11.2 % to +17.2 % | 0.09 ms |
| pyEQL | −11.0 % to +16.9 % | 938 ms |
| FlahaX (calculated pH) | — | 116 ms |

FlahaX and PHREEQC both speciate, including ion pairs such as CaSO4 and MgSO4,
and they agree within 3.5 %. The two tools that work from free-ion totals differ
in both directions, by up to 17 %. Micronutrients and chelates were left out
because not every tool has them; their share of FlahaX's full-recipe EC reaches
7.6 % for one formula and is recorded per recipe.

## What this page does not show

- Physical accuracy on fertilizer mixtures: no measured EC or pH of these
  recipes is included.
- Speed on other machines. The timings are best of three on one laptop.
- Irriblend-DSW's water-blend search and profitability ranking. Only its
  fertiliser optimiser is benchmarked, on the benchmark's fixed waters and
  without real fertiliser prices.
