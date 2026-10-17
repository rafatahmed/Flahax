# Water-to-delivery development status

Updated 2026-10-17 (0.3.1 release audit). The 0.3.1 preparation is merged on
`main`; see the [0.3.1 release audit](release-evidence.md#031-release-audit---2026-10-17).
These changes prepare **0.3.1, not yet published**. Version 0.3.0 is the
previous published baseline. Local verification artifacts are not a release
authorization; hosted checks, review and publication approval remain separate.

## Capability and boundary matrix

| Capability | Implemented evidence | Remaining boundary |
|---|---|---|
| Nutrient targets minus source-water contribution | `fertilizer_workflow.py`, `test_water_workflow.py`, pepper example | User supplies water; nutrient concentrations do not establish complete acid/base chemistry |
| Incidental zero/omitted-target nutrients | `nutrient_acceptance.py`, engine/delivery tests | Separate review or explicit maximum limits; no invented safe threshold |
| Calculated initial pH, mixed species/complexes/SI | `calculated_ph.py`, workflow, existing coupled solver and PHREEQC reference tests | Complete analytical totals, 25 C, closed carbon, explicit phase policy, Davies range |
| Industrial acid selection and product mass/volume | Standard workflow HNO3/H3PO4, `acid_selection.py`, four preserved lower-level PHREEQC acid fixtures | Supplied assay/density/provenance, nutrient and volume limits; no automatic dosing approval |
| Source-specific CLI | `planning_cli.py`, `__main__.py`, `test_site_planning.py` | Explicit JSON/interactive inputs, no default water or equipment model |
| No-new-measurements EC screening | `calculated_ec.py`, exact SQM anchors with source hash, regression tests | Pre-acid dilute approximation at 25 C, restricted loading, unknown accuracy; incomplete products yield no total |
| Optional measured-profile EC method | `conductivity.py`, synthetic regression profiles | Requires matching measured evidence when used; example profiles are fictional |
| A/B and acid report clarity | `pepper_stock_review.py`, HTML/Markdown/JSON examples and tests | Candidate grouping only; trace locations unresolved; no approved full pepper StockPlan |
| Stock planning API | Existing sourced compatibility/solubility/capacity checks | Caller must supply complete applicable records; absence from a pairwise table is not evidence of compatibility |
| Injector design flow and inventory | `injector_sizing.py`, batch/area arithmetic and tests | Pump/venturi/Dosatron operating-point data still needed for a specific model |
| Offline graphical capability report | `examples/run_all.py`, `visual_report.py`, `test_examples.py` | Separate pepper, manufacturer-screening and synthetic demonstrations; no cross-scenario dosing inference |

Paths in this matrix refer to `src/flahax/`, `tests/` or `examples/` as named.
See [site planning](site-planning.md), [water-to-delivery](water-to-delivery.md),
[EC methods](conductivity.md), [source review](source-sheet-review.md) and
[runnable examples](../examples/README.md) for executable instructions.

## Preserved boundaries

- No catalogue or thermodynamic database changes; frozen Fe-only DTPA/EDDHA
  chemistry remains unchanged.
- Existing successful fixtures and failure reproducers are preserved. Four
  additional lower-level acid fixtures remain even though the standard
  fertigation workflow offers only nitric and phosphoric acid.
- Source PDFs remain local and unchanged. Reviewed findings and SHA-256
  identities are versioned; four supplied manufacturer files are explicitly
  excluded from Git and sdist publication pending redistribution review.
- Page 66's acid-containing B concept is distinguished from the proposed
  dedicated acid channel. Recipe phosphoric acid is not counted again as
  extra pH correction. A two-tank-only full pepper system is not yet established.
- No new PyPI release, deployment, hardware operation or independent
  scientific sign-off is part of this increment. The preparation branches were
  merged to `main` through PRs #6 and #7.

## Next work, in order

1. Hosted verification passed on `main` at `2e257d5` (run `38967066279`,
   2026-10-16): Python 3.11-3.13 and the required live PHREEQC replay. The
   remaining 0.3.1 release steps are explicit publication authorization, the
   exact-artifact build and upload, and the fresh PyPI installation check.
2. Resolve exact commercial product assays and trace co-storage evidence for
   the pepper recipe; define volumes, ratios, temperature and acid hardware
   layout before promoting the candidate grouping to an approved stock plan.
3. Specify and validate a full-mixture/acid-adjusted conductivity model and
   a concentrated-stock model, retaining unsupported results until qualified.
4. Add sourced liquid operating curves and hydraulic inputs for manufacturer
   model matching; flow sizing alone is not model selection.
5. Stabilize serialization/CLI contracts, prepare a new version and rerun the
   publishing checklist before any separately authorized release. FlahaFAST
   integration remains in its own project.

## Verification

Final local verification is recorded in [release evidence](release-evidence.md).
Earlier incremental test counts in feature guides are dated historical runs,
not claims about the final branch test count. Source-sheet constants and
screening arithmetic tests establish transcription and implementation
correctness, not measured EC accuracy or physical stock compatibility.
