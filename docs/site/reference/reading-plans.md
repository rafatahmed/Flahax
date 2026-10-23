# Reading plans and results

## Reading a plan's stages

A full plan is split into stages. The report lists every stage with its status
and reason.

| Status | What it means | What to do |
|---|---|---|
| `calculated` | The stage returned a result | Check its warnings and the stages that depend on it |
| `needs_input` | Required evidence is missing | Supply the inputs it names; FlahaX does not invent them |
| `requires_review` | Usable after review: an incidental nutrient without a maximum, a review-class mineral, a missed target or a chemistry assumption | Read the reason and decide |
| `blocked` | The stage was rejected | Read its message and correct the inputs |

A calculated stage is not a validated delivery plan.

Read more: [user manual](manual.md),
[water, targets and acid](../developer/water-to-delivery.md).

## Reading a calculated EC result

FlahaX estimates the EC of the planned solution for comparison with your meter
after mixing. It is experimental, and its results use these statuses:

| Status | What it means |
|---|---|
| `estimated` | FlahaX gives an EC estimate. |
| `estimated`, with a range | Some charged dissolved species have no conductivity value. Their share cannot be negative, so the range starts at the part FlahaX can count and extends only upward. The true value tends to lie in the lower half. The middle of the range and its half-width describe only this missing share; they are not an accuracy statement. |
| `partial` | You supplied the pH and the analysis is missing some counterions. Only the part from known species is reported, with no total. |
| `not_supported` | The mixture is outside the conditions the method covers, or FlahaX calculated the pH and the analysis does not balance closely enough. The result says why, and no EC is given. A blend with undisclosed ingredients also gives this status. |

Every result carries the sentence "Accuracy on this fertilizer mixture has
not yet been established." No measured accuracy is claimed. When you compare a
prediction with your meter, FlahaX reports the difference without a pass or
fail verdict. Always check EC with a suitable meter after the solution is
prepared.

Read more: [stock and irrigation EC](../developer/conductivity.md),
[site planning](../developer/site-planning.md).

## Catalogue terms

**Undisclosed blends (`composition_undisclosed`).** A factory blend has a
declared nutrient analysis, but its exact ingredients, counterions or
additives may not be disclosed. FlahaX can still use the declared analysis to
build a recipe. It will not calculate pH, precipitation or EC for a mixture
that contains such a blend: it reports `composition_undisclosed` instead of
quietly leaving the blend out. A blend whose components are disclosed goes
through the chemistry normally.

**Analysis basis.** For each nutrient, FlahaX records where the value it used
came from:

| Basis | Source of the value |
|---|---|
| `lot_measured` | The measured value on your lot certificate |
| `grade_typical` | The typical value on the supplier's data sheet |
| `grade_minimum` | Only a minimum on the data sheet (flagged as a lower bound) |
| `identity_theoretical` | The theoretical analysis of the pure compound |
| `declared_catalogue` | The value in the shipped catalogue |

A record without this information is reported as `unattributed`; the basis is
never guessed. You pass in your own grades and lots; FlahaX does not store
them. When a grade gives a range, FlahaX shows the resulting nutrient band and
does not pick a "safe" end. Confirm the actual grade of each product before
physical use.

Read more: [traceable materials](../agronomist/formula-and-products.md),
[stock planning](../agronomist/tanks-and-solubility.md), [pH planning](../agronomist/ph-and-acids.md).
