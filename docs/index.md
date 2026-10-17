# FlahaX documentation

## Start here

- [User manual](../src/flahax/data/USER_GUIDE.md) (version 0.4.0): the canonical, self-contained guide shipped inside the package.
- [Changelog](../CHANGELOG.md): new capabilities, compatibility notes and release status.
- [Core API and CLI](usage.md): formulation inputs and output fields.
- [Complete public API reference](../src/flahax/data/API_REFERENCE.md): generated signatures, source docstrings and result-record fields for every top-level export; shipped offline.

## Planning API reference

- [Capability status and next work](development-status.md): implemented features, unresolved limits and evidence boundaries.

- [Interactive site planning](site-planning.md): user-specific water, nitric/phosphoric acids, calculated EC screening and injector flow requirements.
- [Fertilizer sheet review](source-sheet-review.md): exact-brand data, source hashes and applicability limits.

- [Stock and irrigation EC planning](conductivity.md): recipe-calibrated conductivity, meter TDS scale and injection/pump connection.
- [Stock conductivity service (design, not implemented)](stock-conductivity-service-design.md): proposed contract, model layers, evidence and test plan for conductivity of concentrated stocks and their dilutions.

- [Runnable capability examples](../examples/README.md): pepper formulation, chemistry, acids, stocks, titration, delivery and CLI reports (source checkout).

- [Water-to-delivery workflow](water-to-delivery.md): water nutrient subtraction, incidental nutrient review, measured-pH water balancing (0.4.0), complete-analysis pH and standard nitric/phosphoric selection.

- [Quantities and batch recipes](delivery-quantities.md)
- [Input contracts and audit records](delivery-contracts.md)
- [Stock assignment](stock-planning.md)
- [Measured-curve pH planning](ph-planning.md)
- [Equilibrium-to-delivery API and runnable example](package-verification.md)
- [Consumer boundary](../INTEGRATION.md): FlahaFAST implementation belongs to its separate project.

## Scientific model and evidence

- [Formulation method](method.md)
- [Current mixed-equilibrium model](fertilizer-equilibrium-model.md)
- [Coverage summary](full-fertilizer-chemistry.md) and [exact reaction/phase matrix](chemistry-coverage-matrix.md)
- [Reference fixture reproduction](reference-fixtures.md)
- [Chelate parameter assumptions](sources/flahax-chelate-thermodynamic-profile.md)
- [Computational assessment](computational-review.md), [release evidence](release-evidence.md) and [roadmap](implementation-roadmap.md)

## Maintainers and development

- [Development and branch conventions](../CONTRIBUTING.md)
- [Documentation maintenance](documentation-maintenance.md): canonical sources, function-documentation checks and the 0.3.1 audit findings.

- [Development roadmap](development-roadmap.md): priorities, hardening gates and expansion opportunities.
- [Distribution verification](package-verification.md)
- [Release readiness](release-readiness.md)
- [Publishing: hardened release workflow and checklist](publishing.md)

## Positioning and publications

- [Landscape comparison and SWOT](landscape-comparison-swot.md): how FlahaX compares with other nutrient tools.
- [Publication drafts](publication/README.md): JOSS paper, field-trial article, story piece and worked example (drafts, not shipped).

## Historical material — not the current API contract

- [Reduced-equilibrium model history](history/reduced-equilibrium-model.md)
- [Chemistry development history](history/full-fertilizer-development.md)
- [Original delivery design](delivery-control-design.md)
- [Initial reference kernels](equilibrium-kernel.md)

Scientific captures and failure reproducers remain in `tests/fixtures/phreeqc/`. Their provenance is retained rather than removed as unused documentation.
