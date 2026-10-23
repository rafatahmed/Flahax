# Install

FlahaX needs Python 3.11 or newer and has no third-party runtime dependencies. Install it in a
virtual environment:

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux and macOS: source .venv/bin/activate
python -m pip install flahax
```

Pin the version for reproducible work, for example `python -m pip install flahax==0.6.0`.

## Check what is installed

```bash
flahax --version
```

If `flahax` is not recognised, run `python -m flahax --version`: pip may have put the `flahax`
program in a folder that is not on your PATH (its warning names the folder).

## Upgrade

```bash
python -m pip install --upgrade flahax
```

One version lives in each Python environment. To keep an older version for comparison, install it
in its own virtual environment.

## Try unreleased changes

Between releases every commit on `main` has the same development version, so a plain `--upgrade`
can keep the files you already have. Reinstall instead:

```bash
python -m pip install --force-reinstall --no-deps "git+https://github.com/rafatahmed/Flahax.git@main"
```

## Something went wrong

See [Installing and upgrading](../reference/manual.md#installing-and-upgrading) in the
troubleshooting section of the manual.

**Next:** [your first batch](first-batch.md) with `flahax mix`, or
[your first recipe in Python](first-recipe.md).
