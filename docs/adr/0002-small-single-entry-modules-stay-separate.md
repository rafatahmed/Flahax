# Small single-entry modules in the joint and ratio groups stay separate

Date: 2026-11-26

The `joint_*` and `ratio_*` groups hold many small modules, each reached through one or two names: `joint_active_set` (281 lines), `joint_sensitivity` (180), `joint_polishing` (125), `joint_optimality` (114) and `joint_linear` (96) are imported only by `joint_solver` or `joint_workflow`, and `ratio_assay_documents` and `ratio_physical_uncertainty` serve one parent each. An architecture review on 2026-11-26 asked whether to fold them into their callers. We keep them: each is a deep module (a small interface over a real implementation), and `joint_solver` is already 1,175 lines.

## Considered options

- **Fold the single-caller modules into their caller:** rejected. Deleting them would move about 800 lines into `joint_solver` and make it harder to read, not concentrate any complexity, and their tests would lose a separate target.
- **Merge `ratio_stocks` into `ratio_product_stocks`:** rejected. They are layers, not duplicates: `ratio_stocks` validates and prepares element-basis stocks, and `ratio_product_stocks` builds product-mass stocks on top of it. `ratio_recipe` and `batch_volumetric_stocks` each need both.

## Consequences

- A module is worth folding only if its interface is nearly as large as its implementation, or if deleting it would make complexity reappear in several callers. Count the names a module exports against its size before proposing a merge.
