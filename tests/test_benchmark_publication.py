# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Publication gates must reject misleading provenance and preserve failures."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.publish_benchmark_report import (
    case_label,
    count,
    load_capture,
    miss_summary,
    redact,
    sha,
)


class PublicationTests(unittest.TestCase):
    def capture(self):
        inputs = {"example.py": "abc"}
        meta = {
            "dirty_tree": False,
            "source_checkout_import": True,
            "git_commit": "revision",
            "python": "3.13",
            "tool_versions": {"asv": "0.6.6"},
            "input_sha256": inputs,
            "input_manifest_sha256": sha(json.dumps(inputs, sort_keys=True).encode()),
        }
        before = {"metadata": meta, "kernel": {"passes": False}}
        after = {
            "metadata": copy.deepcopy(meta),
            "input_manifest_matches": True,
            "performance": {
                "records": [
                    {
                        "commit_hash": "revision",
                        "samples_seconds": [1.0, 3.0, 2.0],
                        "sample_count": 3,
                        "median_seconds": 2.0,
                        "status": "measured",
                    },
                    {
                        "commit_hash": "revision",
                        "samples_seconds": [],
                        "sample_count": 0,
                        "median_seconds": None,
                        "status": "no_samples_or_failed",
                    },
                ]
            },
        }
        return before, after

    def load(self, before, after):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            for name, value in (("before", before), ("after", after)):
                (path / (name + ".json")).write_text(json.dumps(value), encoding="utf-8")
            return load_capture(path)

    def test_clean_capture_keeps_numerical_failure_and_missing_timing(self):
        result = self.load(*self.capture())
        self.assertFalse(result["kernel"]["passes"])
        self.assertEqual(result["performance"]["records"][1]["status"], "no_samples_or_failed")

    def test_dirty_or_different_checkout_cannot_be_published(self):
        for side in (0, 1):
            before, after = self.capture()
            (before, after)[side]["metadata"]["dirty_tree"] = True
            with self.subTest(side=side), self.assertRaisesRegex(ValueError, "dirty"):
                self.load(before, after)
        before, after = self.capture()
        after["metadata"]["git_commit"] = "different"
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.load(before, after)

    def test_modified_manifest_and_wrong_timing_revision_are_rejected(self):
        before, after = self.capture()
        after["metadata"]["input_sha256"]["example.py"] = "changed"
        with self.assertRaisesRegex(ValueError, "manifest digest"):
            self.load(before, after)
        before, after = self.capture()
        after["performance"]["records"][0]["commit_hash"] = "other"
        with self.assertRaisesRegex(ValueError, "wrong measured revision"):
            self.load(before, after)

    def test_inconsistent_or_invalid_samples_are_rejected(self):
        for change in (
            {"sample_count": 2},
            {"median_seconds": 5.0},
            {"samples_seconds": [float("nan"), 2.0, 3.0]},
        ):
            before, after = self.capture()
            after["performance"]["records"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.load(before, after)

    def test_redaction_preserves_parseable_json_and_measurements(self):
        raw = {
            "path": r"C:\Users\private\checkout\python.exe",
            "file": "C__Users_private_checkout_python.exe.json",
            "samples": [0.123456, 0.25],
        }
        public = redact(json.dumps(raw))
        self.assertNotIn("private", public)
        self.assertEqual(json.loads(public)["samples"], raw["samples"])

    def test_counts_are_grammatical(self):
        self.assertEqual(count(0, "timing workload"), "0 timing workloads")
        self.assertEqual(count(1, "timing workload"), "1 timing workload")
        self.assertEqual(count(2, "timing workload"), "2 timing workloads")

    def test_case_label_keeps_catalogue_id(self):
        names = {"abc": "Tomato"}
        self.assertEqual(
            case_label("abc:zero_nutrients", names),
            "Tomato, zero nutrients (`abc:zero_nutrients`)",
        )
        self.assertIn("Unknown formula", case_label("missing:calcium_20_mg_l", names))

    def test_miss_summary_names_largest_positive_target_miss(self):
        rows = [
            {
                "case": "a:zero_nutrients",
                "ion": "Ca",
                "target_mg_l": "100",
                "delivered_mg_l": "90",
                "error_percent": "-10",
                "passes": "False",
            },
            {
                "case": "a:zero_nutrients",
                "ion": "Si",
                "target_mg_l": "50",
                "delivered_mg_l": "0",
                "error_percent": "-100",
                "passes": "False",
            },
            {
                "case": "a:zero_nutrients",
                "ion": "Ca",
                "target_mg_l": "0",
                "delivered_mg_l": "5",
                "error_percent": "",
                "passes": "False",
            },
            {
                "case": "a:zero_nutrients",
                "ion": "K",
                "target_mg_l": "200",
                "delivered_mg_l": "200",
                "error_percent": "0",
                "passes": True,
            },
        ]
        summary = miss_summary(rows, {"a": "Tomato"})
        self.assertIn("largest miss is Si in Tomato", summary)
        self.assertIn("target 50 mg/L, delivered 0 mg/L (-100.0%)", summary)
        self.assertIn("| Ca | 2/2 |", summary)
        self.assertNotIn("| K |", summary)
        self.assertEqual(
            miss_summary(rows[3:], {}), "All explicit nutrient targets pass in this capture."
        )


if __name__ == "__main__":
    unittest.main()
