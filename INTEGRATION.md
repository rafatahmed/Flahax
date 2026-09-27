# FlahaX consumer boundary

FlahaFAST integration is owned by the separate **FlahaFAST project**, by project-owner decision. This repository supplies the Python package, public API, CLI, tests and release evidence. It does not establish the current FlahaFAST deployment, feature flags, paths or database behavior.

## Supported package interfaces

- Python: `recommend`, explicit catalogue-equilibrium functions and delivery-planning types; see [usage](docs/usage.md) and [equilibrium delivery](docs/package-verification.md).
- CLI: `python -m flahax` or `flahax` consumes one JSON object on standard input and returns a JSON recommendation. A nonempty `salts` array is required; the CLI does not silently choose the packaged catalogue. Check process exit status and the result's `feasible` value; an error is not an empty successful recommendation.
- Nutrient targets/water use elemental ppm; recipe doses use g/L final solution. Equilibrium inputs use explicitly converted g/kg water and molal totals. Do not pass arbitrary application product rows into catalogue-only equilibrium APIs.

## Handoff to the FlahaFAST project

That project must choose and test its package version, deployment mechanism, timeout/error handling, default-off feature flag, review UI and snapshot contract. Preserve the existing flow when disabled and require explicit acceptance before applying a recommendation. External writes and hardware control need separate authorization.

No application adapter is implemented or certified here. The earlier host-specific integration proposal is superseded; Git history retains it, but it is not a release instruction. Optional roadmap P7 is external work, not an unfinished FlahaX package release requirement.
