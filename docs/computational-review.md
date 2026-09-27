# G6 computational assessment — 2026-09-27

## Explicit scope amendment

The project owner requested mathematical evidence with no laboratory work for this release and designated **Rafat Al Khashan** as assessor. This supersedes the earlier G6 requirement for independent scientific and bench/site sign-off **for the planning-package release only**. The record distinguishes the named assessor from the automated verification evidence: it is not independent review, experimental validation, a formal proof over all possible inputs, or operational dosing certification. Naming the assessor does not fabricate a reviewer signature or laboratory results.

The accepted object is a bounded numerical implementation of the selected source-versioned model, not a claim that every selected equilibrium constant accurately represents every commercial lot. The disclosed Dtp/Edd activity/concentration and stereoisomer assumptions remain in [the source profile](sources/flahax-chelate-thermodynamic-profile.md).

## Computational acceptance criteria

| Criterion | Evidence and assessment |
|---|---|
| Product identity and units | All 28 catalogue products retain declared components. P5.5 matches both ID and name, converts batch salt grams using explicit kg water, and checks mass = g/L × L. No assumed unit-density conversion. |
| Equilibrium conservation | `test_chemistry_acceptance.py` and product/phase regressions enforce per-component 1e-9 relative + 1e-15 mol/kg-water residuals, including ligand and phase inventories. |
| Mass action and convergence | Simultaneous ligand order-invariance/mass-action tests; phase complementarity and finite iteration limits; explicit invalid-domain/nonconvergence errors. Agreement is established for the tested cases, not promised for arbitrary inputs. |
| Independent numerical reference | 21 PHREEQC golden families, raw captures and hashes, charge error <= 0.1%, declared Davies/reference tolerances, both nitrate titration and corrected Fix_H+ target proofs. This is an independently implemented reference calculation, not an independent human review. |
| Reagent/recipe feedback | `test_equilibrium_delivery.py`: HNO3 moles → assayed mass → density-qualified volume → added nitrate-N ppm; target rescoring, zero dose, maximum volume and nutrient tolerances; preservation of measured-curve API. |
| Delivery guards | Missing/contradictory input rejection; source hashes in audit; matching recipe and dedicated acid command/channel; target supersaturation/solid formation prevents validation; post-mix measurement remains required. |
| Distributed package | Wheel and sdist installed separately outside checkout with isolated imports; runtime data/export checks, zero runtime dependencies, numerical APIs and both CLI entry points. `tools/verify_distribution.py` emits observed values and artifact hashes. |
| Reference reproducibility | Fresh administrative extraction of the official pinned MSI into TEMP succeeded; installer, executable and database hashes verified; required-live replay succeeds without skips. Missing required PHREEQC is tested as a hard failure. |

## Assessment and release boundary

**Assessor:** Rafat Al Khashan (designated by the project owner).

**Computational assessment:** the automated evidence passes for the above tested, bounded planning capabilities, subject to the exact regression and distribution checks documented in [release evidence](release-evidence.md). Personal sign-off by the named assessor is not inferred from this designation. The assessment does not certify chemistry parameters beyond their selected documented convention.

**Remote release/merge gate remains separate:** GitHub Actions previously could not start because the repository account was billing-locked. Local results do not turn those failed remote checks into passes. Supported Python 3.11/3.12 remote validation and the new hosted jobs must be observed before claiming the entire CI gate complete. Python 3.13 local tests and installed-distribution checks provide evidence for that interpreter only; Python 3.14 checks are additional.

No publishing, automatic merging, deployment, external database write, pump action, or laboratory certification follows from this document. Optional P7 implementation belongs to the separate FlahaFAST project; it is not a FlahaX package release gate. This repository documents only its consumer boundary.
