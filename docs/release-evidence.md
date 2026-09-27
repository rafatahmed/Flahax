# Delivery Planner Release Evidence

## Automated evidence

- Existing nutrient-solver regression suite passes unchanged.
- Delivery contract, stock, pH, pump, aggregate-plan, and chemistry fixture tests run dependency-free.
- A complete 100 L fixture composes a feasible recipe, compatible stock, measured-curve pH plan, calibrated command, and audit record; it must transition through `validated`, `operator-approved`, `executed`, and `verified` explicitly.
- A high-alkalinity (`500 mg/L as CaCO3`) measured-curve fixture confirms a bounded 20 mL initial nitric-acid dose for 100 L and retains the required post-mix measurement.
- The calcium/phosphate incompatibility fixture fails closed when only one tank is supplied.
- Sensitivity evidence demonstrates visible effects from measured dose demand, reagent assay, injector ratio, and pump flow; temperature outside the source-qualified solubility range fails closed.
- Pump commands are planning values only; package code contains no hardware I/O.
- The checked-in PHREEQC inputs provide provenance for reduced activities, species, and saturation-index regressions. They are a dependency-free verification baseline, not a runtime dependency.

## P2/P3 end-to-end numerical acceptance

Validated on branch `p2p3-chemistry-completion`, Python 3.14, installed PHREEQC 3.8.6-17100. One coupled runtime model replaces disconnected chelate allocation. Base MINTEQ remains byte-for-byte unchanged; neither executable nor merged database is distributed.

| Requirement | Passing evidence |
|---|---|
| P2.5 reference verification | `tests/test_product_phreeqc.py`: 10 product/target families and 11 phase families, exact live replay, charge errors <= 0.1%, hashes, full species/activities/SI and phase amounts within declared tolerances |
| P2.7 full fertilizer model | `tests/test_chemistry_acceptance.py`: all 28 catalogue conversions, 197 aqueous entries/28 phases, simultaneous balances, Davies/temperature rejection, phase complementarity and convergence; `docs/chemistry-coverage-matrix.md` resolves aliases before extensions |
| P3.7 acid/base coverage | Actual mixed doses -> initial solve -> nitrate addition -> same target solve. Corrected Fix_H+ and independent nitrate titration agree; tests verify component/charge conservation and post-mix measurement requirement |
| Evidence preservation | `tests/test_preserved_chemistry_evidence.py` hashes six original successes and all diagnostic artifacts; `tests/fixtures/phreeqc/failures/README.md` explains the reduced failure ladder |

Exact validation commands (PowerShell sets `$env:PYTHONPATH='src'`, equivalent to the first command below):

```text
PYTHONPATH=src python -m unittest discover -s tests -t .
python -m compileall -q src
git diff --check
git status
```

The complete unittest run passes **100 tests with zero failures/errors/skips**, including installed-PHREEQC live execution. Compilation and whitespace validation pass. Numerical tolerances and regeneration commands are in `reference-fixtures.md`; executable/base/extension and output hashes are in each fixture's JSON. The closure commit is the commit containing this acceptance record (not an invented self-referential hash).

This accepts the explicitly selected project parameterization, not universal chemical accuracy. In particular the inherited literature-derived Dtp/Edd profile and its activity/concentration and stereoisomer assumptions are disclosed in `sources/flahax-chelate-thermodynamic-profile.md`. The original closure left independent review and lot-specific experimental validation to G6. The owner-amended computational scope below supersedes that release requirement without claiming experimental validation.

## Package and delivery continuation — 2026-09-27

Branch: `codex/package-verification-delivery`, based on merged main `33febd41e1f2854c99275994cc98eaeaf1f0cc41`. No chemistry database, golden fixture or failure reproducer was changed. Assessor: **Rafat Al Khashan**, as designated by the project owner. The [computational assessment](computational-review.md) separates that designation from automated evidence and does not fabricate a personal signature.

| Requirement | Observed evidence | Acceptance |
|---|---|---|
| P5.5 equilibrium delivery | `tests/test_equilibrium_delivery.py`: explicit g/L-to-g/kg-water mapping, HNO3 assay/density, nitrate rescoring, source hashes, dedicated acid command, composed-plan transitions, target reference and rejection guards | Pass |
| P6.6 distributions | `tools/verify_distribution.py`: independent wheel/sdist installations outside checkout; Python 3.13.15 resource hashes, public exports, chemistry/delivery numerical examples and both CLI entry points agree; no required runtime dependencies or bundled executable. Earlier Python 3.14 installs also passed. | Local pass; hosted supported-version matrix outstanding |
| P6.7 live reference | Full suite runs pinned PHREEQC with zero skips; fresh official MSI extraction verifies installer/executable/base hashes. `tests/test_live_reference_policy.py` confirms required-live absence fails rather than skips. New hosted job retains replay logs. | Local pass; hosted job outstanding |
| P6.8 / amended G6 | Conservation, convergence, reference agreement, delivery guards and distribution checks recorded in `computational-review.md`; assessor Rafat Al Khashan | Bounded computational assessment passes; not independent review, formal proof or laboratory certification |
| P7 | No consumer contract or external integration implemented | Optional, not started |

Exact final local suite command (PowerShell):

```powershell
$env:PYTHONPATH = 'src'
$env:FLAHAX_REQUIRE_PHREEQC = '1'
py -3.13 -m unittest discover -s tests -t .
```

Result: **107 tests in 108.796 seconds, OK, zero skips**. This includes the original chemistry evidence and new delivery/live-reference policy regressions.

Pre-commit replay after the README update: **107 tests in 129.919 seconds, OK, zero skips**. A preceding sandboxed run was blocked from writing its temporary merged database; rerunning with temporary-directory permission resolved that environmental error without changing chemistry or tests. `python -m compileall -q src tools`, `git diff --check` and the staged whitespace check also pass.

Clean distribution verification:

```powershell
$testPython = py -3.13 -c "import sys; print(sys.executable)"
.\.venv-verification\Scripts\python.exe tools/verify_distribution.py --python $testPython
```

Result: **PASS: isolated wheel and sdist installs, resources, public APIs and both CLI entry points**. The development environment contains the `build` frontend; see `package-verification.md` to reproduce. The generated local `build/distribution-verification.json` records artifact hashes and observations. Both installs reported 28 catalogue products, chemistry SHA-256 `aeb264a4edf1177102bc1a68fb4dc87de6c1ea9c94cd45ff462dcfc06a0ee575`, library SHA-256 `4ba103d202d9c5374ddd2f5a146dc3a725c34987b209b9575c59ab4465eb8343`, and synthetic delivery reagent volume `0.0003095719864150872 L`. Artifact hashes identify the tested build, not a promise of byte-identical future archive timestamps.

`tools/provision_phreeqc.ps1` was tested both against the existing installation and with a fresh destination under TEMP. It downloads the official pinned MSI, administratively extracts outside the checkout and verifies all three hashes without modifying the base database. This is reference tooling, not a package runtime dependency.

The hosted GitHub run inspected during this increment did not execute because of the account billing lock (run `36322890741`). Python 3.11/3.12 and the new hosted jobs have not been observed passing. No local result substitutes for that gate; account billing changes require the account owner.

## Historical reduced-model evidence (superseded)

The macro-ion target-pH/reagent fixture is now checked in: PHREEQC 3.8.6
`phreeqc.dat`, closed analytical inorganic carbon, 25 °C, and nitric acid.
The dependency-free Davies solver matches its acid amount within `0.0005
mol/kgw`; the broader activity/speciation comparison uses the declared `0.05`
tolerance. Chelated micronutrients and unspecified micro blends remain outside
this evidence because their ligand data are not present.

## Required external gates before operational use

- G2/G3: bounded mixed-product reference/model choices are implemented and numerically verified above; preserve their declared conditions and source-profile limitations.
- G6: for this planning-package release, the owner explicitly requested computational evidence without laboratory work; see the amended assessment above. Independent and physical validation are not claimed.
- P7: define a separate, read-only FlahaFAST interface contract; it is not implemented in the package.

## Release decision

The package remains a dependency-free **planning and verification prototype**. P2/P3 and owner-amended G6 computational acceptance do not authorize autonomous dosing, pump control, deployment or universal chemical certification. The supported-version hosted verification gate remains outstanding; this record does not authorize publication or automatic merging. P7 integration remains unimplemented.
