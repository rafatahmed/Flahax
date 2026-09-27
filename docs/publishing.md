# Publishing

## Release readiness before publication

Preparing or merging a branch is not permission to publish. This increment retains version `0.2.0`; a subsequent authorized release must choose an unused version and update `pyproject.toml`, `src/flahax/__init__.py`, `CITATION.cff` and version-specific documentation together. Do not reuse an existing uploaded version.

Before release, require successful hosted Python 3.11–3.13 distribution checks and pinned live PHREEQC replay for the reviewed revision. Local tests do not substitute for billing-blocked hosted jobs. Use [package verification](package-verification.md), [release evidence](release-evidence.md) and [release-readiness audit](release-readiness.md). Archive historical documentation rather than deleting scientific evidence. FlahaFAST integration is separate project work, not a package publication prerequisite.

After explicit publication authorization, build from the reviewed commit, inspect metadata and distribution contents, and follow the publishing procedure below. No publishing command is part of the cleanup/merge task.

This follows the [Python packaging tutorial](https://packaging.python.org/en/latest/tutorials/packaging-projects/). The project already uses the `src` layout, `pyproject.toml`, `README.md`, `LICENSE`, and `tests/`.

Build from the repository root, in the same directory as `pyproject.toml`:

```powershell
py -m pip install --upgrade build
py -m build
```

That writes two files under `dist/`:

- `flahax-0.2.0.tar.gz`, the source distribution
- `flahax-0.2.0-py3-none-any.whl`, the built distribution

Check them before uploading:

```powershell
py -m pip install --upgrade twine
py -m twine check dist/*
```

## GitHub release

`flahax` already exists on PyPI, so the publisher is added on the project, not as a pending publisher for a new name. Open [Manage projects](https://pypi.org/manage/projects/), choose `flahax`, then Publishing, and add a GitHub Actions publisher:

| Field | Value |
|---|---|
| Owner | `rafatahmed` |
| Repository | `Flahax` |
| Workflow | `publish.yml` |
| Environment | `pypi` |

A published GitHub Release runs `.github/workflows/publish.yml`. The build job makes the archives. The publish job has only `id-token: write` and asks PyPI for a token that lasts about 15 minutes. No long-lived API token is stored in the repository.

PyPI keeps every uploaded filename. The next release needs a new `version` in `pyproject.toml`. Version 0.1.0 stays on the index.

## Manual upload

A local upload is the same build, then:

```powershell
py -m twine upload dist/*
```

The username is `__token__` and the password is an API token, including the `pypi-` prefix. Keep that token in `%USERPROFILE%\.pypirc`, not in this repository. `.gitignore` ignores a `.pypirc` copied here by mistake. A TestPyPI rehearsal adds `--repository testpypi` and uses an account on [test.pypi.org](https://test.pypi.org).
