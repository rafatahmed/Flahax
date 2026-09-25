import json
from pathlib import Path
import unittest

from flahax.reference_fixtures import assert_reference_result, load_reference_fixture
from flahax.equilibrium import (
    calcite_co2_reference_values,
    gypsum_reference_values,
    solve_calcite_co2_equilibrium,
    solve_gypsum_equilibrium,
)


FIXTURE = Path(__file__).parent / "fixtures" / "phreeqc" / "calcite_co2_equilibrium.json"
GYPSUM_FIXTURE = Path(__file__).parent / "fixtures" / "phreeqc" / "gypsum_anhydrite_equilibrium.json"


class ReferenceFixtures(unittest.TestCase):
    def test_official_phreeqc_fixture_has_intact_provenance_and_input(self):
        fixture = load_reference_fixture(FIXTURE)
        self.assertEqual(fixture["reference"]["database"], "phreeqc.dat")
        self.assertIn("Calcite", fixture["phreeqcInput"])
        self.assertEqual(fixture["expected"]["values"]["si.Calcite"], 0.0)

    def test_comparator_accepts_reference_values_and_rejects_drift(self):
        fixture = load_reference_fixture(FIXTURE)
        actual = calcite_co2_reference_values(solve_calcite_co2_equilibrium(-2.0))
        assert_reference_result(fixture, actual)
        actual["si.Calcite"] = 0.01
        with self.assertRaises(AssertionError):
            assert_reference_result(fixture, actual)

    def test_gypsum_anhydrite_example_two_fixture(self):
        fixture = load_reference_fixture(GYPSUM_FIXTURE)
        self.assertIn("Gypsum", fixture["phreeqcInput"])
        self.assertIn("Anhydrite", fixture["phreeqcInput"])
        assert_reference_result(fixture, gypsum_reference_values(solve_gypsum_equilibrium()))

    def test_fixture_hash_mismatch_is_rejected(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["inputSha256"] = "0" * 64
        altered = FIXTURE.parent / "altered.json"
        try:
            altered.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(Exception):
                load_reference_fixture(altered)
        finally:
            if altered.exists():
                altered.unlink()


if __name__ == "__main__":
    unittest.main()
