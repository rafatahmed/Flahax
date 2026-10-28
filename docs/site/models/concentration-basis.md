# Concentration and solvent mass

Mass concentration uses final solution volume. Molality uses solvent mass
([IUPAC definition](https://goldbook.iupac.org/terms/view/M03970)). For component
molar mass `M` in g/mol, final solution volume `V` in L and final solvent mass `W` in kg:

```
mol/kg water = (mg/L) * V / (1000 * M * W)
mg/L = (mol/kg water) * M * 1000 * W / V
g product/kg water = (g product/L) * V / W
```

The component basis must match: nitrate-N uses nitrogen mass, sulfate-S uses sulfur
mass, and urea contains two nitrogen atoms per molecule. Density alone does not
determine solvent mass: `W = density * V - complete nonwater mass`. Elemental
nutrient sums omit counterions and other material and cannot supply nonwater mass.

## Enter the final inventory

Water JSON accepts either pair alongside `mg_per_litre` and `measured_ph`:

```json
{"final_volume_litres": 1000, "water_mass_kg": 997}
```

```json
{"final_volume_litres": 1000, "density_kg_per_litre": 1.002, "nonwater_mass_kg": 5}
```

Both describe 997 kg final solvent in 1000 L solution. This ratio scales to the
requested batch volume. The fixed final inventory includes reagent carrier water
and water released by dissolved hydrates. It is not just the starting water charge;
do not add those contributions twice. Revise the inventory when changing material
or preparation conditions. Dissolution and volume contraction are not predicted.
Incomplete, conflicting and nonpositive bases are rejected. Detection limits use
the same basis; laboratory mg/L remains unchanged for nutrient acceptance.

## Account for source, reagent and hydrate water

```python
from flahax import SolventBasis

basis = SolventBasis.from_water_ledger(
    1.0, source_water_kg=0.9,
    reagent_carrier_water_kg=0.04, dissolved_hydrate_water_kg=0.02,
)
assert abs(basis.water_mass_kg - 0.96) < 1e-12
```

The entries must be disjoint and quantified; unknown water is not zero. Here a
100 g reagent contains 60 g solute and 40 g water; a 60 g hydrate contributes 40 g
nonwater material and 20 g water. Final mass is 1.06 kg: 0.96 kg solvent and 0.10 kg
nonwater material. Final volume is independently supplied, not obtained by adding
ingredient volumes. Nutrient assays do not establish these water contributions.

## Assumptions and uncertainty

Legacy JSON, interactive analyses and `ro` retain a **reported assumption** of
1 kg final solvent/L. JSON summaries carry `concentration_basis`; reports and batch
sheets show the warning. Its uncertainty is unquantified. Explicit mass/density
inputs are declared, not independently verified; uncertainty is not inferred from
printed precision. The calculation does not automatically solve a changing solvent
inventory during reagent selection.

`--water-share` is a volume share; molal dilution uses the corresponding solvent
mass share. Ion-free blend water assumes 1 kg solvent/L and additive solution
volumes, both disclosed. Enter a measured final mixture directly when inappropriate.

These checks establish mathematical accounting, not physical validation, reaction
completeness, EC applicability, stock dissolution or field performance.
