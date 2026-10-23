# Development and release conventions

Everyone who takes part in FlahaX follows the [code of conduct](CODE_OF_CONDUCT.md)
(Contributor Covenant 2.1). Report security problems privately, as
[SECURITY.md](SECURITY.md) explains, not in a public issue.

## Branch names

Name branches after the phase, issue, stage or release being delivered.
Examples: `phase/p6-package-verification`, `issue/42-input-validation`,
`stage/stock-evidence`, `release/0.3.1-site-planning`.
Do not use tool-, vendor- or assistant-branded branch prefixes. Preserve work
when renaming a branch; do not rewrite historical commits merely to change
old branch labels recorded in merge messages.

## Change and evidence boundaries

Inspect the working tree before editing. Preserve unrelated changes, valid
reference fixtures, failure reproducers and local source documents. Keep
scientific citations and actual validation outcomes; do not manufacture
independent sign-off, measured data or compatibility approvals.

Keep code and documentation product-focused. Do not add assistant attribution
or generated-by branding. Maintain source/license attribution where required.
Never commit credentials, executables or private/local-only source material.

## Code style

FlahaX follows PEP 8 with a line length of 99 characters (the team allowance PEP 8 gives). The
settings are in `pyproject.toml`; `ruff` is a development tool only, never a runtime dependency.

```bash
python -m pip install ruff==0.8.4
ruff format .
ruff check .
```

Every Python file starts, in this order, with: a shebang (`#!/usr/bin/env python3`) only for
runnable tools and examples; the header comments (SPDX copyright and license, and the
disclaimer); the module docstring; `from __future__` imports; module dunders such as `__all__`
and `__version__`; then the imports. No encoding line is needed. Code must also run on
Python 3.11: inside an f-string, use the other quote type in replacement fields.
A long message is split into adjacent string literals inside brackets; only text that FlahaX
writes out unchanged (report CSS, Markdown tables) keeps its long lines, with `# noqa: E501` on
the closing line of that string.
Every public class, method and function in `src/flahax` has a docstring that says what it
returns or represents; `tests/test_public_docstrings.py` and ruff (D101-D103) check it.
`tests/test_file_headers.py` and the CI `style` job check all of this.

## Required validation

```powershell
$env:PYTHONPATH = 'src'
$env:FLAHAX_REQUIRE_PHREEQC = '1'
python -m unittest discover -s tests -t .
python -m compileall -q src examples tools
git diff --check
python tools/verify_distribution.py
```

Use the provisioned external PHREEQC and temporary database merge; never
modify the base database to pass tests. Distribution checks require the
development `build` package, not a new runtime dependency. Review staged
paths before committing and verify the remote branch after pushing.

## Releases

Keep package metadata, public version, citation and shipped manual aligned.
Preparation is not publication: do not set a release date until release,
reuse a published version for changed artifacts, or carry a prior CI exception
forward automatically. Obtain review, hosted evidence and explicit publication
approval under [the publishing checklist](docs/publishing.md).
