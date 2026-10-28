(delivery-quantities-and-final-solution-recipes-p1)=
# Units and batch quantities

The quantity layer uses immutable dataclasses with explicit base units and rejects non-finite, negative, ambiguous, or dimensionally wrong values before stock, pH, or pump logic receives them.

## Quantities

| Type | Stored unit | Constraint |
|---|---:|---|
| `MassGrams` | g | non-negative |
| `VolumeLitres` | L | greater than zero |
| `GramsPerLitre` | g/L | non-negative |
| `MilligramsPerLitre` | mg/L (ppm) | non-negative |
| `MilliEquivalentsPerLitre` | meq/L | non-negative |
| `TemperatureCelsius` | °C | at least absolute zero |
| `FlowLitresPerMinute` | L/min | greater than zero |
| `DurationMinutes` | min | non-negative |
| `InjectionRatio` | final L / stock L | greater than zero |

The quantity objects are frozen. Arithmetic stays at full floating-point precision; formatting and rounding are outside the planning API and must occur only after constraint evaluation.

## Final batch adaptation

Call template: supply the named records described on this page; this fragment is not a standalone example. For a complete synthetic repository example, run `python -m examples.equilibrium_delivery` from the checkout.

```text
from flahax import VolumeLitres, final_solution_recipe

recipe = final_solution_recipe(recommendation, VolumeLitres(250))
for salt in recipe.salts:
    print(salt.name, salt.dose.value, salt.mass.value)
```

For each salt:

```text
M_salt [g] = dose [g/L] * final_volume [L]
```

`final_solution_recipe` retains the recommendation's `feasible` flag; it does not turn an infeasible nutrient balance into an accepted delivery plan.

## Reagent nutrient contribution

Acids and bases are not pH-only products. Given reagent mass `M`, elemental mass fraction `f_i`, and final volume `V`, the contribution for ion `i` is:

```text
Delta_C_i [mg/L] = M [g] * f_i * 1000 / V [L]
```

Call template: supply the named records described on this page; this fragment is not a standalone example. For a complete synthetic repository example, run `python -m examples.equilibrium_delivery` from the checkout.

```text
from flahax import MassGrams, VolumeLitres, elemental_contribution, rescore_with_reagent

addition = elemental_contribution(
    MassGrams(10), {"N_NO3": 0.138}, VolumeLitres(100)
)
loss, rows = rescore_with_reagent(achieved, targets, addition)
```

The mass fractions must be elemental fractions from 0 to 1 and cannot total more than 1. Total nitrogen remains prohibited: callers must state nitrate and ammonium separately. `rescore_with_reagent` adds the contribution to the achieved ppm profile and uses FlahaX's existing percentage-error scoring model.

## Boundary

The quantity layer does not calculate stock concentration, tank compatibility, reagent normality, pH dose, pump runtime, or hardware commands. Those calculations belong to their respective planning APIs. Its role is to make their inputs dimensionally clear and preserve the original solver balance.

## Recalculate actual weighed masses

`salts[].gramsPerLitre` is the authoritative binary64 product dose. Every positive
solver dose is retained, including trace doses below 0.000001 g/L. JSON round trips
retain these values. `totalGramsPerLitre` sums the same unrounded doses. Formatting
is for display; a displayed rounded mass must not be substituted silently.

When scale resolution or actual weighing changes a dose, recalculate:

Call template: supply the named records described on this page; this fragment is not a standalone example. For a complete synthetic repository example, run `python -m examples.equilibrium_delivery` from the checkout.

```text
from flahax import MassGrams, VolumeLitres, rescore_weighed_recipe

actual = rescore_weighed_recipe(
    products, {product_id: MassGrams(measured_grams)}, VolumeLitres(100),
    original_targets, original_water,
    maximum_concentrations=original_effective_maxima,
)
```

Pass every actually weighed product; omitted IDs contribute zero. The function
converts grams divided by final litres to g/L, recomputes nutrient concentrations,
loss, zero requirements and hard limits, and returns fresh feasibility. It never
refits the recipe or inherits planned feasibility. Retain original targets and
water; include effective ammonium limits if the original caller set that policy.
A passing nutrient assessment does not establish pH, stock compatibility or scale
suitability. Re-run the applicable chemistry and delivery assessments for changed
quantities. Small masses may require an independently assessed dilution procedure;
the mathematical engine does not silently omit them or invent scale resolution.

Reagent reports use liquid volume only when the product has a density-based
conversion. Otherwise they retain grams in terminal, report and batch sheets;
missing density never implies zero volume or permission to use an acid injector.


## End-to-end delivery balance

For each occupied stock channel, `V_stock = V_final / R`, where `R` is final
solution litres per stock litre. Each product must occur in exactly one stock;
`C_stock * V_stock = dose_final * V_final = mass_recipe` in grams. Capacity is
not prepared inventory. Mixing acid into a fertilizer channel is unsupported.

`compose_delivery_plan` rejects duplicate/unknown channels, inconsistent product
masses, wrong command volumes and nonpositive carrier remainders. Drafts may lack
stock commands; state advancement requires exactly one command for every stock
and nonzero reagent channel. A zero reagent dose has no reagent command.
Titration `PhPlan` retains its `final_volume`; the default separate channel is
`acid`. Legacy manually constructed plans without that volume cannot validate.
Equilibrium plans retain their matching recipe and explicit reagent channel.

Command-volume identities retain `isclose(rel_tol=1e-9, abs_tol=1e-12)` in litres.
Product-mass identities use relative tolerance 1e-9 with **zero absolute floor**,
so a trace product cannot disappear within an absolute gram allowance. This is
a numerical reconciliation check, not a dosing, weighing, calibration or
scientific accuracy specification.

`V_carrier = V_final - sum(V_stock) - V_reagent` is **additive-volume bookkeeping**.
It does not predict solution-volume contraction, water mass, contact time,
transient concentrations, hydraulic mixing or precipitation during injection.
Final solvent mass remains a separate explicit chemistry input. These arithmetic
checks do not qualify an otherwise unsupported stock mixture.

`prepare_stocks` reserves three equal A/B/acid volumes and therefore requires a
ratio greater than three. It rejects derived nonfinite or zero volumes. If actual
reagent volume differs from that reserved container volume, use the explicitly
planned reagent dose when composing delivery; do not count both volumes.

Pump calibration and `as_of` timestamps must be timezone-aware. Future or expired
calibrations fail; inventory and calibrated dose bounds are enforced. Independent
flow and timing standard deviations combine by a stable Euclidean norm. This
propagation assumes independent errors and excludes bias and correlated errors;
the retained minimum represented uncertainty is 1e-15 L.
