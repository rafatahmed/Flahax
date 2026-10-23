#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""#40 chemistry track: FlahaX equilibrium vs live PHREEQC through PhreeqPython.

PhreeqPython (pinned 1.6.2) embeds IPhreeqc, so the PHREEQC reference runs on any
platform without the Windows installer. It uses exactly the reaction set FlahaX was
built from: minteq.v4.dat at the pinned SHA-256, merged with the FlahaX chelate and
phase extensions by tools.phreeqc_evidence.merge (merged hash checked against the
fixtures). Each fixture's own .pqi input is run unchanged (the _target input for acid-target
captures). The live rows are first replayed against the stored PHREEQC 3.8.6 rows, then
FlahaX is solved at the live prescribed pH and scored with Benchmark v1's
evaluate_chemistry and the fixture tolerances.
"""

import argparse
import json
import math
import os
import tempfile
import time
from pathlib import Path

from benchmarks.cases import evaluate_chemistry, read_fixture, solve_fixture
from tools.phreeqc_evidence import merge, sha

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/phreeqc"
PINNED_BASE_SHA256 = "ab0a8f7c7375e1bd997990f4bc3a9af497516f10e57f4aaa3cefb55dccac5ae7"
REPEATS = 3
# Replay agreement: log quantities (pH, pe, la_*, si_*) compare absolutely, everything else
# relatively above a molality floor; charge and pct_err are convergence residuals (~1e-15),
# not results, so they are not compared.
LOG_PREFIXES = ("pH", "pe", "la_", "si_")
RESIDUALS = {"charge", "pct_err"}
MOLALITY_FLOOR = 1e-20


def fixtures():
    for group in ("products", "phases"):
        for folder in sorted((FIXTURES / group).iterdir()):
            if (folder / "expected.json").exists() and (folder / f"{folder.name}.pqi").exists():
                yield f"{group}/{folder.name}", folder


def reference_input(folder, data):
    """The .pqi whose selected output the fixture stores (acid-target captures keep _target)."""
    suffix = "_target" if data.get("nitric_acid_molal") is not None else ""
    return folder / f"{data.get('case', folder.name)}{suffix}.pqi"


def replay_difference(stored, live):
    """Largest disagreement between a stored PHREEQC row and the live one (see LOG_PREFIXES)."""
    worst = 0.0
    for key, value in stored.items():
        if key in RESIDUALS or key not in live:
            continue
        if key.startswith(LOG_PREFIXES):
            worst = max(worst, abs(live[key] - value))
        elif max(abs(value), abs(live[key])) > MOLALITY_FLOOR:
            worst = max(worst, abs(live[key] - value) / max(abs(value), MOLALITY_FLOOR))
    return worst


def phreeqpython_rows(pp, text):
    """Run one PHREEQC input through PhreeqPython's IPhreeqc; return selected rows."""
    with tempfile.TemporaryDirectory() as folder:
        cwd = os.getcwd()
        os.chdir(folder)  # the inputs name a -file for selected output
        try:
            pp.ip.run_string(text)
            table = pp.ip.get_selected_output_array()
        finally:
            os.chdir(cwd)
    # IPhreeqc appends units ("(mol/kgw)", "(eq)") that PHREEQC's selected-output file omits.
    headings = [
        str(h)
        .strip()
        .removesuffix("(mol/kgw)")
        .removesuffix("(eq)")
        .replace("AmmH4", "NH4")
        .replace("AmmH3", "NH3")
        for h in table[0]
    ]
    return [dict(zip(headings, map(float, row))) for row in table[1:]]


def run(base):
    from phreeqpython import PhreeqPython

    if sha(base) != PINNED_BASE_SHA256:
        raise ValueError("minteq.v4.dat does not match the pinned SHA-256")
    out = {"base_sha256": PINNED_BASE_SHA256, "cases": []}
    with tempfile.TemporaryDirectory() as folder:
        merged = Path(folder) / "merged.dat"
        merge(base, merged)
        out["merged_sha256"] = sha(merged)
        for name, folder in fixtures():
            data = read_fixture(name)
            # IPhreeqc keeps SOLUTION_SPECIES/PHASES from earlier inputs (mixed_product_phases
            # redefines ammonium species), so every fixture starts from a freshly loaded database.
            pp = PhreeqPython(database=str(merged))
            if data.get("reference", {}).get("merged_sha256") not in (None, out["merged_sha256"]):
                raise ValueError(f"{name}: merged database differs from the fixture's")
            text = reference_input(folder, data).read_text()
            best_pp = best_fx = math.inf
            rows = result = acid = None
            for _ in range(REPEATS):
                start = time.perf_counter()
                rows = phreeqpython_rows(pp, text)
                best_pp = min(best_pp, time.perf_counter() - start)
                # FlahaX takes its prescribed pH from the same live rows it is scored against;
                # the bundled IPhreeqc converges up to ~2e-9 pH units from PHREEQC 3.8.6 (gypsum).
                live = dict(data, selected_rows=rows)
                start = time.perf_counter()
                result, acid = solve_fixture(live)
                best_fx = min(best_fx, time.perf_counter() - start)
            if len(rows) != len(data["selected_rows"]):
                raise ValueError(
                    f"{name}: {len(rows)} live rows vs {len(data['selected_rows'])} stored"
                )
            replay = max(
                replay_difference(s, line) for s, line in zip(data["selected_rows"], rows)
            )
            checks = evaluate_chemistry(live, result, acid)
            out["cases"].append(
                {
                    "fixture": name,
                    "replay_max_difference": replay,
                    "flahax_passes": checks["passes"],
                    "failed": [c["quantity"] for c in checks["checks"] if not c["passes"]],
                    "checks": len(checks["checks"]),
                    "phreeqpython_ms": 1000 * best_pp,
                    "flahax_ms": 1000 * best_fx,
                }
            )
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, required=True, help="minteq.v4.dat at the pinned SHA-256"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.database)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, default=lambda v: v.item()), encoding="utf-8"
    )
    print(f"merged database {report['merged_sha256'][:16]}")
    for case in report["cases"]:
        print(
            f"{case['fixture']:36s} replay {case['replay_max_difference']:.1e}  "
            f"FlahaX {'pass' if case['flahax_passes'] else 'FAIL'} {case['checks']:4d} checks  "
            f"PHREEQC {case['phreeqpython_ms']:8.2f} ms  FlahaX {case['flahax_ms']:9.2f} ms  {case['failed'][:3]}"
        )


if __name__ == "__main__":
    main()
