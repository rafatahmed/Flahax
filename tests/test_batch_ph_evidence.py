# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Measured pH must support the exact batch preparation and its full error interval."""

import copy
import unittest
from datetime import datetime, timezone, timedelta

from flahax.stock_evidence import assess_stock_evidence
from flahax.ph_evidence import preparation_fingerprint
from tests.test_stock_evidence import records, reference_recipe


class BatchPhEvidenceTests(unittest.TestCase):
    def test_missing_measurement_blocks_otherwise_complete_evidence(self):
        evidence = records()
        evidence.pop("batch_ph")
        result = assess_stock_evidence(reference_recipe(), evidence)
        self.assertFalse(result["verified"])
        self.assertEqual(result["final_volume_check"]["status"], "passed")
        self.assertTrue(all(row["status"] == "passed" for row in result["stock_checks"]))
        self.assertEqual(result["batch_ph_check"]["status"], "missing")
        self.assertEqual(len(result["preparation_fingerprint"]), 64)

    def test_complete_uncertainty_interval_inclusive_boundaries(self):
        for reading, expected in (
            (6.29, True),
            (6.31, True),
            (6.3, True),
            (6.28999, False),
            (6.31001, False),
            (6.34, False),
        ):
            evidence = records()
            evidence["batch_ph"]["measurement"]["indicated_ph"] = reading
            with self.subTest(reading=reading):
                result = assess_stock_evidence(reference_recipe(), evidence)
                self.assertEqual(result["verified"], expected)
                self.assertAlmostEqual(result["batch_ph_check"]["total_uncertainty_ph"], 0.01)

    def test_meter_bias_and_both_uncertainties_count(self):
        for section, key in (
            ("calibration", "maximum_absolute_bias_ph"),
            ("calibration", "absolute_uncertainty_ph"),
            ("measurement", "additional_uncertainty_ph"),
        ):
            evidence = records()
            evidence["batch_ph"][section][key] = 0.021
            self.assertFalse(assess_stock_evidence(reference_recipe(), evidence)["verified"])

    def test_reading_must_match_batch_instrument_vessel_and_preparation(self):
        for change in (
            {"batch_id": "other"},
            {"vessel_id": "other"},
            {"meter_id": "other"},
            {"electrode_id": "other"},
            {"calibration_record_id": "other"},
            {"preparation_fingerprint": "wrong"},
            {"record_id": "other"},
            {"application": "before_final_dilution"},
            {"temperature_c": 20},
        ):
            evidence = records()
            evidence["batch_ph"]["measurement"].update(change)
            with self.subTest(change=change):
                self.assertFalse(assess_stock_evidence(reference_recipe(), evidence)["verified"])
        recipe = copy.deepcopy(reference_recipe())
        recipe["stock_delivery"]["stocks"][0]["dose_ml"] += 0.01
        self.assertFalse(assess_stock_evidence(recipe, records())["verified"])

    def test_calibration_range_buffers_and_provenance(self):
        for change in (
            {"ph_min": 6.29},
            {"ph_max": 6.31},
            {"coverage": "endpoints"},
            {"buffers": []},
            {"source": ""},
            {"method": ""},
            {"record_id": "assay-0"},
            {"uncertainty_basis": "standard_deviation"},
            {
                "buffers": [
                    {"reference": "a", "certified_ph": 6.29},
                    {"reference": "b", "certified_ph": 6.31},
                ]
            },
        ):
            evidence = records()
            evidence["batch_ph"]["calibration"].update(change)
            with self.subTest(change=change):
                self.assertFalse(assess_stock_evidence(reference_recipe(), evidence)["verified"])

    def test_timestamps_dates_and_expiry(self):
        evidence = records()
        cal = evidence["batch_ph"]["calibration"]
        time = datetime.fromisoformat(cal["calibrated_at"])
        evidence["batch_ph"]["measurement"]["measured_at"] = (
            time - timedelta(seconds=1)
        ).isoformat()
        self.assertFalse(assess_stock_evidence(reference_recipe(), evidence)["verified"])
        for section, field in (("calibration", "calibrated_at"), ("measurement", "measured_at")):
            for value in (
                "2026-11-14T12:00:00",
                "bad",
                (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            ):
                evidence = records()
                evidence["batch_ph"][section][field] = value
                self.assertFalse(assess_stock_evidence(reference_recipe(), evidence)["verified"])
            evidence = records()
            evidence["batch_ph"][section]["valid_until"] = (
                time.date() - timedelta(days=1)
            ).isoformat()
            self.assertFalse(assess_stock_evidence(reference_recipe(), evidence)["verified"])

    def test_invalid_numbers_and_record_shape_fail_closed(self):
        for value in (True, "6.3", None, float("nan"), float("inf"), -1, 15):
            evidence = records()
            evidence["batch_ph"]["measurement"]["indicated_ph"] = value
            self.assertFalse(assess_stock_evidence(reference_recipe(), evidence)["verified"])
        for value in ({}, [], {"assignment": None, "calibration": None, "measurement": None}):
            evidence = records()
            evidence["batch_ph"] = value
            self.assertFalse(assess_stock_evidence(reference_recipe(), evidence)["verified"])

    def test_fingerprint_stable_for_equivalent_numeric_types_and_sensitive_to_bounds(self):
        recipe = copy.deepcopy(reference_recipe())
        evidence = records()
        original = preparation_fingerprint(recipe, evidence)
        recipe["temperature_c"] = 25.0
        self.assertEqual(preparation_fingerprint(recipe, evidence), original)
        recipe["uncertainty_verification"]["assumptions"]["volume_error_litres"] = 0.01
        self.assertNotEqual(preparation_fingerprint(recipe, evidence), original)
