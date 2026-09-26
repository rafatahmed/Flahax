import unittest

from flahax import ChMicroProductDose, FertilizerTotals, solve_ch_micro_equilibrium, solve_mixed_fertilizer_equilibrium


class TraceEquilibriumTests(unittest.TestCase):
    def test_declared_ch_micro_stoichiometry_is_conserved(self):
        totals = ChMicroProductDose(1.0).totals(calcium=.002, magnesium=.001)
        result = solve_ch_micro_equilibrium(totals, 6.0, .01)
        s = result.species
        self.assertAlmostEqual(s["Fe+3"] + s["Fe(III)-EDTA"], totals.iron, places=15)
        self.assertAlmostEqual(s["Mn+2"] + s["Mn-EDTA"], totals.manganese, places=15)
        self.assertAlmostEqual(s["Zn+2"] + s["Zn-EDTA"], totals.zinc, places=15)
        self.assertAlmostEqual(s["Cu+2"] + s["Cu-EDTA"], totals.copper, places=15)
        self.assertAlmostEqual(s["B(OH)3"] + s["B(OH)4-"], totals.boron, places=15)
        self.assertAlmostEqual(s["MoO4-2"] + s["HMoO4-"] + s["H2MoO4"], totals.molybdate, places=15)

    def test_edta_is_not_treated_as_free_trace_metal(self):
        result = solve_ch_micro_equilibrium(ChMicroProductDose(1.0).totals(), 6.0, .01)
        self.assertGreater(result.species["Fe(III)-EDTA"], result.species["Fe+3"] * 1e12)
        # With exactly one ligand equivalent per supplied trace metal, Fe(III)'s
        # much stronger EDTA stability displaces some Mn. This is the intended
        # competitive equilibrium, not a free-ion approximation.
        self.assertGreater(result.species["Mn-EDTA"], result.species["Mn+2"])

    def test_calcium_competes_for_excess_ligand_only(self):
        low = solve_ch_micro_equilibrium(ChMicroProductDose(1.0).totals(), 6.0, .01)
        hard = solve_ch_micro_equilibrium(ChMicroProductDose(1.0).totals(calcium=.002), 6.0, .01)
        self.assertGreater(hard.species["Ca-EDTA"], low.species["Ca-EDTA"])

    def test_mixed_entry_point_shares_macro_ionic_strength_with_trace(self):
        result = solve_mixed_fertilizer_equilibrium(FertilizerTotals(calcium=.001, nitrate=.002), 6, trace_totals=ChMicroProductDose(.1).totals())
        self.assertIsNotNone(result.trace)
        self.assertEqual(result.macro.ionic_strength, result.trace.ionic_strength)
