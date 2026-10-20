"""Regression tests for measurement semantics, not timing thresholds."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from benchmarks.cases import evaluate_recipe, objective
from tools.benchmark_baseline import historical, asv_samples


class BenchmarkMeasurementTests(unittest.TestCase):
    def test_recipe_uses_returned_doses_not_claimed_rows(self):
        products = [{"id": "k", "elements": {"K": 10.}}]
        result = {"salts": [{"id": "k", "gramsPerLitre": 1.}],
                  "rows": [{"symbol": "K", "final": 200.}]}
        scored = evaluate_recipe(products, result, {"K": 200.}, {"K": 20.})
        self.assertEqual(scored["rows"][0]["delivered_mg_l"], 120.)
        self.assertFalse(scored["whole_recipe_passes"])

    def test_zero_targets_use_absolute_tolerance_and_whole_recipe_is_distinct(self):
        products = [{"id": "k", "elements": {"K": 10.}}]
        result = {"salts": [{"id": "k", "gramsPerLitre": 1.}]}
        scored = evaluate_recipe(products, result, {"K": 100., "Na": 0.}, {"Na": .02})
        self.assertTrue(scored["rows"][0]["passes"])
        self.assertIsNone(scored["rows"][1]["error_percent"])
        self.assertFalse(scored["whole_recipe_passes"])

    def test_invalid_and_duplicate_doses_are_not_successes(self):
        product = {"id": "a", "elements": {"K": 10.}}
        for dose in [-1., float("nan"), float("inf")]:
            with self.subTest(dose=dose), self.assertRaises(ValueError):
                evaluate_recipe([product], {"salts": [{"id": "a", "gramsPerLitre": dose}]},
                                {"K": 1.}, {})
        item = {"id": "a", "gramsPerLitre": 1.}
        with self.assertRaises(ValueError):
            evaluate_recipe([product], {"salts": [item, item]}, {"K": 1.}, {})

    def test_nonunique_nnls_solutions_compared_by_objective(self):
        matrix, rhs = [[1., 1.], [2., 2.]], [3., 6.]
        self.assertEqual(objective(matrix, rhs, [3., 0.]), objective(matrix, rhs, [0., 3.]))
        with self.assertRaises(ValueError):
            objective(matrix, rhs, [-1., 4.])

    def test_historical_runtime_is_not_weighted_by_element_count(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.csv"
            fields = ["engine", "scenario", "formula", "runtime_s", "err_pct", "err_mg"]
            rows = [{"engine": "engine", "scenario": "water", "formula": name,
                     "runtime_s": time, "err_pct": 0, "err_mg": 0}
                    for name, time in [("a", 1), ("a", 1), ("b", 3)]]
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            result = historical(path)["engines"]["engine"]
            self.assertEqual(result["mean_runtime_ms_once_per_case"], 2000.)
            self.assertEqual(result["element_targets"], 3)
            self.assertEqual(result["cases"], 2)

    def test_asv_samples_and_empty_measurements_remain_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "asv.json"
            path.write_text(json.dumps({
                "commit_hash": "test", "result_columns": ["result", "samples", "params"],
                "results": {"timing": [[2.], [[1., 2., 3.]], []],
                            "failed": [None, None, []]}}))
            rows = asv_samples(folder)["records"]
            timing = next(row for row in rows if row["benchmark"] == "timing")
            failed = next(row for row in rows if row["benchmark"] == "failed")
            self.assertEqual(timing["median_seconds"], 2.)
            self.assertEqual(timing["p95_seconds_nearest_rank"], 3.)
            self.assertEqual(failed["status"], "no_samples_or_failed")


if __name__ == "__main__":
    unittest.main()
