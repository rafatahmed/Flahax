# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""A formula's own cation/anion balance is checked before fitting (research report, Steiner
1961)."""

import unittest

from flahax import load_library, recommend
from flahax.composition import target_ion_balance

LIBRARY = load_library()


def formula(name):
    return next(f for f in LIBRARY["formulas"] if f["name"] == name)["targets"]


class TargetIonBalanceTests(unittest.TestCase):
    def test_meq_sums_follow_the_documented_ion_forms(self):
        # 1 mmol each: NO3- 1, NH4+ 1, H2PO4- 1, K+ 1, Ca2+ 2, Mg2+ 2, SO4 2-, Na+ 1, Cl- 1 meq.
        balance = target_ion_balance({"N_NO3": 14.0067, "K": 39.0983, "Ca": 40.078, "S": 32.06})
        self.assertAlmostEqual(balance["cationsMeqPerL"], 3.0)
        self.assertAlmostEqual(balance["anionsMeqPerL"], 3.0)
        self.assertAlmostEqual(balance["imbalancePercent"], 0.0)
        self.assertNotIn("exceedsWarning", balance)

    def test_balanced_classic_formula(self):
        self.assertLess(
            abs(target_ion_balance(formula("Hoagland solution"))["imbalancePercent"]), 1.0
        )

    def test_unbalanced_formulas_are_reported_as_numbers_only(self):
        pepper = target_ion_balance(formula("Pepper (Howard Resh)"))
        self.assertLess(pepper["imbalancePercent"], -10)
        self.assertNotIn("exceedsWarning", pepper)
        synthetic = target_ion_balance({"N_NO3": 60, "Ca": 160})
        self.assertGreater(synthetic["imbalancePercent"], 10)

    def test_recommend_states_the_imbalance_without_claiming_infeasibility(self):
        # Pepper (Howard Resh): cations 22.58, anions 37.31 meq/L, -39.5 % (hand-computed above).
        result = recommend(LIBRARY["salts"], formula("Pepper (Howard Resh)"), {})
        self.assertIn(
            "The formula's declared ions are not balanced: "
            "cations 22.58 vs anions 37.31 meq/L (-39.5 %).",
            result["warnings"],
        )
        self.assertFalse(any("No salt combination" in w for w in result["warnings"]))
        self.assertNotIn("exceedsWarning", result["targetIonBalance"])

    def test_a_balanced_formula_has_no_imbalance_note(self):
        balanced = recommend(
            [dict(id="kno3", name="kno3", elements={"N_NO3": 14.0067, "K": 39.0983})],
            {"N_NO3": 14.0067, "K": 39.0983},
            {},
        )
        self.assertFalse(any("not balanced" in w for w in balanced["warnings"]))

    def test_permitted_counterion_completes_target_subset(self):
        result = recommend(
            [dict(id='kcl', name='kcl', elements={'K': 39.0983, 'Cl': 35.45})],
            {'K': 39.0983},
            maximum_concentrations={'Cl': 40},
        )
        self.assertTrue(result['feasible'])
        self.assertAlmostEqual(result['targetIonBalance']['imbalancePercent'], 100)
        self.assertAlmostEqual(result['recipeIonBalance']['imbalancePercent'], 0, places=12)
        self.assertFalse(result['recipeIonBalance']['provesInfeasibility'])
        self.assertEqual(result['chargeAssessment']['status'], 'partial_charge_inventory')
        self.assertEqual(result['chargeAssessment']['assayOnlyProducts'], ['kcl'])
        self.assertFalse(any('No salt combination' in w for w in result['warnings']))

    def test_partial_charge_convention_discloses_unrepresented_nutrients(self):
        balance = target_ion_balance({'Mo': 0.1, 'N_UREA': 2, 'K': 0})
        self.assertEqual(balance['unrepresentedNutrients'], ['Mo', 'N_UREA'])
        self.assertEqual(balance['scope'], 'nutrient_subset_convention')
        self.assertFalse(balance['provesInfeasibility'])


if __name__ == "__main__":
    unittest.main()
