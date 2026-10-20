"""#40 formulation track: FlahaX vs Horticalc vs an Irriblend-method baseline.

Every engine receives the same 30-product FlahaX catalogue, 26 shipped formulas
and two waters. Each returned recipe is re-scored by the Benchmark v1 evaluator
(catalogue assays, max(0.01 mg/L, 1%) tolerance), so no reporting convention of
any engine enters the scores. Timings are the best of `REPEATS` calls on the same
machine: FlahaX single fit vs Horticalc (one fit each) and FlahaX's recommend()
pipeline are reported separately.

Run with the pinned competitor environment (see README.md).
"""
import argparse
import json
import math
import statistics
import time
from pathlib import Path

from benchmarks.cases import WATERS, evaluate_recipe
from flahax import load_library, recommend, solve_weights
from flahax.composition import assay_conflict

REPEATS = 3
EXACT_PERCENT = 1e-3
# Agronomic limits for the second scoreboard (#40). A recipe is "acceptable" when every
# positive target is within the Benchmark v1 tolerance AND:
# - incidental Cl <= 3 mmol/L (106.35 mg/L): raw-water cap for open systems with drain,
#   De Kreij, Voogt & Baas (2003), PPO Brochure 191, p. 6;
# - incidental NH4-N <= min(10% of total target N, 1.5 mmol/L): FlahaX default (#54),
#   from Dutch soilless practice (5-15% of N, at most 1-1.5 mmol/L);
# - incidental Na <= 3 mmol/L (68.97 mg/L): same De Kreij raw-water cap;
# - no micronutrient above twice its target (FlahaX design choice; no published bound).
CL_LIMIT = 3.0 * 35.45
NA_LIMIT = 3.0 * 22.989769
MICRO = ("Fe", "Mn", "Zn", "Cu", "B", "Mo")


def timed(call):
    best, value = math.inf, None
    for _ in range(REPEATS):
        start = time.perf_counter()
        value = call()
        best = min(best, time.perf_counter() - start)
    return value, best


def irriblend_method(products, targets, water):
    """Independent LP after Gallego-Elvira et al. (2021): exact NO3-N, NH4-N, P, K and
    micronutrients; Ca, Mg and S at or above target; minimise total grams (the catalogue
    has no prices, so equal cost per gram). Not the authors' code. Returns None when
    infeasible, as the published method does."""
    import numpy as np
    from scipy.optimize import linprog
    exact = {"N_NO3", "N_NH4", "P", "K", "Fe", "Mn", "Zn", "Cu", "B", "Mo"}
    at_least = {"Ca", "Mg", "S"}
    a_eq, b_eq, a_ub, b_ub = [], [], [], []
    for ion, target in targets.items():
        if target <= 0:
            continue
        row = [p["elements"].get(ion, 0.0) * 10.0 for p in products]
        need = target - water.get(ion, 0.0)
        if ion in exact:
            a_eq.append(row)
            b_eq.append(need)
        elif ion in at_least:
            a_ub.append([-v for v in row])
            b_ub.append(-need)
    result = linprog(np.ones(len(products)), A_ub=a_ub or None, b_ub=b_ub or None,
                     A_eq=a_eq or None, b_eq=b_eq or None,
                     bounds=[(0, None)] * len(products), method="highs")
    if result.status != 0:
        return None
    return {"salts": [{"id": p["id"], "gramsPerLitre": g} for p, g in zip(products, result.x) if g > 1e-9]}


def score(salts, recipe, targets, water):
    evaluated = evaluate_recipe(salts, recipe, targets, water)
    return evaluated["rows"], evaluated["whole_recipe_passes"]


def incidental(salts, recipe, targets, water):
    """Delivered incidental Cl, Na, NH4-N (mg/L) and micronutrient overshoot ratio."""
    by_id = {s["id"]: s for s in salts}

    def delivered(ion):
        return water.get(ion, 0.0) + sum(item["gramsPerLitre"] * by_id[item["id"]]["elements"].get(ion, 0.0) * 10.0
                                         for item in recipe["salts"])
    total_n = sum(targets.get(k, 0.0) for k in ("N_NO3", "N_NH4", "N_UREA"))
    ammonium_limit = min(0.10 * total_n, 1.5 * 14.0067)
    out = {"Cl": 0.0 if targets.get("Cl", 0) > 0 else delivered("Cl"),
           "Na": 0.0 if targets.get("Na", 0) > 0 else delivered("Na"),
           "NH4_N": 0.0 if targets.get("N_NH4", 0) > 0 else delivered("N_NH4"),
           "ammonium_limit": ammonium_limit,
           "micro_ratio": max((delivered(m) / targets[m] for m in MICRO if targets.get(m, 0) > 0), default=0.0)}
    out["within_limits"] = (out["Cl"] <= CL_LIMIT and out["Na"] <= NA_LIMIT
                            and out["NH4_N"] <= ammonium_limit + 1e-9 and out["micro_ratio"] <= 2.0)
    return out


def summarise(rows, wholes, times, products_used, attempted, extras):
    pct = [abs(r["error_percent"]) for r in rows if r["error_percent"] is not None]
    return {
        "recipes_acceptable": sum(1 for whole, x in zip(wholes, extras) if whole and x["within_limits"]),
        "recipes_within_limits": sum(x["within_limits"] for x in extras),
        "max_incidental_cl_mg_l": max((x["Cl"] for x in extras), default=None),
        "max_incidental_nh4_n_mg_l": max((x["NH4_N"] for x in extras), default=None),
        "max_micro_ratio": max((x["micro_ratio"] for x in extras), default=None),
        "recipes_attempted": attempted, "recipes_returned": len(wholes),
        "whole_recipes_passing": sum(wholes), "targets_scored": len(rows),
        "targets_passing": sum(r["passes"] for r in rows),
        "targets_within_5pct": sum(p <= 5 for p in pct), "targets_exact": sum(p < EXACT_PERCENT for p in pct),
        "rms_percent": math.sqrt(statistics.mean(p * p for p in pct)) if pct else None,
        "max_abs_percent": max(pct, default=None),
        "mean_products": statistics.mean(products_used) if products_used else None,
        "median_ms": 1000 * statistics.median(times) if times else None,
        "mean_ms": 1000 * statistics.mean(times) if times else None,
    }


def run():
    from benchmarks.competitors import horticalc_adapter as hc
    library = load_library()
    salts = library["salts"]
    usable = [s for s in salts if assay_conflict(s) is None]
    ferts = hc.translate(usable)
    translation_error = hc.validate_translation(usable, ferts)
    by_name = {s["name"]: s for s in usable}
    engines = ("flahax_single_fit", "flahax_recommend", "flahax_recommend_cl_cap", "horticalc_as_shipped",
               "horticalc_aligned", "irriblend_method")
    acc = {e: {"rows": [], "wholes": [], "times": [], "products": [], "extras": []} for e in engines}
    cases = []
    for formula in library["formulas"]:
        for water_name, water in WATERS.items():
            targets = formula["targets"]
            runs = {}
            fit, t = timed(lambda: solve_weights(usable, targets, water))
            runs["flahax_single_fit"] = ({"salts": fit["salts"]}, t)
            rec, t = timed(lambda: recommend(salts, targets, water))
            runs["flahax_recommend"] = ({"salts": rec["salts"]}, t)
            capped, t = timed(lambda: recommend(salts, targets, water, maximum_concentrations={"Cl": CL_LIMIT}))
            runs["flahax_recommend_cl_cap"] = ({"salts": capped["salts"]}, t)
            for config in hc.CONFIGS:
                out, t = timed(lambda: hc.solve(ferts, targets, water, config))
                recipe = {"salts": [{"id": by_name[f["name"]]["id"], "gramsPerLitre": f["grams"]}
                                    for f in out.fertilizers if f["grams"] > 0]}
                runs[f"horticalc_{config}"] = (recipe, t)
            lp, t = timed(lambda: irriblend_method(usable, targets, water))
            runs["irriblend_method"] = (lp, t)
            case = {"formula": formula["name"], "water": water_name}
            for engine, (recipe, seconds) in runs.items():
                if recipe is None:
                    case[engine] = {"returned": False, "seconds": seconds}
                    continue
                rows, whole = score(salts, recipe, targets, water)
                extra = incidental(salts, recipe, targets, water)
                acc[engine]["extras"].append(extra)
                acc[engine]["rows"] += rows
                acc[engine]["wholes"].append(whole)
                acc[engine]["times"].append(seconds)
                acc[engine]["products"].append(len(recipe["salts"]))
                case[engine] = {"returned": True, "seconds": seconds, "whole_recipe_passes": whole,
                                "incidental": extra,
                                "doses": {s["id"]: s["gramsPerLitre"] for s in recipe["salts"]}}
            cases.append(case)
    attempted = len(library["formulas"]) * len(WATERS)
    summary = {e: summarise(acc[e]["rows"], acc[e]["wholes"], acc[e]["times"], acc[e]["products"], attempted,
                            acc[e]["extras"]) for e in engines}
    return {"translation_max_relative_error": translation_error, "horticalc": hc.PIN,
            "repeats": REPEATS, "summary": summary, "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # scipy/numpy scalars (int64, bool_, float64) serialise as plain Python numbers.
    args.output.write_text(json.dumps(report, indent=2, default=lambda v: v.item()), encoding="utf-8")
    keys = ("whole_recipes_passing", "recipes_acceptable", "targets_passing", "targets_exact", "rms_percent",
            "max_incidental_cl_mg_l", "max_incidental_nh4_n_mg_l", "max_micro_ratio", "median_ms")
    print("engine".ljust(22), *[k[:14].rjust(15) for k in keys])
    for engine, s in report["summary"].items():
        print(engine.ljust(22), *[(f"{s[k]:.2f}" if isinstance(s[k], float) else str(s[k])).rjust(15) for k in keys])


if __name__ == "__main__":
    main()
