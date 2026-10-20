"""Fixed Benchmark v1 inputs, independent scoring, and correctness gates."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/phreeqc"
VERSION = "benchmark-v1"
TARGETS = {"N_NO3": 128, "P": 58, "K": 211, "Ca": 104, "Mg": 40, "S": 54}
WATERS = {"zero_nutrients": {}, "calcium_20_mg_l": {"Ca": 20}}
# Analytic numerical systems, not fertilizer identities. Each reference receives
# precisely these rows and RHS; no library filtering or regularization is hidden.
NNLS_CASES = {
    "exact": ([[1., 0.], [0., 1.], [1., 1.]], [2., 3., 5.]),
    "infeasible": ([[1.], [1.]], [1., 3.]),
    "water_exceeds_target": ([[1., 0.], [0., 1.]], [-1., 2.]),
    "duplicate_columns": ([[1., 1.], [2., 2.]], [3., 6.]),
    "near_dependent": ([[1., 1.], [1., 1.000001], [0., .000001]], [2., 2.000001, .000001]),
    "trace_scale": ([[1., 0.], [0., 1.]], [1e-8, 1.]),
    "zero_target": ([[1., 0.], [0., 1.]], [0., 1.]),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_fixture(relative):
    path = FIXTURES / relative / "expected.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for name, expected in data["hashes"].items():
        if digest(path.parent / name) != expected:
            raise ValueError(f"Reference hash mismatch: {relative}/{name}")
    return data


def objective(matrix, rhs, weights):
    if len(weights) != len(matrix[0]) or any(not math.isfinite(x) or x < 0 for x in weights):
        raise ValueError("Invalid nonnegative solution")
    return float(sum((sum(a*x for a, x in zip(row, weights)) - b)**2
                     for row, b in zip(matrix, rhs)))


def evaluate_recipe(products, result, targets, water, *, absolute_mg_l=.01, relative=.01):
    """Reconstruct target nutrients from returned rounded doses, not solver rows.

    Catalogue-assay evaluator: unassayed counterions are outside this target-fit
    scorecard. They remain separately reported by the public workflow.
    """
    by_id = {p["id"]: p for p in products}
    delivered = dict(water)
    seen = set()
    for item in result["salts"]:
        ident, dose = item["id"], item["gramsPerLitre"]
        if ident in seen or ident not in by_id or not math.isfinite(dose) or dose < 0:
            raise ValueError("Invalid, duplicate or unidentified returned dose")
        seen.add(ident)
        for ion, percent in by_id[ident]["elements"].items():
            delivered[ion] = delivered.get(ion, 0.) + dose * percent * 10.
    rows = []
    for ion, target in targets.items():
        actual = delivered.get(ion, 0.)
        error = actual - target
        rows.append({
            "ion": ion, "target_mg_l": target, "delivered_mg_l": actual,
            "error_mg_l": error,
            "error_percent": 100 * error / target if target > 0 else None,
            "tolerance_mg_l": max(absolute_mg_l, relative * abs(target)),
            "passes": abs(error) <= max(absolute_mg_l, relative * abs(target)),
        })
    return {"rows": rows, "whole_recipe_passes": all(r["passes"] for r in rows),
            "products_used": len(seen), "delivered_assay_mg_l": delivered,
            "solver_feasible": result.get("feasible"),
            "incidental_requires_review": result.get("requiresReview")}


def solve_fixture(data):
    from flahax.aqueous_model import solve, nitric_target
    row = data["selected_rows"][-1]
    if data.get("nitric_acid_molal") is not None:
        plan = nitric_target(data["runtime_totals"], data["initial_ph"], row["pH"])
        return plan.target, plan.nitric_acid_molal
    return solve(data["runtime_totals"], row["pH"], phases=data.get("phases", ())), None


def evaluate_chemistry(data, result, acid=None):
    """Quantity-specific comparisons using the existing fixture's tolerances."""
    row, tol = data["selected_rows"][-1], data["tolerances"]
    checks = []

    def check(quantity, actual, expected, absolute, relative=0.):
        limit = absolute + relative * abs(expected)
        checks.append({"quantity": quantity, "actual": actual, "reference": expected,
                       "absolute_error": abs(actual-expected), "tolerance": limit,
                       "passes": math.isfinite(actual) and abs(actual-expected) <= limit})

    phase_case = "phases" in data
    for component, residual in result.residuals.items():
        check("conservation:" + component, residual, 0., 1e-15 + 1e-9 * result.totals[component])
    check("ionic_strength_mol_kgw", result.ionic_strength, row["mu"], 1e-9, .03)
    # pH is prescribed for these captures, not an independently solved pH test.
    check("prescribed_pH", result.ph, row["pH"], 1e-12)
    for key, expected in row.items():
        if key.startswith("m_"):
            check(key, result.species[key[2:]], expected,
                  tol["molality_absolute" if phase_case else "runtime_molality_absolute"],
                  tol["molality_relative" if phase_case else "runtime_molality_relative"])
        elif key.startswith("si_"):
            check(key, result.saturation_indices[key[3:]], expected,
                  tol["si_absolute" if phase_case else "runtime_si_absolute"])
        elif key.startswith("la_") and not phase_case and row.get("m_" + key[3:], 0.) > 1e-10:
            check(key, math.log10(result.activities[key[3:]]), expected,
                  tol["runtime_log_activity_absolute"])
    for phase in data.get("phases", []):
        amount = result.precipitated.get(phase, 0.)
        check("phase_mol_kgw:" + phase, amount, row[phase] / row["mass_H2O"],
              tol["phase_absolute"], tol["phase_relative"])
        si = result.saturation_indices.get(phase)
        # Inapplicable phases may be absent when their components are absent.
        if si is not None:
            checks.append({"quantity": "phase_complementarity:" + phase,
                           "amount_mol_kgw": amount, "saturation_index": si,
                           "passes": amount >= 0 and si <= 1e-7
                           and (amount == 0 or abs(si) <= 1e-7)})
    if acid is not None:
        for name in ("nitric_acid_molal", "fix_h_nitric_acid_molal"):
            check(name, acid, data[name], tol["acid_absolute"], tol["acid_relative"])
    checks.append({"quantity": "iterations", "actual": result.iterations,
                   "passes": 0 <= result.iterations < 1500})
    return {"passes": all(c["passes"] for c in checks),
            "iterations": result.iterations, "checks": checks}


def require_chemistry(data, result, acid=None):
    report = evaluate_chemistry(data, result, acid)
    if not report["passes"]:
        failed = [c["quantity"] for c in report["checks"] if not c["passes"]]
        raise ValueError(f"Chemistry correctness gate failed: {failed}")
