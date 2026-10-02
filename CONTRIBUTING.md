# Development and release conventions

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
