# Session report: P2 audit, slow unit suite, root-cause fix, CI verification

> Note added when retained: the later reconciliation (`phase3-2026-11-25/reconciliation.md` in the evidence folder) finds that section 5's "one cause for every failure" is too strong: 40 of 65 failing sections show the Windows process-start exit code and one reports a full disk (Errno 28). A clean full coverage run on `c62e4cf` is still outstanding.

Date: 2026-11-24 to 2026-11-25. Repository: the contract-remediation clone, branch `perf/unit-test-speed`.
Evidence root: the local contract-remediation evidence folder (called `EV/` below; not part of this repository).
Nothing was pushed, no PR was opened, no GitHub write was made.

## 1. What was asked, in order

1. Audit the current changes and the evidence tables (`EV/coverage-matrix.md`, `EV/phase0-table.md` to `EV/phase3-table.md`).
2. Re-run the full suite and the accounting check at `5154c43` (P2 fix); read the Codex session behind it.
3. Update the tables to `5154c43`.
4. Is the unit suite taking 63 minutes normal? No: find the root cause, no workaround.
5. Commit the fix and check what it does to CI.
6. Run every CI check you had listed as "not verified", do not just list them.

## 2. Result in one table

| Item | Result | Evidence |
|---|---|---|
| P2 accounting and collision acceptance at `5154c43` | PASS | `EV/runs/rerun-5154c43/accounting.log`, `cases/` |
| Full suite at `5154c43`, original code | 3,767 s (62.8 min) | `EV/runs/rerun-5154c43/full-suite.log` |
| Full suite on the fix, quiet machine, Python 3.14 | 1,434 tests OK, 20 skipped, **1,418 s** (2.7x faster) | `EV/runs/serial-final/` |
| Python 3.11.17, 1,434 tests | OK, 26 skipped, 4,287 s (loaded machine) | `EV/runs/ci-py3.11/summary.txt`, `tests.log` |
| Python 3.12.11, 1,434 tests | OK, 25 skipped, 3,976 s (loaded machine) | `EV/runs/ci-py3.12/summary.txt`, `tests.log` |
| `ruff check` and `ruff format --check` (pinned 0.8.4) | exit 0 on candidate and parent | `EV/runs/ci-candidate/ruff-*.log`, `ci-parent/ruff-*.log` |
| Docs build `sphinx -W --keep-going` | exit 0 | `EV/runs/ci-docs/build.log` |
| Distribution check (wheel and sdist, isolated installs, both CLI entry points) | PASS | `EV/runs/ci-candidate/distribution.log` |
| Coverage run, `tools.ci_coverage report` | exit 0 | `EV/runs/ci-candidate/report.log` (empty on success) |
| Coverage-run test failures (see section 5) | 65 failing, all one cause, **25 unique tests re-run in a clean process: all pass** | `EV/runs/ci-candidate/tests.log`, `EV/runs/ci-candidate-rerun-failed/tests.log` |

## 3. Root cause of the 63-minute suite

Profiling and stack sampling showed three repeated computations. Each recomputed a value already computed. None changes a result.

1. **Catalogue parsed per product lookup.** `engine.load_library()` re-parses `library.json` (41 KB) on every call. `product_conversion.catalogue_dose_contributions()` and `materials._shipped_salt()` called it per lookup, reached from the optimiser's inner loops via `engine._nutrients`. 11,988 parses in one batch. Fix: `engine.catalogue_salts_by_name()`, an `lru_cache` index keyed on the loader function (so tests that replace `load_library` get their own index). Unknown and unhashable names still raise `unknown_product`.
2. **Dense sensitivity matrix of exact Fractions.** `joint_sensitivity.equilibrium_charge_gradient` multiplied over every species for every component, about 2.2 million exact products per call, mostly zero. Fix: accumulate non-zero terms only. Exact rational arithmetic, so omitting zeros cannot change a value.
3. **Same cold equilibrium solved repeatedly.** In the slowest test 9,073 of 12,339 evaluations were exact repeats. Fix: remember each cold outcome for the life of one search (bounded at 8,192). Warm-start evaluations are never remembered. A `cold=True` request is the deliberate fresh recheck in `finish()` and is never answered from memory.

Cost of the process: the first version of fix 3 cached `cold=True` rechecks and failed three tests (`test_joint_fit`, `test_polishing_boundaries`). That is how the contract was found; it is recorded in `EV/runs/serial-after-fix2-FAILED-cold-recheck-served-from-cache/`.

Commit `c62e4cf` (7 files, +282 / -27): `CHANGELOG.md`, `src/flahax/engine.py`, `joint_sensitivity.py`, `joint_solver.py`, `materials.py`, `product_conversion.py`, and new `tests/test_solver_hot_paths.py` (8 tests: catalogue loaded once, loader-keyed substitution, index equals linear scan, unknown and unhashable names, gradient values pinned from the dense implementation, search result identical with and without the memory). No attribution lines in the message (checked).

Equivalence evidence: 124 gradients from three real formulas bit-identical; `resolve_material` output for all 29 catalogue products byte-identical; full `solve_joint_problem` result byte-identical on four real batches and on the 250 s scenario (52,457 bytes). Timing: Cucumber batch 28 s to about 4 s; the 250 s test to about 75 s.

## 4. Evidence runs (all under `EV/runs/`)

| Folder | What it is |
|---|---|
| `rerun-5154c43/` | Original full suite and accounting check (the 62.8 min baseline) |
| `timing-5154c43-INVALID-relative-pythonpath/` | Kept but invalid: relative `PYTHONPATH` caused 17 spurious failures |
| `timing-after-fix/` | Per-module timing after the fix, 624 s wall, 0 failing |
| `serial-after-fix/`, `serial-final/` | Serial full runs; `serial-final` is the reference: 1,434 tests, 1,418 s, exit 0 |
| `serial-after-fix2-FAILED-.../` | The failed cache version, kept as evidence |
| `ci-candidate/`, `ci-parent/` | Coverage plus distribution runs on `c62e4cf` and `5154c43` |
| `ci-py3.11/`, `ci-py3.12/` | Python 3.11 and 3.12 test legs (CI matrix legs) |
| `ci-docs/` | Sphinx build |
| `ci-candidate-rerun-failed/` | Re-run of the 25 tests that failed in the coverage run |

## 5. The coverage-run failures, honestly

The coverage runs ended with `FAILED (failures=28, errors=37, skipped=3)` on the candidate (8,814 s) and `failures=28, errors=36` on the parent (20,708 s). I did not look at them until now because the session ended while they ran.

- Every failure is a child process dying with exit code `3221225794` (0xC0000142, `STATUS_DLL_INIT_FAILED`): `git ls-files` returning non-zero, CLI help commands, the PHREEQC replay output files never written. 40 occurrences in the log.
- The parent, which has none of my changes, fails the same way (28 failures, 36 errors). So the commit did not cause it.
- 0xC0000142 means Windows could not start the process (typically desktop-heap or session teardown). It is consistent with the session ending while the long run was in progress. I did not prove which; that is an inference.
- Check that matters: I re-ran the 25 unique failing tests on the candidate in a clean process: **25 tests, OK, 27.7 s** (`EV/runs/ci-candidate-rerun-failed/tests.log`).
- Consequence for the coverage gate: it reported pass (exit 0) while those 65 tests were failing, so those tests covered less than normal. A full pass can only cover more, so the gate result stands, but this run was not a clean CI-equivalent run. I did not re-run the whole coverage pass cleanly (about 2.5 hours on this machine).

## 6. What is not verified

- A clean, uninterrupted coverage run of the whole suite on `c62e4cf` (see section 5).
- The Python 3.13 and 3.14 matrix legs under the CI runner. 3.13 was used for the coverage, ruff and distribution runs, 3.14 for the serial timing; 3.11 and 3.12 were run separately above.
- The real GitHub CI (nothing was pushed).
- P2 closure still needs the preflight-environment full suite plus wheel and sdist verification at `5154c43` per the directive; the evidence tables (`EV/phase3-table.md`, `EV/coverage-matrix.md`) are updated to `5154c43` but **do not yet mention `c62e4cf` or these CI results**.
- Undecided, not changed: some joint searches still end `iteration_budget_exhausted` / `search_incomplete`, even the plain contract problem with default controls. Fixing that changes optimiser behaviour and needs your decision.
- The remaining suite time is the pure-Python Newton equilibrium solver (`test_all_catalogue_formulas` about 189 s, off-label test about 76 s). Going lower needs numerical work that can change results.

## 7. Process notes

- Run the suite with `PYTHONPATH=src` (absolute path); otherwise the installed `flahax` shadows the source.
- `engine.py` and `product_conversion.py` are CRLF in this working copy; edits preserved their line endings. Repo rule: write LF.
- Ruff 0.15 flags `materials.py` formatting (a version artifact); the pinned 0.8.4 passes all 278 files.
- Four jobs run at once made each leg take about 70 minutes instead of about 24. Run them one at a time next time.
- Downloaded with your explicit yes: Python 3.11/3.12 via `uv`, and Sphinx/docs requirements from PyPI.
- Scratch scripts (local, not retained): `ci_run.sh`, `leg.sh`, `commit-msg.txt`, `missed.py`, `failed_ids.txt`.
- Local worktrees used: `remed-candidate`, `-parent`, `-py3.11`, `-py3.12`, `-docs`.
- The full session transcript is kept locally and is not retained here.
