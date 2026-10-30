# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Independent concentration and solvent inventories; no litre=kilogram identity."""

from fractions import Fraction
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from flahax import (
    DeliveryError,
    SolventBasis,
    VolumeLitres,
    load_library,
    plan_fertilizer_workflow,
)
from flahax.batch_cli import BatchOptions, blend, read_water, run_batch, water_basis
from flahax.measured_water import nutrient_mg_per_litre
from tests.catalogue_history import historical_catalogue


class UnitBasisTests(unittest.TestCase):
    # Owner catalogue: re-enable in PR 4 (G5)
    def test_workflow_normalizes_fertilizer_against_declared_solvent(self):
        self.enterContext(historical_catalogue())
        products = [p for p in load_library()['salts'] if p['name'] == 'Potassium Nitrate']
        self.assertEqual(len(products), 1)
        result = plan_fertilizer_workflow(
            products,
            {'K': 100},
            {},
            5.8,
            final_volume=VolumeLitres(10),
            equilibrium=dict(
                water_totals={},
                water_mass_kg=5,
                water_analysis_id='pure',
                complete_analysis=True,
                carbon_boundary='closed',
                temperature_c=25,
                phases=[],
            ),
        )
        chemistry = result.stages['chemistry']
        self.assertIsNotNone(chemistry.value, chemistry.message)
        amount = result.stages['batch'].value.salts[0].mass.value
        dose = chemistry.value['product_doses_g_per_kg_water'][products[0]['name']]
        self.assertAlmostEqual(dose * 5, amount)
        self.assertEqual(chemistry.value['concentration_basis']['water_kg_per_litre'], 0.5)

    def read(self, **values):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'water.json'
            path.write_text(
                json.dumps(
                    dict(
                        mg_per_litre={'Ca': 40.078},
                        measured_ph=7,
                        below_detection={'Mg': 24.305},
                        **values,
                    )
                )
            )
            return read_water(str(path))

    def test_independent_inventory_over_varied_mass_volume_and_density(self):
        # Construct known moles and solvent inventory FIRST, then obtain concentration.
        # Rational arithmetic is independent of the float conversion implementation.
        for volume in (Fraction('0.25'), Fraction(1), Fraction(137)):
            for density in (Fraction('0.95'), Fraction('1.05'), Fraction('1.3')):
                for solute_fraction in (Fraction(0), Fraction('0.01'), Fraction('0.2')):
                    solution = volume * density
                    solute = solution * solute_fraction
                    water = solution - solute
                    for moles in (Fraction(0), Fraction('0.0001'), Fraction('0.03')):
                        mw = Fraction('40.078')
                        mg_l = moles * mw * 1000 / volume
                        basis = SolventBasis.from_solution_mass(
                            float(volume), float(density), float(solute)
                        )
                        self.assertAlmostEqual(basis.water_mass_kg, float(water), places=12)
                        observed = basis.mg_per_litre_to_molality(float(mg_l), float(mw))
                        self.assertAlmostEqual(observed, float(moles / water), places=14)
                        self.assertAlmostEqual(
                            basis.molality_to_mg_per_litre(observed, float(mw)),
                            float(mg_l),
                            places=10,
                        )

    def test_source_reagent_and_hydrate_water_are_counted_once(self):
        # 900 g source solvent + 100 g reagent at 60% solute + 60 g product
        # containing 20 g dissolved hydrate water: 960 g water, 100 g nonwater.
        ledger = SolventBasis.from_water_ledger(
            1, source_water_kg=0.9, reagent_carrier_water_kg=0.04, dissolved_hydrate_water_kg=0.02
        )
        density = SolventBasis.from_solution_mass(1, 1.06, 0.1)
        self.assertAlmostEqual(ledger.water_mass_kg, 0.96)
        self.assertAlmostEqual(ledger.water_mass_kg, density.water_mass_kg)
        self.assertAlmostEqual(ledger.grams_per_litre_to_grams_per_kg_water(60), 62.5)

    def test_invalid_and_incomplete_bases_are_rejected(self):
        for bad in (True, None, -1, 0, float('nan'), float('inf'), 'x'):
            with self.subTest(bad=bad), self.assertRaises(DeliveryError):
                SolventBasis(1, bad)
        for values in (
            {'water_mass_kg': 1},
            {'final_volume_litres': 1},
            {'final_volume_litres': 1, 'density_kg_per_litre': 1},
            {'final_volume_litres': 1, 'water_mass_kg': 1, 'nonwater_mass_kg': 0},
            {'final_volume_litres': 1, 'density_kg_per_litre': 1, 'nonwater_mass_kg': 1},
        ):
            with self.subTest(values=values), self.assertRaises(DeliveryError):
                water_basis(values)
        for bad in (-1, True, float('nan')):
            with self.assertRaises(DeliveryError):
                SolventBasis(1, 1).mg_per_litre_to_molality(bad, 40)
        with self.assertRaises(DeliveryError):
            SolventBasis(1, 1).molality_to_mg_per_litre(1, 0)

    def test_water_analysis_and_detection_limits_use_the_same_mass_basis(self):
        _, nutrients, config = self.read(final_volume_litres=1, water_mass_kg=2)
        self.assertEqual(nutrients, {'Ca': 40.078})
        self.assertAlmostEqual(config['water_totals']['Ca+2'], 0.0005)
        self.assertAlmostEqual(config['below_detection']['Mg+2'], 0.0005)
        self.assertAlmostEqual(nutrient_mg_per_litre(config['water_totals'], 2, 1)['Ca'], 40.078)

    def test_density_requires_nonwater_mass_and_reconstructs_solvent(self):
        _, _, config = self.read(
            final_volume_litres=2, density_kg_per_litre=1.1, nonwater_mass_kg=0.2
        )
        self.assertAlmostEqual(config['water_totals']['Ca+2'], 0.001)
        self.assertEqual(config['concentration_basis']['status'], 'declared')

    def test_legacy_and_ro_uncertainty_is_visible(self):
        for config in (self.read()[2], read_water('ro')[2]):
            self.assertEqual(config['concentration_basis']['status'], 'assumed')
            self.assertEqual(config['concentration_basis']['uncertainty'], 'not quantified')

    def test_volume_blend_uses_solvent_mass_share_for_molal_dilution(self):
        label, nutrients, config = self.read(final_volume_litres=1, water_mass_kg=2)
        balanced = SimpleNamespace(diluted=lambda share: share)
        with patch('flahax.batch_cli.balance_water_analysis', return_value=balanced):
            _, diluted, result = blend(label, nutrients, config, 50)
        self.assertEqual(diluted, {'Ca': 20.039})
        self.assertAlmostEqual(result['water_balance'], 2 / 3)
        self.assertEqual(result['concentration_basis']['water_kg_per_litre'], 1.5)
        self.assertEqual(result['concentration_basis']['status'], 'assumed')

    def test_batch_propagates_scaled_final_inventory_and_reports_assumption(self):
        options = BatchOptions(formula='Hoagland solution', volume=20, water='ro')
        config = read_water('ro')[2]
        config['concentration_basis']['water_kg_per_litre'] = 0.98
        summary = {'tanks': {'tanks': []}, 'warnings': []}
        with (
            patch('flahax.batch_cli.read_water', return_value=('test', {}, config)),
            patch('flahax.batch_cli.plan_fertilizer_workflow') as workflow,
            patch('flahax.batch_cli.summarize_batch', return_value=summary),
        ):
            result = run_batch(options)
        self.assertAlmostEqual(workflow.call_args.kwargs['equilibrium']['water_mass_kg'], 19.6)
        self.assertAlmostEqual(result['concentration_basis']['water_mass_kg'], 19.6)
        self.assertTrue(any('Concentration basis' in warning for warning in result['warnings']))


if __name__ == '__main__':
    unittest.main()
