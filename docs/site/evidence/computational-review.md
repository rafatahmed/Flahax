# Computational assessment (G6)

G6 is the release gate for scientific review of the chemistry. This page
records how that gate was met for the planning package, on **2026-09-27**,
before the 0.3.0 release.

:::{note}
**In short.** The chemistry was accepted on computational evidence alone:
conservation, convergence and agreement with PHREEQC, checked by automated
tests. It was not reviewed by an independent scientist, not tested in a
laboratory or on a site, and is not a proof over all possible inputs or a
dosing certification.

The thermodynamic data assessed here have not changed since (see
[release evidence](release-evidence.md)). Capabilities added later, such as
measured-pH speciation in 0.4.0 and the EC estimate, are covered by their own
release records, not by this assessment.
:::

## Scope

The project owner asked for mathematical evidence with no laboratory work for
this release and named **Rafat Al Khashan** as assessor. This replaces the
earlier G6 requirement for independent scientific and bench or site sign-off,
**for the planning package only**.

The record keeps the named assessor apart from the automated evidence. It is
not independent review, experimental validation, a formal proof over all
possible inputs or operational dosing certification. Naming the assessor does
not stand in for a reviewer's signature or for laboratory results.

What was accepted is a bounded numerical implementation of the selected,
source-versioned model. It is not a claim that every selected equilibrium
constant represents every commercial lot accurately. The assumptions for the
DTPA and EDDHA chelates (`Dtp`, `Edd`) about activity versus concentration and
about stereoisomers are disclosed in the
[chelate extension](../models/flahax-chelate-thermodynamic-profile.md).

## Acceptance criteria

| Criterion | Evidence and assessment |
|---|---|
| Product identity and units | All 28 catalogue products keep their declared components. Equilibrium delivery (P5.5) matches products by ID and name, converts batch salt grams using explicit kg of water, and checks mass = g/L × L. No unit density is assumed. |
| Equilibrium conservation | `test_chemistry_acceptance.py` and the product and phase regressions hold each component to a 1e-9 relative plus 1e-15 mol/kg-water residual, including ligand and phase inventories. |
| Mass action and convergence | Tests show simultaneous ligand solutions are independent of order and satisfy mass action; phases meet complementarity within finite iteration limits; invalid domains and non-convergence raise explicit errors. Agreement is shown for the tested cases, not promised for arbitrary inputs. |
| Independent numerical reference | 21 PHREEQC golden families with raw captures and hashes, charge error ≤ 0.1 %, declared Davies and reference tolerances, and both the nitrate titration and the corrected PHREEQC `Fix_H+` target-pH proofs. This is an independently implemented calculation, not independent human review. See [PHREEQC reference fixtures](../models/reference-fixtures.md). |
| Reagent and recipe feedback | `test_equilibrium_delivery.py`: HNO₃ moles → assayed mass → density-qualified volume → added nitrate-N ppm; target rescoring, zero dose, maximum volume and nutrient tolerances; the measured-curve API is preserved. |
| Delivery guards | Missing or contradictory inputs are rejected; source hashes go into the audit; recipe, acid command and channel must match; target supersaturation or solid formation prevents validation; a post-mix measurement is still required. |
| Distributed package | Wheel and sdist installed separately outside the checkout with isolated imports; runtime data and exports, zero runtime dependencies, numerical APIs and both CLI entry points checked. `tools/verify_distribution.py` records observed values and artifact hashes. See [package verification](../api/package-verification.md). |
| Reference reproducibility | A fresh administrative extraction of the official pinned PHREEQC installer succeeded; installer, executable and database hashes verified; the required live replay runs without skips. A missing PHREEQC is tested as a hard failure when the replay is required. |

## Assessment

**Assessor:** Rafat Al Khashan, designated by the project owner.

**Result:** the automated evidence passes for the tested, bounded planning
capabilities above, subject to the regression and distribution checks in the
[release evidence](release-evidence.md). The assessment does not certify any
chemistry parameter beyond its documented convention. This record does not
replace a personal signature by the assessor.

**Hosted CI.** When this assessment was written, GitHub Actions could not run
because the repository account was billing-locked, so the Python 3.11 and 3.12
checks had not been observed, and local results were not counted as passes.
That gate has since been met: the 0.4.0 release ran the tests on Python 3.11,
3.12 and 3.13 and the live PHREEQC replay on hosted CI before publication (see
[0.4.0 publication](release-evidence.md#040-publication-2026-10-17)).

## What this does not authorize

No publishing, automatic merging, deployment, external database write, pump
action or laboratory certification follows from this document. Integration
with FlahaFAST (P7) belongs to that separate project and is not a FlahaX
release gate; this repository documents only the
[consumer boundary](https://github.com/rafatahmed/Flahax/blob/main/INTEGRATION.md).
