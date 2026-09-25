import unittest

from flahax import DeliveryError
from flahax.equilibrium import solve_gypsum_equilibrium


class GypsumEquilibriumTests(unittest.TestCase):
    def test_pure_water_gypsum_has_neutral_ion_pair_and_stable_phase_order(self):
        result = solve_gypsum_equilibrium()
        self.assertGreater(result.calcium_sulfate_molal, 0.0)
        self.assertAlmostEqual(result.total_calcium_molal, result.total_sulfate_molal)
        self.assertAlmostEqual(result.si_gypsum, 0.0, places=12)
        self.assertAlmostEqual(result.si_anhydrite, -0.22, places=12)

    def test_only_the_fixture_temperature_is_supported(self):
        with self.assertRaises(DeliveryError) as caught:
            solve_gypsum_equilibrium(20.0)
        self.assertEqual(caught.exception.code, "unsupported_temperature")


if __name__ == "__main__":
    unittest.main()
