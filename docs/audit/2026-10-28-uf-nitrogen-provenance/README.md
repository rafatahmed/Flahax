# UF tomato nitrogen provenance (2026-10-28)

## Decision

The five University of Florida tomato-stage presets stay **retired**. They are
not restored to `src/flahax/data/library.json`. #202 retirement stands.

## Removal

Commit `d6a42dd` (`fix: remove extension-based presets and agronomic advice`,
Refs #202) removed the presets from the packaged catalogue. Migration text:
`docs/site/start/migration.md` (“Removed agronomic presets and advice”).
Executable pin: `tests.test_feed_ph_guidance.FeedPhGuidanceTests.test_retired_presets_are_not_selectable`.

## Pre-removal nitrogen mislabel

Before removal, the five packaged targets stored these values under key
`N_NO3` (nitrate-N):

| Preset | Stored key | Value (mg/L) |
|---|---|---|
| Tomatoes - till First Cluster (U of Florida) | `N_NO3` | 70 |
| Tomatoes - Second Cluster (U of Florida) | `N_NO3` | 80 |
| Tomatoes - Third Cluster (U of Florida) | `N_NO3` | 100 |
| Tomatoes - Fourth Cluster (U of Florida) | `N_NO3` | 120 |
| Tomatoes - to termination (U of Florida) | `N_NO3` | 150 |

Primary source UF/IFAS CV216 Table 1 labels that column **N** (total elemental
nitrogen), not nitrate-N alone. The same article counts ammonium nitrate toward
N. Storing those figures as `N_NO3` misclassified total N as a nitrate-only
target.

Source: <https://edis.ifas.ufl.edu/publication/CV216>

Read-only nitrogen audit evidence (sibling checkout, not shipped here):
`outputs/nitrogen-basis-audit-2026-10-28/` on the main FlahaX worktree.

## Future re-ship rule

If these formulas are ever reintroduced, nitrogen targets must use aggregate
elemental **`N`** (nutrient ledger from the core-contract spine), with values
70 / 80 / 100 / 120 / 150 matching the CV216 total-N column. Do **not** store
them again as `N_NO3`. Form-specific keys remain available only when the source
states a form split.

Cucumber / Howard Resh catalogue nitrogen keys are out of scope for this note
and stay unchanged until a separate primary-source audit.
