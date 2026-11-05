# Pull requests run a light gate; the full gate runs before a release

Date: 2026-11-05

A pull request ran the whole suite on six interpreter and operating-system combinations, three of them under branch coverage with an exact three-OS gate. A one-line fix waited 25 to 60 minutes, and a documentation change waited as long as a chemistry change. FlahaX is a pure-Python package with no runtime dependencies, so an operating-system-only break is unlikely and is cheap to find before a release.

Pull requests and pushes to `main` now run the light tier: lint, the documentation build, the PHREEQC replay (skipped when only documentation changed), Linux on Python 3.11, 3.12 and 3.13, and one clean wheel and sdist check. A pull request that changes only `docs/` or top-level `.md` files runs lint, the documentation build and the documentation tests. The full tier is a manual run of the Test workflow before a release: it adds Python 3.14, Windows and macOS, the exact three-OS coverage gate and the Codecov upload. A release calls the full tier on the tagged commit, and nothing is built or published unless it passes.

## Considered options

- **Keep the full gate on every pull request:** rejected. It cost an hour per change and failed Dependabot pull requests that cannot read the Codecov secret.
- **Coverage on Linux only for pull requests:** rejected. The gate is exact, and `terminal.py` has Windows-only and POSIX-only branches, so one operating system can never reach it.
- **Shard the full gate across parallel jobs:** deferred. It keeps every guarantee but changes the coverage tool and its tests; revisit if the full run becomes the bottleneck.

## Consequences

- A coverage gap or an operating-system-only failure is found when the full tier runs, not on the pull request. The fix is a follow-up commit.
- The required check names `test (3.11)`, `test (3.12)`, `test (3.13)`, `phreeqc-live` and `coverage-gate` are unchanged, so branch protection needs no edit. In the light tier `coverage-gate` only requires its prerequisites to pass.
- A release runs the full tier through `publish.yml`, so exact coverage on all three operating systems is enforced where it matters. A failing gate stops the publication; fix it and publish again.
- Run the Test workflow by hand before tagging to find those failures early.
