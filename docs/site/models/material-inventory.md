# Material inventory before fitting

`material_inventory(record, material=...)` returns the nutrient mass percentages
used by the fit and analytical component moles per gram used by chemistry. The
fit includes formula-derived counterions before selecting doses. For example,
13% Fe as sodium Fe-EDTA also supplies `13 / 55.845 * 22.989769` percent Na.
A sodium maximum can therefore change the selected iron source.

The source record is unchanged. Declared nutrient assays remain authoritative;
missing nutrients are derived only from supported formula/ion information.
Assayed sodium is not added a second time. `recommend` includes a
`materialInventory` entry for each selected material with its identity, published
dose, components, nutrient percentages and limitations. Published doses still
use the existing six-decimal representation; this change does not qualify dose
rounding or all hard-limit paths.

## Conserved components and nutrient projection

`component_nutrient_masses(totals)` maps component moles to nutrient grams while
retaining the input denominator. Both iron valences contribute elemental Fe;
urea contains two N atoms. EDTA, DTPA, EDDHA and citrate remain named organic
components. Their nitrogen is not available nitrate, ammonium or urea, and their
carbon is not inorganic carbonate. Potassium carbonate contributes two K per
inorganic carbon; citrate retains its own component.

Water and pH reagent nutrient supply use this same projection before each recipe
fit. Measured analytical water remains distinct from charge-balanced model water.
Reagent components also enter the equilibrium solve. Conversion between g/L and
g/kg water requires the [declared final solvent basis](concentration-basis.md).
Carrier water, hydrate water and unassayed remainder are not inferred from a
nutrient sum. This is analytical component accounting, not complete H/O mass
closure, reaction-data qualification or physical validation.

## Incomplete and conflicting composition

An undefined material can still provide its declared nutrient assay to a linear
fit. Its inventory reports `status: assay_only`, no component inventory and a
reason; chemistry rejects unsupported composition. Pass a resolved grade/lot
through `material=` when inspecting that material directly.

For disclosed blends, `component_nutrient_percent` records ingredient-derived
chemistry and `assay_component_difference_percent` records label minus component
percentages. A nonzero difference needs reconciliation; the two inventories are
not interchangeable. Tiny floating-point differences can also occur for a
consistent assay. Existing blend provenance flags remain applicable. Product
eligibility and explicit restricted-ion consent still follow the declared assay;
this change makes no new promise about those policy gates.

Independent tests check Fe-EDTA stoichiometry, sodium-free alternative selection,
all catalogue projections, no double counting, reagent stoichiometry, water-mass
scaling, and reordered inputs. These checks establish accounting consistency;
independent reaction/domain qualification is a separate stage.
