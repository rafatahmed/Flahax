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
| Full test suite and clean wheel/sdist installs on Python 3.11, 3.12, 3.13 and 3.14 | `test` | Runs on the tagged commit |
| Pinned live PHREEQC replay | `phreeqc-live` | Hash-pinned PHREEQC 3.8.6 on Windows |
| One build, `twine check --strict`, exactly one wheel and one sdist | `build` | Build tools installed from `tools/release/requirements-release.txt` with `--require-hashes`, built without isolation; artifact SHA-256 values appear in the run summary |
| Maintainer approval | `publish` | The `pypi` environment requires a reviewer and accepts only `v*` tags |
| Upload | `publish` | PyPI Trusted Publishing (OIDC). No API token is stored in GitHub |

## Build-tool pinning

The release job installs `build`, `twine` and the build backend (`setuptools`), with every
transitive dependency, from `tools/release/requirements-release.txt` using `pip install --require-hashes`,
then builds with `python -m build --no-isolation`, so the artifacts are made by exactly the
reviewed tool versions. The other jobs that install `build` use the same version
(`build==1.6.1`). Dependabot proposes monthly updates for `/tools/release` only: the file
`tools/competitors/constraints.txt` records the environment of the published #40 comparison run
and is never bumped piecemeal. A pin changes only through a reviewed pull request that
regenerates the file:

```
uv pip compile --universal --generate-hashes --python-version 3.11 \
  tools/release/requirements-release.in -o tools/release/requirements-release.txt
```

Raise the `build==` pins in `test.yml` and `publish.yml` in the same pull request; a test fails if
they disagree. A clean `python tools/verify_distribution.py` still builds in an isolated
environment, as a user of the sdist would.

## Recovering validation after an upstream outage

The PHREEQC provisioner retries transient HTTP responses (408, 429, 500, 502,
503 and 504) at most twice after the first request, with local delays of two
and four seconds and a 60-second connection timeout per request. It does not
use a server's `Retry-After` value to extend those delays. Other download
errors fail immediately. The workflow's job timeout remains the overall limit.
Installer, executable and database hashes remain mandatory; a successful HTTP
response cannot qualify an unverified payload. Temporary downloads are removed
after success or failure. No fallback version or mirror is selected.

If a transient failure still stops validation, rerun the **whole Test workflow**
after recovery. Coverage manifests bind the workflow run and attempt as well as
the candidate and source inputs. A failed-jobs-only rerun can pass PHREEQC but
will correctly reject coverage shards from the earlier attempt. Do not weaken
that check or substitute a prior PR's successful gate for main's result.

## One-time setup

1. **Trusted Publishing on PyPI** (maintainer, on pypi.org). `flahax` already
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
4. **Zenodo DOI** (maintainer, on zenodo.org; approved 2026-10-23). Sign in to
   [Zenodo](https://zenodo.org/) with GitHub, open
   [GitHub settings](https://zenodo.org/account/settings/github/) and switch
   on `rafatahmed/Flahax`. From then on every published GitHub Release is
   archived and gets a version DOI, with the metadata read from
   `CITATION.cff`. After the first archived release, add the concept DOI
   (the one that always resolves to the latest version) to `CITATION.cff`
   as `doi:` and to the README, by pull request.

## Releasing a version

1. On a `release/<version>` branch, align the version in `pyproject.toml`,
   `flahax.__version__`, `CITATION.cff`, README, user manual and API
   reference; write the changelog section; record readiness and evidence.
   Merge it by pull request after CI passes.
2. Confirm the publication decision with the maintainer. Merging is not approval.
3. **Finalize the artifact before tagging** (#71): after publication approval,
   use a short branch to date the changelog and align the manual's version line
   with that date (`released YYYY-MM-DD`). Review every candidate notice in the
   README (including installation and citation instructions), `CITATION.cff`,
   the manual, version release notes, documentation index, readiness page and
   installation pages. Replace candidate wording consistently; set any citation
   release date to the same declared date. Merge after CI passes. The tag must
   point at this commit: packaged documentation cannot change after upload.

   These are three separate states: **candidate**, **finalized artifact awaiting
   upload**, and **verified publication**. A dated changelog and matching manual
   declare the artifact's release date; they do not prove an upload happened.
   Lifecycle tests allow the finalized artifact before publication. Do not add
   a publication receipt to make CI pass. Record external publication only after
   checking the actual registry or archive, even if its date differs from the
   artifact's declared date.
4. Create the GitHub Release for tag `v<version>` on that merged `main`
   commit, with the changelog section as its notes. Publishing it starts the
   workflow.
5. Review the run: the guard notice, all test jobs, the live replay and the
   artifact hashes in the build summary. Then approve the `pypi` deployment.
6. After upload: check PyPI metadata, install `flahax==<version>` in a fresh
   environment, run the manual's examples and both CLI entry points, and
   record the date, run URL and hashes in [release evidence](site/evidence/release-evidence.md).
7. **Open the next development version** (#99): on a short branch, set
   `pyproject.toml`, `flahax.__version__`, the manual's title and the API
   reference to `<next>.dev0` (for example 0.6.0.dev0 after 0.5.0), and leave
   `CITATION.cff` at the released version. A development version sorts after
   the release and before the next one, so
   `pip install --upgrade "git+https://github.com/rafatahmed/Flahax.git@main"`
   replaces an installed release; with the released number on `main`, pip
   keeps the old package.

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
- The default version is `stable` (set and verified for 0.7.0 on 2026-11-19);
  `latest` continues to track development on `main`.
- Never put a Read the Docs token in the repository.

## Checklist (0.7.1)

- [x] Hardening and speed work merged (#334 to #355) and the changelog and
      [release notes](releases/0.7.1.md) written; migration guide updated.
- [x] Clean full CI-equivalent evidence run (#344): hosted run 46087636649 on `ef6ad37` (26 of 26
      jobs, Python 3.11 to 3.14) and a clean local run on Python 3.13; recorded in the release evidence.
- [x] Align the version, runtime version, citation, manual and generated API reference with
      0.7.1 as an unpublished candidate (no date, no version DOI).
- [ ] After approval and before tagging: date the changelog and the manual's version line, and
      add the comparison links; after publication add the version DOI.
- [ ] Explicit maintainer authorization for tag, release and package publication.
- [ ] Publish `v0.7.1`; review the protected publisher run and approve the `pypi` deployment.
- [ ] Verify actual PyPI and GitHub file hashes and fresh wheel and sdist installs.
- [ ] Confirm the Read the Docs `stable` version builds `v0.7.1`; confirm the Zenodo version DOI.
- [ ] Record the publication receipts and open the next development version.

## Checklist (0.7.0)

- [x] Align/finalize release metadata, manual, changelog and citation (2026-11-19).
- [x] Pass exact finalization PR #284 and main 8787877 CI (all 26 jobs).
- [x] Obtain explicit maintainer authorization for tag, release and package publication.
- [x] Publish v0.7.0; protected publisher 44436111286 passes all eight jobs.
- [x] Review artifact hashes and approve the existing pypi deployment protection gate.
- [x] Verify actual PyPI/GitHub file hashes and fresh published wheel/sdist installs.
- [x] Verify installed grower/Appendix I/replay/uncertainty journeys; retain physical limits.
- [x] Verify Zenodo 10.5281/zenodo.24356739 and exact-tag/stable documentation.
- [x] Record actual publication receipts and version DOI in this follow-up.
- [x] Integrate the 0.7.1.dev0 bookkeeping through PR/CI (merged as 485c645).

## Checklist (0.6.0)

- [x] Choose the version and align metadata, runtime version, citation, manual and changelog.
- [x] Review compatibility, scientific provenance and distribution contents (pre-release audit, #149-#151).
- [x] Pass local tests with live PHREEQC and isolated wheel/sdist verification.
- [x] Observe successful hosted checks on the merged revision (Linux 3.11-3.14, Windows and macOS 3.13).
- [x] Date the changelog, the manual's version line and `CITATION.cff` (2026-10-24), and merge, before tagging (#71).
- [x] Obtain explicit publication authorization.
- [x] Publish the `v0.6.0` GitHub Release; review the run; approve the deployment.
- [x] Verify PyPI metadata and a fresh installed-package check; record the date, run and hashes.
- [x] Confirm the Read the Docs `stable` version builds `v0.6.0`.
- [x] Zenodo: confirm the archived version and its DOI; add the concept DOI to `CITATION.cff` and the README.
- [x] Open 0.6.1.dev0 on `main` (step 7; closes #134 with the README reinstall note).

## Checklist (0.5.0)

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

Use only if the workflow route is unavailable, and only with the maintainer's
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
links use absolute documentation or repository URLs so they work on PyPI.
The clean wheel and sdist installation checks reject repository-relative links
in the installed metadata's README description. Render that description to
inspect Markdown presentation as well: `twine check --strict` alone does not
check Markdown links or demonstrate that a package was uploaded.

## Release history

- **0.7.0**, 2026-11-19: published from `8787877`, tag `v0.7.0`, through
  [protected run 44436111286](https://github.com/rafatahmed/Flahax/actions/runs/44436111286).
  Actual wheel/sdist hashes match GitHub assets; fresh PyPI installations and
  Appendix I journeys pass. Zenodo version DOI: 10.5281/zenodo.24356739;
  tagged/stable docs verified. See [publication evidence](site/evidence/release-evidence.md#070-publication-2026-11-19).

- **0.6.0**, 2026-10-24: published through the hardened workflow (run `40032809873`) from
  `03e03ef`, after the finalize step (#156); the deployment was approved by the maintainer, verified by
  a fresh installation from PyPI, and archived on Zenodo (10.5281/zenodo.23605679). See the
  [0.6.0 publication evidence](site/evidence/release-evidence.md).
- **0.5.0**, 2026-10-20: published through the hardened workflow (run
  `39517327774`) from `692108b`; the deployment was approved at the maintainer's
  instruction after artifact review, and verified by a fresh installation from
  PyPI. The packaged manual and changelog still say "not yet published" (#71).
  See the [0.5.0 publication evidence](site/evidence/release-evidence.md#050-publication---2026-10-20).
- **0.4.0**, 2026-10-17: first Apache-2.0 release and first upload through the
  hardened workflow with Trusted Publishing (run `39043172800`), approved by
  the maintainer, verified by a fresh installation from PyPI. See the
  [0.4.0 publication evidence](site/evidence/release-evidence.md#040-publication---2026-10-17).
- **0.3.1**, 2026-10-17: uploaded manually with Twine from `main` at
  `586eddb`, tagged `v0.3.1`, verified by a fresh installation from PyPI;
  hosted CI passed. See the
  [0.3.1 publication evidence](site/evidence/release-evidence.md#031-publication---2026-10-17).
  Its GitHub Release note was added on 2026-10-17; the old-workflow run it
  started was cancelled before approval.
- **0.3.0**, 2026-09-27: uploaded manually with Twine under a maintainer exception
  for local-only verification while hosted CI was blocked by billing.
  **Yanked on 2026-10-17** because its sdist contained a third-party PDF. The
  [GitHub release v0.3.0](https://github.com/rafatahmed/Flahax/releases/tag/v0.3.0)
  of 2026-10-01 used the existing PyPI artifacts; see the
  [release provenance and SHA-256 record](releases/0.3.0.md) and the
  [post-release audit](release-readiness.md).
- **0.2.0** and **0.1.0**, 2026-09-25: early releases; their files stay on
  PyPI.
