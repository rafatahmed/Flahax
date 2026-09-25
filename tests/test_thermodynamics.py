import unittest

from flahax import DeliveryError
from flahax.thermodynamics import MineralPhase, phase_saturation_index


class ThermodynamicPhases(unittest.TestCase):
    def test_calcite_saturation_index_uses_activity_not_concentration(self):
        calcite = MineralPhase(
            "Calcite", {"Ca+2": 1, "CO3-2": 1}, -8.45, "phreeqc.dat", 25
        )
        self.assertAlmostEqual(
            phase_saturation_index(calcite, {"Ca+2": 10 ** -2.91, "CO3-2": 10 ** -5.54}),
            0.0,
            places=2,
        )

    def test_missing_or_nonpositive_activity_fails_closed(self):
        gypsum = MineralPhase("Gypsum", {"Ca+2": 1, "SO4-2": 1}, -4.58, "phreeqc.dat", 25)
        with self.assertRaises(DeliveryError) as caught:
            phase_saturation_index(gypsum, {"Ca+2": 0.001})
        self.assertEqual(caught.exception.code, "missing_species")
        with self.assertRaises(DeliveryError) as caught:
            phase_saturation_index(gypsum, {"Ca+2": 0, "SO4-2": 0.001})
        self.assertEqual(caught.exception.code, "out_of_range")


if __name__ == "__main__":
    unittest.main()
