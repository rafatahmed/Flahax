# Publishing

This follows the [Python packaging tutorial](https://packaging.python.org/en/latest/tutorials/packaging-projects/). The project already uses the `src` layout, `pyproject.toml`, `README.md`, `LICENSE`, and `tests/`.

Build from the repository root, in the same directory as `pyproject.toml`:

```powershell
py -m pip install --upgrade build
py -m build
```

That writes two files under `dist/`:

- `flahax-0.1.0.tar.gz`, the source distribution
- `flahax-0.1.0-py3-none-any.whl`, the built distribution

Check them before uploading:

```powershell
py -m pip install --upgrade twine
py -m twine check dist/*
```

## GitHub release

Pushing a GitHub Release runs `.github/workflows/publish.yml`. That workflow builds `dist/`, checks it with Twine, and publishes to PyPI. The workflow password is the repository secret `PYPI_API_TOKEN`. The username Twine sends is `__token__`. The token value stays in GitHub secret storage, not in this repository.

A new PyPI upload needs a new `version` in `pyproject.toml` before the next release. PyPI keeps a filename that was already published.

## Manual upload

A local upload is the same build, then:

```powershell
py -m twine upload dist/*
```

The username is `__token__` and the password is an API token, including the `pypi-` prefix. Keep that token in `%USERPROFILE%\.pypirc`, not in this repository. `.gitignore` ignores a `.pypirc` copied here by mistake. A TestPyPI rehearsal adds `--repository testpypi` and uses an account on [test.pypi.org](https://test.pypi.org).
