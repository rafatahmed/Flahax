# Delivery Planner Release Evidence

## 0.3.1 publication - 2026-10-17

The owner authorized publication of 0.3.1 in the Claude Code session of
2026-10-17. Released revision: `main` at `586eddb` (merge of PR #10), tagged
`v0.3.1`. Route: manual Twine upload with the owner's PyPI token from the
Windows credential store; the token was never displayed or committed. No
GitHub Release was created, so the automatic publish workflow did not run.

| Step | Result |
|---|---|
| Version unused | `https://pypi.org/pypi/flahax/0.3.1/json` returned 404 before upload |
| Hosted CI on the release content | PR #10 run `39028824252` passed: Python 3.11-3.13 and `phreeqc-live` |
| Local regression | 153 tests, zero skips, live PHREEQC, Python 3.13.15, on `122a942` (same tree as `586eddb` except the merge) |
| Exact artifacts | Built by `tools/verify_distribution.py --artifacts-dir dist/0.3.1-final` from `586eddb`; clean wheel and sdist installs passed on Python 3.13.15 (builder 3.14.0); no PDF in the sdist |
| Metadata | `twine check --strict` passed for both files |
| Upload | 2026-10-17 11:34 UTC; PyPI simple index hashes match the local files |
| Fresh install from PyPI | New Python 3.13 environment, `pip install --no-cache-dir flahax==0.3.1`: version 0.3.1, 100 exports, packaged manual readable, `recommend` quick start returned six salts, `flahax --help` ran |

| Published file | SHA-256 |
|---|---|
| `flahax-0.3.1-py3-none-any.whl` | `508fabae05fcf4790fda9aab4ebbbe897a36a2158228d61242c845112345ce7b` |
| `flahax-0.3.1.tar.gz` | `526c1e770fdb10a1e5006348594a5ccbf1595061d2f96428ab9983bd3eccbddd` |

The audit-candidate hashes in the next section came from an earlier revision
and are superseded by these.

**0.3.0 yanked on 2026-10-17** by the owner in the PyPI web interface, after
0.3.1 was live, with the public reason "Superseded by 0.3.1". The project's
management page lists 0.3.0 under yanked releases. The yank was made because
the 0.3.0 sdist contains the YaraVita PDF; yanked files stay downloadable by
exact pin (`flahax==0.3.0`).

## 0.3.1 release audit - 2026-10-17

Audited revision: `main` at `2e257d5` (merge of PR #7), then the audit commit
`7d4ef15` on `release/0.3.1-audit`, which only excludes the YaraVita PDF and
updates status documents. Assessor: Rafat Al Khashan with Claude Code
assistance. This is release-readiness evidence, not publication authorization.
Version 0.3.1 remains unpublished; PyPI's latest release is 0.3.0.

| Check | Result |
|---|---|
| Version alignment | `0.3.1` in `pyproject.toml`, `flahax.__version__`, `CITATION.cff`, user manual and API reference; changelog section `0.3.1 - Unreleased`; tag `v0.3.1` not yet created |
| Hosted CI on `2e257d5` | Run `38967066279` (2026-10-16) passed: Python 3.11, 3.12 and 3.13 each ran 153 tests, OK with 2 skips (live replay, covered by the dedicated job) plus isolated wheel/sdist verification; `phreeqc-live` ran 6 tests, OK, zero skips, with hash-pinned PHREEQC 3.8.6 |
| Local regression, `2e257d5` | 153 tests passed in 352.243 s on Python 3.13.15, zero skips, `FLAHAX_REQUIRE_PHREEQC=1` |
| Local regression, `7d4ef15` | 153 tests passed in 297.943 s on Python 3.13.15, zero skips, `FLAHAX_REQUIRE_PHREEQC=1`; `compileall` passed |
| Public API compatibility against the published 0.3.0 wheel | 86 exports retained, none removed; 14 added (100 total). Only `EquilibriumPhPlan` (new trailing field `incidental_assessment`, default `None`) and `plan_equilibrium_delivery` (new keyword-only `maximum_concentrations`, default `None`) changed, both backward compatible |
| Distribution contents | Finding: the YaraVita micronutrient guide PDF (3.6 MB) was tracked in Git since 2026-09-26 and shipped in the published 0.3.0 sdist, contrary to the local-only policy for manufacturer PDFs. Fixed in `7d4ef15`: untracked, excluded in `MANIFEST.in`, added to the verifier's leak check, hash recorded in the [source review](source-sheet-review.md). Git history and the uploaded 0.3.0 sdist still contain it |
| Isolated distribution check, `7d4ef15` | `tools/verify_distribution.py` passed with the local PDFs present in the checkout: clean wheel and sdist installs on Python 3.13.15 (builder 3.14.0), seven manual examples, 28 catalogue products, all public exports, both CLI entry points; no PDF in either artifact (sdist 389 files, 3,373,066 bytes) |
| Metadata | `twine check --strict` passed for both artifacts |
| Packaged resources | `USER_GUIDE.md` `b88bf40e5eba2818c0631c60c2342ebe741c1135eac323f0870e3153e91c0c21`; `API_REFERENCE.md` `14f33ef90cd3d5e2ae744109603659891bfd8bceb4bc7f7b21bb7a12f35ecea2`; `chemistry_25c.json` `ad87363818ccc2471c1343a0791f9ae63798bc0b3530b5b710344aff3077188f`; `library.json` `4ba103d202d9c5374ddd2f5a146dc3a725c34987b209b9575c59ab4465eb8343` |

Audit-candidate hashes from `7d4ef15` (this evidence record changes the sdist,
so the publication artifacts must be rebuilt from the final reviewed revision
and hashed again):

| Artifact | SHA-256 |
|---|---|
| `flahax-0.3.1-py3-none-any.whl` | `5645c8fb79ccf22144c77afec6704ed477a80e7e2c4388314619dcde3f28d9e2` |
| `flahax-0.3.1.tar.gz` | `45c2a729602456ba6ece6007c8b0095d69df15342d4630b8230cb1cae4106731` |

Remaining before publication, per the [publishing checklist](publishing.md):
explicit owner authorization; a final build of the exact approved artifacts
with recorded hashes; upload through the approved route; PyPI metadata and
fresh-install verification; and the publication date and `v0.3.1` tag. Hosted
CI must also pass on the final revision that includes this audit.

## 0.3.1 documentation audit - 2026-10-02

The merged preparation branch was audited on `release/0.3.1-documentation`.
See [audit findings and maintenance policy](documentation-maintenance.md).
No numerical algorithm, thermodynamic data, fixture or product scope changed.

The offline user manual now contains seven independently executed Python
examples. The generated API reference covers all 100 top-level public exports,
including signatures and result-record fields. Tests detect reference drift
and execute the README quick start. The recommendation dose-order contract
was corrected in the guide and source docstring.

Clean wheel and sdist checks passed on Python 3.13.15 (builder: Python 3.14.0),
using `tools/verify_distribution.py --report build/documentation-0.3.1-distribution.json`
with the explicit Python 3.13 interpreter. Both installations executed all seven
manual examples and checked API coverage and byte-identical reference resources.
Resource SHA-256 values:

| Resource | SHA-256 |
|---|---|
| `USER_GUIDE.md` | `b88bf40e5eba2818c0631c60c2342ebe741c1135eac323f0870e3153e91c0c21` |
| `API_REFERENCE.md` | `14f33ef90cd3d5e2ae744109603659891bfd8bceb4bc7f7b21bb7a12f35ecea2` |

Full regression (before adding the README-only test):
`PYTHONPATH=src FLAHAX_REQUIRE_PHREEQC=1 py -3.13 -m unittest discover -s tests -t .`
passed **152 tests in 190.122 seconds, zero skips**, including live PHREEQC.
Set these variables with `$env:...` in PowerShell as shown below.

The subsequent README test and maintenance-page additions were checked with
`PYTHONPATH=src py -3.13 -m unittest tests.test_release_hygiene`: **5 passed**.
The reference freshness check passed on Python 3.13 and 3.14. Compilation and
`git diff --check` passed. These are local checks, not a hosted-CI result or
publication authorization. Version 0.3.1 remains unpublished.

## 0.3.1 preparation - 2026-10-01

Branch: `release/0.3.1-site-planning`. This is local preparation, not a new
published release or a hosted-CI pass. See [current status](development-status.md)
for capability boundaries and [conventions](../CONTRIBUTING.md) for branch policy.

Validation commands (PowerShell; pinned PHREEQC remains outside the checkout):

```powershell
$env:PYTHONPATH = 'src'
$env:FLAHAX_REQUIRE_PHREEQC = '1'
py -3.13 -m unittest discover -s tests -t .
py -3.13 -m compileall -q src examples tools
git diff --check
.venv-verification/Scripts/python.exe tools/verify_distribution.py --python C:/Users/rafat/AppData/Local/Programs/Python/Python313/python.exe --report build/release-0.3.1-distribution.json
```

The distribution check passed: isolated wheel and sdist installations on
Python 3.13.15, four shipped manual examples, all public exports, both original
CLI entry points, the EC planning command, injector sizing, and missing-water-
chemistry rejection. The build interpreter was Python 3.14.0. No runtime
dependency was added. The check also verified byte-identical catalogue/model
resources and exclusion of the four local-only manufacturer PDFs.

Full regression result: **151 tests passed in 290.462 seconds on Python
3.13.15, zero skips**, with `FLAHAX_REQUIRE_PHREEQC=1`. This includes the
preserved product/phase references, four additional acid replays, conservation,
workflow, EC boundary, stock-report, CLI and release-hygiene checks. A separate
final manual/export/documentation-link check passed all three tests.

Development-build hashes (before this final documentation record; these are
not publication artifacts and must be rebuilt from the reviewed release revision):

| Artifact | SHA-256 |
|---|---|
| `flahax-0.3.1-py3-none-any.whl` | `e05951bfe6a9be5cd329d297c35d9d46178293ea97e052f09c3ef7db9f8b1512` |
| `flahax-0.3.1.tar.gz` | `00624d1530d0bf5d89a3aa05b4340eb667ea9f7be92bc9e61951d0f6459121c8` |

Compilation, final documentation-link/manual/export checks and whitespace
validation passed. The catalogue and thermodynamic data are unchanged. The
historical evidence below is retained, not reclassified as a 0.3.1 result.

## Authorized publication exception — 0.3.0

On 2026-09-27 the owner explicitly approved manual PyPI publication using the verified local evidence despite the GitHub Actions billing blocker. This exception applies to the hosted publication gate for 0.3.0; it does not convert blocked checks into passes or imply independent/experimental validation. The release candidate passed clean-install/manual/metadata checks. On 2026-09-28, PyPI metadata confirmed both artifacts were uploaded on 2026-09-27. A fresh isolated Python 3.13 installation of the published wheel passed version/import checks, all four manual examples and both CLI entry points. See the post-release audit in `release-readiness.md`; candidate-sdist evidence remains separate.

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

Package-verification work was based on merged main `33febd41e1f2854c99275994cc98eaeaf1f0cc41`. No chemistry database, golden fixture or failure reproducer was changed. Assessor: **Rafat Al Khashan**, as designated by the project owner. The [computational assessment](computational-review.md) separates that designation from automated evidence and does not fabricate a personal signature.

| Requirement | Observed evidence | Acceptance |
|---|---|---|
| P5.5 equilibrium delivery | `tests/test_equilibrium_delivery.py`: explicit g/L-to-g/kg-water mapping, HNO3 assay/density, nitrate rescoring, source hashes, dedicated acid command, composed-plan transitions, target reference and rejection guards | Pass |
| P6.6 distributions | `tools/verify_distribution.py`: independent wheel/sdist installations outside checkout; Python 3.13.15 resource hashes, public exports, chemistry/delivery numerical examples and both CLI entry points agree; no required runtime dependencies or bundled executable. Earlier Python 3.14 installs also passed. | Local pass; hosted supported-version matrix outstanding |
| P6.7 live reference | Full suite runs pinned PHREEQC with zero skips; fresh official MSI extraction verifies installer/executable/base hashes. `tests/test_live_reference_policy.py` confirms required-live absence fails rather than skips. New hosted job retains replay logs. | Local pass; hosted job outstanding |
| P6.8 / amended G6 | Conservation, convergence, reference agreement, delivery guards and distribution checks recorded in `computational-review.md`; assessor Rafat Al Khashan | Bounded computational assessment passes; not independent review, formal proof or laboratory certification |
| P7 | Consumer boundary documented in `INTEGRATION.md`; implementation belongs to separate FlahaFAST project | External; not a package release gate |

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

## Release-readiness cleanup

The release-readiness cleanup adds metadata/export and documentation-link checks, fixes expired-date-prone test fixtures without changing runtime expiry policy, and archives superseded notes without deleting scientific evidence. Final local validation: `$env:PYTHONPATH='src'; $env:FLAHAX_REQUIRE_PHREEQC='1'; py -3.13 -m unittest discover -s tests -t .` — **109 tests in 142.086 seconds, OK, zero skips**. Clean wheel/sdist verification passes after the packaging changes; compilation and whitespace checks pass. The corrected explicit-salts CLI example returns `feasible: true`.

Hosted PR #3 run `36345628921` was attempted and all four jobs were prevented from starting by the account billing lock. Actions is enabled; P6.6/P6.7 hosted acceptance and merge remain blocked. See [release-readiness audit](release-readiness.md). FlahaFAST implementation is assigned to the separate FlahaFAST project and is not a package release gate.

## 0.3.0 preparation evidence

Version metadata and citation now identify the owner-requested **0.3.0** candidate; no publication date is asserted. The user manual is a bundled package resource, and all four Python examples execute in source tests and both clean installed distributions. The build report includes the manual SHA-256, version, example count and distribution hashes. The documentation index and changelog distinguish current guidance from historical provenance.

Final candidate source run: `$env:PYTHONPATH='src'; $env:FLAHAX_REQUIRE_PHREEQC='1'; py -3.13 -m unittest discover -s tests -t .` — **110 tests in 127.103 seconds, OK, zero skips**. Compilation and whitespace checks pass. `tools/verify_distribution.py --python <Python-3.13-executable> --artifacts-dir <new-empty-output-directory>` passes independent wheel/sdist installation, all manual examples and numerical/resource checks. `python -m twine check dist/0.3.0/*` passes for both first candidate archives. These are local build/metadata checks, not a PyPI upload or hosted-CI pass.

Public PyPI metadata checked during preparation lists 0.2.0 and no 0.3.0 release. Recheck before publication. Final review, hosted verification and explicit publication authorization remain required; no scientific fixture or runtime chemistry was changed in this version/manual preparation.

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
