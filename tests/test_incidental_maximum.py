# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""A stated maximum lets an incidental ion be used up to that limit, never past it silently."""

import unittest

from flahax import load_library, recommend
from tests.catalogue_history import historical_catalogue

# The pre-owner products, which include Calcium Chloride (Dihydrate).
with historical_catalogue():
    LIBRARY = load_library()
# Synthetic conflicting Ca/nitrate requirements; not a crop recommendation.
FORMULA = {'targets': {'N_NO3': 60, 'Ca': 160}}


def final(result, symbol):
    return next((row["final"] for row in result["rows"] if row["symbol"] == symbol), 0.0)


def delta(result, symbol):
    return next(row["deltaPct"] for row in result["rows"] if row["symbol"] == symbol)


class IncidentalMaximumTests(unittest.TestCase):
    def test_default_behaviour_is_unchanged(self):
        self.assertEqual(
            recommend(LIBRARY["salts"], FORMULA["targets"], {}),
            recommend(LIBRARY["salts"], FORMULA["targets"], {}, maximum_concentrations=None),
        )

    def test_chloride_allowance_closes_the_calcium_gap(self):
        base = recommend(LIBRARY["salts"], FORMULA["targets"], {})
        allowed = recommend(
            LIBRARY["salts"], FORMULA["targets"], {}, maximum_concentrations={"Cl": 150}
        )
        self.assertLess(abs(delta(allowed, "Ca")), 1.0)
        self.assertLess(abs(delta(allowed, "Ca")), abs(delta(base, "Ca")))
        self.assertIn("Calcium Chloride (Dihydrate)", [s["name"] for s in allowed["salts"]])
        self.assertLessEqual(final(allowed, "Cl"), 150 + 1e-9)
        self.assertEqual(allowed["limitViolations"], [])
        cl = next(c for c in allowed["incidentalContributions"] if c["symbol"] == "Cl")
        self.assertEqual(cl["assessment"], "within_limit")

    def test_tight_maximum_is_respected_or_reported(self):
        tight = recommend(
            LIBRARY["salts"], FORMULA["targets"], {}, maximum_concentrations={"Cl": 20}
        )
        cl = final(tight, "Cl")
        if cl > 20 + 1e-9:
            self.assertTrue(tight["limitViolations"])
            self.assertFalse(tight["feasible"])
        else:
            self.assertEqual(tight["limitViolations"], [])

    def test_ceiling_holds_for_every_shipped_formula(self):
        for formula in LIBRARY["formulas"]:
            for water in ({}, {"Ca": 20}):
                with self.subTest(formula=formula["name"], water=water):
                    result = recommend(
                        LIBRARY["salts"],
                        formula["targets"],
                        water,
                        maximum_concentrations={"Cl": 50},
                    )
                    self.assertLessEqual(final(result, "Cl"), 50 + 1e-12)
                    self.assertEqual(result["limitViolations"], [])

    def test_violation_is_never_silent(self):
        # A tiny limit the fit cannot fully honour must surface as a violation.
        result = recommend(
            LIBRARY["salts"], FORMULA["targets"], {}, maximum_concentrations={"Cl": 1e-6}
        )
        if final(result, "Cl") > 1e-6 + 1e-12:
            self.assertFalse(result["feasible"])
            self.assertEqual(result["limitViolations"][0]["symbol"], "Cl")

    def test_a_ceiling_the_water_already_breaks_is_reported_not_a_solver_failure(self):
        # #86: 9% of Shomar et al. (2024) station 104 brings 115.2 mg/L Cl, over a 106.35 mg/L
        # (3 mmol/L) ceiling, while the Na ceiling binds. This raised "NNLS did not reach
        # optimality".
        well = {
            'Ca': 244,
            'Mg': 100.8,
            'K': 44.2,
            'Na': 680,
            'Cl': 1280.4,
            'S': 241.43,
            'N_NO3': 3.474,
        }
        water = {k: v * 0.09 for k, v in well.items()}
        tomato = next(
            f["targets"] for f in LIBRARY["formulas"] if f["name"] == "Tomato (Howard Resh)"
        )
        result = recommend(
            LIBRARY["salts"], tomato, water, maximum_concentrations={"Na": 68.97, "Cl": 106.35}
        )
        self.assertFalse(result["feasible"])
        self.assertEqual([v["symbol"] for v in result["limitViolations"]], ["Cl"])
        self.assertAlmostEqual(
            final(result, "Cl"), 1280.4 * 0.09, places=9
        )  # the products add none
        # It is the infinite-multiplier limit: the fit without any chloride product.
        reference = recommend(
            [s for s in LIBRARY["salts"] if not s["elements"].get("Cl")],
            tomato,
            water,
            maximum_concentrations={"Na": 68.97, "Cl": 1e9},
        )
        self.assertEqual(result["salts"], reference["salts"])
        self.assertEqual(result["loss"], reference["loss"])

    def test_invalid_maximum_is_rejected(self):
        with self.assertRaises(Exception):
            recommend(LIBRARY["salts"], FORMULA["targets"], {}, maximum_concentrations={"Cl": -1})


if __name__ == "__main__":
    unittest.main()
