# Publishing

## Owner-authorized 0.3.0 exception — 2026-09-27

The owner explicitly approved publishing based on verified local evidence despite the billing blocker. For **0.3.0 only**, this supersedes the hosted-CI publication prerequisite below. Evidence: 110 local tests with zero skips, pinned live PHREEQC, clean wheel/sdist installs, four shipped-manual examples and strict Twine checks. Hosted Python 3.11/3.12 checks remain unverified; no pass is inferred. Manual Twine upload is authorized, subject to final artifact validation and available local authentication. Upload success must be confirmed separately.

## Release readiness before publication

Preparing or merging a branch is not permission to publish. The owner requested preparation of `0.3.0`; metadata, citation and manual now use that version. Public PyPI metadata was checked during preparation: latest `0.2.0`, no `0.3.0` release. Recheck availability before upload; add the actual release date to `CITATION.cff` only when publication is authorized. Do not reuse an existing uploaded version.

Before release, require successful hosted Python 3.11–3.13 distribution checks and pinned live PHREEQC replay for the reviewed revision. Local tests do not substitute for billing-blocked hosted jobs. Use [package verification](package-verification.md), [release evidence](release-evidence.md) and [release-readiness audit](release-readiness.md). Archive historical documentation rather than deleting scientific evidence. FlahaFAST integration is separate project work, not a package publication prerequisite.

After explicit publication authorization, build from the reviewed commit, inspect metadata and distribution contents, and follow the publishing procedure below. No publishing command is part of the cleanup/merge task.

### 0.3.0 checklist

- [x] Align package metadata, runtime version, citation and changelog.
- [x] Ship the user manual in wheel and source distribution; test all four Python examples in each installed artifact.
- [x] Pass 110 local tests including live PHREEQC, isolated distribution checks and Twine metadata validation.
- [ ] Resolve GitHub account billing and pass all hosted checks on the final reviewed revision.
- [ ] Review and merge the release branch without bypassing failed checks.
- [ ] Obtain explicit publication approval; confirm PyPI version availability, set the actual citation release date and review the release/tag.
- [ ] Publish and verify the installed PyPI version in a new environment.

The preserved local candidate archives are build evidence, not an instruction to skip rebuilding from the final approved release revision. FlahaFAST integration remains outside this checklist.

This follows the [Python packaging tutorial](https://packaging.python.org/en/latest/tutorials/packaging-projects/). The project already uses the `src` layout, `pyproject.toml`, `README.md`, `LICENSE`, and `tests/`.

Build from the repository root, in the same directory as `pyproject.toml`:

```powershell
py -m pip install --upgrade build
py -m build
```

That writes two files under `dist/`:

- `flahax-0.3.0.tar.gz`, the source distribution
- `flahax-0.3.0-py3-none-any.whl`, the built distribution

Check them before uploading:

```powershell
py -m pip install --upgrade twine
py -m twine check dist/*
```

## Manual Twine upload — selected release method

The project owner selected local Twine upload for 0.3.0. This does not require GitHub Trusted Publishing or an account-level pending publisher. It also does not, by itself, waive the hosted verification requirement above.

Once release approval and verification gates are resolved, upload only the exact approved wheel and source distribution, not every file in an old `dist` folder. The locally verified candidate paths are:

```powershell
.\.venv-verification\Scripts\python.exe -m twine check --strict dist/0.3.0-final/flahax-0.3.0.tar.gz dist/0.3.0-final/flahax-0.3.0-py3-none-any.whl
# Run only after release approval and final artifact review:
.\.venv-verification\Scripts\python.exe -m twine upload --repository-url https://upload.pypi.org/legacy/ dist/0.3.0-final/flahax-0.3.0.tar.gz dist/0.3.0-final/flahax-0.3.0-py3-none-any.whl
```

Use a PyPI token authorized for the existing `flahax` project through Twine's secure prompt or operating-system keyring. Never paste tokens into chat, commit them, or put them directly in shell command arguments. Do not inspect or print credential files. See [Twine configuration and keyring guidance](https://twine.readthedocs.io/en/stable/).

After upload, verify the version on PyPI and install `flahax==0.3.0` in a new environment; check imports, CLI and the bundled manual again. A TestPyPI rehearsal is a separate upload with its own credentials and authorization.

## Optional GitHub Trusted Publishing — not the selected 0.3.0 route

`flahax` already exists on PyPI, so the publisher is added on the project, not as a pending publisher for a new name. Open [Manage projects](https://pypi.org/manage/projects/), choose `flahax`, then Publishing, and add a GitHub Actions publisher:

| Field | Value |
|---|---|
| Owner | `rafatahmed` |
| Repository | `Flahax` |
| Workflow | `publish.yml` |
| Environment | `pypi` |

A published GitHub Release currently triggers `.github/workflows/publish.yml`. Do not trigger this automatic uploader for a version uploaded manually; duplicate publication is not part of this procedure. The workflow and external publisher settings have not been changed by selecting the manual route.

PyPI keeps every uploaded filename. The next release needs a new `version` in `pyproject.toml`. Version 0.1.0 stays on the index.

## PyPI README validation

The built metadata declares `Description-Content-Type: text/markdown`. README links use absolute repository URLs so they work from the PyPI project page. Both 0.3.0 candidate archives pass `twine check --strict`. This follows the [PyPA README guidance](https://packaging.python.org/en/latest/guides/making-a-pypi-friendly-readme/); metadata validation does not assert that the package has been uploaded.
