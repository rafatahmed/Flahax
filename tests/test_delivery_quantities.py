import unittest
from dataclasses import FrozenInstanceError

from flahax import (
    DeliveryError,
    InjectionRatio,
    MassGrams,
    MilliEquivalentsPerLitre,
    VolumeLitres,
    elemental_contribution,
    final_solution_recipe,
    rescore_with_reagent,
)


class DeliveryQuantities(unittest.TestCase):
    def test_values_are_immutable_and_reject_invalid_dimensions(self):
        volume = VolumeLitres(100)
        with self.assertRaises(FrozenInstanceError):
            volume.value = 200
        with self.assertRaises(DeliveryError):
            VolumeLitres(0)
        with self.assertRaises(DeliveryError):
            MassGrams(float("nan"))
        self.assertEqual(InjectionRatio(100).value, 100)
        self.assertEqual(MilliEquivalentsPerLitre(2.4).value, 2.4)

    def test_recommendation_adapts_to_a_final_batch_without_rounding(self):
        recipe = final_solution_recipe(
            {
                "feasible": True,
                "salts": [
                    {"id": "kn", "name": "Potassium nitrate", "gramsPerLitre": 0.5456789},
                    {"id": "cn", "name": "Calcium nitrate", "gramsPerLitre": 0.046},
                ],
            },
            VolumeLitres(250),
        )
        self.assertTrue(recipe.feasible)
        self.assertEqual(recipe.salts[0].mass.value, 136.419725)
        self.assertEqual(recipe.salts[1].mass.value, 11.5)
        self.assertEqual(recipe.total_mass.value, 147.919725)

    def test_adapter_preserves_feasibility_and_rejects_invalid_solver_output(self):
        recipe = final_solution_recipe({"feasible": False, "salts": []}, VolumeLitres(1))
        self.assertFalse(recipe.feasible)
        with self.assertRaises(DeliveryError) as caught:
            final_solution_recipe({"feasible": True, "salts": [{"id": "x", "name": "X", "gramsPerLitre": 0}]}, VolumeLitres(1))
        self.assertEqual(caught.exception.code, "out_of_range")

    def test_reagent_elemental_contribution_is_in_ppm(self):
        contribution = elemental_contribution(
            MassGrams(10), {"N_NO3": 0.138, "P": 0.01}, VolumeLitres(100)
        )
        self.assertAlmostEqual(contribution["N_NO3"].value, 13.8)
        self.assertAlmostEqual(contribution["P"].value, 1.0)
        _loss, rows = rescore_with_reagent({"N_NO3": 100}, {"N_NO3": 113.8, "P": 1}, contribution)
        self.assertAlmostEqual(next(row for row in rows if row["symbol"] == "N_NO3")["deltaPct"], 0)
        self.assertAlmostEqual(next(row for row in rows if row["symbol"] == "P")["deltaPct"], 0)

    def test_ambiguous_or_impossible_reagent_assay_is_rejected(self):
        with self.assertRaises(DeliveryError) as caught:
            elemental_contribution(MassGrams(1), {"N": 0.1}, VolumeLitres(1))
        self.assertEqual(caught.exception.code, "ambiguous_unit")
        with self.assertRaises(DeliveryError) as caught:
            elemental_contribution(MassGrams(1), {"K": 1.1}, VolumeLitres(1))
        self.assertEqual(caught.exception.code, "out_of_range")
        with self.assertRaises(DeliveryError) as caught:
            elemental_contribution(MassGrams(1), {"K": 0.8, "Ca": 0.8}, VolumeLitres(1))
        self.assertEqual(caught.exception.code, "out_of_range")


if __name__ == "__main__":
    unittest.main()
