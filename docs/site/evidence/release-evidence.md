# Release evidence

This page is the release log: for each FlahaX version, what was checked, on
which revision, and with what result. Newest first.

:::{note}
**Current release: 0.6.0**, the latest publication recorded on this page, dated
2026-10-24. Its exact tagged revision, checks and artifact hashes are recorded
[below](#060-publication-2026-10-24). This index summarizes recorded publications;
it is not a new registry or hosted-CI verification.

The checkout is **0.6.1.dev0**, an unpublished development version. Historical CI,
reference replay and package checks do not certify this modified checkout.
FlahaX is a planning and verification prototype: computational evidence is not
laboratory/field validation and does not authorize dosing or deployment.
See the [migration guide](../start/migration.md) and
[computational assessment](computational-review.md).

Each section is a record written at the time. Words such as "unpublished",
"remaining" or "outstanding" describe that moment, not today.

Codes such as P2, P5.5 or G6 are work phases and release gates from the
[implementation roadmap](https://github.com/rafatahmed/Flahax/blob/main/docs/implementation-roadmap.md).
They are kept here because the records cite them.
:::

| Version | Date | Status | Record |
|---|---|---|---|
| 0.6.0 | 2026-10-24 | Published, latest recorded | [Publication](#060-publication-2026-10-24) |
| 0.5.0 | 2026-10-20 | Published | [Publication](#050-publication-2026-10-20) |
| 0.4.0 | 2026-10-17 | Published | [Publication](#040-publication-2026-10-17), [preparation](#040-preparation-2026-10-17) |
| 0.3.1 | 2026-10-17 | Published | [Publication](#031-publication-2026-10-17), [release audit](#031-release-audit-2026-10-17), [documentation audit](#031-documentation-audit-2026-10-02), [preparation](#031-preparation-2026-10-01) |
| 0.3.0 | 2026-09-27 | Yanked 2026-10-17 | [Publication exception](#030-authorized-publication-exception-2026-09-27), [automated evidence](#030-automated-evidence), [P2/P3 acceptance](#p2p3-end-to-end-numerical-acceptance), [continuation](#package-and-delivery-continuation-2026-09-27), [cleanup](#030-release-readiness-cleanup), [preparation](#030-preparation) |

## 0.6.0 publication (2026-10-24)

0.6.0 was published to PyPI on **2026-10-24** (22:24 UTC on 2026-10-23) by the hardened release
workflow ([run 40032809873](https://github.com/rafatahmed/Flahax/actions/runs/40032809873)), triggered by the GitHub Release for tag `v0.6.0` on `main` at
`03e03ef` (merge of #156, the finalize step). Hosted CI on that commit had passed on Linux
(Python 3.11-3.14), Windows and macOS (3.13), with the docs build and the live PHREEQC replay.

| Check | Result |
|---|---|
| Release guard | Tag `v0.6.0` matched `pyproject.toml`; 0.6.0 was new on PyPI |
| Workflow tests | Python 3.11, 3.12, 3.13 and 3.14 and the live PHREEQC replay passed on the tagged commit |
| Approval | The owner approved the `pypi` deployment after the gates passed |
| PyPI upload | Wheel 22:24:31 UTC (288,855 bytes); sdist 22:24:33 UTC (5,437,125 bytes). PyPI reports 0.6.0 with licence `Apache-2.0`, `Requires-Python >=3.11`, Development Status 4 - Beta, no runtime dependency, not yanked |
| Fresh install from PyPI | New Python 3.14 virtual environment outside the checkout, `pip install flahax==0.6.0`: `flahax --version` prints FlahaX 0.6.0; 135 public names; the README example meets every target within 1 %; the packaged manual is the 0.6.0 manual; `flahax batch` writes the sheet, report and summary; `flahax mix --help` lists `--plain` |
| Documentation | Read the Docs `stable` serves the restructured site (#155); old addresses such as `growers.html` redirect |
| Archive | Zenodo version DOI [10.5281/zenodo.23605679](https://doi.org/10.5281/zenodo.23605679); concept DOI [10.5281/zenodo.23605678](https://doi.org/10.5281/zenodo.23605678) |
| Wording | The packaged changelog and manual are dated 2026-10-24 (finalize step, #71) |

| File | SHA-256 |
|---|---|
| `flahax-0.6.0-py3-none-any.whl` | `06954424329c5a128acc713cdbdea7e2e6f8cab7d9447706a74ffd507c1cfa70` |
| `flahax-0.6.0.tar.gz` | `8453b7004844ba6295b57357e3eacc2185e9e8284ce7de2d6971782d052b82a2` |

## 0.5.0 publication (2026-10-20)

0.5.0 was published to PyPI on **2026-10-20** (23:51 UTC) by the hardened release
workflow (run [`39517327774`](https://github.com/rafatahmed/Flahax/actions/runs/39517327774)),
triggered by the GitHub Release for tag `v0.5.0` on `main` at `692108b` (merge of
[PR #70](https://github.com/rafatahmed/Flahax/pull/70)). Hosted CI had passed on `692108b`
([run 39517146974](https://github.com/rafatahmed/Flahax/actions/runs/39517146974): Python
3.11, 3.12 and 3.13, live PHREEQC replay, docs). The owner authorized publication
and instructed approval of the `pypi` deployment, which was then approved through
the GitHub API after the review below.

| Check | Result |
|---|---|
| Release guard | Tag `v0.5.0` matched `pyproject.toml`; "flahax 0.5.0 is not on PyPI; continuing to verification" |
| Workflow gates on `692108b` | Tests on Python 3.11, 3.12 and 3.13 with clean wheel/sdist verification, live PHREEQC replay, one build with `twine check --strict` (both PASSED): all passed before the approval gate |
| Pre-approval artifact review | The workflow's artifacts were downloaded and inspected before approval. `USER_GUIDE.md`, `API_REFERENCE.md`, `chemistry_25c.json` and `library.json` in both the wheel and the sdist match the hashes in the 0.5.0 preparation record. Metadata: version 0.5.0, `License-Expression: Apache-2.0`, `Requires-Python: >=3.11`, no runtime dependency. Sdist 468 files with no PDF and no `docs/publication/` file |
| PyPI upload | Wheel 2026-10-20 23:51:03 UTC (172,854 bytes); sdist 23:51:05 UTC (5,117,131 bytes). PyPI reports 0.5.0 as the latest version, licence `Apache-2.0`, `Requires-Python >=3.11`, not yanked |
| Hash identity | The SHA-256 values on PyPI equal those of the reviewed workflow artifacts, and a fresh `pip download` of the wheel matches |
| Fresh install from PyPI | New Python 3.14.0 virtual environment outside the checkout, `pip install flahax==0.5.0`. The release smoke test from `tools/verify_distribution.py` passed: version, all public exports, nine manual examples, 30 catalogue products, both CLI entry points, planning EC 1.15 mS/cm; installed resource hashes as below |
| Documentation | Read the Docs `stable` serves 0.5.0, including [Benchmark v1 results](https://flahax.readthedocs.io/en/stable/evidence/benchmark-results.html) (snapshot `2026-10-20-linux-df0d30b`) and the [competitor comparison](https://flahax.readthedocs.io/en/stable/evidence/competitor-comparison.html) (#48) |
| Known wording defect | The published manual (line 5) says "release candidate prepared 2026-10-21; not yet published" and the sdist changelog says "0.5.0 — Unreleased": the finalize step that 0.4.0 performed before tagging was not done. Code and data are unaffected; corrected on `main` (#71) |

| Artifact | SHA-256 |
|---|---|
| `flahax-0.5.0-py3-none-any.whl` | `c209476ae768f79da807068073aacbd55d3ffb6f59024f88e7cff83cb4359141` |
| `flahax-0.5.0.tar.gz` | `08ca45bc53645a482a57d01a73c6b028f42ce7e7af288b930202d02887e5ab3c` |

Installed resources: `USER_GUIDE.md` `92f5d5806b1f0931df05fe490b738b8b277486d70a21d6ea53e2839f36c5ffb9`;
`API_REFERENCE.md` `db350573e41e407468d0ddb7bd7b86304c80562baf8d6b77d146d4f8df1ab9c8`;
`chemistry_25c.json` `ad87363818ccc2471c1343a0791f9ae63798bc0b3530b5b710344aff3077188f`;
`library.json` `dfc65ac7fc0060ebe760870b832e6c2c4febce2babf8cfa9defa6a858e28a05a`.
The thermodynamic data are unchanged since 0.3.1.

## 0.5.0 preparation (2026-10-21)

Prepared revision: `release/0.5.0`, cut from `main` at `9bea54a` (merge of
[PR #67](https://github.com/rafatahmed/Flahax/pull/67)). Hosted CI passed on `9bea54a`
([run 39515601654](https://github.com/rafatahmed/Flahax/actions/runs/39515601654):
Python 3.11, 3.12 and 3.13, live PHREEQC replay, docs). Assessor: Rafat Al Khashan
with Claude Code assistance. This is release-readiness evidence, not publication
authorization. Version 0.5.0 is unpublished; PyPI's latest release is 0.4.0.

| Check | Result |
|---|---|
| Version alignment | `0.5.0` in `pyproject.toml`, `flahax.__version__`, `CITATION.cff`, README, user manual and API reference; changelog section `0.5.0 — Unreleased`; tag `v0.5.0` not yet created |
| Licence | Unchanged: Apache-2.0. Wheel metadata `License-Expression: Apache-2.0`, with `LICENSE` and `NOTICE` as licence files |
| Local regression | 373 tests passed with zero skips and `FLAHAX_REQUIRE_PHREEQC=1` (pinned PHREEQC 3.8.6) on Python 3.13.15 (33.4 s) and 3.14.0 (28.2 s), with the documentation site built so its checks run. `compileall` and `git diff --check` passed |
| Public API compatibility against `v0.4.0` | 103 exports retained, none removed; 18 added (121 total): the material traceability API (`DocumentReference`, `Grade`, `Lot`, `ResolvedMaterial`, `load_identities`, `identity_for_product`, `make_grade`, `make_lot`, `resolve_material`, `nutrient_band`) and experimental irrigation EC (`DeclaredPureWater`, `IrrigationECResult`, `assay_charge_residual`, `calculate_ec_from_totals`, `calculate_irrigation_ec`, `calculate_irrigation_ec_band`, `calculate_irrigation_ec_from_plan`, `compare_measured_ec`). Two signatures gain keyword-only parameters with defaults: `recommend` (`maximum_concentrations`, `max_ammonium_fraction`) and `catalogue_dose_totals` (`materials`) |
| Isolated distribution check | `tools/verify_distribution.py` passed: clean wheel and sdist installs on Python 3.13.15 (builder 3.14.0, `build` 1.6.1), nine manual examples, 30 catalogue products, all public exports, both CLI entry points, planning EC 1.15 mS/cm. Sdist 468 files, 5,086,439 bytes; no PDF; `docs/publication/` excluded |
| Metadata | `twine check --strict` (Twine 7.0.0) passed for both artifacts |
| Packaged resources | `USER_GUIDE.md` `92f5d5806b1f0931df05fe490b738b8b277486d70a21d6ea53e2839f36c5ffb9`; `API_REFERENCE.md` `db350573e41e407468d0ddb7bd7b86304c80562baf8d6b77d146d4f8df1ab9c8`; `chemistry_25c.json` `ad87363818ccc2471c1343a0791f9ae63798bc0b3530b5b710344aff3077188f`; `library.json` `dfc65ac7fc0060ebe760870b832e6c2c4febce2babf8cfa9defa6a858e28a05a` |
| Thermodynamic data | Unchanged since 0.3.1: `chemistry_25c.json` has the same LF hash as the published 0.4.0 wheel |
| Benchmark and comparison evidence | [Benchmark v1 snapshot 2026-10-20-linux-df0d30b](benchmark-results.md): every correctness gate passes (NNLS 7/7, stored chemistry 21/21, timing 17/17; complete recipes 34/52). [Competitor comparison](competitor-comparison.md) at `ed568c5` |

Candidate hashes, built on Windows from the LF working tree before the final
form of this record (the record changes the sdist, so the publication artifacts
must be rebuilt from the final reviewed revision and hashed again):

| Artifact | SHA-256 |
|---|---|
| `flahax-0.5.0-py3-none-any.whl` | `1c6d76bdf04cb21860b153fae8ccd294af7a3142d503173a09158bf0baadb96e` |
| `flahax-0.5.0.tar.gz` | `52122a12d154753b8726ba6649a954c78325314378ea6ac9c8995c7c421ae987` |

What 0.5.0 changes scientifically:
- **Recipes.** `recommend` allows incidental NH4-N up to the smaller of 10% of
  the target N and 1.5 mmol/L when the formula omits NH4 (#54). It treats a
  binding incidental-ion ceiling as a constraint (#68), and it explains every
  missed target and the formula's own ion balance (#39).
- **Catalogue.** Mg nitrate is corrected to the hexahydrate and phosphoric acid
  to a 75% solution. Potassium chloride and calcium chloride dihydrate are
  added, and are used only with chloride consent. Every product is linked to a
  chemical identity and source document.
- **Shipped recipes change.** Most shipped formulas get different doses, and
  chelate sodium appears in chemistry and EC.
- **Solvers.** The equilibrium and NNLS solvers are faster, with numerically
  equivalent or more accurate results (#59, #61, #68).
- **Unchanged.** No reaction constant or phase changed.

Remaining before publication, per the [publishing checklist](https://github.com/rafatahmed/Flahax/blob/main/docs/publishing.md):
- hosted CI on the release revision;
- explicit owner authorization;
- the `v0.5.0` GitHub Release, the workflow's own build and gates, and approval of the `pypi` deployment;
- PyPI metadata, hash identity and fresh-install verification;
- the publication date in the changelog and the manual;
- confirming that the Read the Docs `stable` version serves the benchmark pages (#48).

## 0.4.0 publication (2026-10-17)

0.4.0 was published to PyPI on **2026-10-17** by the hardened release workflow
(run [`39043172800`](https://github.com/rafatahmed/Flahax/actions/runs/39043172800)),
triggered by the GitHub Release for tag `v0.4.0` on `main` at `3610a59`
(merge of [PR #18](https://github.com/rafatahmed/Flahax/pull/18)). It is the first release under the Apache License 2.0 and the
first published through PyPI Trusted Publishing. The owner authorized
publication and approved the `pypi` environment deployment.

| Check | Result |
|---|---|
| Release guard | Tag `v0.4.0` matched `pyproject.toml`; 0.4.0 was absent from PyPI |
| Workflow gates on `3610a59` | Tests on Python 3.11, 3.12 and 3.13 with clean wheel/sdist verification, live PHREEQC replay, one build with `twine check --strict`: all passed before the approval gate |
| Pre-approval artifact review | The workflow's artifacts were downloaded and inspected before approval: version 0.4.0, `License-Expression: Apache-2.0`, `LICENSE` and `NOTICE`, `measured_water.py` present, manual states "released 2026-10-17"; sdist 392 files with no PDF, image or `docs/publication/` file |
| PyPI upload | Wheel 2026-10-17 15:08:40 UTC; sdist 15:08:41 UTC. PyPI reports 0.4.0 as the latest version, licence `Apache-2.0`, `Requires-Python >=3.11` |
| Hash identity | The SHA-256 values on PyPI equal those of the reviewed workflow artifacts, and a fresh `pip download` of the wheel matches |
| Fresh install from PyPI | New Python 3.13.15 virtual environment outside the checkout, `pip install flahax==0.4.0`. The release smoke test from `tools/verify_distribution.py` passed: version, all 103 exports, eight manual examples, 28 catalogue products, both CLI entry points, planning EC 1.15 mS/cm |
| Measured-pH check on the installed package | Shomar et al. (2024) station 104 balances at pH 7.8, imbalance -3.52%, chloride adjusted -9.52% |
| Publication worked example | `docs/publication/example/qatar_tomato.py` reproduces every number in the drafts on the installed 0.4.0 (output identical to the pre-release run apart from one-decimal dose display) |

| Artifact | SHA-256 |
|---|---|
| `flahax-0.4.0-py3-none-any.whl` | `7da1db2cb06c3ea6e9174726f1897e48d2ab59e0d5f848f0759a0c4108ec14ee` |
| `flahax-0.4.0.tar.gz` | `70568d7266e889d51d93e4ecb3a24e82016b4ec2af5bc1f7c288f929a404d5f4` |

Installed resources: `USER_GUIDE.md` `5fd398582e1994e547c43e719282da92684bbad0db802957d56391e56d58542b`;
`API_REFERENCE.md` `0da9b7ca85eed173f0308007fcceb4682662b132dd6d2248eea7c303265cd81e`;
`chemistry_25c.json` `ad87363818ccc2471c1343a0791f9ae63798bc0b3530b5b710344aff3077188f`;
`library.json` `4ba103d202d9c5374ddd2f5a146dc3a725c34987b209b9575c59ab4465eb8343`.
The chemistry hash is the LF form because the workflow builds on Linux; the
Windows-built candidates recorded `aeb264a...`, the same data with CRLF line
endings. The thermodynamic data are unchanged since 0.3.1.

The `v0.3.1` GitHub Release note was published the same day. Its tag carries
the old workflow, which started a build that stopped at the approval gate; that
run ([`39042767902`](https://github.com/rafatahmed/Flahax/actions/runs/39042767902)) was cancelled and nothing was uploaded.

## 0.4.0 preparation (2026-10-17)

Prepared revision: `release/0.4.0`, cut from `main` at `00d855a` (merge of
[PR #15](https://github.com/rafatahmed/Flahax/pull/15)). Hosted CI passed on `00d855a`. Assessor: Rafat Al Khashan with
Claude Code assistance. This is release-readiness evidence, not publication
authorization. Version 0.4.0 is unpublished; PyPI's latest release is 0.3.1.

| Check | Result |
|---|---|
| Version alignment | `0.4.0` in `pyproject.toml`, `flahax.__version__`, `CITATION.cff`, README, user manual and API reference; changelog section `0.4.0 — Unreleased`; tag `v0.4.0` not yet created |
| Licence | First release under Apache-2.0 ([PR #13](https://github.com/rafatahmed/Flahax/pull/13)). Wheel metadata `License-Expression: Apache-2.0`, with `LICENSE` and `NOTICE` as licence files; `NOTICE` is also in the sdist. 0.3.1 and earlier remain under the Flaha Free Use License 1.0 |
| Local regression | 162 tests passed in 210.0 s on Python 3.13.15, zero skips, `FLAHAX_REQUIRE_PHREEQC=1`; also 162 passed on Python 3.14.0. `compileall` and `git diff --check` passed |
| Public API compatibility against the published 0.3.1 wheel | 100 exports retained, none removed, no signature changed; 3 added (`BalancedWaterAnalysis`, `balance_water_analysis`, `carbonate_alkalinity`; 103 total). The workflow `equilibrium` record gains optional keys only (`measured_ph`, `alkalinity_eq_per_kg`, `balance_ion`, `maximum_imbalance_percent`) |
| Isolated distribution check | `tools/verify_distribution.py` passed: clean wheel and sdist installs on Python 3.13.15 (builder 3.14.0), eight manual examples, 28 catalogue products, all public exports, both CLI entry points. Sdist 394 files, 3,397,413 bytes; no PDF; `docs/publication/` excluded |
| Metadata | `twine check --strict` passed for both artifacts |
| Packaged resources | `USER_GUIDE.md` `fa54d6389b479f02f048b2bb54c8c228fc40bf5de7872f4e2a757d86448dc5e1`; `API_REFERENCE.md` `0da9b7ca85eed173f0308007fcceb4682662b132dd6d2248eea7c303265cd81e`; `chemistry_25c.json` `aeb264a4edf1177102bc1a68fb4dc87de6c1ea9c94cd45ff462dcfc06a0ee575`; `library.json` `4ba103d202d9c5374ddd2f5a146dc3a725c34987b209b9575c59ab4465eb8343` |
| Thermodynamic data | Unchanged since 0.3.1. The installed `chemistry_25c.json` is byte-identical to the published 0.3.1 wheel's (`aeb264a…`). The `ad87363…` value in the 0.3.1 audit below is the same file as stored in Git with LF line endings |

Candidate hashes, built before this evidence record was written (the record
changes the sdist, so the publication artifacts must be rebuilt from the final
reviewed revision and hashed again):

| Artifact | SHA-256 |
|---|---|
| `flahax-0.4.0-py3-none-any.whl` | `25f919d7cd91dadd9abb4237cba2ea0b5ac5e1e68f7f6121d5a739ee559a8943` |
| `flahax-0.4.0.tar.gz` | `08d5ca638dd0661f3cbf446fa84027a7e98282eb5861b7d59b98d8964aa2c583` |

What 0.4.0 changes scientifically: source water can be speciated at its
measured pH, with the analysis's charge imbalance closed on Cl- or Na+ and
recorded. On a published Qatar well (Shomar et al. 2024, station 104), charge
balance alone gave pH 3.8 against a measured 7.80. No reaction constant,
phase, catalogue product or existing default changed.

Changes after this record, before publication: the release workflow was
hardened (tag/version guard, no re-upload, tests and live replay before build,
reviewer-gated Trusted Publishing), the documentation was brought up to date,
and two unreferenced 0.2.0 images were removed from `docs/`, so the sdist
shrinks. No runtime code or packaged resource changed.

Remaining before publication, per the [publishing checklist](https://github.com/rafatahmed/Flahax/blob/main/docs/publishing.md):
hosted CI and the pinned live replay on the final revision; explicit owner
authorization; a final build of the exact approved artifacts with recorded
hashes; upload through the approved route; PyPI metadata and fresh-install
verification; and the publication date and `v0.4.0` tag.

## 0.3.1 publication (2026-10-17)

The owner authorized publication of 0.3.1 on 2026-10-17. Released revision: `main` at `586eddb` (merge of [PR #10](https://github.com/rafatahmed/Flahax/pull/10)), tagged
`v0.3.1`. Route: manual Twine upload by the owner. No
GitHub Release was created, so the automatic publish workflow did not run.

| Step | Result |
|---|---|
| Version unused | `https://pypi.org/pypi/flahax/0.3.1/json` returned 404 before upload |
| Hosted CI on the release content | [PR #10](https://github.com/rafatahmed/Flahax/pull/10) run [`39028824252`](https://github.com/rafatahmed/Flahax/actions/runs/39028824252) passed: Python 3.11-3.13 and `phreeqc-live` |
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

## 0.3.1 release audit (2026-10-17)

Audited revision: `main` at `2e257d5` (merge of [PR #7](https://github.com/rafatahmed/Flahax/pull/7)), then the audit commit
`7d4ef15` on `release/0.3.1-audit`, which only excludes the YaraVita PDF and
updates status documents. Assessor: Rafat Al Khashan with Claude Code
assistance. This is release-readiness evidence, not publication authorization.
Version 0.3.1 remains unpublished; PyPI's latest release is 0.3.0.

| Check | Result |
|---|---|
| Version alignment | `0.3.1` in `pyproject.toml`, `flahax.__version__`, `CITATION.cff`, user manual and API reference; changelog section `0.3.1 - Unreleased`; tag `v0.3.1` not yet created |
| Hosted CI on `2e257d5` | Run [`38967066279`](https://github.com/rafatahmed/Flahax/actions/runs/38967066279) (2026-10-16) passed: Python 3.11, 3.12 and 3.13 each ran 153 tests, OK with 2 skips (live replay, covered by the dedicated job) plus isolated wheel/sdist verification; `phreeqc-live` ran 6 tests, OK, zero skips, with hash-pinned PHREEQC 3.8.6 |
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

Remaining before publication, per the [publishing checklist](https://github.com/rafatahmed/Flahax/blob/main/docs/publishing.md):
explicit owner authorization; a final build of the exact approved artifacts
with recorded hashes; upload through the approved route; PyPI metadata and
fresh-install verification; and the publication date and `v0.3.1` tag. Hosted
CI must also pass on the final revision that includes this audit.

## 0.3.1 documentation audit (2026-10-02)

The merged preparation branch was audited on `release/0.3.1-documentation`.
See [audit findings and maintenance policy](https://github.com/rafatahmed/Flahax/blob/main/docs/documentation-maintenance.md).
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
In PowerShell, set the two variables with `$env:` as in the
[0.3.1 preparation](#031-preparation-2026-10-01) commands.

The subsequent README test and maintenance-page additions were checked with
`PYTHONPATH=src py -3.13 -m unittest tests.test_release_hygiene`: **5 passed**.
The reference freshness check passed on Python 3.13 and 3.14. Compilation and
`git diff --check` passed. These are local checks, not a hosted-CI result or
publication authorization. Version 0.3.1 remains unpublished.

## 0.3.1 preparation (2026-10-01)

Branch: `release/0.3.1-site-planning`. This is local preparation, not a new
published release or a hosted-CI pass. See [current status](https://github.com/rafatahmed/Flahax/blob/main/docs/development-status.md)
for capability boundaries and [conventions](https://github.com/rafatahmed/Flahax/blob/main/CONTRIBUTING.md) for branch policy.

Validation commands (PowerShell; pinned PHREEQC remains outside the checkout):

```powershell
$env:PYTHONPATH = 'src'
$env:FLAHAX_REQUIRE_PHREEQC = '1'
py -3.13 -m unittest discover -s tests -t .
py -3.13 -m compileall -q src examples tools
git diff --check
.venv-verification/Scripts/python.exe tools/verify_distribution.py --python <path-to-python-3.13> --report build/release-0.3.1-distribution.json
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

## 0.3.0 authorized publication exception (2026-09-27)

On 2026-09-27 the owner explicitly approved manual PyPI publication using the verified local evidence despite the GitHub Actions billing blocker. This exception applies to the hosted publication gate for 0.3.0; it does not convert blocked checks into passes or imply independent/experimental validation. The release candidate passed clean-install/manual/metadata checks. On 2026-09-28, PyPI metadata confirmed both artifacts were uploaded on 2026-09-27. A fresh isolated Python 3.13 installation of the published wheel passed version/import checks, all four manual examples and both CLI entry points. See the [post-release audit](https://github.com/rafatahmed/Flahax/blob/main/docs/release-readiness.md); candidate-sdist evidence remains separate.

## 0.3.0 automated evidence

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
| P2.7 full fertilizer model | `tests/test_chemistry_acceptance.py`: all 28 catalogue conversions, 197 aqueous entries/28 phases, simultaneous balances, Davies/temperature rejection, phase complementarity and convergence; the [chemistry coverage matrix](../models/chemistry-coverage-matrix.md) resolves aliases before extensions |
| P3.7 acid/base coverage | Actual mixed doses -> initial solve -> nitrate addition -> same target solve. Corrected Fix_H+ and independent nitrate titration agree; tests verify component/charge conservation and post-mix measurement requirement |
| Evidence preservation | `tests/test_preserved_chemistry_evidence.py` hashes six original successes and all diagnostic artifacts; `tests/fixtures/phreeqc/failures/README.md` explains the reduced failure ladder |

Exact validation commands (PowerShell sets `$env:PYTHONPATH='src'`, equivalent to the first command below):

```text
PYTHONPATH=src python -m unittest discover -s tests -t .
python -m compileall -q src
git diff --check
git status
```

The complete unittest run passes **100 tests with zero failures/errors/skips**, including installed-PHREEQC live execution. Compilation and whitespace validation pass. Numerical tolerances and regeneration commands are in [PHREEQC reference fixtures](../models/reference-fixtures.md); executable/base/extension and output hashes are in each fixture's JSON.

This accepts the explicitly selected project parameterization, not universal chemical accuracy. In particular the inherited literature-derived Dtp/Edd profile and its activity/concentration and stereoisomer assumptions are disclosed in the [chelate extension](../models/flahax-chelate-thermodynamic-profile.md). The original closure left independent review and lot-specific experimental validation to G6. The owner-amended [computational scope](computational-review.md) supersedes that release requirement without claiming experimental validation.

## Package and delivery continuation (2026-09-27)

Package-verification work was based on merged main `33febd41e1f2854c99275994cc98eaeaf1f0cc41`. No chemistry database, golden fixture or failure reproducer was changed. Assessor: **Rafat Al Khashan**, as designated by the project owner. The [computational assessment](computational-review.md) separates that designation from automated evidence and does not fabricate a personal signature.

| Requirement | Observed evidence | Acceptance |
|---|---|---|
| P5.5 equilibrium delivery | `tests/test_equilibrium_delivery.py`: explicit g/L-to-g/kg-water mapping, HNO3 assay/density, nitrate rescoring, source hashes, dedicated acid command, composed-plan transitions, target reference and rejection guards | Pass |
| P6.6 distributions | `tools/verify_distribution.py`: independent wheel/sdist installations outside checkout; Python 3.13.15 resource hashes, public exports, chemistry/delivery numerical examples and both CLI entry points agree; no required runtime dependencies or bundled executable. Earlier Python 3.14 installs also passed. | Local pass; hosted supported-version matrix outstanding |
| P6.7 live reference | Full suite runs pinned PHREEQC with zero skips; fresh official MSI extraction verifies installer/executable/base hashes. `tests/test_live_reference_policy.py` confirms required-live absence fails rather than skips. New hosted job retains replay logs. | Local pass; hosted job outstanding |
| P6.8 / amended G6 | Conservation, convergence, reference agreement, delivery guards and distribution checks recorded in the [computational assessment](computational-review.md); assessor Rafat Al Khashan | Bounded computational assessment passes; not independent review, formal proof or laboratory certification |
| P7 | Consumer boundary documented in [INTEGRATION.md](https://github.com/rafatahmed/Flahax/blob/main/INTEGRATION.md); implementation belongs to separate FlahaFAST project | External; not a package release gate |

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

Result: **PASS: isolated wheel and sdist installs, resources, public APIs and both CLI entry points**. The development environment contains the `build` frontend; see [package verification](../developer/verification.md) to reproduce. The generated local `build/distribution-verification.json` records artifact hashes and observations. Both installs reported 28 catalogue products, chemistry SHA-256 `aeb264a4edf1177102bc1a68fb4dc87de6c1ea9c94cd45ff462dcfc06a0ee575`, library SHA-256 `4ba103d202d9c5374ddd2f5a146dc3a725c34987b209b9575c59ab4465eb8343`, and synthetic delivery reagent volume `0.0003095719864150872 L`. Artifact hashes identify the tested build, not a promise of byte-identical future archive timestamps.

`tools/provision_phreeqc.ps1` was tested both against the existing installation and with a fresh destination under TEMP. It downloads the official pinned MSI, administratively extracts outside the checkout and verifies all three hashes without modifying the base database. This is reference tooling, not a package runtime dependency.

The hosted GitHub run inspected during this increment did not execute because of the account billing lock (run [`36322890741`](https://github.com/rafatahmed/Flahax/actions/runs/36322890741)). Python 3.11/3.12 and the new hosted jobs have not been observed passing. No local result substitutes for that gate; account billing changes require the account owner.

## 0.3.0 release-readiness cleanup

The release-readiness cleanup adds metadata/export and documentation-link checks, fixes expired-date-prone test fixtures without changing runtime expiry policy, and archives superseded notes without deleting scientific evidence. Final local validation: `$env:PYTHONPATH='src'; $env:FLAHAX_REQUIRE_PHREEQC='1'; py -3.13 -m unittest discover -s tests -t .` — **109 tests in 142.086 seconds, OK, zero skips**. Clean wheel/sdist verification passes after the packaging changes; compilation and whitespace checks pass. The corrected explicit-salts CLI example returns `feasible: true`.

Hosted [PR #3](https://github.com/rafatahmed/Flahax/pull/3) run [`36345628921`](https://github.com/rafatahmed/Flahax/actions/runs/36345628921) was attempted and all four jobs were prevented from starting by the account billing lock. Actions is enabled; P6.6/P6.7 hosted acceptance and merge remain blocked. See [release-readiness audit](https://github.com/rafatahmed/Flahax/blob/main/docs/release-readiness.md). FlahaFAST implementation is assigned to the separate FlahaFAST project and is not a package release gate.

## 0.3.0 preparation

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

## Gates before operational use

These still apply to every release:

- **G2/G3:** the bounded mixed-product reference and model choices are implemented and numerically verified above; their declared conditions and source-profile limits must be kept.
- **G6:** for the planning package, the owner asked for computational evidence without laboratory work; see the [computational assessment](computational-review.md). Independent and physical validation are not claimed.
- **P7:** a separate, read-only FlahaFAST interface contract; it is not implemented in the package.

The package remains a dependency-free **planning and verification prototype**. P2/P3 and the owner-amended G6 computational acceptance do not authorize autonomous dosing, pump control, deployment or universal chemical certification. P7 integration remains unimplemented.

When 0.3.0 was prepared, hosted verification on the supported Python versions was still outstanding because of the billing lock. It has since passed: see [0.4.0 publication](#040-publication-2026-10-17).
