# Implementation evidence validation

The implementation ledger is a local execution artifact, supplied explicitly to
`tools/check_traceability.py`. Keep personal plans and execution records out of
commits and distributions. The validator does not execute commands, contact GitHub,
approve changes, or independently certify the scientific content of a report.

```powershell
python tools/check_traceability.py PATH_TO_LEDGER
python tools/check_traceability.py PATH_TO_LEDGER --check-ready TASK_ID
python tools/check_traceability.py PATH_TO_LEDGER --csv PATH_TO_CSV --plan PATH_TO_PLAN
```

The last command checks derived summaries for drift. Add `--write-summaries` to
regenerate them only after the ledger passes validation. Preserve the prior ledger
and raw evidence before updating state. A successful command means the recorded
state satisfies this contract; it does not mean the mathematical engine is complete.

## Dependencies and issue tracking

Schema version 2 names an issue gate, reproduction task and final acceptance task.
Every fix and the acceptance task must depend transitively on the issue gate.
Active tasks require completed direct prerequisites. Mathematical tasks cannot
depend on a physical-validation task. Unknown dependencies, duplicates and cycles
fail validation.

Before a fix starts, record its deduplicated issue URL, verified open state,
the assignee required by the external ledger policy, existing repository labels, verification time and raw
metadata evidence. The offline validator checks the recorded evidence file hash;
the executor must obtain the metadata from GitHub and verify its accuracy. A
missing issue is a blocker, not a reason to mark the tracking package complete.

## Reproduction is distinct from resolution

A reproduction package can complete with `test_outcome: reproduction_verified`.
It requires the complete registered control inventory, independently validated
oracles, immutable input hashes, retained assertion-failure reports and fix owners.
Oracle self-tests must pass. Baseline assertion checks must exit 1; an import error,
missing executable, timeout or unrelated suite failure is not a reproduced defect.
Keep control-level logs so an unrelated failure cannot be substituted for evidence.

Product regressions remain failing and unresolved. Do not use expected-failure
decorators, change expected truth, or label reproduction as a passing repair.
Each owning fix must pass the same frozen control input, retain its passing report,
and identify the implementation revision. Review must verify the oracle and
assertion themselves have not been weakened. Historical failing logs are retained.

Ordinary completed packages require passing tests, documentation, review and
hash-checked evidence. Final acceptance additionally requires every mathematical
package complete and every registered control resolved. Physical validation is
excluded from that completion gate.

## Evidence limitations

Evidence records include a file path, SHA-256, command, environment, source revision
and process exit code. Hash verification detects missing or altered artifacts, not
fabricated evidence or an incorrect oracle. Review of commands, source identity,
scientific applicability and report contents remains mandatory. Source revisions
must be augmented with dirty-source hashes when results come from uncommitted work.

Run `python -m unittest tests.test_traceability` to exercise bypasses, reproduction
semantics, unchanged-input checks, evidence corruption and final-acceptance rules.

## Requirement inventory

`python tools/check_requirements.py PATH_TO_REGISTER` checks required identifiers,
finding links, task ownership and the current public exports/runtime files. Each
export needs a public-path contract. Passing this inventory check means requirements
are assigned; it does not mean they are implemented. Proposed numerical criteria
remain explicitly unqualified until their independent error analysis is reviewed.

## Coverage evidence

Use the pinned Coverage.py 7.17.0 development tool with the shared project
configuration. It measures branches, child Python processes, runtime modules,
tools, examples, benchmarks and Sphinx configuration. Record source identity before
collection and do not edit measured source until collection and reporting finish.

```powershell
$env:PYTHONPATH = 'src'
$env:COVERAGE_FILE = 'build/coverage-run/.coverage'
python tools/check_coverage.py --manifest build/coverage-run/manifest.json --record-manifest
python -m coverage run -m unittest discover -s tests -t .
python -m coverage combine
python -m coverage json -o build/coverage-run/coverage.json
python tools/check_coverage.py --manifest build/coverage-run/manifest.json --report build/coverage-run/coverage.json
```

Use a new run directory; manifests refuse overwrites. Retain failures and skips.
The gate requires zero missing statements and branch destinations, checks the full
source inventory and rejects source/configuration changes. An incomplete baseline
is expected to fail the gate; never turn that result into a passing acceptance claim.
Runtime, support and documentation-build counts are separate. Existing tool-level
structural branch handling must still be reviewed before an unqualified coverage claim.

Native Python 3.13 CI jobs collect separate artifacts for Linux, Windows and macOS.
Cross-platform aggregation, required-job completeness and hosted status enforcement
remain separate acceptance infrastructure. A single local report cannot certify them.

## Numeric decisions and regression controls

`python tools/inventory_numeric_decisions.py --output PATH_TO_NEW_SNAPSHOT` inventories
runtime numeric literals, comparisons (including named thresholds), argument defaults,
and numeric values (including numeric-only strings) in packaged JSON. Each entry retains
its source hash and location.
All entries start unreviewed. Syntax is not a scientific/numerical/policy/input
classification, and a source hash is not evidence of applicability. Semantic review
must also inspect formula/equation strings and computed parameters before closing the
source audit. Existing review dispositions are never overwritten automatically.

`python -m unittest tests.test_audit_controls -v` runs exact rational oracle checks and
the preserved product counterexamples. The latter are ordinary failing assertions
until their owning fixes pass. They also participate in normal test discovery.
The controls cover zeros, targeted maxima, fit penalties, secondary selection, trace
doses and infeasibility warnings. The scientific and joint-control modules add unit
bases, carbon preservation, model-domain reporting, tank/phase policy, provenance
and consistency of final recipe diagnoses. These are minimum counterexamples, not
complete scientific closure. Keep individual failure logs, frozen source and the
catalogue/model/helper inputs; an import/setup error never counts as reproduction.

Run the independent reference checks separately:

```powershell
python -m unittest tests.test_audit_oracles tests.test_audit_controls.IndependentOracleTests tests.test_audit_scientific_controls.ScientificOracleTests -v
```

The carbon-free phosphate witness is an exact proton/charge inventory, not a solved
equilibrium at the helper's pH. It establishes that positive alkalinity does not imply
positive carbon. The regression's known-zero inventory must be preserved or its
unsupported/contradictory input rejected; the witness does not qualify carbon inference.

For the omitted-competition control, explicit unsupported/incomplete refusal is valid.
A returned result may instead expose `model_limitations` containing a record with
`code: omitted_competition` and `components: [Dtp-5, Cu+2]`. This is an acceptance
contract for future implementation, not a claim that the current result supports it.
An unrelated limitation or generic accuracy disclaimer does not qualify that pair.
Preserve old test versions and failure evidence when reviewing a control before
freezing its final acceptance contract; never silently overwrite historical evidence.

## Reviewing numeric sources

```powershell
python tools/check_numeric_review.py PATH_TO_REVIEW_REGISTER
python tools/check_numeric_review.py PATH_TO_REVIEW_REGISTER --require-qualified
```

The first command verifies complete, current inventory mapping and recorded semantic
dispositions. Groups may contain scientific, numerical, policy and input decisions
together where expressions combine them. The exact expressions, assignments and
source hashes remain available for quantity-level follow-up. Grouping does not qualify
every coefficient or tolerance in a file.

`retain_unqualified` records an inherited decision with its units/context, conditions,
source limitations and follow-up owner. It cannot be marked adopted. This allows the
inventory/disposition audit to finish while the assigned scientific and numerical
qualification work remains open. It does not authorize treating inherited values as
newly approved ranges, limits or target flexibility. The strict command rejects these
unqualified groups. A qualified claim additionally requires passing, hash-bound
independent evidence, applicability and review; the validator cannot assess the
scientific truth of that evidence. Only purely structural metadata can use the
structural disposition.

Run `python -m unittest tests.test_numeric_review tests.test_threshold_register` to
check missing entries, stale source, numeric strings, omitted context, false adoption
and qualification evidence corruption.
