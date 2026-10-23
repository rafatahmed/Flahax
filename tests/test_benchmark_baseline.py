# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Regression tests for measurement semantics, not timing thresholds."""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from benchmarks.cases import evaluate_recipe, objective
from tools.benchmark_baseline import historical, asv_samples, provenance


class BenchmarkMeasurementTests(unittest.TestCase):
    def test_provenance_covers_delivery_helper_and_historical_data(self):
        from benchmarks.cases import ROOT, digest

        if not (ROOT / ".git").exists():
            self.skipTest("checkout-only provenance")
        manifest = provenance()["input_sha256"]
        for relative in (
            "examples/equilibrium_delivery.py",
            "docs/site/evidence/audit/2026-10-17-flahax-vs-horticalc/data/bench_formulation_variants.csv",
            ".github/workflows/benchmark.yml",
            "pyproject.toml",
        ):
            self.assertEqual(manifest[relative], digest(ROOT / relative))

    def test_recipe_uses_returned_doses_not_claimed_rows(self):
        products = [{"id": "k", "elements": {"K": 10.0}}]
        result = {
            "salts": [{"id": "k", "gramsPerLitre": 1.0}],
            "rows": [{"symbol": "K", "final": 200.0}],
        }
        scored = evaluate_recipe(products, result, {"K": 200.0}, {"K": 20.0})
        self.assertEqual(scored["rows"][0]["delivered_mg_l"], 120.0)
        self.assertFalse(scored["whole_recipe_passes"])

    def test_zero_targets_use_absolute_tolerance_and_whole_recipe_is_distinct(self):
        products = [{"id": "k", "elements": {"K": 10.0}}]
        result = {"salts": [{"id": "k", "gramsPerLitre": 1.0}]}
        scored = evaluate_recipe(products, result, {"K": 100.0, "Na": 0.0}, {"Na": 0.02})
        self.assertTrue(scored["rows"][0]["passes"])
        self.assertIsNone(scored["rows"][1]["error_percent"])
        self.assertFalse(scored["whole_recipe_passes"])

    def test_invalid_and_duplicate_doses_are_not_successes(self):
        product = {"id": "a", "elements": {"K": 10.0}}
        for dose in [-1.0, float("nan"), float("inf")]:
            with self.subTest(dose=dose), self.assertRaises(ValueError):
                evaluate_recipe(
                    [product], {"salts": [{"id": "a", "gramsPerLitre": dose}]}, {"K": 1.0}, {}
                )
        item = {"id": "a", "gramsPerLitre": 1.0}
        with self.assertRaises(ValueError):
            evaluate_recipe([product], {"salts": [item, item]}, {"K": 1.0}, {})

    def test_nonunique_nnls_solutions_compared_by_objective(self):
        matrix, rhs = [[1.0, 1.0], [2.0, 2.0]], [3.0, 6.0]
        self.assertEqual(objective(matrix, rhs, [3.0, 0.0]), objective(matrix, rhs, [0.0, 3.0]))
        with self.assertRaises(ValueError):
            objective(matrix, rhs, [-1.0, 4.0])

    def test_historical_runtime_is_not_weighted_by_element_count(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.csv"
            fields = ["engine", "scenario", "formula", "runtime_s", "err_pct", "err_mg"]
            rows = [
                {
                    "engine": "engine",
                    "scenario": "water",
                    "formula": name,
                    "runtime_s": time,
                    "err_pct": 0,
                    "err_mg": 0,
                }
                for name, time in [("a", 1), ("a", 1), ("b", 3)]
            ]
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            result = historical(path)["engines"]["engine"]
            self.assertEqual(result["mean_runtime_ms_once_per_case"], 2000.0)
            self.assertEqual(result["element_targets"], 3)
            self.assertEqual(result["cases"], 2)

    def test_asv_samples_and_empty_measurements_remain_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "asv.json"
            path.write_text(
                json.dumps(
                    {
                        "commit_hash": "test",
                        "result_columns": ["result", "samples", "params"],
                        "results": {
                            "timing": [[2.0], [[1.0, 2.0, 3.0]], []],
                            "failed": [None, None, []],
                        },
                    }
                )
            )
            rows = asv_samples(folder)["records"]
            timing = next(row for row in rows if row["benchmark"] == "timing")
            failed = next(row for row in rows if row["benchmark"] == "failed")
            self.assertEqual(timing["median_seconds"], 2.0)
            self.assertEqual(timing["p95_seconds_nearest_rank"], 3.0)
            self.assertEqual(failed["status"], "no_samples_or_failed")


if __name__ == "__main__":
    unittest.main()
