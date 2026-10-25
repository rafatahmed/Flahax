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
        state = calculate_equilibrium_ph(
            STATION_104, complete_analysis=True, carbon_boundary='closed', phases=[]
        )
        self.assertLess(state.ph, 4.5)

    def test_measured_ph_is_kept_and_charge_closed_on_chloride(self):
        b = self.balanced
        self.assertEqual(b.measured_ph, 7.8)
        self.assertEqual(b.state.ph, 7.8)
        self.assertLessEqual(abs(b.state.charge_balance), 1e-12)
        self.assertEqual(b.balance_ion, 'Cl-')
        self.assertEqual(b.carbon_source, 'inorganic_carbon')
        self.assertAlmostEqual(b.imbalance_percent, -3.52, places=2)
        self.assertAlmostEqual(
            b.balance_adjustment_molal / b.analysed_balance_ion_molal, -0.0953, places=4
        )
        self.assertEqual(b.analysed_balance_ion_molal, STATION_104['Cl-'])
        for name in STATION_104:
            if name != 'Cl-':
                self.assertEqual(b.totals[name], STATION_104[name])

    def test_balanced_totals_reproduce_the_measured_ph(self):
        state = calculate_equilibrium_ph(
            self.balanced.totals, complete_analysis=True, carbon_boundary='closed', phases=[]
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

    def test_large_imbalance_is_rejected_not_forced(self):
        with self.assertRaises(DeliveryError) as raised:
            balance_water_analysis(
                STATION_104 | {'Na+': STATION_104['Na+'] * 1.3}, measured_ph=7.8
            )
        self.assertEqual(raised.exception.code, 'charge_imbalance_exceeded')

    def test_sodium_can_close_the_charge_instead(self):
        b = balance_water_analysis(STATION_104, measured_ph=7.8, balance_ion='Na+')
        self.assertGreater(b.balance_adjustment_molal, 0)
        self.assertEqual(b.totals['Cl-'], STATION_104['Cl-'])
        self.assertLessEqual(abs(b.state.charge_balance), 1e-12)

    def test_input_errors(self):
        cases = [
            (
                dict(totals=STATION_104, measured_ph=7.8, alkalinity_eq_per_kg=0.003),
                'ambiguous_carbon',
            ),
            (dict(totals=WITHOUT_CARBON, measured_ph=7.8), 'missing_carbon'),
            (
                dict(totals=STATION_104, measured_ph=7.8, balance_ion='SO4-2'),
                'unsupported_balance_ion',
            ),
            # A named balance ion that is absent still stops (no chloride closes on alkalinity by
            # default, #100).
            (
                dict(
                    totals={k: v for k, v in STATION_104.items() if k != 'Na+'},
                    measured_ph=7.8,
                    balance_ion='Na+',
                    maximum_imbalance_percent=100,
                ),
                'missing_balance_ion',
            ),
            (dict(totals=STATION_104, measured_ph=15), 'out_of_range'),
            (
                dict(totals=STATION_104, measured_ph=7.8, temperature_c=20),
                'temperature_out_of_range',
            ),
            (dict(totals=STATION_104 | {'Xx': 1}, measured_ph=7.8), 'invalid_totals'),
            (
                dict(totals=STATION_104, measured_ph=7.8, maximum_imbalance_percent=0),
                'invalid_value',
            ),
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
            complete_analysis=True,
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
        # Closed on chloride without a stated uncertainty: usable, but the chemistry asks for
        # review (#84).
        self.assertEqual(chemistry.status, 'requires_review', chemistry.message)
        self.assertIn('without a stated measurement uncertainty', chemistry.message)
        balance = chemistry.value['water_balance']
        self.assertEqual(balance.reconciliation, 'assumed')
        self.assertEqual(chemistry.value['analytical_water_totals'], quarter)
        self.assertEqual(chemistry.value['water'].ph, 7.92)
        self.assertEqual(balance.balance_ion, 'Cl-')
        self.assertLessEqual(abs(balance.imbalance_percent), 5)
        self.assertNotEqual(balance.balance_adjustment_molal, 0)
        self.assertLess(chemistry.value['mixed'].ph, 7.92)

    def test_measured_ph_must_be_a_number(self):
        equilibrium = dict(
            water_totals=STATION_104,
            water_mass_kg=100,
            water_analysis_id='x',
            complete_analysis=True,
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
    """Measured titration stays fixed; missing chloride cannot be replaced by invented carbon."""

    def analysis(self, **extra):
        totals = {'Ca+2': 1.6e-3, 'NO3-': 1e-3, **extra}
        return balance_water_analysis(
            totals, measured_ph=7.5, alkalinity_eq_per_kg=2e-3, phases=[]
        )

    def test_no_chloride_cannot_change_the_measured_titration(self):
        for extra in ({}, {'Cl-': 0.0}):
            with self.subTest(extra=extra), self.assertRaises(DeliveryError) as caught:
                self.analysis(**extra)
            self.assertIn(caught.exception.code, ('missing_balance_ion', 'fixed_balance_ion'))

    def test_chloride_present_still_closes_on_chloride(self):
        water = self.analysis(**{'Cl-': 1.9e-4})
        self.assertEqual((water.balance_ion, water.reconciliation), ('Cl-', 'assumed'))


if __name__ == '__main__':
    unittest.main()
