# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""pH inputs and stated model conditions (decisions G1-G4): no declarations, no guessed pH.

The pH stage reports what it needs or what the model cannot reach; the recipe is produced in
every case.
"""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from flahax import calculate_equilibrium_ph
from flahax.batch_cli import main as batch

FORMULA = 'Lettuce 2 (Howard Resh)'
ALKALINITY_MESSAGE = 'measure alkalinity (HCO3) of the water'
RANGE_REASON = "ionic strength above 0.1 mol/kg: outside the activity model's range"
WELL = dict(Ca=60, Mg=20, K=5, Na=30, Cl=40, S=20, N_NO3=3)


class PhInputTests(unittest.TestCase):
    def run_batch(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = batch(list(argv))
        return code, err.getvalue()

    def summary(self, water, **extra):
        with tempfile.TemporaryDirectory() as tmp:
            args = ['--formula', FORMULA, '--output', str(Path(tmp) / 'out')]
            if water == 'ro':
                args += ['--water', 'ro']
            else:
                path = Path(tmp) / 'water.json'
                path.write_text(json.dumps(dict(id='w', measured_ph=7.8, **water)), 'utf-8')
                args += ['--water', str(path)]
            self.run_batch(*args)
            return json.loads((Path(tmp) / 'out' / 'summary.json').read_text('utf-8'))

    def test_the_equilibrium_pH_needs_no_completeness_declaration(self):
        # Ion-free water with 1 mmol/kg KCl: the pH is the neutral one the model calculates.
        state = calculate_equilibrium_ph({'K+': 1e-3, 'Cl-': 1e-3}, phases=[])
        self.assertAlmostEqual(state.ph, 7.0, places=1)
        self.assertAlmostEqual(state.charge_balance, 0, delta=1e-12)

    def test_the_measured_imbalance_is_reproduced_not_forced_to_zero(self):
        totals = {'Na+': 2e-3, 'Cl-': 1e-3, 'CO3-2': 1e-3}
        balanced = calculate_equilibrium_ph(totals, phases=[])
        residual = calculate_equilibrium_ph(totals, phases=[], residual_charge=1e-4)
        self.assertAlmostEqual(residual.charge_balance, 1e-4, delta=1e-11)
        # Charge the ions do not carry is an excess of cations: fewer anions are needed.
        self.assertLess(residual.ph, balanced.ph)

    def test_ro_water_calculates_the_ph_with_nothing_declared(self):
        summary = self.summary('ro')
        self.assertEqual(summary['stages']['chemistry']['status'], 'calculated')

    def test_a_water_without_alkalinity_asks_for_it_and_still_gives_the_recipe(self):
        summary = self.summary(dict(mg_per_litre=WELL))
        chemistry = summary['stages']['chemistry']
        self.assertEqual(chemistry['status'], 'needs_input')
        self.assertEqual(chemistry['message'], ALKALINITY_MESSAGE)
        self.assertTrue(summary['formulation']['salts'])
        self.assertNotIn('blocked', {stage['status'] for stage in summary['stages'].values()})

    def test_a_measured_zero_alkalinity_is_calculated(self):
        summary = self.summary(dict(mg_per_litre=dict(WELL, HCO3=0)))
        self.assertEqual(summary['stages']['chemistry']['status'], 'calculated')

    def test_ionic_strength_above_the_model_range_is_not_calculated(self):
        salty = dict(WELL, Na=4000, Cl=6000, HCO3=0)
        summary = self.summary(dict(mg_per_litre=salty))
        chemistry = summary['stages']['chemistry']
        self.assertEqual(chemistry['status'], 'not_calculated')
        self.assertEqual(chemistry['message'], RANGE_REASON)
        self.assertTrue(summary['formulation']['salts'])

    def test_a_reagent_search_that_leaves_the_model_range_is_not_calculated(self):
        from unittest import mock

        from flahax import DeliveryError

        out_of_range = DeliveryError('activity_model_out_of_range', 'Davies ionic strength 0.2')
        with mock.patch('flahax.fertilizer_workflow.plan_coupled_ph', side_effect=out_of_range):
            summary = self.summary('ro')
        stage = summary['stages']['ph_adjustment']
        self.assertEqual((stage['status'], stage['message']), ('not_calculated', RANGE_REASON))
        self.assertTrue(summary['formulation']['salts'])
        self.assertNotIn('blocked', {s['status'] for s in summary['stages'].values()})

    def test_the_stated_model_conditions_are_in_the_summary(self):
        assumptions = self.summary('ro')['assumptions']
        for text in (
            'Closed carbon: the mixed tank does not exchange CO2 with air.',
            'Chemistry at 25 °C only.',
            '1 L of solution is taken as 1 kg of water.',
        ):
            self.assertIn(text, assumptions)


if __name__ == '__main__':
    unittest.main()
