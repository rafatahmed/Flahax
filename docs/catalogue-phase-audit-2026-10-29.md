# Catalogue audit with current-main phase policy (2026-10-29)

Issue: https://github.com/rafatahmed/Flahax/issues/204

Runtime base: 12afceece3585be783f7bee86afa2eca468c7afa. The earlier checkout was 42 commits behind; its review exemptions, EC estimates and tank waivers do not describe current main.

## Fix

The audit now calculates dissolved chemistry with no enabled solid phases and calls the runtime saturation policy. Supersaturation is not converted into forced precipitation. Current main still blocks approval when phase-applicability evidence is missing; this is not proof that solids will form. No constants, thresholds or production policy are changed.

## Inputs and method

Frozen approved catalogue (Flaha Agri Tech Analysis Ver 0.0): tests/fixtures/catalogue-audit-2026-10-29.json. All 13 formulas; pure ion-free water, closed carbon, 25 C, no pH reagent and no pH/EC target bands. Each 100 L finished stock is diluted 1:100. Chemistry approximates 1 L final solution by 1 kg water. Total N replaces the separate nitrate target; positive ammonium targets remain, otherwise min(10% target N,21.01005 mg/L) is the ceiling.

Minimize worst relative nutrient error, then total product mass. This tie-break differs from the earlier minimum-ammonium audit; equally feasible doses can produce different pH. The production engine is not modified. Full-catalogue and EDTA-only runs are separate.

Chemistry-incompatible products are not silently corrected: the primary result retains its error. Separate alternatives omit potassium nitrate (updated assay charge inconsistency) and incompletely specified blends. Calculated pH in the table belongs to the alternative where marked.

## Reproduce
```powershell
$env:PYTHONPATH='src'
python tools/catalogue_workflow_audit.py --catalogue tests/fixtures/catalogue-audit-2026-10-29.json --output audit.json
python tools/catalogue_workflow_audit.py --catalogue tests/fixtures/catalogue-audit-2026-10-29.json --edta-only --output audit-edta.json
```

## Full updated catalogue

Input SHA256: 1a35b9aedeab752865793b93fe5b894d82ee74045d1355c0fc9ca103ff52ea0a

| Crop | Full fit error % | Chemistry recipe error % | Alternative | Calculated pH | EC | Phase | Tanks required |
|---|---:|---:|---|---:|---|---|---:|
| Cucumber (Howard Resh) | 8.190 | 8.204 | yes | 4.745 | not_supported | MnHPO4: evidence missing | 3 |
| DEFAULT | 3.548 | 9.237 | yes | 4.774 | not_supported | MnHPO4: evidence missing | 3 |
| Hoagland solution | 3.548 | 9.237 | yes | 4.774 | not_supported | MnHPO4: evidence missing | 3 |
| Lettuce 2 (Howard Resh) | 0.000 | 0.000 | no | 4.733 | not_supported | MnHPO4: evidence missing | 3 |
| Lettuce General (Howard Resh) | 5.211 | 5.581 | yes | 4.737 | not_supported | MnHPO4: evidence missing | 3 |
| Melons (Douglas Peckenpaugh) | 0.972 | 1.528 | yes | 4.692 | not_supported | MnHPO4: evidence missing | 3 |
| Pepper (Howard Resh) | 26.189 | 26.189 | no | 4.660 | not_supported | MnHPO4: evidence missing | 3 |
| Strawberry Drip Irrigation (schundler.com) | 34.199 | 34.199 | no | 4.841 | not_supported | MnHPO4: evidence missing | 3 |
| Strawberry Fruiting (growing edge) | 0.673 | 1.440 | yes | 4.815 | not_supported | MnHPO4: evidence missing | 3 |
| Tomato (Howard Resh) | 3.287 | 3.308 | yes | 4.758 | not_supported | MnHPO4: evidence missing | 3 |
| Tomato Stage.1 - 10-14 days (Howard Resh) | 3.110 | 5.315 | yes | 4.872 | not_supported | MnHPO4: evidence missing | 3 |
| Tomato Stage.2 - first cluster (Howard Resh) | 3.265 | 3.426 | yes | 4.778 | not_supported | MnHPO4: evidence missing | 3 |
| Tomato Stage.3 - to plant maturity (Howard Resh) | 28.898 | 28.898 | no | 4.664 | not_supported | MnHPO4: evidence missing | 3 |

EC: every calculated case returns ionic_strength_outside_phosphate_fit; no supported total EC is reported. Every phase screen flags MnHPO4 and blocks approval for missing applicability evidence, without allocating a solid. Stock data are screening_only or not_checked, not validated limits. No mixed-stock approval follows from these checks. More than two required tanks fails the requested equipment constraint.

## EDTA-only sources of Fe/Mn/Zn/Cu

Input SHA256: 1a35b9aedeab752865793b93fe5b894d82ee74045d1355c0fc9ca103ff52ea0a

| Crop | Full fit error % | Chemistry recipe error % | Alternative | Calculated pH | EC | Phase | Tanks required |
|---|---:|---:|---|---:|---|---|---:|
| Cucumber (Howard Resh) | 8.190 | 8.204 | yes | 4.745 | not_supported | MnHPO4: evidence missing | 3 |
| DEFAULT | 3.548 | 9.237 | yes | 4.774 | not_supported | MnHPO4: evidence missing | 2 |
| Hoagland solution | 3.548 | 9.237 | yes | 4.774 | not_supported | MnHPO4: evidence missing | 2 |
| Lettuce 2 (Howard Resh) | 0.000 | 0.000 | no | 4.738 | not_supported | MnHPO4: evidence missing | 3 |
| Lettuce General (Howard Resh) | 5.211 | 5.581 | yes | 4.737 | not_supported | MnHPO4: evidence missing | 3 |
| Melons (Douglas Peckenpaugh) | 0.972 | 1.528 | yes | 4.692 | not_supported | MnHPO4: evidence missing | 3 |
| Pepper (Howard Resh) | 26.814 | 26.814 | no | 4.667 | not_supported | MnHPO4: evidence missing | 3 |
| Strawberry Drip Irrigation (schundler.com) | 34.199 | 34.199 | no | 4.843 | not_supported | MnHPO4: evidence missing | 3 |
| Strawberry Fruiting (growing edge) | 0.673 | 1.440 | yes | 4.815 | not_supported | MnHPO4: evidence missing | 2 |
| Tomato (Howard Resh) | 3.287 | 3.308 | yes | 4.758 | not_supported | MnHPO4: evidence missing | 3 |
| Tomato Stage.1 - 10-14 days (Howard Resh) | 3.110 | 5.315 | yes | 4.872 | not_supported | MnHPO4: evidence missing | 2 |
| Tomato Stage.2 - first cluster (Howard Resh) | 3.265 | 3.426 | yes | 4.778 | not_supported | MnHPO4: evidence missing | 3 |
| Tomato Stage.3 - to plant maturity (Howard Resh) | 28.898 | 28.898 | no | 4.667 | not_supported | MnHPO4: evidence missing | 3 |

EC: every calculated case returns ionic_strength_outside_phosphate_fit; no supported total EC is reported. Every phase screen flags MnHPO4 and blocks approval for missing applicability evidence, without allocating a solid. Stock data are screening_only or not_checked, not validated limits. No mixed-stock approval follows from these checks. More than two required tanks fails the requested equipment constraint.

## Evidence limitations

This audit does not prove that no alternative fertilizer allocation could meet equipment/chemistry constraints; nutrient fitting does not jointly optimize those constraints. The full-catalogue nutrient optima pass 1% for Lettuce 2, Melons and Strawberry Fruiting. Their selected chemistry-supported alternatives pass 1% only for Lettuce 2. None is fully verified under the requested conditions. No new live PHREEQC replay or laboratory experiment was performed.

The fixed input is a reproducibility snapshot, not a production-catalogue replacement. Pending catalogue/engine work in the original checkout is excluded from this change.
