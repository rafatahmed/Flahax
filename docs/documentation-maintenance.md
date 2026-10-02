# Documentation maintenance and pre-publication review

## Sources of truth

| Reader need | Canonical source | Validation |
|---|---|---|
| Package introduction and install | Root README | Python quick start executed in tests |
| End-to-end use, units and interpretation | Shipped `USER_GUIDE.md` | Every Python block runs independently in source and clean installs |
| Public signatures and result fields | Shipped `API_REFERENCE.md` | Generated from `flahax.__all__`; exact-content regression |
| Nested input schemas | Focused pages linked from `docs/index.md` | Workflow/CLI contract tests |
| Scientific acceptance | Coverage, fixtures and release evidence | Offline regressions and required live PHREEQC replay |
| Version changes and publication | Changelog and publishing checklist | Release metadata tests; explicit owner authorization |

Do not copy historical test counts into current product claims. Keep dated
verification evidence separate from instructions. The PyPI release, checkout
version, schema revision and thermodynamic profile are different identifiers.
Older evidence remains historical; editing a guide does not retrospectively
validate a published artifact.

## Updating a function

1. Describe its purpose, required inputs, units, defaults, return values and
   rejection behavior in its source docstring. Explain distinctions between
   missing, zero and unsupported values. Avoid promises beyond tested scope.
2. Update the relevant workflow contract and runnable manual example when
   semantics change; do not merely change a generated signature.
3. Regenerate the reference with `tools/generate_api_reference.py`. Its inventory
   includes compatibility kernels, which are not interchangeable with the
   coupled solver. Importable submodule helpers are not automatically public APIs.
4. Run the checks below. If adding a manual Python example, update the expected
   count in both source and clean-install checks so accidental removal is caught.
5. Record behavior changes in the changelog. Never label a generated inventory
   or numerical agreement as independent scientific review.

```powershell
$env:PYTHONPATH = 'src'
py -3.13 tools/generate_api_reference.py --check
py -3.13 -m unittest tests.test_release_hygiene
$env:FLAHAX_REQUIRE_PHREEQC = '1'
py -3.13 -m unittest discover -s tests -t .
py -3.13 -m compileall -q src tools examples
git diff --check
.venv-verification/Scripts/python.exe tools/verify_distribution.py --python C:/Users/rafat/AppData/Local/Programs/Python/Python313/python.exe --report build/documentation-0.3.1-distribution.json
```

The last command shows this repository's local verification environment;
replace interpreter paths with your own development environment containing
`build`. It creates isolated installs and does not upload packages.

## 0.3.1 documentation audit findings

- Corrected the manual and formulation guide: `recommend` filters/reorders
  candidate products, so its raw `grams` vector cannot be zipped with the
  original catalogue. Use identity-bearing `salts` records instead.
- Replaced the README's undated 110-test claim with a link to dated evidence.
- Added a shipped inventory of all public exports, not just formulation calls.
- Added independently executable workflow, EC-rejection and A/B sizing examples.
- Clarified numerical result versus approval, source-water nutrients versus
  complete acid/base analysis, recipe acid versus additional acid, and stock
  inventory versus tank capacity.
- Kept 0.3.1 unpublished and preserved the historical 0.3.0 exception without
  applying it to a new release. Hosted CI and publication approval remain gates.

This is a documentation/verification improvement, not a new thermodynamic
model, field-calibrated EC claim or equipment integration. No chemical
parameters, fixtures, product boundaries or numerical solver algorithms changed.
