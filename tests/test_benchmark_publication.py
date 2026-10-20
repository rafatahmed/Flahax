"""Publication gates must reject misleading provenance and preserve failures."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.publish_benchmark_report import load_capture, redact, sha


class PublicationTests(unittest.TestCase):
    def capture(self):
        inputs = {"example.py": "abc"}
        meta = {"dirty_tree": False, "source_checkout_import": True,
                "git_commit": "revision", "python": "3.13",
                "tool_versions": {"asv": "0.6.6"}, "input_sha256": inputs,
                "input_manifest_sha256": sha(json.dumps(inputs, sort_keys=True).encode())}
        before = {"metadata": meta, "kernel": {"passes": False}}
        after = {"metadata": copy.deepcopy(meta), "input_manifest_matches": True,
                 "performance": {"records": [
                     {"commit_hash": "revision", "samples_seconds": [1., 3., 2.],
                      "sample_count": 3, "median_seconds": 2., "status": "measured"},
                     {"commit_hash": "revision", "samples_seconds": [],
                      "sample_count": 0, "median_seconds": None,
                      "status": "no_samples_or_failed"}]}}
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
        for change in ({"sample_count": 2}, {"median_seconds": 5.},
                       {"samples_seconds": [float("nan"), 2., 3.]}):
            before, after = self.capture()
            after["performance"]["records"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.load(before, after)

    def test_redaction_preserves_parseable_json_and_measurements(self):
        raw = {"path": r"C:\Users\private\checkout\python.exe",
               "file": "C__Users_private_checkout_python.exe.json",
               "samples": [.123456, .25]}
        public = redact(json.dumps(raw))
        self.assertNotIn("private", public)
        self.assertEqual(json.loads(public)["samples"], raw["samples"])


if __name__ == "__main__":
    unittest.main()
