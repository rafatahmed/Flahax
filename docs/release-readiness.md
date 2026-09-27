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

## Release gate

PR #3's first hosted run, `36345628921`, did not execute any of its four jobs. GitHub annotations state: “The job was not started because your account is locked due to a billing issue.” Actions is enabled in repository settings; no repository setting can establish successful execution while this account restriction remains.

The account owner must resolve payment and then rerun the final PR revision. Merge is conditional on successful Python 3.11–3.13 package jobs and pinned live-reference replay. No bypass, automatic merge, tag or publication is configured by this cleanup. The release version remains unchanged until an explicitly authorized publication task chooses the next version.

Local verification results are recorded in [release evidence](release-evidence.md); automated and computational acceptance are not independent human review. Assessor: Rafat Al Khashan.
