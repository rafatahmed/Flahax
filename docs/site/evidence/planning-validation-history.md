# Planning validation history

These records were moved from the workflow guides without changing their
reported results. They describe dated local development runs, including failed
attempts, reruns, and checks performed before later edits. They are not current
test counts, hosted release acceptance, independent review, or physical
validation. For version-specific evidence, see [release evidence](release-evidence.md).

## Water-to-delivery validation

Original guide: [water-to-delivery](../developer/water-to-delivery.md).

### Local validation, 2026-09-28

During water-to-delivery development, Windows / Python 3.14.0:

| Command / check | Observed result |
|---|---|
| `PYTHONPATH=src FLAHAX_REQUIRE_PHREEQC=1 python -m unittest discover -s tests -t .` | 121 tests passed in 261.424 seconds; no skips |
| Two subsequently added tests: changed catalogue assay and non-mapping maxima (`tests.test_water_workflow.WaterWorkflowTests`) | Both passed; 123 distinct tests exercised across these runs, not a claimed 123-test single run |
| `python -m unittest tests.test_acid_reference -v` with required PHREEQC | Both golden comparison and live replay passed |
| `.venv-verification/Scripts/python.exe tools/verify_distribution.py --report build/water-workflow-distribution-verification.json` | Clean wheel and sdist installs passed, including four existing manual examples, exports and CLI checks |
| `python -m compileall -q src tools`; `git diff --check` | Passed |

Historical record from the 0.3.1 development increment. The distribution check preceded final documentation-only edits. Its report is
local build evidence, not a release artifact manifest. No new version was
published, no hosted acceptance was claimed and the published 0.3.0 files were
not replaced. Run the current complete suite again before release; these local
results do not waive the normal supported-version/hosted verification gates.


## Site planning validation

Original guide: [site-planning](../developer/site-planning.md).

### Local verification, 2026-09-30

- `PYTHONPATH=src FLAHAX_REQUIRE_PHREEQC=1 python -m unittest discover -s tests -t .`:
  **149 tests passed, 207.550 s, zero skips** (environment variables set with
  `$env:...` in PowerShell). PHREEQC live replay used the existing external
  installation; its executable and base database were not modified.
- Initial sandboxed full run: 149 tests, two temporary-directory permission
  errors in live PHREEQC replay. The successful full rerun used approved
  temporary-directory access; no test or tolerance was removed to pass.
- Focused workflow/examples/source-input tests: 31 passed in 73.327 s.
  Final site-input/release-hygiene check: 13 passed in 1.175 s.
- `python -m compileall -q src examples`: passed.
- `git diff --check`: passed (line-ending normalization warnings only).
- `python -m examples.run_all --output build/site-planning-reviewed`: generated
  HTML, Markdown and JSON; browser inspection confirmed the calculated EC chart,
  unavailable-stock rows and per-channel flow table render correctly.

These checks verify arithmetic, data transcription and rejection boundaries;
they do not establish experimental accuracy of the screening approximation,
validate a concentrated-stock conductivity model, or approve equipment.


## Conductivity validation

Original guide: [conductivity](../developer/conductivity.md).

Local verification on Windows/Python 3.14.0, 2026-09-28: the full suite with
`PYTHONPATH=src` and `FLAHAX_REQUIRE_PHREEQC=1` passed 137 tests in 167.484 s,
with no skips. After the final overflow-safe TDS arithmetic adjustment,
`python -m unittest tests.test_conductivity tests.test_examples tests.test_release_hygiene -q`
passed all 17 tests. Compilation and `git diff --check` passed. Clean wheel
and sdist installation checks passed before that final arithmetic adjustment
(`build/ec-distribution-verification.json`); these are local development checks,
not hosted release approval or a physical EC accuracy certification.
