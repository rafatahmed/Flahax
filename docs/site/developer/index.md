# Developer and researcher guide

This guide is for people who call FlahaX from Python, build on its chemistry, or check its
evidence. FlahaX is pure Python with no third-party runtime dependencies; every public function
has a docstring and is listed in the [Python API reference](../reference/api.md).

```{mermaid}
---
caption: How the package fits together
---
flowchart TB
    subgraph entry[Entry points]
        CLI1[flahax mix<br/>mix_cli, mix_tui]
        CLI2[flahax batch<br/>batch_cli]
        CLI3[flahax JSON and planning<br/>__main__, planning_cli]
    end
    subgraph plan[Planning]
        WF[plan_fertilizer_workflow<br/>fertilizer_workflow]
        PH[plan_coupled_ph<br/>ph_adjustment]
        TK[group_tanks, prepare_stocks<br/>tank_grouping, stock_volumes,<br/>stock_solubility]
    end
    subgraph core[Core]
        EN[recommend<br/>engine: NNLS fit]
        EQ[equilibrium<br/>aqueous_model, mixed_equilibrium]
        MA[materials<br/>materials, material_chemistry]
        WA[water<br/>measured_water]
    end
    OUT[summarize_batch, render_report,<br/>render_batch_sheet<br/>grower_report, grower_sheet]
    entry --> plan
    plan --> core
    plan --> OUT
```

## In this guide

| Page | What it covers |
|---|---|
| [Python API in practice](python-api.md) | `recommend`, its inputs and results, tolerances, ceilings and feed-pH notes |
| [Water, targets and acids](water-to-delivery.md) | The workflow from a water analysis to the acid plan, measured-pH balancing and saturation indices |
| [Site planning](site-planning.md) | Interactive and JSON planning commands: water, acids, EC screening and injector sizing |
| [Conductivity](conductivity.md) | Irrigation EC25 from speciation and its bounds |
| [Delivery contracts](delivery-contracts.md) and [quantities](delivery-quantities.md) | Typed planning records, units and plan states |
| [Verification](verification.md) | The test suite, the live PHREEQC replay and the distribution checks |
| [Contributing](contributing.md) | Branches, code style, the changelog and the validation each change needs |

For the science behind the calculations, see the Explanation section, starting with
[How a recipe is calculated](../explanation/how-a-recipe-is-calculated.md). For the evidence, see
the [benchmark results](../evidence/benchmark-results.md) and the
[release evidence](../evidence/release-evidence.md).
