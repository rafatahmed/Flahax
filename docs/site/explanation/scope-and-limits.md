# Scope and limits

FlahaX plans **one batch**: one crop formula and one water give one recipe, its pH reagent and two
concentrate tanks. It does not manage a season, a recirculating system or drainage, and it never
operates pumps, valves or other hardware.

## What the results are

Results are calculations for planning, not dosing instructions. FlahaX has not been validated in
the laboratory or in the field; a [physical validation protocol](../evidence/physical-validation-protocol.md)
is in draft. Its owner's [computational assessment](../evidence/computational-review.md) is not an
independent review. Measure pH and EC after mixing, and keep the sheet with your measurements.

## Chemistry model boundary

- 25 °C, with Davies activity coefficients, for dilute solutions (ionic strength up to
  0.1 mol/kg water). Concentrated stock tanks are outside the model.
- Fixed oxidation states of the products and closed analytical inorganic carbon.
- Checked against pinned PHREEQC 3.8.6 (USGS) for every catalogue product, phase and acid
  equilibrium case; see the [PHREEQC reference fixtures](../models/reference-fixtures.md) and the
  [coverage matrix](../models/chemistry-coverage-matrix.md). That agreement does not verify
  NNLS salt selection, crop-formula nitrogen semantics or measured EC accuracy.

## Other limits

- **Solubility** checks use single-salt values in pure water, a lower bound; products sharing a
  tank dissolve less together, and there is no mixed-salt data. Products without sourced data are
  listed as not checked.
- **Conductivity** is experimental: EC screening has unknown accuracy, and EC from speciation has
  stated bounds. PHREEQC agreement is not measured EC accuracy.
- **Nutrient maxima.** Aside from the disclosed Dutch incidental NH4 default when `N_NH4` is
  omitted, a maximum concentration is checked only when you declare it. An acid is planned only
  when you offer one from its certificate.
- **The full-screen `flahax mix` is alpha.** `flahax mix --plain` always works; on Windows, typing
  "à" in it swallows the next key (#127).

See the [changelog](../changelog.md) for what each release changed and its known limits.
