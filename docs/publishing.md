# Publishing

## Published 0.3.0 record

PyPI metadata confirms the wheel and sdist were uploaded on **2026-09-27**. PRs #3 and #4 are merged. Version 0.3.0 is already used and must not be uploaded again. See the [post-release audit](release-readiness.md).

The owner explicitly approved manual Twine publication based on verified local evidence despite the GitHub billing blocker. The exception applies only to 0.3.0. Release evidence records 110 local tests with zero skips, pinned live PHREEQC, clean candidate wheel/sdist installs, four shipped-manual examples and strict Twine checks. Hosted verification remains open; neither merging nor publication establishes a hosted pass.

A fresh isolated Python 3.13 installation from PyPI passed version/import checks, all four bundled manual examples and both CLI entry points on 2026-09-28. See the post-release audit for the distinction between published-wheel and candidate-sdist evidence.

## Checklist for the next release

- [ ] Choose a new version and align metadata, runtime version, citation, manual and changelog.
- [ ] Review compatibility, scientific provenance and distribution contents.
- [ ] Pass relevant local tests, required pinned live replay and isolated wheel/sdist verification.
- [ ] Observe successful hosted Python 3.11–3.13 checks and pinned live-reference replay on the reviewed revision.
- [ ] Obtain explicit publication authorization and check that the new version is unused on PyPI.
- [ ] Build and strictly validate the exact approved artifacts; record their hashes.
- [ ] Upload through the approved release route; verify PyPI metadata and a fresh installed-package check.
- [ ] Record the actual publication date and retain release evidence.

Preparing or merging a branch does not authorize publication. Use [package verification](package-verification.md) and [release evidence](release-evidence.md). FlahaFAST integration is separate work. The commands below preserve the historical 0.3.0 procedure; substitute a newly approved version and artifact directory for future releases.

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

The project owner selected local Twine upload for 0.3.0. This does not require GitHub Trusted Publishing or an account-level pending publisher. The separate owner exception waived the hosted publication prerequisite for that release only.

Once release approval and verification gates are resolved, upload only the exact approved wheel and source distribution, not every file in an old `dist` folder. The locally verified candidate paths are:

```powershell
.\.venv-verification\Scripts\python.exe -m twine check --strict dist/0.3.0-final/flahax-0.3.0.tar.gz dist/0.3.0-final/flahax-0.3.0-py3-none-any.whl
# Historical example only: 0.3.0 is already published; do not rerun this upload.
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
