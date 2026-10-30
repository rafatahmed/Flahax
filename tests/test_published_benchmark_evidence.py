# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Verify that published downloads and headline counts match the evidence."""

import csv
import hashlib
import io
import json
from pathlib import Path
import re
import unittest
import zipfile

from tools.publish_benchmark_report import formula_names, miss_summary, scorecard_notice
from tests.catalogue_history import historical_catalogue

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
                for download in path.parent.iterdir():
                    if download.name != "evidence.zip":
                        self.assertEqual(
                            download.read_bytes(), bundle.read(download.name), download.name
                        )
                for name in bundle.namelist():
                    if name.endswith((".json", ".log", ".txt")):
                        self.assertIsNone(
                            re.search(
                                rb"[A-Za-z]:[\\/]+Users[\\/]+|[A-Za-z]__Users_|/home/[a-z]",
                                bundle.read(name),
                            ),
                            name,
                        )

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

    def test_pages_name_misses_from_their_own_snapshot(self):
        self.enterContext(historical_catalogue())
        names = formula_names(ROOT)
        for page_path in (ROOT / "docs/site/evidence").glob("benchmark-results*.md"):
            page = page_path.read_text(encoding="utf-8")
            snapshot = re.search(r"\*\*Measured snapshot: ([a-z0-9-]+)\.", page).group(1)
            with (ASSETS / snapshot / "formulation.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            with self.subTest(page=page_path.name):
                self.assertIn(miss_summary(rows, names), page)
                self.assertNotRegex(page, r"\b1 timing workloads\b")
                self.assertNotRegex(page, r"(?m)^\| cmb[a-z0-9]+:")


class ScorecardNoticeTests(unittest.TestCase):
    """#66: the page head warns only when a gate actually failed."""

    MANUAL = {"url": "https://example.invalid/run", "conclusion": "success"}

    def test_all_gates_passing_gives_a_note(self):
        text = scorecard_notice(
            7,
            7,
            {"passed": 21, "attempted": 21},
            "0 timing workloads have no " "completed measurement.",
            0,
            self.MANUAL,
        )
        self.assertTrue(text.startswith("```{note}"))
        self.assertNotIn("not fully passing", text)

    def test_any_failed_gate_gives_a_warning(self):
        failing = [
            (6, 7, {"passed": 21, "attempted": 21}, 0, self.MANUAL),
            (7, 7, {"passed": 20, "attempted": 21}, 0, self.MANUAL),
            (7, 7, {"passed": 21, "attempted": 21}, 1, self.MANUAL),
            (7, 7, {"passed": 21, "attempted": 21}, 0, dict(self.MANUAL, conclusion="failure")),
        ]
        for kernel_pass, total, chemistry, missing, manual in failing:
            with self.subTest(kernel_pass=kernel_pass, chemistry=chemistry, missing=missing):
                text = scorecard_notice(
                    kernel_pass, total, chemistry, "missing text", missing, manual
                )
                self.assertTrue(text.startswith("```{warning}"))
                self.assertIn("not fully passing", text)


if __name__ == "__main__":
    unittest.main()
