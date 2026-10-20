# Benchmark v1: specification and reproduction

**Objective:** measure FlahaX's speed, numerical agreement, and limitations
reproducibly. No outcome is assumed in advance. A lower runtime is meaningful
only when the calculation passes its correctness gate.

This is a versioned benchmark protocol, not a claim of physical validation.
The scripts produce local JSON and ASV records; running them does not publish
results or modify the chemistry model. Initial timings are informational.

## Four separate scorecards

| Scorecard | v1 implementation | Interpretation |
|---|---|---|
| Formulation | All shipped crop formulas, each with zero nutrient contributions and 20 mg/L water calcium; returned rounded doses independently reconstructed from catalogue elemental assays | Target fit, not a unique optimal fertilizer recipe or agronomic suitability |
| Numerical chemistry | Existing product and phase PHREEQC captures, their hashes and quantity-specific tolerances | Agreement with stored reference calculations sharing thermodynamic data; not new live replay or physical validation |
| Performance | ASV workloads below, with setup and correctness checks outside timed kernels | Runtime and peak process memory on the recorded machine, not a universal speed claim |
| Experimental validation | Not performed by this suite | Needs an independent physical protocol, measured concentrations/pH/EC and measurement uncertainty |

## Frozen inputs and evaluation rules

The protocol identifier is `benchmark-v1`. Each run records hashes of the
runtime source, model/catalogue JSON, benchmark harness, and stored PHREEQC
fixtures. Catalogue changes therefore create a different input manifest even
if the protocol identifier remains the same. Do not compare such runs as
performance-only changes without disclosing the changed inputs.

### Formulation

The application scorecard evaluates `recommend()` with its current documented
defaults. It maps returned product IDs back to assays and reconstructs delivered
mg/L from **returned six-decimal g/L doses**, not the solver's reported rows.
The pass tolerance per explicit target is `max(0.01 mg/L, 1% of target)`.
Zero targets use the absolute tolerance. Missing targets are not scored.
These are benchmark tolerances, not crop safety thresholds.

Report per-element residuals, element pass fraction, RMS percentage deviation,
maximum percentage deviation, RMSE in mg/L, and whole-recipe pass fraction.
The recipe denominator includes every attempted case. Exceptions remain
visible; completed-case element metrics exclude exceptions and must be read
alongside attempted/completed counts. A target-fit failure is a measured
limitation and does not by itself fail the harness.

The evaluator covers declared catalogue assays. Unassayed counterion sodium
is outside this independent target-fit reconstruction; incidental review and
the solver's feasibility flag are retained separately. This scorecard does
not certify every incidental nutrient or concentration limit.

The separate kernel scorecard compares FlahaX NNLS with
[SciPy NNLS](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.nnls.html)
on identical explicit matrices and right-hand sides: feasible, infeasible,
water-excess, duplicate, nearly dependent, trace-scale, and zero-target cases.
Nonnegative finite weights are required. The squared-objective difference
must be at most `1e-12 + 1e-8 * reference objective`. Equal dose vectors are not
required for nonunique systems. These small controlled cases do not establish
global solver correctness or an aligned comparison of full product policies.

### Chemistry

Product and phase records are read from `tests/fixtures/phreeqc/`; recorded
source hashes are verified before use. Preserve fixture-specific combined
absolute/relative molality and acid-dose tolerances, absolute log-activity and
saturation-index tolerances, and phase-amount tolerances. Conservation uses
`1e-15 + 1e-9 * component total`; phase complementarity uses `1e-7` SI.
Report every comparison and available final-state iteration count, including
failed comparisons. Do not silently widen tolerances to improve results.

These captures prescribe pH. The nitric case solves reagent demand to a
prescribed target; it does not independently validate prediction of an unknown
initial pH. Iterations describe the returned final state, not the total work
across all acid-search solves. Existing mass-action, charge, input-boundary,
and calculated-pH regression tests remain necessary in addition to this report.
Run live replay separately using the existing PHREEQC CI procedure.

### Performance

| Workload | Timed scope | Gate / limitation |
|---|---|---|
| Fresh-process import | Interpreter/process startup and `import flahax` | Nonzero exit fails; filesystem cache is not flushed |
| Library loading | Catalogue JSON loading | Nonempty catalogue |
| NNLS kernel | Fixed numerical systems | Independent SciPy objective check |
| Full formulation | `recommend()` with the pepper targets and two calcium levels | Independent returned-dose target-fit check; includes selection and simplification |
| Mixed speciation | Existing mixed-product fixture, no active phases | Stored capture and conservation checks |
| Active phases | Calcite and mixed-product phase fixtures | Capture, conservation and complementarity checks |
| Nitric target | Existing acid-target fixture | Capture and acid-demand checks |
| Experimental EC | Speciation-based 0.01 mol/kg-water KCl at calculated pH | Versioned numerical regression, not physical validation |
| Composed delivery | Existing synthetic equilibrium delivery example | Completed calculation; includes record construction and planning, never hardware control |

ASV runs one round of ten measured repetitions with `number=1`. Setup loads inputs and
warms calculations outside timings; teardown rejects incorrect results.
Peak-memory benchmarks cover formulation and equilibrium and report process
peak memory, including interpreter/import overhead. They are not incremental
allocation measurements. Iteration tracking is separate from timings.

Use the raw samples, median, and nearest-rank p95. With ten samples, p95 is
the maximum: it is descriptive and not a stable production tail-latency
estimate. ASV's `--quick` is smoke validation only. Installation time, full
scaling curves, and whole-workflow iteration counts are not measured in v1.

## Run locally

Use a separate development environment; these tools are not runtime
dependencies. The pinned toolchain requires Python 3.13 or newer for the
commands below (the library still supports its documented Python versions).

```console
python -m venv .venv-benchmark
# Activate that environment using your shell.
python -m pip install -e . -r benchmarks/requirements.txt
python -m unittest tests.test_benchmark_baseline
python -m tools.benchmark_baseline --output build/benchmark-v1/baseline.json
python -m asv check --python=same
python -m asv machine --yes --machine flahax-local
python -m asv run --python=same --quick --show-stderr --dry-run
```

For recorded measurements, replace `COMMIT_SHA` with `git rev-parse HEAD`.
Capture metadata before and after the run and do not edit inputs in between.
A dirty checkout is a development measurement, even when ASV stores it under
the HEAD identifier; the manifest and dirty-tree flag are authoritative.

```console
python -m tools.benchmark_baseline --metadata-only --output build/benchmark-v1/before.json
python -m asv run --python=same --machine flahax-local --set-commit-hash COMMIT_SHA --record-samples --show-stderr
python -m tools.benchmark_baseline --compare-inputs build/benchmark-v1/before.json --asv-results build/asv/results --output build/benchmark-v1/baseline.json
```

Keep `build/asv/results/` alongside the baseline JSON: it contains raw samples,
memory results, machine metadata, and failures. The baseline's performance
summary does not replace ASV's records. Compare the before/after manifest
hashes and reject a run if benchmark inputs changed. Do not relabel dirty
local results as evidence for a clean release.

An existing environment (`--python=same`) executes the currently installed
checkout and does not accept a positional revision range. Use a clean checkout
of the intended commit, verify the package imports from it, and set
`--set-commit-hash` to that checkout's HEAD. ASV's initial console revision label
can reflect its configured branch; inspect the recorded hash and provenance.

ASV reruns setup between timing samples. Setup includes a warm calculation and
correctness gate, so total wall time can substantially exceed the sum of the
timed samples. The equilibrium benchmark has a 900-second process timeout;
this budget includes setup. A timeout is a benchmark-budget failure, not proof
that one solve exceeded 900 seconds or failed to converge. Preserve it as a
missing measurement and use a separately identified run if changing the budget.

The manual `Benchmark v1` CI workflow retains JSON, ASV records, and its
measurement log as artifacts. A correctness failure makes the workflow fail.
Other ASV workloads still run, but a workload that fails its own setup or
teardown gate cannot supply a successful timing result. There is no automatic
performance-regression threshold and no automated publication.

For commit-to-commit timing, use the same runner and ASV's
[continuous comparison](https://asv.readthedocs.io/en/stable/commands.html):

```console
python -m asv continuous BASE_SHA CANDIDATE_SHA --machine flahax-local
```

Use a common benchmark specification and input manifest, review failures before
ratios, and establish run-to-run variation before selecting blocking thresholds.
ASV environments install each revision separately. The suite's stored reference
fixtures and examples come from the benchmark checkout, so their hashes must
match across comparisons; older revisions that do not implement a workload
must be reported as unsupported, not as faster.

## Historical comparison

The runner recomputes the archived
[FlahaX–Horticalc CSV](audit/2026-10-17-flahax-vs-horticalc/data/bench_formulation_variants.csv).
Runtime is counted once per `(water scenario, formula, engine)`, not once per
element. Recomputed historical means are not newly measured performance.
The [maintainer review](audit/2026-10-17-flahax-vs-horticalc/review.md) takes
precedence over the original report, including its EC and scope corrections.

A new aligned competitor run is **not implemented** in v1. It requires pinned
competitor code, a checked elemental-N translation, matching restrictions,
regularization, simplification and objectives, and a common returned-dose
evaluator. Old scope claims must not describe current experimental EC support.

## Publication and remaining work

Publish raw records with commit, dirty-tree status, package/tool versions,
machine/Python/OS data, model and input hashes, repeat configuration, and all
failures. State unsupported cases and physical-validation status. Downloads,
community activity, and adoption are separate evidence and do not enter any
technical scorecard.

Future increments include independently sourced waters, broader adversarial
systems, scaling sweeps, installation measurements, a new aligned competitor
replay, and an independently reviewed physical protocol. No accuracy or speed
claim should expand beyond the actual completed cases.
