"""Synthetic records exercise the gate; they are not measured laboratory evidence."""

import copy
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from flahax import plan_ratio_recipe, search_ratio_recipe
from flahax.ratio_stocks import prepare_stock_delivery
from flahax.stock_evidence import assess_stock_evidence
from tests.test_ratio_search import OPTIONS
from tests.test_ratio_stocks import STOCKS, UNCERTAINTY


def records():
    """Synthetic, deliberately labeled examples for validator tests only."""
    today = datetime.now(timezone.utc).date()
    common = dict(
        source="SYNTHETIC UNIT TEST - no physical measurement",
        method="synthetic bounded-result fixture",
        measured_on=today.isoformat(),
        valid_until=(today + timedelta(days=7)).isoformat(),
        temperature_c=25,
        uncertainty_basis="total_bound_through_valid_until",
    )
    evidence = dict(assignments={}, assays=[], calibrations=[])
    for index, (formula, concentration) in enumerate(STOCKS["concentrations_g_l"].items()):
        stock = f"stock-{index}"
        evidence["assignments"][formula] = dict(
            stock_id=stock,
            dispenser_id="dispenser-1",
            assay_record_id=f"assay-{index}",
            calibration_record_id=f"calibration-{index}",
        )
        evidence["assays"].append(
            dict(
                common,
                record_id=f"assay-{index}",
                stock_id=stock,
                formula=formula,
                measured_concentration_g_l=concentration,
                absolute_uncertainty_g_l=concentration * 0.0005,
                concentration_basis="specified_compound_equivalent_g_l",
                reactive_impurities="excluded_by_measurement",
            )
        )
        evidence["calibrations"].append(
            dict(
                common,
                record_id=f"calibration-{index}",
                stock_id=stock,
                dispenser_id="dispenser-1",
                dose_min_ml=1,
                dose_max_ml=100,
                maximum_absolute_bias_ml=0.005,
                absolute_uncertainty_ml=0.005,
                coverage="entire_declared_range",
            )
        )
    evidence["final_volume"] = {
        "assignment": {"vessel_id": "vessel-10l", "calibration_record_id": "volume-1"},
        "calibration": dict(
            common,
            record_id="volume-1",
            vessel_id="vessel-10l",
            nominal_volume_litres=10,
            measured_volume_litres=10,
            absolute_uncertainty_litres=0.02,
            capacity_basis="to_contain",
            application="final_solution_including_stocks",
        ),
    }
    return evidence


class StockEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Real nominal chemistry, synthetic passing uncertainty status for isolated
        # record tests. Integration below separately exercises the actual checker.
        cls.recipe = plan_ratio_recipe(**dict(OPTIONS, counted_mmol_l=1.7))
        cls.recipe["stock_delivery"] = prepare_stock_delivery(cls.recipe, STOCKS, 0.05)
        cls.recipe["uncertainty_verification"] = {
            "status": "passed",
            "assumptions": dict(UNCERTAINTY),
        }

    def test_valid_records_bind_all_stocks_and_are_snapshotted(self):
        evidence = records()
        result = assess_stock_evidence(self.recipe, evidence)
        self.assertTrue(result["verified"])
        self.assertEqual(len(result["stock_checks"]), 6)
        self.assertEqual(len(result["records_sha256"]), 64)
        evidence["assays"][0]["measured_concentration_g_l"] = 99
        self.assertEqual(result["records"]["assays"][0]["measured_concentration_g_l"], 10)

    def test_missing_invalid_and_incomplete_records_fail_closed(self):
        for evidence in (None, {}, [], {"verified": True}):
            with self.subTest(evidence=evidence):
                self.assertFalse(assess_stock_evidence(self.recipe, evidence)["verified"])
        evidence = records()
        evidence["assays"].pop()
        self.assertFalse(assess_stock_evidence(self.recipe, evidence)["verified"])

    def test_assay_bias_plus_uncertainty_must_fit(self):
        evidence = records()
        evidence["assays"][0].update(
            measured_concentration_g_l=10.006, absolute_uncertainty_g_l=0.005
        )
        result = assess_stock_evidence(self.recipe, evidence)
        self.assertFalse(result["verified"])
        self.assertAlmostEqual(result["stock_checks"][0]["assay_total_deviation_g_l"], 0.011)
        evidence["assays"][0]["measured_concentration_g_l"] = 10.005
        self.assertTrue(assess_stock_evidence(self.recipe, evidence)["verified"])

    def test_dosing_bias_plus_uncertainty_and_actual_dose_coverage(self):
        for change in (
            {"maximum_absolute_bias_ml": 0.016},
            {"dose_max_ml": 2},
            {"dose_min_ml": 80},
            {"coverage": "tested_endpoints_only"},
            {"dispenser_id": "other"},
            {"stock_id": "water-only"},
        ):
            evidence = records()
            evidence["calibrations"][0].update(change)
            with self.subTest(change=change):
                self.assertFalse(assess_stock_evidence(self.recipe, evidence)["verified"])

    def test_dates_provenance_temperature_identity_and_basis(self):
        today = datetime.now(timezone.utc).date()
        for change in (
            {"valid_until": (today - timedelta(days=1)).isoformat()},
            {"measured_on": (today + timedelta(days=1)).isoformat()},
            {"measured_on": "20261114"},
            {"source": ""},
            {"method": ""},
            {"temperature_c": 20},
            {"formula": "Ca(NO3)2"},
            {"concentration_basis": "total_alkalinity"},
            {"uncertainty_basis": "standard_deviation"},
            {"reactive_impurities": "unknown"},
        ):
            evidence = records()
            evidence["assays"][0].update(change)
            with self.subTest(change=change):
                self.assertFalse(assess_stock_evidence(self.recipe, evidence)["verified"])

    def test_duplicate_ids_and_nonfinite_or_boolean_measurements(self):
        evidence = records()
        evidence["assays"].append(copy.deepcopy(evidence["assays"][0]))
        self.assertFalse(assess_stock_evidence(self.recipe, evidence)["verified"])
        for value in (float("nan"), float("inf"), True, -1, "10"):
            evidence = records()
            evidence["assays"][0]["measured_concentration_g_l"] = value
            self.assertFalse(assess_stock_evidence(self.recipe, evidence)["verified"])

    def test_evidence_cannot_override_failed_or_incomplete_chemistry(self):
        for status in ("failed", "incomplete"):
            recipe = copy.deepcopy(self.recipe)
            recipe["uncertainty_verification"]["status"] = status
            result = assess_stock_evidence(recipe, records())
            self.assertEqual(result["evidence_status"], "passed")
            self.assertFalse(result["verified"])

    def test_search_with_records_rejects_unverified_candidate(self):
        recipe = copy.deepcopy(self.recipe)
        recipe.update(verified=False, stock_verification={"status": "unverified", "failures": []})
        recipe["uncertainty_verification"]["failed_checks"] = []
        with patch("flahax.ratio_search.plan_ratio_recipe", return_value=recipe):
            result = search_ratio_recipe(
                **dict(
                    OPTIONS,
                    strength_range=[1, 2],
                    scan_points=3,
                    stock_dosing=STOCKS,
                    uncertainty=UNCERTAINTY,
                    stock_evidence=records(),
                )
            )
        self.assertEqual(result["status"], "no_feasible_candidate_found")
        self.assertFalse(result["verified"])

    def test_final_delivery_rechecks_records(self):
        accepted = copy.deepcopy(self.recipe)
        accepted.update(verified=True, stock_verification={"status": "verified", "failures": []})
        accepted["uncertainty_verification"]["failed_checks"] = []
        rejected = copy.deepcopy(accepted)
        rejected.update(
            verified=False, stock_verification={"status": "unverified", "failures": []}
        )
        with patch(
            "flahax.ratio_search.plan_ratio_recipe",
            side_effect=[accepted, accepted, accepted, rejected],
        ):
            result = search_ratio_recipe(
                **dict(
                    OPTIONS,
                    strength_range=[1, 2],
                    scan_points=3,
                    stock_dosing=STOCKS,
                    uncertainty=UNCERTAINTY,
                    stock_evidence=records(),
                )
            )
        self.assertEqual(result["status"], "incomplete")
        self.assertFalse(result["verified"])
        self.assertIsNone(result["recipe"])

    def test_blank_template_is_not_measurement_evidence(self):
        import json
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "examples/stock-evidence-template.json"
        self.assertFalse(
            assess_stock_evidence(self.recipe, json.loads(path.read_text()))["verified"]
        )

    def test_actual_api_and_cli_gate(self):
        from flahax.planning_cli import execute

        # Zero errors make real chemistry integration inexpensive; record bounds
        # are also zero here solely for this synthetic integration fixture.
        evidence = records()
        for row in evidence["assays"]:
            row["absolute_uncertainty_g_l"] = 0
        for row in evidence["calibrations"]:
            row.update(maximum_absolute_bias_ml=0, absolute_uncertainty_ml=0)
        evidence["final_volume"]["calibration"]["absolute_uncertainty_litres"] = 0
        request = dict(
            OPTIONS,
            counted_mmol_l=1.7,
            stock_dosing=dict(STOCKS, concentration_relative_error=0, dose_error_ml=0),
            uncertainty=dict(UNCERTAINTY, volume_error_litres=0),
        )
        self.assertFalse(execute("ratio", request)["verified"])
        result = execute("ratio", dict(request, stock_evidence=evidence))
        self.assertTrue(result["verified"])
        self.assertEqual(result["stock_verification"]["status"], "verified")
        self.assertNotIn(
            "no measured stock assays", result["uncertainty_verification"]["verification_scope"]
        )
        request.pop("counted_mmol_l")
        request.update(strength_range=[1, 1.5], scan_points=3)
        conditional = execute("ratio", request)
        self.assertEqual(conditional["status"], "found")
        self.assertFalse(conditional["verified"])
        verified = execute("ratio", dict(request, stock_evidence=evidence))
        self.assertEqual(verified["status"], "found")
        self.assertTrue(verified["verified"])
        self.assertTrue(verified["recipe"]["verified"])
        bad_volume = copy.deepcopy(evidence)
        bad_volume["final_volume"]["calibration"]["measured_volume_litres"] = 10.001
        rejected = execute("ratio", dict(request, stock_evidence=bad_volume))
        self.assertEqual(rejected["status"], "no_feasible_candidate_found")
        self.assertFalse(rejected["verified"])

    def test_stock_records_alone_no_longer_verify_recipe(self):
        evidence = records()
        evidence.pop("final_volume")
        result = assess_stock_evidence(self.recipe, evidence)
        self.assertTrue(all(row["status"] == "passed" for row in result["stock_checks"]))
        self.assertFalse(result["verified"])
        self.assertEqual(result["final_volume_check"]["status"], "missing")
        self.assertIn({"code": "missing_final_volume_calibration"}, result["failures"])

    def test_final_volume_interval_must_fit_exactly(self):
        for measured, uncertainty, expected in (
            (10.03, 0.02, True),
            (9.97, 0.02, True),
            (10.03001, 0.02, False),
            (9.96999, 0.02, False),
            (10, 0.05001, False),
            (0.01, 0.02, False),
        ):
            evidence = records()
            evidence["final_volume"]["calibration"].update(
                measured_volume_litres=measured, absolute_uncertainty_litres=uncertainty
            )
            with self.subTest(measured=measured, uncertainty=uncertainty):
                result = assess_stock_evidence(self.recipe, evidence)
                self.assertEqual(result["verified"], expected)

    def test_final_volume_identity_dates_units_and_capacity_basis(self):
        today = datetime.now(timezone.utc).date()
        for change in (
            {"vessel_id": "other-vessel"},
            {"record_id": "other-record"},
            {"record_id": "assay-0"},
            {"nominal_volume_litres": 20},
            {"capacity_basis": "to_deliver"},
            {"application": "initial_water_only"},
            {"temperature_c": 20},
            {"source": ""},
            {"method": ""},
            {"valid_until": (today - timedelta(days=1)).isoformat()},
            {"measured_on": (today + timedelta(days=1)).isoformat()},
            {"uncertainty_basis": "standard_deviation"},
            {"measured_volume_ml": 10000},
        ):
            evidence = records()
            evidence["final_volume"]["calibration"].update(change)
            with self.subTest(change=change):
                result = assess_stock_evidence(self.recipe, evidence)
                self.assertFalse(result["verified"])
                self.assertEqual(result["final_volume_check"]["status"], "failed")

    def test_final_volume_nonfinite_and_malformed_records_fail_closed(self):
        for value in (True, "10", float("nan"), float("inf"), -1, None):
            evidence = records()
            evidence["final_volume"]["calibration"]["absolute_uncertainty_litres"] = value
            self.assertFalse(assess_stock_evidence(self.recipe, evidence)["verified"])
        for value in ({}, [], {"assignment": None, "calibration": None}):
            evidence = records()
            evidence["final_volume"] = value
            self.assertFalse(assess_stock_evidence(self.recipe, evidence)["verified"])

    def test_volume_record_is_part_of_snapshot_hash(self):
        evidence = records()
        first = assess_stock_evidence(self.recipe, evidence)
        evidence["final_volume"]["calibration"]["absolute_uncertainty_litres"] = 0.01
        second = assess_stock_evidence(self.recipe, evidence)
        self.assertNotEqual(first["records_sha256"], second["records_sha256"])
        self.assertEqual(
            first["records"]["final_volume"]["calibration"]["absolute_uncertainty_litres"], 0.02
        )
