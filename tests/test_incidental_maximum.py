"""A stated maximum lets an incidental ion be used up to that limit, never past it silently."""
import unittest

from flahax import load_library, recommend

LIBRARY = load_library()
# Florida till-first-cluster: Ca 150 with N_NO3 70 cannot be met from calcium nitrate alone.
FORMULA = next(f for f in LIBRARY["formulas"] if f["name"] == "Tomatoes - till First Cluster (U of Florida)")


def final(result, symbol):
    return next((row["final"] for row in result["rows"] if row["symbol"] == symbol), 0.0)


def delta(result, symbol):
    return next(row["deltaPct"] for row in result["rows"] if row["symbol"] == symbol)


class IncidentalMaximumTests(unittest.TestCase):
    def test_default_behaviour_is_unchanged(self):
        self.assertEqual(recommend(LIBRARY["salts"], FORMULA["targets"], {}),
                         recommend(LIBRARY["salts"], FORMULA["targets"], {}, maximum_concentrations=None))

    def test_chloride_allowance_closes_the_calcium_gap(self):
        base = recommend(LIBRARY["salts"], FORMULA["targets"], {})
        allowed = recommend(LIBRARY["salts"], FORMULA["targets"], {}, maximum_concentrations={"Cl": 150})
        self.assertLess(abs(delta(allowed, "Ca")), 1.0)
        self.assertLess(abs(delta(allowed, "Ca")), abs(delta(base, "Ca")))
        self.assertIn("Calcium Chloride (Dihydrate)", [s["name"] for s in allowed["salts"]])
        self.assertLessEqual(final(allowed, "Cl"), 150 + 1e-9)
        self.assertEqual(allowed["limitViolations"], [])
        cl = next(c for c in allowed["incidentalContributions"] if c["symbol"] == "Cl")
        self.assertEqual(cl["assessment"], "within_limit")

    def test_tight_maximum_is_respected_or_reported(self):
        tight = recommend(LIBRARY["salts"], FORMULA["targets"], {}, maximum_concentrations={"Cl": 20})
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
                    result = recommend(LIBRARY["salts"], formula["targets"], water,
                                       maximum_concentrations={"Cl": 50})
                    self.assertLessEqual(final(result, "Cl"), 50 + 1e-12)
                    self.assertEqual(result["limitViolations"], [])

    def test_violation_is_never_silent(self):
        # A tiny limit the fit cannot fully honour must surface as a violation.
        result = recommend(LIBRARY["salts"], FORMULA["targets"], {}, maximum_concentrations={"Cl": 1e-6})
        if final(result, "Cl") > 1e-6 + 1e-12:
            self.assertFalse(result["feasible"])
            self.assertEqual(result["limitViolations"][0]["symbol"], "Cl")

    def test_invalid_maximum_is_rejected(self):
        with self.assertRaises(Exception):
            recommend(LIBRARY["salts"], FORMULA["targets"], {}, maximum_concentrations={"Cl": -1})


if __name__ == "__main__":
    unittest.main()
