# FlahaX landscape comparison and SWOT

Prepared 2026-10-17 as input for a FlahaX introduction article. Status:
**draft for owner review**. This is a desk review of public material, not a
hands-on benchmark. Where a tool's behaviour could not be confirmed from its
public documentation it is marked *not documented*, which is not evidence
that the feature is absent.

## Question asked

Is there another software package dedicated to plant nutrition that
researchers, agronomists, growers and developers can all use, and that does
what FlahaX does? If not, what can the article truthfully claim?

## Tools reviewed

| Tool | What it is | Form and language | Licence | Activity seen |
|---|---|---|---|---|
| **FlahaX** | Fertilizer formulation, bounded aqueous chemistry and auditable delivery planning | Python library + CLI on PyPI, no runtime dependencies | Flaha Free Use 1.0: free use, **no modification or redistribution** | 0.3.0 on PyPI 2026-09-27; 0.3.1 in preparation |
| **hydrosolver** | Optimisation-driven hydroponic nutrient calculator and small DSL (`Composition`, `Solution`, `solve_lstsq`) | Python package on PyPI | GPLv3 | Single release 0.1, 2021-10-17 |
| **NutrientMixingAlgorithm** (TU Chemnitz ACSD lab) | Convex optimisation of water-source volumes and fertilizer masses into a mixing tank; aquaponics focus | Python 3.11 script, XML tables, CasADi + IPOPT; not on PyPI | Open source (repo) | Last push 2024-11-14; companion paper Kobelski et al., *Appl. Sci.* 2024, 14, 8140 |
| **HydroBuddy** | Best-known free nutrient calculator: salt weights from target elements, water quality input, 1:100 A/B stocks, empirical EC estimate, acid for alkalinity | Desktop program, Lazarus/Pascal | GPL | v1.100 described as last release |
| **NUTRISENSE** (Agricultural University of Athens, Savvas group) | Decision support system that calculates nutrient-solution formulae and readjusts them from drainage analysis in closed systems; ISE-linked real-time version | Web application (nutrisense.online) | Not documented | Research project outputs 2021–2022 |
| **Haifa NutriNet** | Vendor expert system for crop fertigation programmes; crop database (about 80 crops), water and soil analysis input | Free web service | Proprietary | Active vendor service |
| **PHREEQC / phreeqpy** | USGS general geochemical equilibrium code and Python wrapper | Executable / Python bindings | Public domain / BSD-3 | phreeqpy 0.6.0, 2024-06-10 |
| **Web and spreadsheet calculators** (Hydroponicity, WUR Nutrient Solution Calculator, Omni, Clemson, Nutrient Pro Hydro) | Recipe-to-salt arithmetic, some with source water and A/B stock tanks | Web pages / spreadsheets | Mixed | Varies |
| **SMART! Fertilizer Management** | Commercial fertilizer optimisation software (field and fertigation) | Desktop/commercial | Proprietary | One listing reports the company ceased operating after a 2017 acquisition; unconfirmed |

## Capability comparison

Legend: **Yes** documented; **Partial** documented with a material limit;
**No** documented as absent or clearly out of scope; **—** not documented.

| Capability | FlahaX | hydrosolver | Mixing Algorithm | HydroBuddy | NUTRISENSE | NutriNet | PHREEQC |
|---|---|---|---|---|---|---|---|
| Fertilizer salt selection to meet a target | Yes, non-negative grams over the full shipped library | Yes, least squares | Yes, convex optimisation with resource weights | Yes, linear solve | Yes | Yes | No |
| Source water subtracted from the target | Yes | Yes (water as a composition) | Yes, several water sources | Yes | Yes | Yes | No |
| Crop recipe / crop database | Fixed crop formula supplied by user | No | No | Partial (formulation library) | Yes, crop and stage | Yes, about 80 crops | No |
| Aqueous speciation and complexes | Yes, 197 aqueous entries, Davies, I ≤ 0.1 mol/kg, 25 °C | No | No | No | — | — | Yes, general |
| Precipitation / saturation of fertilizer phases | Yes, 28 phases, saturation indices and formed solids | No | No | Partial (fixed incompatibility rules for A/B) | — | — | Yes, general |
| pH prediction of the mixed solution | Yes, calculated initial pH | No | No | No | — | — | Yes |
| Acid dose to a target pH | Yes, nitric (equilibrium) and phosphoric workflow, assay and density | No | No | Partial (acid to neutralise alkalinity) | Partial (pH control as facility input) | — | Possible with hand-written input files |
| EC estimate | Partial: dilute pre-acid screening and measured-profile method; no validated concentrated-stock model | No | No | Partial: empirical, author warns it may be far off | — | — | Partial (specific conductance) |
| A/B stock planning with compatibility and solubility | Yes, from caller-supplied records; candidate grouping in reports | No | No | Yes, 1:100 A/B with built-in incompatibilities | Yes (stock volumes as input) | — | No |
| Injector / pump flow sizing | Yes, flow and inventory arithmetic; no equipment model selection | No | Partial (tank geometry) | No | Yes, injection rates (ISE version) | Partial (irrigation system setup) | No |
| Closed-system drain readjustment | No | No | Partial (aquaponics water sources) | No | **Yes, core function** | Yes (recycled water mixing) | No |
| Provenance: source hashes, model IDs, explicit units | Yes, a design principle | No | No | No | — | No | Partial |
| Verification against an independent reference | Yes, pinned PHREEQC replay and golden fixtures | — | Paper validation of mixing | — | Tomato trials versus commercial practice | — | Reference code itself |
| Scriptable API for developers | Yes, Python API + JSON CLI | Yes | Partial (XML-driven script) | No | No | No | Yes, general |
| Interface for growers without code | Partial: interactive CLI and offline HTML reports | No | No | Yes, desktop GUI | Yes, web | Yes, web | No |
| Field / greenhouse validation | **No** (computational evidence only) | — | Yes (aquaponics paper) | — | Yes (tomato trials) | — | Not applicable |

FlahaX evidence: [development status](development-status.md), [chemistry
coverage matrix](chemistry-coverage-matrix.md), [release
evidence](release-evidence.md) and the README.

## What the evidence supports

1. **No reviewed tool combines all four layers** that FlahaX combines in one
   installable Python package: formulation against the actual water,
   fertilizer-specific aqueous equilibrium with precipitation, acid-to-target
   pH planning, and stock/injector delivery planning with an audit trail.
2. **"First plant nutrition Python package" is not defensible.** hydrosolver
   (PyPI, 2021) is a Python plant-nutrition package, and NutrientMixingAlgorithm
   is Python research code with a peer-reviewed paper.
3. **"Open source" is not accurate for FlahaX.** Its licence permits free use
   but forbids modification and redistribution. "Free to use" or
   "source-available" are accurate.
4. **The audience claim needs care.** FlahaX serves developers and
   researchers well today. Agronomists and growers are served only through the
   CLI and reports; HydroBuddy, NUTRISENSE and NutriNet are easier for them.
5. **NUTRISENSE is the strongest scientific peer**, not a package but a
   validated, crop-aware DSS with closed-system readjustment that FlahaX does
   not do. The article should acknowledge it rather than ignore it.

Candidate claim wording, strongest defensible first:

> To our knowledge, FlahaX is the first Python package to unite fertilizer
> formulation, fertilizer-specific aqueous equilibrium chemistry and auditable
> delivery planning (stock tanks, acid dosing and injection) in one
> dependency-free library, verified against PHREEQC.

## SWOT

### Strengths

- **Chemistry depth unique among nutrient tools.** Mixed equilibrium over the
  full catalogue (197 aqueous species, 28 phases) predicts pH, complexes and
  precipitation instead of assuming ideal dissolution.
- **Verification discipline.** Pinned PHREEQC replay, golden fixtures, failure
  reproducers and versioned release evidence; few nutrient tools publish any
  verification at all.
- **Honest boundaries built in.** Explicit units (g/L of final solution versus
  g/kg water), validity ranges (25 °C, I ≤ 0.1, closed carbon) and rejection
  of incomplete inputs instead of plausible-looking wrong answers.
- **Auditability.** Source hashes, model identifiers and explicit assays make
  a plan reviewable — valuable for research reproducibility and for
  commercial accountability.
- **End-to-end scope.** Water analysis through stock tanks, acid and injector
  flow in one workflow.
- **Zero runtime dependencies, Python 3.11–3.13, on PyPI.** Easy to install
  and embed.
- **Planned engine for FlahaFAST**, giving it a path to a grower-facing
  product without diluting the library.

### Weaknesses

- **Licence blocks open-source use.** No modification or redistribution:
  researchers cannot fork or extend it, developers cannot ship it inside their
  products, and venues such as JOSS that require an OSI licence are closed.
- **No laboratory or field validation.** Evidence is computational; EC
  accuracy is unknown and no grower trial exists, unlike NUTRISENSE. The
  [route to accurate EC](#route-to-accurate-ec) sets out how to close the EC
  part.
- **Narrow validity window.** 25 °C only, dilute ionic strength, fixed
  oxidation states; concentrated stock tanks (the real operating condition)
  are outside the validated model.
- **Hosted CI still open.** 0.3.0 shipped under a local-evidence exception;
  supported-version CI is unresolved.
- **High data burden on the user.** Water analysis, product assays,
  compatibility and solubility records must be supplied; no crop database.
- **No grower-friendly interface yet.** CLI and reports only until FlahaFAST
  integration happens.
- **Single maintainer and self-assessment.** The G6 assessment is by the
  owner, not an independent reviewer.
- **No closed-system (drain recycling) readjustment.**

### Opportunities

- **A clear gap in the ecosystem.** Python tools stop at mass balance;
  chemistry tools are generic. FlahaX can own "chemistry-aware nutrient
  planning in Python".
- **Peer-reviewed software paper** (for example *SoftwareX*, *Computers and
  Electronics in Agriculture*, or JOSS if the licence changes) establishes
  priority and citation.
- **Research collaborations** for laboratory and greenhouse validation —
  NUTRISENSE's group, TU Chemnitz's lab and horticulture departments are
  natural partners and would close the biggest weakness.
- **FlahaFAST as the grower front end**, with FlahaX as the verified engine.
- **Roadmap items with real user value:** explainable infeasibility,
  versioned product evidence packs, uncertainty reports and cost-aware
  formulation.
- **Integration with sensors and controllers** (ISE, EC/pH probes, open
  dosing hardware) as a planning backend.
- **Teaching use** in plant nutrition and hydroponics courses, where showing
  precipitation and pH effects is hard with spreadsheets.
- **Validated EC with stated uncertainty**, built on the speciation FlahaX
  already has, would give growers a daily-use number no reviewed peer offers
  with stated error; see the [route to accurate EC](#route-to-accurate-ec).

### Threats

- **Established free tools** (HydroBuddy, NutriNet) already satisfy most
  growers' everyday needs; "good enough" competes with "correct".
- **Vendor ecosystems** (Haifa, Yara, ICL) give away planning tools to sell
  fertilizer and own grower relationships.
- **Academic DSSs with field validation** (NUTRISENSE) set the credibility bar
  that reviewers will compare against.
- **Overclaiming risk.** A "first of its kind" headline that critics can
  refute with hydrosolver, HydroBuddy or PHREEQC damages the credibility that
  the project's careful evidence earns.
- **Liability perception.** Any plan that leads to crop damage reflects on the
  tool; the boundaries must stay visible in FlahaFAST too.
- **Licence-driven non-adoption.** Researchers may prefer an inferior open
  tool they can modify, or build an open competitor on PHREEQC.
- **Bus factor.** Single-maintainer projects lose trust if releases stall.

## Route to accurate EC

EC is the number growers watch every day, and it is FlahaX's least developed
output: the shipped screening is a dilute pre-acid approximation with unknown
accuracy, and no concentrated-stock model is validated
([development status](development-status.md)). This section sets out how to
reach the accuracy the scope actually needs, building on the open decisions
D1–D3 and D7 in the [stock conductivity service
design](stock-conductivity-service-design.md). Accuracy targets below are
**proposals for the owner's decision D1**, not agreed criteria.

### What "optimum" means here

More model is not always more accuracy. Past a point, the prediction error is
smaller than errors the model cannot remove: the meter's own tolerance, the
spread in commercial product assays, weighing and make-up volume, and how the
source water analysis was taken. The optimum is the simplest model whose error
is comparable to those irreducible errors **and** smaller than the step a
grower or researcher would act on. Accuracy beyond that adds cost and
fragility without changing any decision.

### The scope, in conductivity terms

| Use | Typical EC | Approximate ionic strength (mol/L and mol/kg are close in this dilute band, not at stock strength) | What the user decides from it |
|---|---|---|---|
| Irrigation (drip) solution | about 1–3 mS/cm | about 0.01–0.04 mol/L | Whether the injected mix is on target; dilution setpoint |
| Drain / recirculated solution | up to about 5–6 mS/cm | up to about 0.08 mol/L | When to flush or readjust |
| A/B stock at 1:100 to 1:200 | far above meter range for many salts | about 1 mol/kg to near saturation | Whether a tank was made up correctly |
| Intermediate check dilutions | between the two | 0.1–0.5 mol/kg | Spot checks of stock strength |

Ionic strength from EC uses the Griffin–Jurinak approximation
I ≈ 0.0127 × EC (dS/m), which is adequate for sizing the ranges, not for
prediction.

Two scope facts shape the design:

- **25 °C is fit for scope.** Field meters with automatic temperature
  compensation display EC referenced to 25 °C, so a 25 °C prediction is
  directly comparable to what the grower reads. Raw uncompensated readings
  and non-standard compensation coefficients remain out of scope and must be
  stated.
- **Most decisions happen at irrigation strength.** The highest-value
  accuracy is in the dilute band, which is also where the existing
  speciation kernel is valid (Davies, I ≤ 0.1 mol/kg).

### Tiered model, matched to the scope

| Tier | Range | Model | Why this fits | Proposed target (D1) |
|---|---|---|---|---|
| T1 Irrigation | I ≤ 0.1 mol/kg | Free ions and ion pairs from the existing speciation kernel, then an extended Onsager-type molar conductivity per ion (Fuoss–Onsager / Lee–Wheaton family, including the ion-size term) | Reuses verified chemistry; pairs and chelates correctly remove charge carriers; same validity window as the kernel; no new dependency | Within ±5 % or ±0.1 mS/cm, whichever is larger, against measured mixtures |
| T2 Stock | 0.5 mol/kg to saturation | Casteel–Amis curve per salt (four fitted parameters: peak conductivity, molality at the peak and two shape terms) from cited handbook or primary data, combined with a stated mixing rule | The only lightweight model that reaches saturation; fitted from published single-salt conductivity data, which exist for most macronutrient salts (to be confirmed per salt in E1) | Within ±10 % for supported A/B compositions; any unsupported salt makes the point `not_supported` |
| Bridge | 0.1–0.5 mol/kg | T2 with the mixing rule, or T1 if validation shows it holds; choose the crossover from evidence | Avoids a third model; the boundary is set by measured residuals, not preference | Whichever tier meets its target, else `not_supported` |
| Cross-check | All tiers where defined | PHREEQC specific conductance on the same composition | Independent of FlahaX's implementation, already pinned for equilibrium verification; development-only, never a runtime dependency | Disagreements beyond the target are investigated, not averaged |

Explicitly **not** chosen now: mean-spherical-approximation models
(Anderko–Lencka, the OLI engine). They are the most accurate in concentrated
mixtures, but they need large thermodynamic databases or a commercial
licence, which would break the dependency-free design for a gain the scope
does not require. Revisit only if T2 fails its target on real stocks.

### Known limits that stay visible

- **Chelates and micronutrients.** Few published conductivity data exist. At
  irrigation strength their contribution is small; at stock strength they are
  reported as unsupported or carried as a bounded uncertainty, never guessed.
- **Acid-adjusted solutions.** The hydrogen ion is far more mobile than any
  nutrient ion, and acid also converts bicarbonate. EC after acid injection
  must come from the existing pH solver's final speciation, as a later stage,
  not by adding acid EC on top.
- **Mixing rule error.** The rule for combining single-salt curves is itself an
  approximation, and its error must be measured on real mixtures.
- **Precipitation.** Where the equilibrium model expects solids, no EC is
  returned for that point.

### Validation evidence, in order

1. **E1 single salts:** cited conductivity-versus-concentration tables to
   saturation for KNO3, Ca(NO3)2, MgSO4, KH2PO4, K2SO4, NH4NO3, (NH4)2SO4 and
   KCl, used to fit and check T2 curves. The provisional KCl figures in the
   service design must be replaced by primary citations first.
2. **Laboratory mixtures:** prepared irrigation-strength and stock-strength
   recipes measured with a calibrated, temperature-compensated meter, split
   into tuning and acceptance sets before any fitting.
3. **Grower measurements** collected through FlahaFAST, used only to evaluate
   and report drift. A model revision is a reviewed change in this repository
   (design decision D6), never automatic.

### What changes in the SWOT when this is done

| Today | After T1 is validated | After T2 is validated |
|---|---|---|
| Weakness: EC accuracy unknown | Strength: validated EC for irrigation and drain solutions, with stated uncertainty | Strength: validated stock-tank EC — a check no reviewed peer tool offers with stated uncertainty |
| Weakness: concentrated stocks outside the model | Unchanged | Closed for supported salts |
| Threat: "good enough" EC from HydroBuddy | Reduced: FlahaX states its error, HydroBuddy's author warns its estimate can be far off | Further reduced for stock checks |

## Implications for the article

- Lead with the combination and the verification, not with "first".
- Name the peers fairly; the comparison makes FlahaX look stronger, not weaker.
- State the licence plainly as free to use and avoid "open source".
- Say clearly that FlahaX is the planned engine for FlahaFAST and that
  FlahaFAST does not use it yet.
- Keep the validity boundaries in the article; they are a differentiator.
- Present EC as work in progress with a defined route and targets; claim
  validated EC only after the T1 or T2 evidence exists.

## Sources

- hydrosolver: <https://pypi.org/project/hydrosolver/>,
  <https://src.strelnikov.xyz/dstrelnikov/hydrosolver>
- NutrientMixingAlgorithm: <https://github.com/TUCACSD/NutrientMixingAlgorithm>;
  Kobelski et al. 2024, <https://doi.org/10.3390/app14188140>
- HydroBuddy:
  <https://scienceinhydroponics.com/2016/03/the-first-free-hydroponic-nutrient-calculator-program-o.html>,
  <https://scienceinhydroponics.com/tag/hydrobuddy>
- NUTRISENSE: <https://www.aua.gr/ekk/en/nutrisense>,
  <https://hortidaily.com/article/9264160/nutrisense-a-decision-support-system-to-calculate-and-readjust-hydroponic-nutrient-solutions>,
  <https://ishs.org/ishs-article/1317_24/>
- Haifa NutriNet:
  <https://www.haifa-group.com/nutrinet%E2%84%A2-plant-nutrition-expert-system>
- phreeqpy: <https://pypi.org/project/phreeqpy/>
- SMART! Fertilizer Management:
  <https://www.feedstrategy.com/product/smart-fertilizer-management-software>,
  <https://startupim.com/company/smart>
- Hydroponicity: <https://hydroponicity.com/>
- PySNM (soil mapping, out of scope):
  <https://link.springer.com/article/10.1007/s44378-025-00132-6>

EC route references (cited from memory; confirm the full citations before
publication):

- Casteel, J. F.; Amis, E. S. Specific conductance of concentrated solutions of
  magnesium salts in water–ethanol system. *J. Chem. Eng. Data* 1972, 17,
  55–59 (origin of the Casteel–Amis equation).
- Griffin, R. A.; Jurinak, J. J. Estimation of activity coefficients from the
  electrical conductivity of natural aquatic systems and soil extracts.
  *Soil Science* 1973, 116, 26–30 (I ≈ 0.0127 × EC).
- Anderko, A.; Lencka, M. M. Computation of electrical conductivity of
  multicomponent aqueous systems in wide concentration and temperature
  ranges. *Ind. Eng. Chem. Res.* 1997, 36, 1932–1943.

Search limits: PyPI's search page did not load, so likely package names were
checked through the PyPI JSON API. The NUTRISENSE, NutriNet and SMART!
feature cells rely on secondary descriptions; confirm before publication.
