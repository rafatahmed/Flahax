# Delivery Quantities and Final-Solution Recipes (P1)

P1 adds a small, dependency-free quantity layer for delivery planning. It uses immutable dataclasses with explicit base units and rejects non-finite, negative, ambiguous, or dimensionally wrong values before later stock, pH, or pump logic receives them.

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

```python
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

```python
from flahax import MassGrams, VolumeLitres, elemental_contribution, rescore_with_reagent

addition = elemental_contribution(
    MassGrams(10), {"N_NO3": 0.138}, VolumeLitres(100)
)
loss, rows = rescore_with_reagent(achieved, targets, addition)
```

The mass fractions must be elemental fractions from 0 to 1 and cannot total more than 1. Total nitrogen remains prohibited: callers must state nitrate and ammonium separately. `rescore_with_reagent` adds the contribution to the achieved ppm profile and uses FlahaX's existing percentage-error scoring model.

## Boundary

P1 does not calculate stock concentration, tank compatibility, reagent normality, pH dose, pump runtime, or hardware commands. Those remain P2–P4 work packages. Its role is to make their inputs dimensionally clear and preserve the original solver balance.
