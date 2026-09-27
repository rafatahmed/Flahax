# FlahaX documentation

## Start here

- [0.3.0 User Manual](../src/flahax/data/USER_GUIDE.md): the canonical, self-contained guide shipped inside the package.
- [Changelog](../CHANGELOG.md): new capabilities, compatibility notes and release status.
- [Core API and CLI](usage.md): formulation inputs and output fields.

## Planning API reference

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

## Maintainers and release preparation

- [Distribution verification](package-verification.md)
- [Release-readiness audit](release-readiness.md)
- [Publication checklist](publishing.md)

## Historical material — not the current API contract

- [Reduced-equilibrium model history](history/reduced-equilibrium-model.md)
- [Chemistry development history](history/full-fertilizer-development.md)
- [Original delivery design](delivery-control-design.md)
- [Initial reference kernels](equilibrium-kernel.md)

Scientific captures and failure reproducers remain in `tests/fixtures/phreeqc/`. Their provenance is retained rather than removed as unused documentation.
