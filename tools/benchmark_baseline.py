#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Generate Benchmark v1 correctness/evidence JSON; ASV owns all new timings.

Run from the repository root: python -m tools.benchmark_baseline --output PATH
An unsuccessful comparison is recorded before a nonzero exit. A recipe missing
its target is a measured limitation, not automatically an implementation error.
"""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys

from benchmarks.cases import (
    FIXTURES,
    NNLS_CASES,
    ROOT,
    VERSION,
    WATERS,
    digest,
    evaluate_chemistry,
    evaluate_recipe,
    objective,
    read_fixture,
    solve_fixture,
)


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True)
    return result.stdout.decode("utf-8").strip()


def provenance():
    import flahax

    source = Path(flahax.__file__).resolve().parent
    versions = {}
    for name in ("asv", "scipy", "numpy", "asv-runner"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    inputs = {}
    # Includes runtime code/data and the exact benchmark harness, even uncommitted.
    for folder, patterns in [
        (source, ("*.py", "*.json")),
        (ROOT / "benchmarks", ("*.py", "*.txt")),
        (FIXTURES, ("*",)),
    ]:
        for pattern in patterns:
            for path in sorted(folder.rglob(pattern)):
                if (
                    path.is_file()
                    and "__pycache__" not in path.parts
                    and path.name != "phreeqc.log"
                ):
                    try:
                        key = path.relative_to(ROOT).as_posix()
                    except ValueError:
                        key = "installed/flahax/" + path.relative_to(source).as_posix()
                    inputs[key] = digest(path)
    # Only shipped helpers: local tutorial scripts are deliberately ignored.
    for relative in git("ls-files", "examples/*.py").splitlines():
        inputs[relative] = digest(ROOT / relative)
    for path in [
        ROOT / "asv.conf.json",
        ROOT / "pyproject.toml",
        ROOT / ".github/workflows/benchmark.yml",
        ROOT
        / "docs/site/evidence/audit/2026-10-17-flahax-vs-horticalc"
        / "data/bench_formulation_variants.csv",
        Path(__file__).resolve(),
    ]:
        inputs[path.relative_to(ROOT).as_posix()] = digest(path)
    return {
        "schema": VERSION,
        "utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git("rev-parse", "HEAD"),
        "dirty_tree": bool(git("status", "--porcelain")),
        "package_version": flahax.__version__,
        "source_checkout_import": source == ROOT / "src/flahax",
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "os": platform.platform(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "tool_versions": versions,
        "input_sha256": inputs,
        "input_manifest_sha256": hashlib.sha256(
            json.dumps(inputs, sort_keys=True).encode()
        ).hexdigest(),
        "physical_validation": "not performed",
        "live_phreeqc": "not run by this command; comparisons use pinned stored captures",
    }


def metrics(rows):
    percentages = [r["error_percent"] for r in rows if r["error_percent"] is not None]
    return {
        "element_targets": len(rows),
        "element_pass_fraction": sum(r["passes"] for r in rows) / len(rows) if rows else None,
        "rms_percent": math.sqrt(statistics.mean(p * p for p in percentages))
        if percentages
        else None,
        "max_absolute_percent": max(map(abs, percentages), default=None),
        "rmse_mg_l": math.sqrt(statistics.mean(r["error_mg_l"] ** 2 for r in rows))
        if rows
        else None,
    }


def formulation():
    from flahax import load_library, recommend

    library = load_library()
    cases, failures, rows = [], [], []
    for formula in library["formulas"]:
        for water_name, water in WATERS.items():
            name = formula["id"] + ":" + water_name
            try:
                result = recommend(library["salts"], formula["targets"], water)
                scored = evaluate_recipe(library["salts"], result, formula["targets"], water)
                cases.append(
                    {
                        "id": name,
                        "formula": formula["name"],
                        "water": water,
                        "doses": result["salts"],
                        **scored,
                    }
                )
                rows.extend(scored["rows"])
            except Exception as exc:
                failures.append({"case": name, "error": type(exc).__name__, "message": str(exc)})
    attempted = len(library["formulas"]) * len(WATERS)
    return {
        "basis": "returned rounded g/L doses and catalogue elemental assays",
        "tolerance": "max(0.01 mg/L, 1% of target); missing targets not scored",
        "counterion_scope": "Unassayed counterions excluded; incidental review is not target fit.",
        "attempted": attempted,
        "completed": len(cases),
        "failures": failures,
        "summary": {
            **metrics(rows),
            "whole_recipe_pass_fraction_of_attempted": sum(c["whole_recipe_passes"] for c in cases)
            / attempted,
        },
        "cases": cases,
    }


def kernel():
    from flahax.engine import nnls
    from scipy.optimize import nnls as reference

    rows = []
    for name, (matrix, rhs) in NNLS_CASES.items():
        try:
            actual = nnls(matrix, rhs)
            expected, _ = reference(matrix, rhs)
            actual_objective = objective(matrix, rhs, actual)
            expected_objective = objective(matrix, rhs, expected)
            gap = abs(actual_objective - expected_objective)
            rows.append(
                {
                    "case": name,
                    "matrix": matrix,
                    "rhs": rhs,
                    "weights": actual,
                    "reference_weights": expected.tolist(),
                    "objective": actual_objective,
                    "reference_objective": expected_objective,
                    "objective_gap": gap,
                    "tolerance": 1e-12 + 1e-8 * expected_objective,
                    "passes": gap <= 1e-12 + 1e-8 * expected_objective,
                }
            )
        except Exception as exc:
            rows.append(
                {"case": name, "passes": False, "error": type(exc).__name__, "message": str(exc)}
            )
    return {
        "reference": "scipy.optimize.nnls, identical explicit A and b",
        "note": "Kernel comparison only; not an objective-aligned competitor workflow comparison.",
        "cases": rows,
        "passes": all(row["passes"] for row in rows),
    }


def chemistry():
    cases = []
    for folder in ("products", "phases"):
        for path in sorted((FIXTURES / folder).glob("*/expected.json")):
            name = folder + "/" + path.parent.name
            try:
                data = read_fixture(name)
                result, acid = solve_fixture(data)
                cases.append(
                    {
                        "case": name,
                        "fixture_sha256": digest(path),
                        "reference": data["reference"],
                        **evaluate_chemistry(data, result, acid),
                    }
                )
            except Exception as exc:
                cases.append(
                    {
                        "case": name,
                        "passes": False,
                        "error": type(exc).__name__,
                        "message": str(exc),
                    }
                )
    return {
        "basis": "stored PHREEQC captures; shared thermodynamic data",
        "note": "Prescribed-pH captures do not independently test calculated pH. "
        "Mass-action/charge/unsupported-boundary tests remain in unittest.",
        "attempted": len(cases),
        "passed": sum(c["passes"] for c in cases),
        "cases": cases,
        "passes": bool(cases) and all(c["passes"] for c in cases),
    }


def historical(path):
    """Recompute archived statistics; count each case runtime ONCE."""
    groups = {}
    with Path(path).open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            groups.setdefault(row["engine"], []).append(row)
    report = {}
    for engine, rows in groups.items():
        times = {}
        errors = []
        absolute = []
        case_passes = {}
        for row in rows:
            key = (row["scenario"], row["formula"])
            time = float(row["runtime_s"])
            if key in times and times[key] != time:
                raise ValueError("Inconsistent repeated historical runtime")
            times[key] = time
            error = float(row["err_pct"])
            errors.append(error)
            absolute.append(float(row["err_mg"]))
            case_passes[key] = case_passes.get(key, True) and abs(error) <= 1.0
        report[engine] = {
            "cases": len(times),
            "element_targets": len(rows),
            "within_1_percent": 100 * sum(abs(e) <= 1 for e in errors) / len(errors),
            "within_5_percent": 100 * sum(abs(e) <= 5 for e in errors) / len(errors),
            "rms_percent": math.sqrt(statistics.mean(e * e for e in errors)),
            "max_absolute_percent": max(map(abs, errors)),
            "rmse_mg_l": math.sqrt(statistics.mean(e * e for e in absolute)),
            "whole_recipe_within_1_percent": 100 * sum(case_passes.values()) / len(times),
            "mean_runtime_ms_once_per_case": 1000 * statistics.mean(times.values()),
        }
    return {
        "status": "recomputed historical statistics; NOT newly timed",
        "source_sha256": digest(path),
        "engines": report,
        "caveat": "Different default objectives/policies; maintainer errata take precedence. "
        "Not a current or objective-aligned head-to-head run.",
    }


def asv_samples(directory):
    """Export ASV timing samples and nearest-rank p95 without relabelling averages."""
    reports = []
    for path in sorted(Path(directory).rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        columns = data.get("result_columns", [])
        if "samples" not in columns:
            continue
        for name, result in data["results"].items():
            entry = dict(zip(columns, result))
            parameters = entry.get("params") or []
            count = math.prod(len(axis) for axis in parameters) if parameters else 1
            raw_results = entry.get("result") or [None] * count
            samples = entry.get("samples") or [None] * count
            for index, sample in enumerate(samples):
                values = sample or []
                valid = [v for v in values if v is not None and math.isfinite(v)]
                reports.append(
                    {
                        "asv_file": path.relative_to(directory).as_posix(),
                        "benchmark": name,
                        "parameter_index": index,
                        "parameters": entry.get("params"),
                        "samples_seconds": values,
                        "sample_count": len(valid),
                        "median_seconds": statistics.median(valid) if valid else None,
                        "p95_seconds_nearest_rank": sorted(valid)[math.ceil(0.95 * len(valid)) - 1]
                        if valid
                        else None,
                        "asv_result": raw_results[index],
                        "status": (
                            "measured"
                            if valid
                            else "non_timing_or_samples_not_recorded"
                            if raw_results[index] is not None
                            else "no_samples_or_failed"
                        ),
                        "commit_hash": data.get("commit_hash"),
                    }
                )
    return {
        "note": "ASV samples may be per-loop averages, not request latency. "
        "number=1 is configured for this suite. Inspect ASV raw failures and memory results.",
        "records": reports,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asv-results", type=Path)
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument(
        "--compare-inputs",
        type=Path,
        help="Fail if this run's input manifest differs from a prior report",
    )
    args = parser.parse_args(argv)
    report = {"metadata": provenance()}
    failed = False
    if args.compare_inputs:
        previous = json.loads(args.compare_inputs.read_text(encoding="utf-8"))
        report["input_manifest_matches"] = (
            previous["metadata"]["input_manifest_sha256"]
            == report["metadata"]["input_manifest_sha256"]
        )
        failed = not report["input_manifest_matches"]
    if not args.metadata_only:
        # Missing SciPy is a dependency error, not silently skipped evidence.
        for name, function in [
            ("kernel", kernel),
            ("formulation", formulation),
            ("chemistry", chemistry),
        ]:
            print("Measuring " + name, flush=True)
            try:
                report[name] = function()
                failed |= bool(report[name].get("failures")) or report[name].get("passes") is False
            except Exception as exc:
                report[name] = {"passes": False, "error": type(exc).__name__, "message": str(exc)}
                failed = True
        path = (
            ROOT
            / "docs/site/evidence/audit/2026-10-17-flahax-vs-horticalc"
            / "data/bench_formulation_variants.csv"
        )
        report["historical"] = historical(path)
    if args.asv_results:
        report["performance"] = asv_samples(args.asv_results)
    report["correctness_checks_passed"] = None if args.metadata_only else not failed
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}; correctness checks {'failed' if failed else 'completed'}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
