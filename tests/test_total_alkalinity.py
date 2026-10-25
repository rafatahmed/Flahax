# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent proton inventories, carbon inference and preserved titration inputs."""

from fractions import Fraction
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from flahax import DeliveryError, balance_water_analysis, total_alkalinity
from flahax.aqueous_model import solve
from flahax.batch_cli import read_water
from flahax.measured_water import _carbon_for_alkalinity


class TotalAlkalinityTests(unittest.TestCase):
    def test_signed_carbon_free_value_and_numerical_equality_boundary(self):
        state = solve({}, 4, phases=[])
        measured = state.species['OH-'] - state.species['H+']
        self.assertLess(measured, 0)
        self.assertEqual(_carbon_for_alkalinity({}, 4, measured, []), 0)
        self.assertEqual(_carbon_for_alkalinity({}, 4, measured + 0.5e-12, []), 0)
        with self.assertRaises(DeliveryError) as caught:
            _carbon_for_alkalinity({}, 4, measured - 2e-12, [])
        self.assertEqual(caught.exception.code, 'alkalinity_out_of_range')

    def test_reconciliation_preserves_titration_and_analytical_inventory(self):
        source = {'Ca+2': 0.0016, 'NO3-': 0.001, 'Cl-': 0.00019}
        result = balance_water_analysis(source, measured_ph=7.5, alkalinity_eq_per_kg=0.002)
        self.assertEqual(result.analytical_totals, source)
        self.assertEqual(result.alkalinity_eq_per_kg, 0.002)
        self.assertNotIn('CO3-2', source)
        self.assertAlmostEqual(total_alkalinity(result.state), 0.002, places=12)
        self.assertLess(abs(result.state.charge_balance), 1e-12)

    def test_prescribed_species_have_independent_proton_equivalents(self):
        # Relative to H2CO3, H2PO4-, H3BO3, NH4+ and SO4-2.
        weights = {
            'HCO3-': 1,
            'CO3-2': 2,
            'HPO4-2': 1,
            'PO4-3': 2,
            'H2PO4-': 0,
            'H3PO4': -1,
            'H2BO3-': 1,
            'H3BO3': 0,
            'NH3': 1,
            'NH4+': 0,
            'HSO4-': -1,
            'OH-': 1,
            'H+': -1,
        }
        amounts = {name: Fraction(i + 1, 10000) for i, name in enumerate(weights)}
        expected = sum(amounts[name] * weight for name, weight in weights.items())
        state = SimpleNamespace(species={k: float(v) for k, v in amounts.items()})
        self.assertAlmostEqual(total_alkalinity(state), float(expected), places=15)

    def test_carbon_free_phosphate_and_borate_do_not_create_carbon(self):
        for totals, ph in (({'PO4-3': 0.001}, 8), ({'H3BO3': 0.001}, 9)):
            state = solve(totals, ph, phases=[])
            s = state.species
            # Species sum independent of runtime reaction powers/reference mapping.
            measured = (
                s.get('HPO4-2', 0)
                + 2 * s.get('PO4-3', 0)
                - s.get('H3PO4', 0)
                + s.get('H2BO3-', 0)
                + s.get('H5(BO3)2-', 0)
                + s.get('H8(BO3)3-', 0)
                + s.get('OH-', 0)
                - s.get('H+', 0)
            )
            self.assertGreater(measured, 0)
            self.assertAlmostEqual(total_alkalinity(state), measured, places=14)
            self.assertEqual(_carbon_for_alkalinity(totals, ph, measured, []), 0)

    def test_acid_titration_proton_difference_agrees_with_charge_difference(self):
        totals = {'Na+': 0.003, 'Cl-': 0.001, 'PO4-3': 0.001, 'H3BO3': 0.001, 'SO4-2': 0.0002}
        high = solve(totals, 9, phases=[])
        low = solve(totals, 4, phases=[])
        proton_demand = total_alkalinity(high) - total_alkalinity(low)
        self.assertGreater(proton_demand, 0)
        self.assertAlmostEqual(proton_demand, low.charge_balance - high.charge_balance, places=11)
        # Strong-ion inventory derives from element and electric-charge conservation.
        constant = totals['Na+'] - totals['Cl-'] - 2 * totals['SO4-2'] - totals['PO4-3']
        for state in (high, low):
            self.assertAlmostEqual(
                total_alkalinity(state) + state.charge_balance, constant, places=11
            )

    def test_inferred_carbon_recovers_known_mixed_inorganic_inventory(self):
        totals = {'Na+': 0.004, 'CO3-2': 0.001, 'PO4-3': 0.0003, 'H3BO3': 0.0002}
        state = solve(totals, 8, phases=[])
        recovered = _carbon_for_alkalinity(
            {k: v for k, v in totals.items() if k != 'CO3-2'}, 8, total_alkalinity(state), []
        )
        self.assertAlmostEqual(recovered, 0.001, places=11)

    def test_explicit_carbon_and_titration_are_rejected_even_for_zero(self):
        for carbon in (0, 0.001):
            with self.assertRaises(DeliveryError) as caught:
                balance_water_analysis(
                    {'CO3-2': carbon, 'PO4-3': 0.001}, measured_ph=8, alkalinity_eq_per_kg=0.001
                )
            self.assertEqual(caught.exception.code, 'ambiguous_carbon')

    def test_unqualified_species_are_rejected_not_folded_into_carbon(self):
        for species in ({'H3BO3': 0, 'Edta-4': 0.001}, {'unknown': 0.001}, {'Fe+3': 0.001}):
            with self.assertRaises(DeliveryError) as caught:
                total_alkalinity(SimpleNamespace(species=species))
            self.assertEqual(caught.exception.code, 'unsupported_alkalinity')
        for amount in (-1, True, float('nan'), float('inf')):
            with self.assertRaises(DeliveryError):
                total_alkalinity(SimpleNamespace(species={'H+': amount}))

    def test_titration_is_not_changed_when_chloride_is_missing(self):
        for chloride in ({}, {'Cl-': 0}):
            source = {'Ca+2': 0.0016, 'NO3-': 0.001, **chloride}
            with self.assertRaises(DeliveryError) as caught:
                balance_water_analysis(source, measured_ph=7.5, alkalinity_eq_per_kg=0.002)
            self.assertIn(caught.exception.code, ('missing_balance_ion', 'fixed_balance_ion'))
            self.assertNotIn('CO3-2', source)

    def test_explicit_fixed_carbon_is_not_adjusted_as_fallback(self):
        with self.assertRaises(DeliveryError) as caught:
            balance_water_analysis(
                {'Ca+2': 0.0016, 'NO3-': 0.001, 'CO3-2': 0.002},
                measured_ph=7.5,
                fixed=('CO3-2',),
                maximum_imbalance_percent=100,
            )
        self.assertEqual(caught.exception.code, 'missing_balance_ion')

    def test_lab_alkalinity_units_use_solvent_basis_without_inventing_carbon(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'water.json'
            data = dict(
                mg_per_litre={'P': 30.973762},
                measured_ph=8,
                alkalinity_meq_per_litre=2,
                water_mass_kg=2,
                final_volume_litres=1,
            )
            path.write_text(json.dumps(data))
            _, nutrients, config = read_water(str(path))
            self.assertEqual(config['alkalinity_eq_per_kg'], 0.001)
            self.assertNotIn('CO3-2', config['water_totals'])
            self.assertEqual(nutrients, {'P': 30.973762})
            for change in (
                {'mg_per_litre': {'HCO3': 0}},
                {'alkalinity_meq_per_litre': True},
                {'alkalinity_meq_per_litre': None},
                {'alkalinity_below_detection_meq_per_litre': 0.01},
            ):
                path.write_text(json.dumps(data | change))
                with self.assertRaises(DeliveryError):
                    read_water(str(path))


if __name__ == '__main__':
    unittest.main()
