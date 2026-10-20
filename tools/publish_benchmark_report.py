"""Render a clean benchmark capture as static docs and a portable evidence bundle.

No benchmark is run and no external service is modified by this command.
Install tools/requirements-benchmark-report.txt to regenerate the charts.
"""
import argparse
import copy
import csv
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
import re
import statistics
import sys
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_capture(capture):
    before = json.loads((capture / "before.json").read_text(encoding="utf-8-sig"))
    after = json.loads((capture / "after.json").read_text(encoding="utf-8-sig"))
    for report in (before, after):
        if report["metadata"]["dirty_tree"]:
            raise ValueError("Cannot publish a dirty checkout as a clean baseline")
        if not report["metadata"]["source_checkout_import"]:
            raise ValueError("Measured package was not imported from the checkout")
    for key in ("git_commit", "input_manifest_sha256", "python", "tool_versions"):
        if before["metadata"][key] != after["metadata"][key]:
            raise ValueError("Before/after provenance mismatch: " + key)
    if after.get("input_manifest_matches") is not True:
        raise ValueError("Input stability was not verified")
    metadata = before["metadata"]
    expected = sha(json.dumps(metadata["input_sha256"], sort_keys=True).encode())
    after_expected = sha(json.dumps(
        after["metadata"]["input_sha256"], sort_keys=True).encode())
    if expected != metadata["input_manifest_sha256"] or after_expected != expected:
        raise ValueError("Invalid input manifest digest")
    records = after["performance"]["records"]
    if not records or any(r["commit_hash"] != metadata["git_commit"] for r in records):
        raise ValueError("Missing performance records or wrong measured revision")
    for row in records:
        samples = row["samples_seconds"]
        if any(not math.isfinite(x) or x < 0 for x in samples):
            raise ValueError("Invalid timing sample")
        if row["sample_count"] != len(samples):
            raise ValueError("Timing sample count mismatch")
        if samples and row["median_seconds"] != statistics.median(samples):
            raise ValueError("Timing median mismatch")
    combined = copy.deepcopy(before)
    combined["performance"] = after["performance"]
    combined["after_metadata"] = after["metadata"]
    combined["input_manifest_matches"] = True
    return combined


def redact(text):
    """Remove user-home identifiers only; numerical measurements stay unchanged."""
    text = re.sub(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\"\s]+", "<USER_HOME>", text)
    text = re.sub(r"[A-Za-z]__Users_[^_\\/\"\s]+", "USER_HOME", text)
    text = re.sub(r"/home/[^/\"\s]+", "<USER_HOME>", text)
    # JSON-escaped Windows separators can leave repeated slashes after replacement.
    return text


def label(row):
    parts = row["benchmark"].split(".")
    axes = row.get("parameters") or []
    params = list(itertools.product(*axes))[row["parameter_index"]] if axes else ()
    return parts[-2] + (": " + ", ".join(str(x) for x in params) if params else "")


def csv_bytes(rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def render(capture, asv, site, snapshot, source, page_stem="benchmark-results",
           related_page=None):
    report = load_capture(capture)
    from tools.benchmark_baseline import asv_samples
    if asv_samples(asv) != report["performance"]:
        raise ValueError("ASV source records do not match the captured summary")
    machines = [json.loads(p.read_text(encoding="utf-8-sig"))
                for p in asv.rglob("machine.json")]
    if len(machines) != 1:
        raise ValueError("A published capture must contain exactly one ASV machine")
    machine = machines[0]
    report["asv_machine"] = machine
    report["publication_schema"] = "benchmark-publication-v1"
    if not re.fullmatch(r"[a-z0-9-]+", snapshot):
        raise ValueError("Snapshot must be a safe lowercase identifier")
    destination = site / "_static" / "benchmarks" / snapshot
    if destination.exists():
        raise ValueError("Snapshot already exists; use a new identifier")
    meta = report["metadata"]
    hosted = json.loads((capture / "hosted-ci.json").read_text(encoding="utf-8-sig"))
    if hosted["headSha"] != meta["git_commit"]:
        raise ValueError("Hosted checks refer to a different revision")
    ci_table = "\n".join(
        f"| [{job['name']}]({job['url']}) | {job['conclusion'] or job['status']} |"
        for job in hosted["jobs"])
    manual = json.loads((capture / "manual-workflow.json").read_text(encoding="utf-8-sig"))
    if manual["headSha"] != meta["git_commit"] or manual["status"] != "completed":
        raise ValueError("Manual benchmark workflow must have completed at the measured revision")
    if not re.fullmatch(r"[a-z0-9-]+", page_stem):
        raise ValueError("Invalid page identifier")
    for relative, expected in meta["input_sha256"].items():
        if sha((source / relative).read_bytes()) != expected:
            raise ValueError("Measured source/input changed: " + relative)
    archive = {}
    for relative in ("asv.conf.json", "benchmarks/requirements.txt",
                     ".github/workflows/benchmark.yml"):
        archive["configuration/" + relative] = (source / relative).read_bytes()
    archive["baseline.json"] = redact(json.dumps(report, indent=2, allow_nan=False)).encode()
    for path in sorted(capture.iterdir()):
        if path.is_file() and path.suffix in (".json", ".txt", ".log"):
            archive["capture/" + path.name] = redact(
                path.read_text(encoding="utf-8-sig")).encode()
    for path in sorted(asv.rglob("*.json")):
        archive["asv/" + redact(path.relative_to(asv).as_posix())] = redact(
            path.read_text(encoding="utf-8-sig")).encode()
    archive["publish_benchmark_report.py"] = Path(__file__).read_bytes()
    archive["requirements-benchmark-report.txt"] = Path(__file__).with_name(
        "requirements-benchmark-report.txt").read_bytes()
    archive["README.txt"] = (
        "Clean-checkout Benchmark v1 capture. Numerical failures are retained.\n"
        "Paths identifying user home directories have been replaced with USER_HOME.\n"
        "This changes path metadata and container bytes, not measurements or input hashes.\n"
        "CHECKSUMS.sha256 covers these redistributed files, not the original local containers.\n"
        "ASV JSON and logs remain the authoritative timing/failure records.\n"
        "A failed scientific exit is intentional when a reference criterion is missed.\n"
        "No physical validation or new live PHREEQC replay is included.\n"
        "See manual-workflow.json for the hosted execution status. Earlier dispatch\n"
        "errors, when present, are retained as historical logs.\n"
    ).encode()
    rows = []
    for case in report["formulation"]["cases"]:
        for row in case["rows"]:
            rows.append({"case": case["id"], **row})
    fields = ["case", "ion", "target_mg_l", "delivered_mg_l", "error_mg_l",
              "error_percent", "tolerance_mg_l", "passes"]
    archive["formulation.csv"] = csv_bytes(rows, fields)
    timings = [r for r in report["performance"]["records"] if ".time_" in r["benchmark"]]
    measured = [r for r in timings if r["status"] == "measured"]
    missing = [r for r in timings if r["status"] != "measured"]
    timing_rows = [{"workload": label(r), "status": r["status"], "samples": r["sample_count"],
                    "median_ms": r["median_seconds"] * 1000 if r["sample_count"] else "",
                    "minimum_ms": min(r["samples_seconds"]) * 1000 if r["sample_count"] else "",
                    "maximum_ms": max(r["samples_seconds"]) * 1000 if r["sample_count"] else ""}
                   for r in timings]
    archive["timings.csv"] = csv_bytes(timing_rows, list(timing_rows[0]))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    archive["renderer-environment.json"] = json.dumps({
        "python": sys.version, "matplotlib": matplotlib.__version__,
        "renderer_sha256": sha(Path(__file__).read_bytes()),
    }, indent=2).encode()
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "svg.fonttype": "none", "svg.hashsalt": "flahax-benchmark-v1"})
    element_pass = sum(r["passes"] for r in rows)
    recipe_pass = sum(c["whole_recipe_passes"] for c in report["formulation"]["cases"])
    recipe_total = report["formulation"]["attempted"]
    fit = report["formulation"]["summary"]
    fig, ax = plt.subplots(figsize=(9, 3.3), layout="constrained")
    counts = [(element_pass, len(rows)), (recipe_pass, recipe_total)]
    for i, (passed, total) in enumerate(counts):
        fraction = 100 * passed / total
        ax.barh(i, fraction, color="#16654a")
        ax.barh(i, 100-fraction, left=fraction, color="#e7a34b")
        ax.text(2, i, f"{passed}/{total} pass ({fraction:.1f}%)",
                va="center", color="white", weight="bold")
    ax.set(yticks=[0, 1], yticklabels=["Explicit nutrient targets", "Complete recipes"],
           xlim=(0, 100), xlabel="Percent of each denominator",
           title="Target fit from returned rounded doses")
    ax.invert_yaxis()
    fig.text(.5, -.03, "Tolerance: max(0.01 mg/L, 1% of target). Not crop safety or physical accuracy.",
             ha="center", fontsize=10)
    for extension in ("svg", "png"):
        output = io.BytesIO()
        fig.savefig(output, format=extension, bbox_inches="tight",
                    metadata={"Date": None} if extension == "svg" else None)
        archive["formulation." + extension] = output.getvalue()
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, max(5, len(measured)*.36)), layout="constrained")
    for i, row in enumerate(measured):
        values = [x*1000 for x in row["samples_seconds"]]
        median = statistics.median(values)
        ax.plot(values, [i]*len(values), "o", color="#91bfc4", markersize=4)
        ax.errorbar(median, i, xerr=[[median-min(values)], [max(values)-median]],
                    fmt="D", color="#124c52", capsize=3, markersize=5)
    ax.set(yticks=range(len(measured)), yticklabels=[label(r) for r in measured],
           xscale="log", xlabel="Milliseconds per call (log scale)",
           title="Completed timings: samples, median, and observed range")
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=.2)
    fig.text(.5, -.025, f"{len(missing)} missing timings excluded from plot; listed in the table. "
             "Ranges are not confidence intervals.", ha="center", fontsize=10)
    for extension in ("svg", "png"):
        output = io.BytesIO()
        fig.savefig(output, format=extension, bbox_inches="tight",
                    metadata={"Date": None} if extension == "svg" else None)
        archive["timings." + extension] = output.getvalue()
    plt.close(fig)
    checksums = "".join(f"{sha(data)}  {name}\n" for name, data in sorted(archive.items()))
    archive["CHECKSUMS.sha256"] = checksums.encode()
    destination.mkdir(parents=True)
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, data in sorted(archive.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zipped.writestr(info, data)
    for name in ("baseline.json", "formulation.csv", "timings.csv", "CHECKSUMS.sha256",
                 "formulation.svg", "formulation.png", "timings.svg", "timings.png"):
        (destination / name).write_bytes(archive[name])
    (destination / "evidence.zip").write_bytes(bundle.getvalue())
    link = "../_static/benchmarks/" + snapshot
    kernel = report["kernel"]["cases"]
    kernel_pass = sum(r["passes"] for r in kernel)
    chemistry = report["chemistry"]
    time_table = "\n".join(
        f"| {r['workload']} | {r['samples']} | "
        + (f"{r['median_ms']:.4g} | {r['minimum_ms']:.4g}–{r['maximum_ms']:.4g}"
           if r["samples"] else "— | Missing; see limitations and ASV log") + " |"
        for r in timing_rows)
    recipe_table = "\n".join(
        f"| {c['id']} | {sum(r['passes'] for r in c['rows'])}/{len(c['rows'])} | "
        f"{'Pass' if c['whole_recipe_passes'] else 'Miss'} |"
        for c in report["formulation"]["cases"])
    kernel_failures = "\n".join(
        f"- `{r['case']}`: objective gap {r.get('objective_gap', float('nan')):.6g}; "
        f"tolerance {r.get('tolerance', float('nan')):.6g}."
        for r in kernel if not r["passes"]) or "- None in this capture."
    versions = ", ".join(f"{k} {v}" for k, v in meta["tool_versions"].items())
    memory_table = "\n".join(
        f"| {label(r)} | " + (f"{r['asv_result']/1e6:.2f}"
                             if r["asv_result"] is not None else "Missing; see ASV log") + " |"
        for r in report["performance"]["records"]
        if ".peakmem_" in r["benchmark"])
    related = (f"\n[Results from the other recorded environment]({related_page}). "
               "Treat environments separately; this is not a controlled OS comparison.\n"
               if related_page else "")
    if related_page and page_stem == "benchmark-results":
        related += f"\n:::{{toctree}}\n:hidden:\n\n{Path(related_page).stem}\n:::\n"
    notes_path = capture / "publication-notes.txt"
    capture_notes = ("\n## Capture notes\n\n" + notes_path.read_text(encoding="utf-8-sig")
                     if notes_path.exists() else "")
    environment_name = "Linux" if meta["os"].startswith("Linux") else "Windows"
    page = f"""# Benchmark results: {environment_name}

**Measured snapshot: {snapshot}.** This page reports one clean-checkout development
baseline, including failures. It is not a release certification, a comparison
against another product, or physical validation.

```{{warning}}
The numerical scorecard is not fully passing: {kernel_pass}/{len(kernel)} controlled
NNLS cases pass. {len(missing)} timing workloads have no completed measurement.
The [manual GitHub benchmark workflow]({manual['url']}) completed with conclusion
**{manual['conclusion']}**. A completed capture is not necessarily a passing
scientific scorecard; failed gates and timeouts are retained.
```

Read the [protocol and reproduction instructions](benchmark-v1.md) before comparing results.
{related}
Historical Horticalc statistics in the evidence JSON are **not newly measured** and
are deliberately excluded from the charts on this page.

## What passed, and what did not

| Scorecard | Result | Meaning |
|---|---|---|
| Nutrient targets | {element_pass}/{len(rows)} ({100*element_pass/len(rows):.2f}%) | Explicit catalogue-assay targets within max(0.01 mg/L, 1%) |
| Complete recipes | {recipe_pass}/{recipe_total} ({100*recipe_pass/recipe_total:.2f}%) | Every target passes; denominator includes attempted recipes |
| RMS target deviation | {fit['rms_percent']:.3f}% | Percentage deviations across positive targets |
| Maximum absolute target deviation | {fit['max_absolute_percent']:.3f}% | Largest percentage miss across positive targets |
| Nutrient RMSE | {fit['rmse_mg_l']:.3f} mg/L | Absolute concentration residuals across explicit targets |
| Stored chemistry comparisons | {chemistry['passed']}/{chemistry['attempted']} | Quantity-specific agreement with stored PHREEQC captures |
| Controlled NNLS problems | {kernel_pass}/{len(kernel)} | Identical matrices/objectives compared with pinned SciPy |
| Completed timing workloads | {len(measured)}/{len(timings)} | Parameterized timings, with failures retained |
| Physical validation | Not performed | No measured mixture/pH/titration/EC accuracy claim |

![Target-fit pass fractions with separate element and whole-recipe denominators]({link}/formulation.svg)

Formula targets are desired inputs, not proof of agronomic suitability.
Reconstruction uses returned rounded doses and declared assays; unassayed
counterions are outside this scorecard. Missing targets are not scored.
Percentage statistics exclude zero targets; absolute residual metrics retain them.
There were {len(report['formulation']['failures'])} formulation exceptions; their
element rows are excluded, while attempted recipes remain in the recipe denominator.

## Timing and memory

![Completed timing samples, medians and ranges on a logarithmic millisecond axis]({link}/timings.svg)

Dots are samples; diamonds are medians; bars show the observed minimum–maximum.
These are single-machine, single-run observations, **not confidence intervals or
an established estimate of between-run variation**. Ten samples do not establish
a stable tail-latency estimate. No blocking speed thresholds are proposed.
Setup and correctness checks are outside timed calls; process timeout budgets
include repeated setup. Fresh-process import includes interpreter startup and
does not establish a cold filesystem cache.

| Workload / parameter | Samples | Median (ms) | Observed range (ms) |
|---|---:|---:|---|
{time_table}

Peak memory is total process peak RSS, including the interpreter and setup,
not the incremental allocation of the solver. Decimal MB are used.

| Workload / parameter | Peak process memory (MB) |
|---|---:|
{memory_table}

## Retained limitations

{kernel_failures}

See [NNLS investigation #36](https://github.com/rafatahmed/Flahax/issues/36).
No solver tolerance was loosened to produce a passing score.

Missing timings are not zero-duration or successful calculations. The ASV log
in the evidence bundle records each failure. The acid workload's 900-second
budget includes repeated warm/setup solves; a timeout does not mean that one
solve takes 900 seconds or fails chemistry checks.
See [measurement-budget issue #37](https://github.com/rafatahmed/Flahax/issues/37).

Stored PHREEQC agreement shares thermodynamic data and is not independent
experimental validation. This benchmark command did not run live PHREEQC.
Prescribed-pH fixtures do not independently test calculated-pH accuracy.
Experimental EC is a regression check, not measured conductivity validation.
Recipe misses need [per-case analysis #39](https://github.com/rafatahmed/Flahax/issues/39).
The [follow-up tracker](https://github.com/rafatahmed/Flahax/issues/42) also covers
aligned competitor comparisons and physical validation.

## Provenance and reproduction

The normal [CI run]({hosted['url']}) for this exact revision is recorded separately
from these performance measurements. Its jobs are shown below; this is **not**
the manual benchmark workflow. In particular, the hosted live-PHREEQC job is
separate evidence and its results are not counted as benchmark cases.

| Hosted check | Recorded conclusion |
|---|---|
{ci_table}

{capture_notes}

## Recorded environment

| Field | Recorded value |
|---|---|
| Source revision | [{meta['git_commit'][:12]}](https://github.com/rafatahmed/Flahax/commit/{meta['git_commit']}) |
| Checkout | Clean before and after measurement |
| Capture started (UTC) | {meta['utc']} |
| Capture finished (UTC) | {report['after_metadata']['utc']} |
| Python | {meta['python'].splitlines()[0]} |
| OS / architecture | {meta['os']} / {meta['architecture']} |
| Processor (ASV model or platform label) | {machine.get('cpu') or meta['processor'] or 'Not recorded'} |
| Logical CPUs | {meta['logical_cpus']} |
| RAM (ASV bytes) | {machine.get('ram', 'Not recorded')} |
| Direct benchmark tooling | {versions} |
| Input manifest SHA-256 | `{meta['input_manifest_sha256']}` |

Input manifests match before and after. They cover runtime/model/catalogue data,
benchmark sources, tracked example helpers, stored reference captures, the historical
CSV, package configuration and workflow. The bundle includes resolved environment
versions, regression-test output, ASV configuration metadata and raw samples.
The documentation renderer is separate from the measured commit; its exact source
and pinned plotting requirement are included in the evidence bundle.

Reproduce in a clean checkout of the linked revision using Python 3.13 and the
[protocol's commands](benchmark-v1.md). Keep all exit statuses, even on failure.
Charts can be regenerated with `tools/publish_benchmark_report.py`; see its CLI
help and `tools/requirements-benchmark-report.txt`.

From the publication checkout, use the unchanged measured checkout as `CLEAN`
and a new lowercase snapshot identifier as `NEW_SNAPSHOT`:

```console
python -m pip install -r tools/requirements-benchmark-report.txt
python -m tools.publish_benchmark_report --capture CLEAN/build/benchmark-v1 --asv-results CLEAN/build/asv/results --source-checkout CLEAN --site docs/site --snapshot NEW_SNAPSHOT
```

The renderer refuses to overwrite a snapshot and verifies every recorded input
against the measured checkout before publishing files.

## Download the evidence

- [Complete evidence ZIP]({link}/evidence.zip) — scorecards, before/after metadata,
  raw ASV records and logs, environment, CSVs, charts and renderer source.
- [Machine-readable combined report]({link}/baseline.json)
- [Per-target formulation CSV]({link}/formulation.csv)
- [Timing summary CSV]({link}/timings.csv)
- [SHA-256 checksums of bundle contents]({link}/CHECKSUMS.sha256)
- Chart downloads: [target fit PNG]({link}/formulation.png), [timing PNG]({link}/timings.png).

ZIP SHA-256: `{sha(bundle.getvalue())}`.

User-home identifiers in paths were replaced for public redistribution.
Numerical values and source/input hashes are unchanged. Checksums refer to the
redistributed files; the archive explains the path-only redaction.

:::{{dropdown}} All recipe cases
| Case | Targets passing | Whole recipe |
|---|---:|---|
{recipe_table}
:::
"""
    (site / "evidence" / (page_stem + ".md")).write_text(page, encoding="utf-8")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--asv-results", type=Path, required=True)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--source-checkout", type=Path, required=True,
                        help="Unchanged checkout of the measured revision; hashes are verified")
    parser.add_argument("--page-stem", default="benchmark-results")
    parser.add_argument("--related-page", help="Relative link to a separate environment's results")
    args = parser.parse_args()
    print(render(args.capture, args.asv_results, args.site, args.snapshot, args.source_checkout,
                 args.page_stem, args.related_page))


if __name__ == "__main__":
    main()
