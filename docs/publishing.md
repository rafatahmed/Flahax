# Publishing

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
