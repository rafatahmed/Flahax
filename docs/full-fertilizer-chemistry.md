# Full Fertilizer Chemistry Coverage

FlahaX's final chemistry model is a source-versioned aqueous-equilibrium system, not a salt-name rule set. Every supported species family needs a thermodynamic definition, activity model, named phases, and checked-in PHREEQC golden fixtures before it can make a planning decision.

## Coverage matrix

| Family | Aqueous forms and reactions | Candidate solids / constraints | Status |
|---|---|---|---|
| Carbonate / calcium | CO₂, HCO₃⁻, CO₃²⁻, Ca²⁺, H⁺, OH⁻ | Calcite | First 25 °C open-CO₂ kernel verified |
| Sulfate / calcium / magnesium | SO₄²⁻, HSO₄⁻, Ca²⁺, Mg²⁺ and complexes | Gypsum, anhydrite, epsomite, kieserite | Pure-water Ca²⁺/SO₄²⁻/CaSO₄(aq) gypsum kernel and PHREEQC fixture verified; magnesium and mixture coverage remain |
| Phosphate / calcium / magnesium | H₃PO₄, H₂PO₄⁻, HPO₄²⁻, PO₄³⁻, Ca/Mg complexes | Calcium phosphate phases, struvite where ammonium/Mg are present | PHREEQC 3.8.9 Ca/Mg/phosphate fixture and fixed-pH complexation kernel added; solid equilibrium and full activity coverage pending |
| Nitrogen | NO₃⁻, NH₄⁺, NH₃ and acid/base relation | Ammonia volatility boundary where applicable | Pending |
| Potassium / sodium / chloride | K⁺, Na⁺, Cl⁻ and ion pairs where supplied by selected database | K/Na salts only when named phase data applies | Pending |
| Micronutrients | Fe, Mn, Zn, Cu, B, Mo species and chelates | Hydroxide/phosphate/carbonate precipitation; chelate stability | Pending, requires chelate dataset |

## Generic phase model

`MineralPhase` stores the dissolved-species stoichiometry, `log K`, database identity, and temperature. For each phase:

```text
log IAP = sum_i(nu_i * log10(a_i))
SI = log IAP - log K
```

This requires activities, not raw ppm. The phase record must identify the exact thermodynamic database and temperature to avoid combining constants from different sources.

## Data-source rule

The initial reference is the PHREEQC `phreeqc.dat` database and its documented activity/speciation framework. Each expansion must record its source URL, PHREEQC/database version, selected activity model, temperature range, phase reaction, `log K`, and fixture output. The PHREEQC source database is available in the [official repository](https://github.com/phreeqc-dev/phreeqc3/blob/master/database/phreeqc.dat); the underlying solver is documented by the [USGS](https://doi.org/10.3133/tm6A43).

## Next chemistry increment

Calcium sulfate is central to stock compatibility because only **free-ion activities**, not total label concentrations, enter the gypsum saturation index. The first sulfate increment is fixture-backed for pure water at 25 °C and includes neutral `CaSO4(aq)`. It is not a mixed-fertilizer solubility claim: magnesium, phosphate, counter-ions, acidity, background-water composition, and additional phases remain outside that kernel.

## Orthophosphate foundation

The package now distributes an explicitly supplied total *uncomplexed* orthophosphate amount across `PO4³⁻`, `HPO4²⁻`, `H2PO4⁻`, and `H3PO4` at 25 °C. It uses the PHREEQC `phreeqc.dat` reactions and Davies activities:

```text
PO4^3- + H+     <-> HPO4^2-     log beta = 12.346
PO4^3- + 2 H+   <-> H2PO4-      log beta = 19.553
PO4^3- + 3 H+   <-> H3PO4       log beta = 21.721
a_i = gamma_i m_i
sum(m_i) = P_total_uncomplexed
```

It requires pH and ionic strength as model inputs, applies only through `I = 0.1 mol/kgw`, and rejects wider use. It does not yet solve pH, ionic strength, calcium/magnesium complexes, or solids. Consequently it must not approve a calcium–phosphate stock. The next required evidence is a PHREEQC mixture fixture with stated Ca, Mg, P, counter-ions, temperature, and phase set; only then can those complex and phase equations be enabled for planning.

## Calcium–magnesium–phosphate reference mixture

That fixture is now checked in: 2 mmol/kgw Ca as calcium chloride, 1 mmol/kgw Mg as magnesium chloride, and 1 mmol/kgw P as sodium dihydrogen phosphate, at 25 °C and pH 6.5. PHREEQC 3.8.9 reports free-ion activities and `SI(Hydroxyapatite) = 3.15`. The compact FlahaX kernel solves the matching Ca/Mg phosphate complexes at specified pH and ionic strength:

```text
Ca2+ + HPO4^2- <-> CaHPO4(aq)     log beta = 2.739
Mg2+ + HPO4^2- <-> MgHPO4(aq)     log beta = 2.870
Ca2+ + PO4^3-  <-> CaPO4-         log beta = 6.459
Mg2+ + PO4^3-  <-> MgPO4-         log beta = 6.589
```

The reference test uses `±0.05 SI` because the package intentionally uses a reduced Davies activity calculation while PHREEQC uses its complete ion-association model. This is verification of the direction and bounded numerical behavior—not permission to precipitate or approve a stock. Solid-equilibrium and broader activity-model coverage are still required before that decision is automated.

## Hydroxyapatite boundary

FlahaX now also exposes the fixed-pH thermodynamic boundary for the phase reaction:

```text
Hydroxyapatite + 4H+ <-> 5Ca2+ + 3HPO4^2- + H2O
log10(a_HPO4,eq) = (log K - 5 log10(a_Ca) - 4 pH) / 3
```

This gives the HPO₄²⁻ activity at `SI = 0` and makes the separation between a phase boundary and precipitation kinetics explicit. It does not calculate how much solid forms, nor can it replace the conservative A/B stock separation rule.

## Struvite boundary

For ammonium-bearing mixtures, FlahaX now evaluates the explicit 25 °C phase relation `MgNH4PO4:6H2O = Mg²⁺ + NH4⁺ + PO4³⁻ + 6H2O`, with `log K = -13.26`. The corresponding PHREEQC probe is undersaturated (`SI = -0.30`). As with hydroxyapatite, this is an activity-product boundary only; ammonium acid/base speciation and full mixed-ion equilibrium are the next required extension.

The first nitrogen extension now solves `NH4+ = NH3 + H+` with PHREEQC `log K = -9.252` at 25 °C. It accepts total ammoniacal nitrogen, pH, and ionic strength, returns activity-corrected NH₄⁺ and neutral NH₃, and preserves their molal mass balance.

The checked-in struvite probe is now coupled at fixed pH and ionic strength: magnesium/phosphate and ammonium/ammonia mass balances, sodium association, and the struvite activity product are solved together. The reduced Davies result is `SI = -0.306`, compared with PHREEQC's `-0.30`. It still does not solve pH, ionic strength, solid amount, calcium competition, or sulfate/carbonate interference.

The next reduced-system step now iterates pH and ionic strength to charge closure for stated Mg, total NHx, total phosphate, Na, and Cl inputs. It is deliberately not a general water model: calcium, sulfate, carbonate, other counter-ions, and solid precipitation remain excluded.

The first calcium/sulfate competition probe is now checked in separately. Its PHREEQC 3.8.9 output is `SI(Gypsum) = -1.98`, `SI(Struvite) = -0.46`, and `SI(Hydroxyapatite) = 10.69`. FlahaX compares the gypsum and struvite free-ion activity products within the reduced-model tolerance; hydroxyapatite remains a separately modelled calcium-phosphate constraint.

Calcium and sulfate can now be supplied explicitly to the reduced charge-balanced struvite solver. They contribute to charge balance and ionic strength, and the result includes a gypsum saturation index when both are present. Their aqueous complexes and any precipitated amount remain deliberately outside this increment.

The solver now includes neutral `CaSO4(aq)` using the current `phreeqc.dat` `log beta = 2.14`. It conserves analytical calcium and sulfate totals, reports free Ca²⁺/SO₄²⁻ and the neutral pair, and bases gypsum SI on free-ion activities. Calcium-phosphate and carbonate complexes remain outside this reduced family.

The carbonate competition probe adds bicarbonate to the Ca/SO4/struvite mixture. PHREEQC reports calcite `SI = 0.26`, gypsum `SI = -1.99`, and struvite `SI = -0.48`. FlahaX now exposes these three named activity-product indices together; it still does not allocate precipitated mass between phases.
