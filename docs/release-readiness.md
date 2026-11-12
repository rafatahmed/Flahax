# Release readiness

## Current preparation — unreleased

The checkout identifies itself as `0.6.1.dev0`. The planned changes are collected
under [unreleased detailed notes](releases/unreleased.md); no future release version is designated. Final version selection and release
preparation are tracked in issue #234.

Current documentation and clean-distribution qualification are tracked in #199.
Computational qualification (#200) and the source/model qualification audits
(#161, #201) are complete within their documented scopes. Unresolved attribution
and model assumptions remain explicit limits, not rejected custom inputs. Physical
validation (#41, #42) and the hands-on grower trial (#231) remain unfinished.
A passing calculation or package check does not establish those outcomes.
The final candidate still needs its own artifact hashes, installed-package checks,
required CI and reference replay, review, and publication authorization.

The dated records below describe their own revisions. Their remaining gates and
capability claims are historical, not the status of the current checkout.

## Current release assessment

The development candidate is not a qualified release. No version bump,
publication date, tag, DOI or release upload is established by these corrections.

| Item | Current disposition |
| --- | --- |
| Documentation and distribution (#199) | Candidate qualification and artifact identities are recorded in #199; local checks do not establish merge, hosted CI or a published release |
| Historical comparison (#203) | Local report corrected; it is not packaged as current performance evidence |
| Formula provenance (#201) | Audit completed; recovered sources and unresolved attributions recorded; custom targets unchanged |
| Scientific/source claims (#161) | Qualification audit completed; EC, ammonium, declared-product, solubility and reaction-domain limits remain explicit |
| Grower acceptance (#231) | Hands-on trial not performed; automation cannot substitute for it |
| Computational qualification (#200) | Completed within its recorded computational scope, not physical/source validation |
| Physical validation (#41/#42) | Separate unfinished programme; no laboratory or field accuracy claim |

The packaged water profiles are examples, not laboratory analyses. Release
assessment must distinguish them from an actual supplied water measurement.
Final release preparation (#234) requires an agreed candidate, the outstanding
grower acceptance, exact-candidate full/native CI and required reference replay,
strict documentation and clean-distribution checks, then separate publication
authorization. Historical benchmark timings retain their measured revisions.

## Historical release records

## 0.5.0 - published 2026-10-20

Published from `692108b` (tag `v0.5.0`); see the
[publication evidence](site/evidence/release-evidence.md#050-publication---2026-10-20).
Prepared on `release/0.5.0` from `main` at `9bea54a`. The evidence is the
[0.5.0 preparation record](site/evidence/release-evidence.md#050-preparation---2026-10-21).

0.5.0 changes:
- recipe selection: the ammonium limit, ceilings as constraints and miss diagnosis;
- catalogue identities and provenance;
- experimental irrigation EC;
- solver speed and accuracy.

It keeps every 0.4.0 export. Remaining gates:
- hosted checks on the release revision;
- review and explicit maintainer publication authorization;
- the workflow build, with recorded hashes and a fresh-install check.

## 0.4.0 - published 2026-10-17

Prepared on `release/0.4.0` from `main` at `00d855a`, finalized in PR #18 and
published from `3610a59` (tag `v0.4.0`). See the
[publication evidence](site/evidence/release-evidence.md#040-publication---2026-10-17).
The preparation record follows.

0.4.0 is the first release under the Apache License 2.0 (PR #13) and adds
measured-pH water balancing (PR #15). Evidence is in
[release evidence](site/evidence/release-evidence.md#040-preparation---2026-10-17).
Remaining gates: hosted Python 3.11–3.13 checks and live replay on the final
revision, review, explicit maintainer publication authorization, and a final build
of the exact approved artifacts with recorded hashes.

## Historical preparation - 0.3.1 / 2026-10-01

Current branch: `release/0.3.1-site-planning`. Package metadata, citation and
the shipped manual now identify the unreleased 0.3.1 preparation; no release
date or publication is claimed. The audit below is retained as 0.3.0 history.

Current cleanup removes stale branch branding and contradictory current-version
descriptions, adds explicit CLI/report boundaries, and retains public
compatibility kernels and scientific fixtures. Local manufacturer PDFs remain
untouched and excluded from versioned/distribution artifacts. Branch conventions
are recorded in [CONTRIBUTING](../CONTRIBUTING.md).

See [current capability status](development-status.md) and
[verification evidence](site/evidence/release-evidence.md). Remaining release gates are
hosted supported-version verification, review and explicit publication approval.
No historical CI exception is inherited by 0.3.1.

## Changes and retained boundaries

| Finding | Resolution |
|---|---|
| README CLI example omitted required salts | Example now explicitly supplies the packaged catalogue; the CLI input contract is unchanged. |
| FlahaFAST instructions asserted unverified deployment paths and application state | Replaced with a package consumer contract; P7 implementation belongs to the separate FlahaFAST project. |
| Historical chemistry notes mixed pending reduced-kernel work with current acceptance | Moved intact to `docs/history/`; current model documents link to them. No golden captures, failure reproducers, constants or runtime chemistry were removed. |
| Older G6 language contradicted the maintainer's computational scope | Current source-profile and roadmap language links to the named-assessor computational assessment, without claiming independent or physical validation. |
| Pump fixtures expired as the real date advanced | Tests now supply a fixed assessment date; the runtime's actual-clock calibration expiry policy and explicit stale-date test are preserved. |
| Metadata and documentation could drift | `tests/test_release_hygiene.py` checks version/citation/export consistency and local documentation links. Source distributions include citation and documentation assets. |
| Apparently old runtime modules | Reduced kernels remain exported compatibility APIs or legacy-fixture dependencies; they are not presumed orphaned merely because the mixed solver supersedes their planning use. No public exports were removed. |

## Publication and remaining verification — 2026-09-28

PR #3 and PR #4 are merged; remote main was inspected at `25bfcb397b523bd538fde07bc6c99cbd818437aa`. PyPI's version JSON confirms both 0.3.0 artifacts were uploaded on 2026-09-27 (wheel 20:50:59 UTC; sdist 20:51:01 UTC). A fresh Python 3.13 virtual environment subsequently installed `flahax==0.3.0` from PyPI outside the checkout: version/import verification, all four bundled manual examples and both CLI entry points passed. This check exercised the published wheel; the candidate sdist evidence remains separately recorded.

The maintainer authorized this release using local evidence despite the hosted billing blocker. The latest inspected main run, `36348839031`, reports failure; P6.6/P6.7 remain open. The earlier run `36345628921` recorded an account billing lock. No successful hosted validation is inferred from publication or merging.

The retired package-verification branch contained one post-merge authorization commit, `96ce35c`. It was preserved in the post-release roadmap history, together with main's merge history, before the old local and remote refs were deleted. Existing scientific captures, failure reproducers, public compatibility modules and local release artifacts were retained.

Local release results remain in [release evidence](site/evidence/release-evidence.md); automated and computational acceptance are not independent human review. Assessor: Rafat Al Khashan. Future work follows the [development roadmap](development-roadmap.md).

## Cleanup validation — 2026-09-28

- Python 3.13 full suite: 110 tests, zero skips; 109 passed and the live PHREEQC test hit a sandbox temporary-file permission error. That exact test passed on a separate rerun with temporary-file access (all product and phase replay inputs). No runtime change was needed.
- Release-hygiene checks: all three passed, including documentation links, metadata/export consistency and shipped-manual examples.
- Fresh published-wheel install: version/import checks, four manual examples and both CLI entry points passed outside the checkout.
- `git diff --check`: passed. Runtime code, model data and scientific fixtures were unchanged.
- The obsolete local `p2p3-chemistry-completion` branch was also removed after confirming it was an ancestor of main and its remote ref was already gone.

At that audit, the roadmap and documentation updates were local work in the post-release roadmap branch; no new publication, hosted workflow run or application deployment was performed.
