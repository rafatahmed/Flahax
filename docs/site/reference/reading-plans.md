# Reading plans and results

## Reading a plan's stages

A full plan is split into stages. The report lists every stage with its status
and reason.

| Status | What it means | What to do |
|---|---|---|
| `calculated` | The stage returned a result | Check its warnings and the stages that depend on it |
| `needs_input` | Required evidence is missing | Supply the inputs it names; FlahaX does not invent them |
| `requires_review` | Usable after review: an incidental nutrient without a maximum, a precipitation risk label, a missed target or a chemistry assumption | Read the reason and decide |
| `blocked` | The stage was rejected | Read its message and correct the inputs |

A calculated stage is not a validated delivery plan.

Read more: [user manual](manual.md),
[water, targets and acid](../developer/water-to-delivery.md).

## Reading a calculated EC result

FlahaX estimates the EC of the planned solution for comparison with your meter
after mixing. It is experimental, and its results use these statuses:

| Status | What it means |
|---|---|
| `estimated` | Every charged species has a conductivity value: FlahaX gives one EC estimate. |
| `range` | Some charged species have no conductivity value, phosphate is beyond its fitted range, or you supplied a pH that leaves charge unbalanced. The low end counts what FlahaX can; the high end adds an upper limit for the rest. It is reported as low to high, with no midpoint and no accuracy claim. |
| `not_supported` | FlahaX could not solve the mixture (it is outside the conditions the method covers). The result says why, and no EC is given. A blend with undisclosed ingredients also gives this status. |

Every result carries the sentence "Model: McCleskey et al. (2012); its reported accuracy (-0.7 ± 5 %) is for natural waters, not fertilizer solutions. Measure EC after mixing."
No measured accuracy is claimed. A requested EC (`--ec`) is only compared with the range:
"compatible with the estimated range; target attainment unverified", or "requested X mS/cm
is Y mS/cm from the estimated range". When you compare a
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
