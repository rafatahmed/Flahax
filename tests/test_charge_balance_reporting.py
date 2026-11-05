# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""A water analysis is accepted as measured; its charge imbalance is reported (G10, G11).

No ion is added, removed or adjusted to close it, and no imbalance size rejects it.
"""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from flahax import balance_water_analysis, calculate_equilibrium_ph
from flahax.batch_cli import main as batch

# mol/kg water: Na+ is 1.1505 times Cl-, so cations exceed anions by 100 x 0.1505 / 2.1505 = 7.0 %.
SEVEN_PERCENT = {'Na+': 1.1505e-3, 'Cl-': 1.0e-3, 'CO3-2': 0.0}


class WaterImbalanceTests(unittest.TestCase):
    def test_a_seven_percent_imbalance_is_accepted_and_reported(self):
        water = balance_water_analysis(SEVEN_PERCENT, measured_ph=7.0)
        self.assertAlmostEqual(water.imbalance_percent, 7.0, delta=0.01)
        self.assertAlmostEqual(water.residual_charge_eq, water.state.charge_balance, delta=1e-15)
        self.assertGreater(water.residual_charge_eq, 0)

    def test_no_ion_is_added_or_changed(self):
        water = balance_water_analysis(SEVEN_PERCENT, measured_ph=7.0)
        self.assertEqual(water.totals, SEVEN_PERCENT)
        self.assertEqual(water.analytical_totals, SEVEN_PERCENT)
        self.assertIsNone(water.balance_ion)
        self.assertEqual(water.balance_adjustment_molal, 0.0)

    def test_a_large_imbalance_is_not_rejected(self):
        water = balance_water_analysis({'Na+': 5e-3, 'Cl-': 1e-3, 'CO3-2': 0.0}, measured_ph=7.0)
        self.assertGreater(water.imbalance_percent, 50)

    def test_the_measured_alkalinity_still_gives_the_carbon(self):
        # 2 meq/kg alkalinity at pH 8.2: carbon comes from the titration, not from a guess.
        totals = {'Na+': 2e-3, 'Cl-': 0.5e-3}
        water = balance_water_analysis(totals, measured_ph=8.2, alkalinity_eq_per_kg=1.5e-3)
        self.assertEqual(water.carbon_source, 'alkalinity')
        self.assertGreater(water.inorganic_carbon_molal, 0)
        self.assertEqual(water.analytical_totals, totals)

    def test_the_modelled_water_is_the_analysed_water(self):
        water = balance_water_analysis(SEVEN_PERCENT, measured_ph=7.0)
        self.assertEqual(water.modelled_mg_per_litre(), water.analytical_mg_per_litre())

    def test_the_diluted_water_keeps_its_residual_charge(self):
        water = balance_water_analysis(SEVEN_PERCENT, measured_ph=7.0)
        half = water.diluted(0.5)
        self.assertAlmostEqual(half.residual_charge_eq, water.residual_charge_eq / 2, delta=1e-12)
        state = calculate_equilibrium_ph(
            half.totals, phases=[], residual_charge=half.residual_charge_eq
        )
        self.assertAlmostEqual(state.charge_balance, half.residual_charge_eq, delta=1e-12)


class EcResidualTests(unittest.TestCase):
    def test_the_ec_ph_solve_carries_the_waters_residual_charge(self):
        from flahax import calculate_ec_from_totals

        water = balance_water_analysis(SEVEN_PERCENT, measured_ph=7.0)
        forced = calculate_ec_from_totals(
            water.totals, solution_id='w', ph_mode='calculated', phase_policy='dissolved'
        )
        carried = calculate_ec_from_totals(
            water.totals,
            solution_id='w',
            ph_mode='calculated',
            phase_policy='dissolved',
            residual_charge_eq_per_kgw=water.residual_charge_eq,
        )
        expected = calculate_equilibrium_ph(
            water.totals, phases=[], residual_charge=water.residual_charge_eq
        )
        self.assertAlmostEqual(carried.ph, expected.ph, places=6)
        self.assertGreater(
            forced.ph - carried.ph, 1
        )  # forcing zero charge moves the pH by pH units


class AcidDoseTests(unittest.TestCase):
    def test_the_nitric_dose_for_a_target_ph_is_planned_on_an_imbalanced_water(self):
        water = dict(
            id='w',
            measured_ph=7.8,
            mg_per_litre=dict(Ca=60, Mg=20, K=5, Na=60, Cl=40, S=20, N_NO3=3, HCO3=120),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'w.json'
            path.write_text(json.dumps(water), 'utf-8')
            out = Path(tmp) / 'out'
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                batch(
                    [
                        '--formula',
                        'Lettuce 2 (Howard Resh)',
                        '--water',
                        str(path),
                        '--output',
                        str(out),
                    ]
                )
            summary = json.loads((out / 'summary.json').read_text('utf-8'))
        stages = summary['stages']
        self.assertEqual(stages['chemistry']['status'], 'calculated')
        # Reagents were evaluated against the target pH (saturation findings are a later PR's).
        self.assertNotEqual(stages['ph_adjustment']['error_code'], 'chemistry_required')
        self.assertTrue(summary['ph']['candidates'])
        self.assertNotIn('exceeds the maximum imbalance', json.dumps(summary))
        self.assertGreater(summary['water']['imbalance_percent'], 5)


if __name__ == '__main__':
    unittest.main()
