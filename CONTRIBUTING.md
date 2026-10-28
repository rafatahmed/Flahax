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

## Changelog

`CHANGELOG.md` follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) for every
release:

- `## [Unreleased]` comes first; at release its entries move to `## [X.Y.Z] - YYYY-MM-DD`
  (a yanked release adds `[YANKED]` and keeps its section);
- each release opens with a short paragraph: what it is, any breaking change, the supported
  Python and known limits;
- bullets are grouped under the six change types only: **Added**, **Changed**, **Deprecated**,
  **Removed**, **Fixed**, **Security**; each bullet names its issues and is at most 400
  characters, and related changes share one bullet;
- the bottom of the file has a comparison link for every version and for `unreleased`.

The full text of a change (numbers, sources, decisions) belongs in `docs/releases/<version>.md`,
linked with a full GitHub URL, because the docs site includes the changelog. `tests/test_changelog.py`
checks all of this.

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

For implementation evidence, use the [traceability validator](https://github.com/rafatahmed/Flahax/blob/main/docs/traceability-validation.md).
It checks issue-first dependencies and distinguishes reproduced defects from passing fixes.
Keep personal execution ledgers outside versioned sources; validate them before starting a
dependent task or recording completion.

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

## Runtime coverage evidence

Coverage is a control-flow check, not independent numerical verification. Retain
analytical or independently implemented numerical witnesses alongside regression
tests, and label synthetic states and fault injection explicitly. Never interpret
a passing rendering or refusal test as a physically validated recipe.

Measure statements and branches with the configuration in pyproject.toml. Keep
all runtime modules in the denominator, including modules not imported by a test.
A rounded percentage is insufficient: completion requires zero missing statements
and zero missing branches for every runtime Python file. Tool, example, benchmark
and documentation Python coverage remains a separate package-wide obligation.

Record the Git revision, exact source hashes, Python/platform versions, coverage
configuration and commands before measuring. Use tools/check_coverage.py to
inventory and validate the evidence; see its --help for manifest and report
options. Preserve failed test logs as failures, then retain the passing regression
rerun separately. Coverage accumulated during a failed run does not establish that
the test suite passed.

Combine native-platform coverage only for identical source contents and preserve
the raw data files. If any runtime file changes, discard its earlier measurements
and measure that file again; line-number unions across changed source are invalid.
Platform-specific tests must report actual executed tests and skips. Cygwin
evidence identifies the Cygwin interpreter and does not establish a Linux or macOS
result.

Executable documentation may create synthetic filenames such as a Markdown path
with a line-number suffix. Generate the final JSON report using the complete
inventoried Python source list, with paths normalized for the measurement host.
Check that report files match that inventory. Do not omit real Python sources to
work around synthetic snippet filenames or silently ignore missing source.
