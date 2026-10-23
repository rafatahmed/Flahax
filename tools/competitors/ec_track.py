#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""#40 EC track: irrigation EC25 from FlahaX, Horticalc, PHREEQC (PhreeqPython) and pyEQL.

Two parts:

1. Accuracy against the IUPAC molality-based primary standards (Pratt et al. 2001,
   Table 1, KCl at 0.01, 0.1 and 1.0 mol/kg, 25 C; see
   tests/fixtures/conductivity/iupac2001_kcl_table1.json). A tool may decline a
   standard outside its stated domain; that is reported, not scored as an error.
2. Agreement on the catalogue recipes FlahaX recommends for every shipped formula in
   ion-free water. There is no measured EC for these solutions, so this part shows how
   far the tools disagree, not which one is right. Every tool receives the same
   macronutrient totals; micronutrients and chelates are left out because not every
   tool has them (their share of FlahaX's full-recipe EC is reported per recipe). Phosphate is given as H2PO4- to the
   tools that do not speciate (the catalogue P sources are dihydrogen phosphates);
   FlahaX and PHREEQC speciate P from its total at the charge-balance pH.

PHREEQC conductivity needs diffusion coefficients (-dw), which minteq.v4.dat lacks, so
it runs on the phreeqc.dat that PhreeqPython bundles (SHA-256 recorded).
"""

import argparse
import hashlib
import json
import logging
import math
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STANDARDS = ROOT / "tests/fixtures/conductivity/iupac2001_kcl_table1.json"
REPEATS = 3
MACRO = {
    "K+": ("K", "K+"),
    "Ca+2": ("Ca", "Ca+2"),
    "Mg+2": ("Mg", "Mg+2"),
    "Na+": ("Na", "Na+"),
    "NH4+": ("N(-3)", "NH4+"),
    "NO3-": ("N(5)", "NO3-"),
    "SO4-2": ("S(6)", "SO4-2"),
    "PO4-3": ("P", "H2PO4-"),
    "Cl-": ("Cl", "Cl-"),
}


def timed(call):
    best, value = math.inf, None
    for _ in range(REPEATS):
        start = time.perf_counter()
        value = call()
        best = min(best, time.perf_counter() - start)
    return value, best


def flahax_ec(totals):
    from flahax.irrigation_ec import calculate_ec_from_totals

    result = calculate_ec_from_totals(
        totals, solution_id="ec_track", ph_mode="calculated", phase_policy="dissolved"
    )
    ec = None if result.ec25_ms_cm is None else 1000 * result.ec25_ms_cm
    return {"ec_us_cm": ec, "status": result.status, "reason": result.reason}


def horticalc_ec(ions):
    from horticalc.ec import compute_ec

    out = compute_ec(
        {ion: 1000 * m for ion, m in ions.items()}, temps_c=(25.0,), density_kg_per_l=1.0
    )
    if out.get("warnings"):
        raise ValueError(f"Horticalc ignored input: {out['warnings']}")
    return {"ec_us_cm": out["ec_uS_per_cm"]["25.0"], "status": "estimated"}


def phreeqc_ec(pp, elements):
    solution = pp.add_solution({"units": "mol/kgw", "temp": 25, "pH": "7 charge", **elements})
    try:
        return {"ec_us_cm": solution.sc, "status": "estimated", "ph": solution.pH}
    finally:
        solution.forget()


def pyeql_ec(ions):
    from pyEQL import Solution

    solution = Solution({ion: f"{m} mol/kg" for ion, m in ions.items()}, temperature="25 degC")
    return {"ec_us_cm": float(solution.conductivity.to("uS/cm").magnitude), "status": "estimated"}


def engines(pp):
    return {
        "flahax": lambda flahax, ions, elements: flahax_ec(flahax),
        "horticalc": lambda flahax, ions, elements: horticalc_ec(ions),
        "phreeqc": lambda flahax, ions, elements: phreeqc_ec(pp, elements),
        "pyeql": lambda flahax, ions, elements: pyeql_ec(ions),
    }


def inputs(totals):
    """The same macronutrient totals as FlahaX bases, free ions and PHREEQC elements."""
    macro = {b: m for b, m in totals.items() if b in MACRO and m > 0}
    return (
        macro,
        {MACRO[b][1]: m for b, m in macro.items()},
        {MACRO[b][0]: m for b, m in macro.items()},
    )


def standards_part(run):
    data = json.loads(STANDARDS.read_text())
    rows = []
    for standard in data["kcl"]:
        m = standard["molality"]
        row = {
            "molality": m,
            "reference_us_cm": standard["kappa"],
            "expanded_uncertainty_us_cm": standard["expanded_uncertainty"],
        }
        for name, call in run.items():
            value, seconds = timed(
                lambda: call({"K+": m, "Cl-": m}, {"K+": m, "Cl-": m}, {"K": m, "Cl": m})
            )
            ec = value["ec_us_cm"]
            row[name] = dict(
                value,
                ms=1000 * seconds,
                error_percent=None
                if ec is None
                else 100 * (ec - standard["kappa"]) / standard["kappa"],
            )
        rows.append(row)
    return {"source": data["citation"], "rows": rows}


def catalogue_part(run):
    from flahax import load_library, recommend
    from flahax.product_conversion import catalogue_dose_totals

    library = load_library()
    rows = []
    for formula in library["formulas"]:
        recipe = recommend(library["salts"], formula["targets"], {})
        totals = catalogue_dose_totals({s["name"]: s["gramsPerLitre"] for s in recipe["salts"]})
        macro, ions, elements = inputs(totals)
        full = flahax_ec(totals)
        row = {
            "formula": formula["name"],
            "dropped": sorted(b for b in totals if b not in macro),
            "flahax_full_recipe": full,
        }
        for name, call in run.items():
            value, seconds = timed(lambda: call(macro, ions, elements))
            row[name] = dict(value, ms=1000 * seconds)
        if full["ec_us_cm"] is not None:
            row["dropped_share_percent"] = 100 * (full["ec_us_cm"] / row["flahax"]["ec_us_cm"] - 1)
        values = [row[n]["ec_us_cm"] for n in run if row[n]["ec_us_cm"] is not None]
        mean = sum(values) / len(values)
        row["spread_percent"] = 100 * (max(values) - min(values)) / mean
        rows.append(row)
    return {"rows": rows}


def summarise(part, names, key):
    out = {}
    for name in names:
        values = [abs(r[name][key]) for r in part["rows"] if r[name].get(key) is not None]
        out[name] = {
            "max_abs": max(values, default=None),
            "count": len(values),
            "median_ms": sorted(r[name]["ms"] for r in part["rows"])[len(part["rows"]) // 2],
        }
    return out


def run():
    from phreeqpython import PhreeqPython
    import phreeqpython

    database = Path(phreeqpython.__file__).parent / "database" / "phreeqc.dat"
    pp = PhreeqPython(database=str(database))
    calls = engines(pp)
    standards = standards_part(calls)
    catalogue = catalogue_part(calls)
    for row in catalogue["rows"]:
        for name in calls:
            row[name]["vs_flahax_percent"] = 100 * (
                row[name]["ec_us_cm"] / row["flahax"]["ec_us_cm"] - 1
            )
    return {
        "phreeqc_database": {
            "file": "phreeqpython/database/phreeqc.dat",
            "sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        },
        "repeats": REPEATS,
        "standards": standards,
        "catalogue": catalogue,
        "summary": {
            "standards_error_percent": summarise(standards, calls, "error_percent"),
            "catalogue_vs_flahax_percent": summarise(catalogue, calls, "vs_flahax_percent"),
            "catalogue_max_spread_percent": max(r["spread_percent"] for r in catalogue["rows"]),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    warnings.filterwarnings("ignore")
    logging.disable(logging.WARNING)  # pyEQL logs every unknown-parameter fallback
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, default=lambda v: v.item()), encoding="utf-8"
    )
    names = ("flahax", "horticalc", "phreeqc", "pyeql")
    print("KCl standard (IUPAC 2001)".ljust(28), *[n.rjust(12) for n in names])
    for row in report["standards"]["rows"]:
        cells = [row[n]["error_percent"] for n in names]
        print(
            f"{row['molality']:>6} mol/kg {row['reference_us_cm']:>12.1f}",
            *[
                ("%+.2f%%" % c if c is not None else row[n]["status"][:11]).rjust(12)
                for c, n in zip(cells, names)
            ],
        )
    print(
        "catalogue vs FlahaX, max |%|",
        {
            n: round(s["max_abs"], 2)
            for n, s in report["summary"]["catalogue_vs_flahax_percent"].items()
        },
    )
    print(
        "median ms",
        {
            n: round(s["median_ms"], 2)
            for n, s in report["summary"]["catalogue_vs_flahax_percent"].items()
        },
    )


if __name__ == "__main__":
    main()
