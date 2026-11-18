# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Synthetic longitudinal observations must not be confused with real
stability data.
"""

import copy
import unittest
from datetime import datetime, timezone, timedelta

from flahax.batch_stability import assess_batch_stability
from flahax.composition import ATOMIC
from flahax.stock_evidence import assess_stock_evidence
from tests.test_stock_evidence import records, reference_recipe

POLICY = dict(
    required_hours=[0, 24, 72, 168],
    maximum_delay_hours=1,
    maximum_turbidity_ntu=1,
    minimum_retention_fraction=0.95,
    initial_nutrient_relative_tolerance=0.05,
)


def old_records():
    """Create explicitly synthetic records predating a completed
    seven-day study.
    """
    evidence = records()
    start = datetime.now(timezone.utc) - timedelta(hours=169)
    for row in (
        evidence["assays"] + evidence["calibrations"] + [evidence["final_volume"]["calibration"]]
    ):
        row["measured_on"] = start.date().isoformat()
    calibration = evidence["batch_ph"]["calibration"]
    calibration["calibrated_at"] = (start - timedelta(hours=1)).isoformat()
    calibration["measured_on"] = (start - timedelta(hours=1)).date().isoformat()
    measurement = evidence["batch_ph"]["measurement"]
    measurement.update(measured_at=start.isoformat(), measured_on=start.date().isoformat())
    return evidence


def observations(recipe):
    """Return synthetic measurements centered on the calculated Ca/P
    quantities.
    """
    records = recipe["stock_verification"]["records"]
    initial = records["batch_ph"]["measurement"]
    start = datetime.fromisoformat(initial["measured_at"])

    def metric(value, error):
        return dict(
            value=value,
            absolute_uncertainty=error,
            instrument_id="synthetic-instrument",
            calibration_reference="synthetic-calibration",
            method="synthetic-method",
            source="SYNTHETIC TEST ONLY",
            uncertainty_basis="total_bounded_error",
        )

    result = dict(
        assignment={
            k: recipe["stock_verification"]["batch_ph_check"][k]
            for k in ("batch_id", "vessel_id", "preparation_fingerprint")
        },
        policy=copy.deepcopy(POLICY),
        protocol=dict(
            protocol_id="synthetic-protocol",
            source="SYNTHETIC TEST ONLY",
            storage_conditions="synthetic closed plant-free batch",
            filter_pore_um=0.45,
            turbidity_sample="representative_unfiltered_batch",
            dissolved_basis="filtered_elemental_Ca_and_total_dissolved_P",
            material_accounting="no_additions_withdrawals_count_as_loss",
        ),
        observations=[],
    )
    for index, hour in enumerate(POLICY["required_hours"]):
        time = start + timedelta(hours=hour)
        ph = copy.deepcopy(initial)
        if index:
            ph.update(
                record_id=f"synthetic-ph-{index}",
                measured_at=time.isoformat(),
                measured_on=time.date().isoformat(),
            )
        ca = recipe["rounded_verification"]["analytical_mmol_l"]["Ca"] * ATOMIC["Ca"]
        phosphorus = recipe["rounded_verification"]["analytical_mmol_l"]["P"] * ATOMIC["P"]
        result["observations"].append(
            dict(
                observation_id=f"sample-{index}",
                sampled_at=time.isoformat(),
                turbidity_ntu=metric(0.2, 0.05),
                dissolved_calcium_mg_l=metric(ca, ca * 0.001),
                dissolved_phosphorus_mg_l=metric(phosphorus, phosphorus * 0.001),
                volume_litres=metric(
                    10,
                    min(
                        0.001,
                        recipe["uncertainty_verification"]["assumptions"]["volume_error_litres"],
                    ),
                ),
                ph_measurement=ph,
            )
        )
    return result


class BatchStabilityTests(unittest.TestCase):
    def setUp(self):
        self.recipe = copy.deepcopy(reference_recipe())
        self.recipe["stock_verification"] = assess_stock_evidence(self.recipe, old_records())
        self.recipe["verified"] = self.recipe["stock_verification"]["verified"]
        self.assertTrue(self.recipe["verified"])
        self.evidence = observations(self.recipe)

    def test_complete_measured_series_passes_and_is_snapshotted(self):
        result = assess_batch_stability(self.recipe, self.evidence)
        self.assertTrue(result["stable"])
        self.assertEqual(result["observed_hours"], 168)
        self.assertEqual(len(result["observation_checks"]), 4)
        self.evidence["observations"][1]["turbidity_ntu"]["value"] = 5
        self.assertEqual(result["records"]["observations"][1]["turbidity_ntu"]["value"], 0.2)

    def test_missing_and_unverified_preparation_cannot_be_stable(self):
        self.assertFalse(assess_batch_stability(self.recipe, None)["stable"])
        self.recipe["verified"] = False
        self.assertEqual(
            assess_batch_stability(self.recipe, self.evidence)["status"], "unverified"
        )

    def test_missing_timepoints_and_short_followup_are_incomplete(self):
        for index in (1, 2, 3):
            evidence = copy.deepcopy(self.evidence)
            evidence["observations"].pop(index)
            result = assess_batch_stability(self.recipe, evidence)
            self.assertEqual(result["status"], "insufficient_evidence")
            self.assertFalse(result["stable"])

    def test_turbidity_upper_bound_and_intermediate_failure(self):
        self.evidence["observations"][1]["turbidity_ntu"].update(
            value=0.96, absolute_uncertainty=0.05
        )
        result = assess_batch_stability(self.recipe, self.evidence)
        self.assertEqual(result["status"], "not_stable")
        self.assertIn("turbidity", result["observation_checks"][1]["failed_checks"])

    def test_nutrient_uncertainty_is_conservative(self):
        for key, name in (("dissolved_calcium_mg_l", "Ca"), ("dissolved_phosphorus_mg_l", "P")):
            evidence = copy.deepcopy(self.evidence)
            # A 95% central result fails once both measurement bounds
            # are included.
            evidence["observations"][-1][key]["value"] *= 0.95
            result = assess_batch_stability(self.recipe, evidence)
            self.assertFalse(result["stable"])
            self.assertLess(result["observation_checks"][-1]["retention_lower_bounds"][name], 0.95)

    def test_volume_loss_cannot_hide_nutrient_mass_loss(self):
        self.evidence["observations"][-1]["volume_litres"]["value"] = 9
        result = assess_batch_stability(self.recipe, self.evidence)
        self.assertFalse(result["stable"])
        self.assertLess(result["observation_checks"][-1]["retention_lower_bounds"]["Ca"], 0.91)

    def test_initial_depletion_and_unaccounted_additions_rejected(self):
        self.evidence["observations"][0]["dissolved_calcium_mg_l"]["value"] *= 0.8
        self.assertFalse(assess_batch_stability(self.recipe, self.evidence)["stable"])
        self.evidence = observations(self.recipe)
        self.evidence["protocol"]["material_accounting"] = "topped_up_nutrients"
        self.assertEqual(
            assess_batch_stability(self.recipe, self.evidence)["status"], "invalid_evidence"
        )

    def test_evaporation_with_retained_mass_is_not_mistaken_for_nutrient_loss(self):
        last = self.evidence["observations"][-1]
        last["volume_litres"]["value"] = 9
        for key in ("dissolved_calcium_mg_l", "dissolved_phosphorus_mg_l"):
            last[key]["value"] *= 10 / 9
        self.assertTrue(assess_batch_stability(self.recipe, self.evidence)["stable"])

    def test_wrong_batch_future_duplicate_and_missing_provenance(self):
        cases = []
        wrong = copy.deepcopy(self.evidence)
        wrong["assignment"]["batch_id"] = "other"
        cases.append(wrong)
        future = copy.deepcopy(self.evidence)
        future["observations"][-1]["sampled_at"] = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).isoformat()
        cases.append(future)
        duplicate = copy.deepcopy(self.evidence)
        duplicate["observations"][1]["observation_id"] = "sample-0"
        cases.append(duplicate)
        missing = copy.deepcopy(self.evidence)
        missing["observations"][1]["turbidity_ntu"]["calibration_reference"] = ""
        cases.append(missing)
        for evidence in cases:
            self.assertEqual(
                assess_batch_stability(self.recipe, evidence)["status"], "invalid_evidence"
            )

    def test_ph_drift_blocks_stability_even_if_clear_and_retained(self):
        self.evidence["observations"][2]["ph_measurement"]["indicated_ph"] = 6.4
        result = assess_batch_stability(self.recipe, self.evidence)
        self.assertFalse(result["stable"])
        self.assertIn("batch_ph", result["observation_checks"][2]["failed_checks"])

    def test_malformed_numbers_and_schedule_rejected(self):
        for value in (True, float("nan"), float("inf"), -1, "0.2"):
            evidence = copy.deepcopy(self.evidence)
            evidence["observations"][1]["turbidity_ntu"]["value"] = value
            self.assertFalse(assess_batch_stability(self.recipe, evidence)["stable"])
        self.evidence["policy"]["required_hours"] = [0, 24, 24]
        self.assertEqual(
            assess_batch_stability(self.recipe, self.evidence)["status"], "invalid_evidence"
        )

    def test_real_api_and_cli_preserve_separate_verified_and_stable_flags(self):
        from flahax.planning_cli import execute
        from tests.test_ratio_stocks import STOCKS, UNCERTAINTY
        from tests.test_ratio_search import OPTIONS

        stock_evidence = old_records()
        for row in stock_evidence["assays"]:
            row["absolute_uncertainty_g_l"] = 0
        for row in stock_evidence["calibrations"]:
            row.update(maximum_absolute_bias_ml=0, absolute_uncertainty_ml=0)
        stock_evidence["final_volume"]["calibration"]["absolute_uncertainty_litres"] = 0
        request = dict(
            OPTIONS,
            counted_mmol_l=1.7,
            stock_dosing=dict(STOCKS, concentration_relative_error=0, dose_error_ml=0),
            uncertainty=dict(UNCERTAINTY, volume_error_litres=0),
            stock_evidence=stock_evidence,
        )
        first = execute("ratio", request)
        stock_evidence["batch_ph"]["measurement"]["preparation_fingerprint"] = first[
            "stock_verification"
        ]["preparation_fingerprint"]
        verified = execute("ratio", request)
        self.assertTrue(verified["verified"])
        self.assertFalse(verified["stable"])
        request["batch_stability"] = observations(verified)
        stable = execute("ratio", request)
        self.assertTrue(stable["verified"])
        self.assertTrue(stable["stable"])
        search_request = dict(request)
        search_request.pop("counted_mmol_l")
        search_request.update(strength_range=[1, 1.7], scan_points=3)
        found = execute("ratio", search_request)
        self.assertTrue(found["stable"])
        self.assertTrue(found["recipe"]["stable"])
        request["batch_stability"]["observations"][-1]["turbidity_ntu"]["value"] = 2
        failed = execute("ratio", request)
        self.assertTrue(failed["verified"])
        self.assertFalse(failed["stable"])
        not_found = execute("ratio", search_request)
        self.assertEqual(not_found["status"], "no_feasible_candidate_found")
        self.assertFalse(not_found["stable"])
