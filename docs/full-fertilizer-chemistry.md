# Full Fertilizer Chemistry Coverage

The current P2/P3 implementation is one source-versioned aqueous-equilibrium system. The authoritative [coverage matrix](chemistry-coverage-matrix.md) lists 197 aqueous entries and 28 phases. All 28 catalogue products convert to conserved analytical components before one simultaneous solve. See [the current model contract](fertilizer-equilibrium-model.md) and [release evidence](release-evidence.md).

## Current end-to-end coverage

| Acceptance family | Implementation | Independent evidence |
|---|---|---|
| Carbonate, sulfate, phosphate and Ca/Mg complexes | Native MINTEQ mass action and simultaneous balances | calcite, calcium_phosphate, gypsum, magnesium_salts phase captures |
| Nitrate, ammonium/ammonia, K/Na/Cl pairs | Conserved oxidation states; all eligible native pairs | mixed_products, struvite, mixed_target_ph_nitric |
| Fe/Mn/Zn/Cu, boron, molybdate | Native aqueous reactions and trace solid allocation | Six chelate products, CH-micro, trace-phase families, ferrous_phases |
| Fe-DTPA; Fe-o,o-EDDHA | Fe(III)-only 1:1 profiles and ligand protonation | fe_dtpa, fe_eddha; no non-Fe Dtp/Edd complexes |
| EDTA and citrate | Native protonated/hydrolysed complexes solved simultaneously | Four EDTA products, citrate, mixed_product_phases |
| Neutral urea | Conserved Ure inventory, two N per molecule; no instantaneous hydrolysis | Every-product conversion test and mixed_products |
| Nitric target pH | Same mixed model at both endpoints, added nitrate conserved | Corrected Fix_H+ capture, nitrate titration, conservation tests |

The closed-carbon, fixed-valence, 25 C, I <= 0.1 mol/kgw boundary is mandatory. Equilibrium allocation is not a kinetic prediction, and no fixture replaces stock compatibility rules or post-mix measurement. Assays are rounded elemental data: unlabelled counterions are not invented. Fixtures explicitly declare charge-balancing background electrolyte.

## Historical reference

Earlier reduced-model development notes are [archived separately](history/full-fertilizer-development.md). Legacy kernels and fixtures remain available for compatibility and regression evidence; they are not the current mixed-system planning contract.
