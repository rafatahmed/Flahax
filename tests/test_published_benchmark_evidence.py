"""Verify that published downloads and headline counts match the evidence."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs/site/_static/benchmarks"


class PublishedEvidenceTests(unittest.TestCase):
    def test_archives_checksums_and_public_path_redaction(self):
        archives = list(ASSETS.glob("*/evidence.zip"))
        self.assertTrue(archives, "Published benchmark evidence is missing")
        for path in archives:
            with self.subTest(snapshot=path.parent.name), zipfile.ZipFile(path) as bundle:
                checksums = bundle.read("CHECKSUMS.sha256").decode().splitlines()
                covered = set()
                for line in checksums:
                    expected, name = line.split("  ", 1)
                    covered.add(name)
                    self.assertEqual(hashlib.sha256(bundle.read(name)).hexdigest(), expected)
                self.assertEqual(covered, set(bundle.namelist()) - {"CHECKSUMS.sha256"})
                self.assertEqual(path.with_name("baseline.json").read_bytes(),
                                 bundle.read("baseline.json"))
                for name in bundle.namelist():
                    if name.endswith((".json", ".log", ".txt")):
                        self.assertIsNone(re.search(
                            rb"[A-Za-z]:[\\/]+Users[\\/]+|[A-Za-z]__Users_|/home/[a-z]",
                            bundle.read(name)), name)

    def test_current_page_counts_and_download_digest_match(self):
        page = (ROOT / "docs/site/evidence/benchmark-results.md").read_text(encoding="utf-8")
        snapshot = re.search(r"\*\*Measured snapshot: ([a-z0-9-]+)\.", page).group(1)
        folder = ASSETS / snapshot
        report = json.loads((folder / "baseline.json").read_text())
        self.assertFalse(report["metadata"]["dirty_tree"])
        self.assertFalse(report["after_metadata"]["dirty_tree"])
        self.assertTrue(report["input_manifest_matches"])
        with (folder / "formulation.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        passed = sum(r["passes"] == "True" for r in rows)
        self.assertIn(f"| Nutrient targets | {passed}/{len(rows)} ", page)
        self.assertIn(hashlib.sha256((folder / "evidence.zip").read_bytes()).hexdigest(), page)
        timing = list(csv.DictReader(io.StringIO((folder / "timings.csv").read_text())))
        measured = sum(r["status"] == "measured" for r in timing)
        self.assertIn(f"| Completed timing workloads | {measured}/{len(timing)} ", page)


if __name__ == "__main__":
    unittest.main()
