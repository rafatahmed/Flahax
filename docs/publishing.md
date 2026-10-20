# Publishing

From 0.4.0, a release reaches PyPI through one route: publishing a GitHub
Release runs the hardened [`publish.yml`](../.github/workflows/publish.yml)
workflow. Preparing or merging a branch never publishes, and neither does
pushing a tag.

## What the workflow enforces

| Gate | Job | Effect |
|---|---|---|
| Release tag is exactly `v<version in pyproject.toml>` | `guard` | A mismatch fails the run; nothing is built |
| Version is not already on PyPI | `guard` | An existing version is skipped with a notice, never re-uploaded |
| Full test suite and clean wheel/sdist installs on Python 3.11, 3.12 and 3.13 | `test` | Runs on the tagged commit |
| Pinned live PHREEQC replay | `phreeqc-live` | Hash-pinned PHREEQC 3.8.6 on Windows |
| One build, `twine check --strict`, exactly one wheel and one sdist | `build` | Artifact SHA-256 values appear in the run summary |
| Owner approval | `publish` | The `pypi` environment requires a reviewer and accepts only `v*` tags |
| Upload | `publish` | PyPI Trusted Publishing (OIDC). No API token is stored in GitHub |

## One-time setup

1. **Trusted Publishing on PyPI** (owner, on pypi.org). `flahax` already
   exists, so the publisher is added on the project: open
   [Manage projects](https://pypi.org/manage/projects/), choose `flahax`, then
   Publishing, and add a GitHub Actions publisher:

   | Field | Value |
   |---|---|
   | Owner | `rafatahmed` |
   | Repository | `Flahax` |
   | Workflow | `publish.yml` |
   | Environment | `pypi` |

   Without it, the `publish` job fails after approval and nothing is uploaded.
2. **`pypi` environment** (GitHub): required reviewer `rafatahmed`;
   deployment restricted to tags matching `v*`.
3. **Branch protection on `main`**: changes arrive by pull request, and the
   `Test` workflow's checks must pass before merging.

## Releasing a version

1. On a `release/<version>` branch, align the version in `pyproject.toml`,
   `flahax.__version__`, `CITATION.cff`, README, user manual and API
   reference; write the changelog section; record readiness and evidence.
   Merge it by pull request after CI passes.
2. Confirm the publication decision with the owner. Merging is not approval.
3. **Finalize the wording before tagging** (#71): on a short branch, date the
   changelog section and change the manual's version line from "release
   candidate ... not yet published" to "released <date>"; merge it after CI
   passes. The tag must point at this commit, because the packaged manual and
   the sdist changelog are fixed at upload.
4. Create the GitHub Release for tag `v<version>` on that merged `main`
   commit, with the changelog section as its notes. Publishing it starts the
   workflow.
5. Review the run: the guard notice, all test jobs, the live replay and the
   artifact hashes in the build summary. Then approve the `pypi` deployment.
6. After upload: check PyPI metadata, install `flahax==<version>` in a fresh
   environment, run the manual's examples and both CLI entry points, and
   record the date, run URL and hashes in [release evidence](site/evidence/release-evidence.md).

**Old tags run old workflows.** For a Release event, GitHub runs
`publish.yml` as it exists at the tagged commit. Tags before `v0.4.0` carry the
old, unguarded workflow: a Release note for one of them starts a build that
waits at the `pypi` approval gate. Cancel that run; never approve it. (This
happened for the `v0.3.1` note on 2026-10-17; the run was cancelled and nothing
was uploaded.)

Withdrawn versions are **yanked** on PyPI, never deleted: PyPI keeps every
uploaded filename, so a version number can be used only once.

## Documentation site

The documentation is built by Read the Docs from `docs/site/` (Sphinx + MyST;
see `.readthedocs.yaml`) and published at <https://flahax.readthedocs.io/>.
Dashboard settings, recorded here because they live outside the repository:

- `latest` tracks `main`.
- Pull request preview builds are on.
- Tags v0.1.0 to v0.4.0 stay inactive.
- An automation rule activates `v*` tags from the next release.
- The default version is `latest` until that release, then `stable`.
- Never put a Read the Docs token in the repository.

## Checklist (last run: 0.5.0)

- [x] Choose the version and align metadata, runtime version, citation, manual and changelog.
- [x] Review compatibility, scientific provenance and distribution contents.
- [x] Pass local tests with live PHREEQC and isolated wheel/sdist verification.
- [x] Observe successful hosted Python 3.11–3.13 checks on the merged revision.
- [ ] Date the changelog and the manual's version line, and merge, before tagging. **Missed for 0.5.0** (#71); do it for every release.
- [x] Obtain explicit publication authorization.
- [x] Publish the `v0.5.0` GitHub Release; review the run; approve the deployment.
- [x] Verify PyPI metadata and a fresh installed-package check; record the date, run and hashes.
- [x] Confirm the Read the Docs `stable` version builds `v0.5.0` and serves the benchmark pages (#48).

Completed 2026-10-20 apart from the finalize step. Copy this checklist, with that step, for the next release.

## Checklist (0.4.0)

- [x] Choose the version and align metadata, runtime version, citation, manual and changelog.
- [x] Review compatibility, scientific provenance and distribution contents.
- [x] Pass local tests with live PHREEQC and isolated wheel/sdist verification.
- [x] Observe successful hosted Python 3.11–3.13 checks on the merged revision.
- [x] Complete the one-time setup above.
- [x] Obtain explicit publication authorization.
- [x] Publish the `v0.4.0` GitHub Release; review the run; approve the deployment.
- [x] Verify PyPI metadata and a fresh installed-package check; record the date, run and hashes.

Completed 2026-10-17. Copy this checklist for the next release.

## Fallback: manual Twine upload

Use only if the workflow route is unavailable, and only with the owner's
explicit approval for that version. Build in a clean checkout of the tagged
commit, run `tools/verify_distribution.py --artifacts-dir <new empty dir>`,
`twine check --strict`, then upload only those two files:

```powershell
py -m twine upload <dir>/flahax-<version>.tar.gz <dir>/flahax-<version>-py3-none-any.whl
```

Use a PyPI token through Twine's secure prompt or the operating-system
keyring. Never paste tokens into chat, commit them, or put them in command
arguments. A version uploaded manually must not also get a workflow run; the
guard would skip it anyway.

## PyPI README validation

The built metadata declares `Description-Content-Type: text/markdown`. README
links use absolute repository URLs so they work on the PyPI project page.
`twine check --strict` validates the metadata; it does not show that a
package was uploaded.

## Release history

- **0.5.0**, 2026-10-20: published through the hardened workflow (run
  `39517327774`) from `692108b`; the deployment was approved at the owner's
  instruction after artifact review, and verified by a fresh installation from
  PyPI. The packaged manual and changelog still say "not yet published" (#71).
  See the [0.5.0 publication evidence](site/evidence/release-evidence.md#050-publication---2026-10-20).
- **0.4.0**, 2026-10-17: first Apache-2.0 release and first upload through the
  hardened workflow with Trusted Publishing (run `39043172800`), approved by
  the owner, verified by a fresh installation from PyPI. See the
  [0.4.0 publication evidence](site/evidence/release-evidence.md#040-publication---2026-10-17).
- **0.3.1**, 2026-10-17: uploaded manually with Twine from `main` at
  `586eddb`, tagged `v0.3.1`, verified by a fresh installation from PyPI;
  hosted CI passed. See the
  [0.3.1 publication evidence](site/evidence/release-evidence.md#031-publication---2026-10-17).
  Its GitHub Release note was added on 2026-10-17; the old-workflow run it
  started was cancelled before approval.
- **0.3.0**, 2026-09-27: uploaded manually with Twine under an owner exception
  for local-only verification while hosted CI was blocked by billing.
  **Yanked on 2026-10-17** because its sdist contained a third-party PDF. The
  [GitHub release v0.3.0](https://github.com/rafatahmed/Flahax/releases/tag/v0.3.0)
  of 2026-10-01 used the existing PyPI artifacts; see the
  [release provenance and SHA-256 record](releases/0.3.0.md) and the
  [post-release audit](release-readiness.md).
- **0.2.0** and **0.1.0**, 2026-09-25: early releases; their files stay on
  PyPI.
