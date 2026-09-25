# Full Fertilizer Chemistry Coverage

FlahaX's final chemistry model is a source-versioned aqueous-equilibrium system, not a salt-name rule set. Every supported species family needs a thermodynamic definition, activity model, named phases, and checked-in PHREEQC golden fixtures before it can make a planning decision.

## Coverage matrix

| Family | Aqueous forms and reactions | Candidate solids / constraints | Status |
|---|---|---|---|
| Carbonate / calcium | CO₂, HCO₃⁻, CO₃²⁻, Ca²⁺, H⁺, OH⁻ | Calcite | First 25 °C open-CO₂ kernel verified |
| Sulfate / calcium / magnesium | SO₄²⁻, HSO₄⁻, Ca²⁺, Mg²⁺ and complexes | Gypsum, anhydrite, epsomite, kieserite | Next |
| Phosphate / calcium / magnesium | H₃PO₄, H₂PO₄⁻, HPO₄²⁻, PO₄³⁻, Ca/Mg complexes | Calcium phosphate phases, struvite where ammonium/Mg are present | Pending |
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

Sulfate is next because calcium sulfate is central to stock compatibility. The increment will add a PHREEQC sulfate/calcium fixture first, then implement only the species and phases required to match it. Phosphate follows with the same fixture-first rule. This keeps the package mathematically traceable while it grows toward complete fertilizer chemistry.
