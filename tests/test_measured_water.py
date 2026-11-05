# SPDX-FileCopyrightText: 2026 Flaha. Created by Rafat A. Al Khashan.
# SPDX-License-Identifier: Apache-2.0
# Disclaimer: planning software provided without warranty (Apache-2.0, section 7);
# its results are calculations, not dosing instructions.
"""Tests for flahax.measured_water."""

import unittest

from flahax import (
    DeliveryError,
    VolumeLitres,
    balance_water_analysis,
    calculate_equilibrium_ph,
    carbonate_alkalinity,
    total_alkalinity,
    plan_fertilizer_workflow,
)
from flahax.product_conversion import MOLAR_MASS
from tests.test_water_workflow import products, TARGETS

# Shomar et al. (2024), Groundwater, doi:10.1111/gwat.13411, Table S1, station 104
# (mg/L; IC is inorganic carbon as C). Measured pH 7.80.
STATION_104 = {
    'Na+': 680 / 22.98977e3,
    'K+': 44.2 / 39.0983e3,
    'Ca+2': 244 / 40.078e3,
    'Mg+2': 100.8 / 24.305e3,
    'Cl-': 1280.4 / 35.45e3,
    'SO4-2': 723.3 / 96.06e3,
    'NO3-': 15.38 / 62.004e3,
    'CO3-2': 38.75 / 12.011e3,
}
WITHOUT_CARBON = {k: v for k, v in STATION_104.items() if k != 'CO3-2'}


class MeasuredWaterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.balanced = balance_water_analysis(STATION_104, measured_ph=7.8)

    def test_charge_balance_alone_misses_the_measured_ph(self):
        state = calculate_equilibrium_ph(STATION_104, carbon_boundary='closed', phases=[])
        self.assertLess(state.ph, 4.5)

    def test_measured_ph_is_kept_and_the_imbalance_is_reported(self):
        b = self.balanced
        self.assertEqual(b.measured_ph, 7.8)
        self.assertEqual(b.state.ph, 7.8)
        self.assertIsNone(b.balance_ion)
        self.assertEqual(b.carbon_source, 'inorganic_carbon')
        self.assertAlmostEqual(b.imbalance_percent, -3.52, places=2)
        self.assertEqual(b.residual_charge_eq, b.state.charge_balance)
        self.assertLess(b.residual_charge_eq, 0)
        self.assertEqual(b.balance_adjustment_molal, 0.0)
        self.assertEqual(b.reconciliation, 'imbalance_reported')
        self.assertEqual(b.totals, STATION_104)

    def test_the_residual_charge_reproduces_the_measured_ph(self):
        state = calculate_equilibrium_ph(
            self.balanced.totals,
            carbon_boundary='closed',
            phases=[],
            residual_charge=self.balanced.residual_charge_eq,
        )
        self.assertAlmostEqual(state.ph, 7.8, places=6)

    def test_alkalinity_gives_the_same_carbon(self):
        self.assertAlmostEqual(carbonate_alkalinity(self.balanced.state) * 1000, 3.1955, places=3)
        alkalinity = total_alkalinity(self.balanced.state)
        from_alkalinity = balance_water_analysis(
            WITHOUT_CARBON, measured_ph=7.8, alkalinity_eq_per_kg=alkalinity
        )
        self.assertEqual(from_alkalinity.carbon_source, 'alkalinity')
        self.assertAlmostEqual(
            from_alkalinity.inorganic_carbon_molal / self.balanced.inorganic_carbon_molal,
            1,
            places=9,
        )
        self.assertAlmostEqual(
            from_alkalinity.totals['Cl-'] / self.balanced.totals['Cl-'], 1, places=9
        )

    def test_large_imbalance_is_reported_not_rejected_or_forced(self):
        source = STATION_104 | {'Na+': STATION_104['Na+'] * 1.3}
        b = balance_water_analysis(source, measured_ph=7.8)
        self.assertGreater(b.imbalance_percent, 5)
        self.assertEqual(b.totals, source)
        self.assertIsNone(b.balance_ion)

    def test_input_errors(self):
        cases = [
            (
                dict(totals=STATION_104, measured_ph=7.8, alkalinity_eq_per_kg=0.003),
                'ambiguous_carbon',
            ),
            (dict(totals=WITHOUT_CARBON, measured_ph=7.8), 'missing_carbon'),
            (dict(totals=STATION_104, measured_ph=15), 'out_of_range'),
            (
                dict(totals=STATION_104, measured_ph=7.8, temperature_c=20),
                'temperature_out_of_range',
            ),
            (dict(totals=STATION_104 | {'Xx': 1}, measured_ph=7.8), 'invalid_totals'),
            (
                dict(totals=WITHOUT_CARBON, measured_ph=7.8, alkalinity_eq_per_kg=-1),
                'alkalinity_out_of_range',
            ),
        ]
        for kwargs, code in cases:
            totals = kwargs.pop('totals')
            with self.subTest(code=code), self.assertRaises(DeliveryError) as raised:
                balance_water_analysis(totals, **kwargs)
            self.assertEqual(raised.exception.code, code)


class MeasuredWaterWorkflowTests(unittest.TestCase):
    def test_workflow_chemistry_starts_from_the_measured_water(self):
        # A quarter of station 104, as a 1:3 blend with ion-free water.
        quarter = {k: v / 4 for k, v in STATION_104.items()}
        ppm = {
            'Ca': quarter['Ca+2'] * MOLAR_MASS['Ca'] * 1000,
            'Mg': quarter['Mg+2'] * MOLAR_MASS['Mg'] * 1000,
            'K': quarter['K+'] * MOLAR_MASS['K'] * 1000,
            'Na': quarter['Na+'] * MOLAR_MASS['Na'] * 1000,
            'Cl': quarter['Cl-'] * MOLAR_MASS['Cl'] * 1000,
            'S': quarter['SO4-2'] * MOLAR_MASS['S'] * 1000,
            'N_NO3': quarter['NO3-'] * MOLAR_MASS['N'] * 1000,
        }
        equilibrium = dict(
            water_totals=quarter,
            water_mass_kg=100,
            water_analysis_id='station-104-quarter',
            carbon_boundary='closed',
            temperature_c=25,
            phases=[],
            measured_ph=7.92,
        )
        targets = {k: v for k, v in TARGETS.items() if k != 'Na'}
        result = plan_fertilizer_workflow(
            products(), targets, ppm, 6.0, final_volume=VolumeLitres(100), equilibrium=equilibrium
        )
        chemistry = result.stages['chemistry']
        # Taken as measured: the imbalance is carried, nothing is closed on an ion.
        self.assertEqual(chemistry.status, 'calculated', chemistry.message)
        balance = chemistry.value['water_balance']
        self.assertEqual(balance.reconciliation, 'imbalance_reported')
        self.assertEqual(chemistry.value['analytical_water_totals'], quarter)
        self.assertEqual(chemistry.value['water'].ph, 7.92)
        self.assertIsNone(balance.balance_ion)
        self.assertEqual(balance.balance_adjustment_molal, 0)
        self.assertLess(chemistry.value['mixed'].ph, 7.92)

    def test_measured_ph_must_be_a_number(self):
        equilibrium = dict(
            water_totals=STATION_104,
            water_mass_kg=100,
            water_analysis_id='x',
            carbon_boundary='closed',
            temperature_c=25,
            phases=[],
            measured_ph='7.8',
        )
        result = plan_fertilizer_workflow(
            products(), TARGETS, {}, 6.0, final_volume=VolumeLitres(100), equilibrium=equilibrium
        )
        self.assertEqual(result.stages['chemistry'].status, 'blocked')
        self.assertEqual(result.stages['chemistry'].error_code, 'out_of_range')


class NoChlorideTests(unittest.TestCase):
    """Measured titration stays fixed; nothing is adjusted to close the charge."""

    def analysis(self, **extra):
        totals = {'Ca+2': 1.6e-3, 'NO3-': 1e-3, **extra}
        return balance_water_analysis(
            totals, measured_ph=7.5, alkalinity_eq_per_kg=2e-3, phases=[]
        )

    def test_no_chloride_cannot_change_the_measured_titration(self):
        for extra in ({}, {'Cl-': 0.0}):
            with self.subTest(extra=extra):
                water = self.analysis(**extra)
                self.assertEqual(water.alkalinity_eq_per_kg, 2e-3)
                self.assertIsNone(water.balance_ion)
                self.assertEqual(water.analytical_totals, {'Ca+2': 1.6e-3, 'NO3-': 1e-3, **extra})

    def test_chloride_present_is_not_adjusted_either(self):
        water = self.analysis(**{'Cl-': 1.9e-4})
        self.assertEqual((water.balance_ion, water.reconciliation), (None, 'imbalance_reported'))
        self.assertEqual(water.totals['Cl-'], 1.9e-4)


if __name__ == '__main__':
    unittest.main()
