# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Steiner 1a arithmetic and model regression, with measured pH reported
separately.
"""

import json
from pathlib import Path
import unittest

from flahax.aqueous_model import solve
from flahax.steiner_context import article_evidence

FIXTURE = json.loads((Path(__file__).parent / "fixtures/steiner/solution_1a.json").read_text())
VALENCES = (1, 2, 2, 1, 1, 2)
BASIS = ("K+", "Ca+2", "Mg+2", "NO3-", "PO4-3", "SO4-2")


def counted_total(amounts):
    return sum(value / charge for value, charge in zip(amounts, VALENCES))


def preparations():
    shares = FIXTURE["cation_shares"] + FIXTURE["anion_shares"]
    factor = FIXTURE["target_counted_mmol_l"] / counted_total(shares)
    initial = [value * factor for value in shares]
    dose = FIXTURE["test_koh_meq_l"]
    titrated = initial.copy()
    titrated[0] += dose
    corrected = [
        value + dose * share / 100
        for value, share in zip(initial, FIXTURE["cation_shares"] + [0, 0, 0])
    ]
    scale = FIXTURE["target_counted_mmol_l"] / counted_total(corrected)
    return {
        "initial": initial,
        "titrated": titrated,
        "final": [value * scale for value in corrected],
    }, dose * scale


def predicted_ph(amounts):
    """Separate charge-balance bisection using the production speciation
    kernel.
    """
    totals = {name: value / charge / 1000 for name, value, charge in zip(BASIS, amounts, VALENCES)}
    low, high = 3.0, 9.0
    assert solve(totals, low).charge_balance > 0
    assert solve(totals, high).charge_balance < 0
    for _ in range(38):
        ph = (low + high) / 2
        state = solve(totals, ph)
        if state.charge_balance > 0:
            low = ph
        else:
            high = ph
    return ph, state


class SteinerReferenceTests(unittest.TestCase):
    def test_table_two_stocks_reproduce_table_one(self):
        delivered = dict.fromkeys(FIXTURE["order"], 0.0)
        for stock in FIXTURE["stocks"]:
            meq_l = stock["normality"] * stock["ml_per_10_l"] / 10
            for ion in stock["ions"]:
                delivered[ion] += meq_l
        for ion, expected in zip(FIXTURE["order"], FIXTURE["initial_printed_meq_l"]):
            self.assertAlmostEqual(delivered[ion], expected, places=10)

    def test_ratios_and_total_survive_reformulation(self):
        batches, dose = preparations()
        for stage in ("initial", "final"):
            amounts = batches[stage]
            self.assertAlmostEqual(counted_total(amounts), 30, places=12)
            for group, shares in ((amounts[:3], [80, 10, 10]), (amounts[3:], [80, 5, 15])):
                for value, expected in zip(group, shares):
                    self.assertAlmostEqual(100 * value / sum(group), expected, places=12)
        self.assertAlmostEqual(dose, 0.2933946554595, places=12)
        final = batches["final"]
        self.assertAlmostEqual(sum(final[:3]) - sum(final[3:]), dose, places=12)
        for value, printed in zip(final, FIXTURE["final_printed_meq_l"]):
            self.assertLess(abs(value - printed), 0.001)

    def test_titration_adds_potassium_and_increases_count(self):
        batches, _ = preparations()
        self.assertAlmostEqual(batches["titrated"][0] - batches["initial"][0], 0.296)
        self.assertEqual(batches["titrated"][1:], batches["initial"][1:])
        self.assertAlmostEqual(counted_total(batches["titrated"]), 30.296)

    def test_three_stage_model_regression(self):
        batches, _ = preparations()
        regression = FIXTURE["regression"]
        for stage, amounts in batches.items():
            with self.subTest(stage=stage):
                ph, state = predicted_ph(amounts)
                self.assertAlmostEqual(
                    ph, regression["expected_ph"][stage], delta=regression["ph_absolute_tolerance"]
                )
                self.assertLess(abs(state.charge_balance), 1e-10)
                self.assertLess(state.ionic_strength, 0.1)
        self.assertAlmostEqual(
            FIXTURE["measurements"]["final"] - FIXTURE["measurements"]["titrated"], 0.13
        )

    def test_source_measurements_remain_observations(self):
        self.assertEqual(
            FIXTURE["measurements"], {"initial": 5.33, "titrated": 6.45, "final": 6.58}
        )
        self.assertTrue(FIXTURE["uncertainties"])
        self.assertEqual(FIXTURE["model_assumptions"]["temperature_c"], 25)
        self.assertEqual(
            article_evidence()["solution_1a"]["measured_ph"],
            [FIXTURE["measurements"][s] for s in ("initial", "titrated", "final")],
        )


if __name__ == "__main__":
    batches, dose = preparations()
    rows = []
    for stage, amounts in batches.items():
        ph, state = predicted_ph(amounts)
        measured = FIXTURE["measurements"][stage]
        rows.append(
            {
                "stage": stage,
                "measured_ph": measured,
                "predicted_ph": ph,
                "difference": ph - measured,
                "meq_l": amounts,
                "counted_mmol_l": counted_total(amounts),
                "charge_residual_mol_kg": state.charge_balance,
            }
        )
    print(
        json.dumps(
            {
                "source": FIXTURE["source"],
                "article_evidence": article_evidence(),
                "assumptions": FIXTURE["model_assumptions"],
                "final_koh_meq_l": dose,
                "results": rows,
            },
            indent=2,
        )
    )
