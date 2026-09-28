# Release-readiness audit — 2026-09-27

## Changes and retained boundaries

| Finding | Resolution |
|---|---|
| README CLI example omitted required salts | Example now explicitly supplies the packaged catalogue; the CLI input contract is unchanged. |
| FlahaFAST instructions asserted unverified deployment paths and application state | Replaced with a package consumer contract; P7 implementation belongs to the separate FlahaFAST project. |
| Historical chemistry notes mixed pending reduced-kernel work with current acceptance | Moved intact to `docs/history/`; current model documents link to them. No golden captures, failure reproducers, constants or runtime chemistry were removed. |
| Older G6 language contradicted the owner's computational scope | Current source-profile and roadmap language links to the named-assessor computational assessment, without claiming independent or physical validation. |
| Pump fixtures expired as the real date advanced | Tests now supply a fixed assessment date; the runtime's actual-clock calibration expiry policy and explicit stale-date test are preserved. |
| Metadata and documentation could drift | `tests/test_release_hygiene.py` checks version/citation/export consistency and local documentation links. Source distributions include citation and documentation assets. |
| Apparently old runtime modules | Reduced kernels remain exported compatibility APIs or legacy-fixture dependencies; they are not presumed orphaned merely because the mixed solver supersedes their planning use. No public exports were removed. |

## Publication and remaining verification — 2026-09-28

PR #3 and PR #4 are merged; remote main was inspected at `25bfcb397b523bd538fde07bc6c99cbd818437aa`. PyPI's version JSON confirms both 0.3.0 artifacts were uploaded on 2026-09-27 (wheel 20:50:59 UTC; sdist 20:51:01 UTC). A fresh Python 3.13 virtual environment subsequently installed `flahax==0.3.0` from PyPI outside the checkout: version/import verification, all four bundled manual examples and both CLI entry points passed. This check exercised the published wheel; the candidate sdist evidence remains separately recorded.

The owner authorized this release using local evidence despite the hosted billing blocker. The latest inspected main run, `36348839031`, reports failure; P6.6/P6.7 remain open. The earlier run `36345628921` recorded an account billing lock. No successful hosted validation is inferred from publication or merging.

The retired `codex/package-verification-delivery` branch contained one post-merge authorization commit, `96ce35c`. It was preserved on `codex/post-release-roadmap`, together with main's merge history, before the old local and remote refs were deleted. Existing scientific captures, failure reproducers, public compatibility modules and local release artifacts were retained.

Local release results remain in [release evidence](release-evidence.md); automated and computational acceptance are not independent human review. Assessor: Rafat Al Khashan. Future work follows the [development roadmap](development-roadmap.md).

## Cleanup validation — 2026-09-28

- Python 3.13 full suite: 110 tests, zero skips; 109 passed and the live PHREEQC test hit a sandbox temporary-file permission error. That exact test passed on a separate rerun with temporary-file access (all product and phase replay inputs). No runtime change was needed.
- Release-hygiene checks: all three passed, including documentation links, metadata/export consistency and shipped-manual examples.
- Fresh published-wheel install: version/import checks, four manual examples and both CLI entry points passed outside the checkout.
- `git diff --check`: passed. Runtime code, model data and scientific fixtures were unchanged.
- The obsolete local `p2p3-chemistry-completion` branch was also removed after confirming it was an ancestor of main and its remote ref was already gone.

The roadmap and documentation updates are local work on `codex/post-release-roadmap`; no new publication, hosted workflow run or application deployment was performed.
